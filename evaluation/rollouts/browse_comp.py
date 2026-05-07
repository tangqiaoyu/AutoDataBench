"""BrowseComp rollout: multi-turn web-search agent with tool-response omission.

Drives an LLM in a loop with web_search and fetch tools. Tool-call parsing is
delegated to :class:`SGLangToolCallParser` so we can swap formats (JSON for
``qwen``/``qwen25``; XML for ``qwen3_coder``) by passing ``tool_call_parser``.
The matching system prompt is picked the same way.

When the chat-template token count exceeds a configurable threshold after an
assistant turn, previous tool responses are replaced with an omission marker.
Each pre-omission conversation is preserved in ``trajectory.metadata["segments"]``
so downstream formatters can keep it as a separate training sample.

Assistant turns whose tool call failed to parse are marked ``loss=False`` so
SFT does not learn the malformed output even though the trajectory continues.
"""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from threading import Lock
from typing import Any, Optional

from ..framework.config import DistillConfig
from ..framework.llm import agenerate_chat
from ..framework.rollout import BaseRollout
from ..framework.trajectory import Step, Trajectory
from ..prompts.browse_comp import get_system_prompt
from ..tools.fetch import FetchSession
from ..tools.tool_call_parser import SGLangToolCallParser
from ..tools.web_search import search as web_search

# SGLang's import side-effects flip the root logger to INFO and attach a
# stderr handler, which makes httpx / openai spam a line per HTTP request.
# Silence those loggers so the rollout's own ``iteration: ...`` prints stay
# readable.
for _noisy in ("httpx", "httpcore", "openai", "openai._base_client"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger("bc_rollout")

# Override via the BC_TOKENIZER_PATH env var (or extend _TOKENIZER_PATHS) to
# point at a local tokenizer directory. The default below is a placeholder; the
# rollout will fall back to remote download via Hugging Face if it cannot be
# resolved locally.
_TOKENIZER_PATHS: dict[str, str] = {}
_DEFAULT_TOKENIZER_PATH = os.environ.get(
    "BC_TOKENIZER_PATH", "Qwen/Qwen2.5-7B-Instruct"
)
_OMITTED_TOOL_RESPONSE = "This tool response has been omitted"


class BrowseCompRollout(BaseRollout):
    def __init__(
        self,
        max_iterations: int = 15,
        threshold: int = 1024 * 16,
        tool_timeout: float = 300.0,
        search_api_endpoint: str = "",
        search_api_key: str = "",
        fetch_api_endpoint: str = "",
        fetch_api_key: str = "",
        tool_call_parser: str = "qwen",
    ) -> None:
        self.max_iterations = max_iterations
        self.threshold = threshold
        self.tool_timeout = tool_timeout
        self.search_api_endpoint = search_api_endpoint
        self.search_api_key = search_api_key
        self.fetch_api_endpoint = fetch_api_endpoint
        self.fetch_api_key = fetch_api_key
        self.tool_call_parser_type = tool_call_parser or "qwen"
        self._config: Optional[DistillConfig] = None
        self._tokenizer = None
        self._tokenizer_lock = Lock()
        self._tool_call_parser = SGLangToolCallParser(
            parser_type=self.tool_call_parser_type,
        )
        self._system_prompt = get_system_prompt(self.tool_call_parser_type)

    def setup(self, config: DistillConfig) -> None:
        self._config = config
        if self._tokenizer is None:
            from transformers import AutoTokenizer

            tokenizer_path = _TOKENIZER_PATHS.get(
                self.tool_call_parser_type.lower(),
                _DEFAULT_TOKENIZER_PATH,
            )
            self._tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_path,
                trust_remote_code=True,
            )

    def _count_tokens(self, messages: list[dict]) -> int:
        assert self._tokenizer is not None, "setup() must initialize tokenizer"
        chat_messages = []
        for msg in messages:
            chat_messages.append({
                "role": "user" if msg["role"] == "tool" else msg["role"],
                "content": msg.get("content", "") or "",
            })
        with self._tokenizer_lock:
            text = self._tokenizer.apply_chat_template(
                chat_messages,
                tokenize=False,
                add_generation_prompt=False,
            )
            token_ids = self._tokenizer.encode(text)
        return len(token_ids)

    @staticmethod
    def _mark_default_loss(messages: list[dict]) -> None:
        for msg in messages:
            if msg.get("role") == "assistant" and "loss" not in msg:
                msg["loss"] = True

    @staticmethod
    def _omit_tool_responses(messages: list[dict]) -> None:
        for msg in messages:
            if msg.get("role") == "tool":
                msg["content"] = "<tool_response>\n" + _OMITTED_TOOL_RESPONSE + "\n</tool_response>"
            if msg.get("role") == "assistant":
                msg["loss"] = False

    @staticmethod
    def _has_tool_call_request(content: str) -> bool:
        return "<tool_call>" in content or "</tool_call>" in content

    # Expected argument types per tool — used to reject malformed LLM output.
    _ARG_VALIDATORS: dict[str, dict[str, type]] = {
        "web_search": {"queries": list},
        "fetch": {"url": str},
    }

    def _validate_args(self, name: str, args: Any) -> Optional[str]:
        """Return an error string if *args* don't match the tool schema."""
        if not isinstance(args, dict):
            return f"arguments is not a JSON object (got {type(args).__name__})"
        schema = self._ARG_VALIDATORS.get(name)
        if schema is None:
            return None
        for field, expected_type in schema.items():
            if field in args and not isinstance(args[field], expected_type):
                return (
                    f"parameter '{field}' should be {expected_type.__name__}, "
                    f"got {type(args[field]).__name__}: {str(args[field])[:120]}"
                )
        return None

    def _parse_tool_calls(self, content: str) -> tuple[list[dict], Optional[str]]:
        """Delegate to SGLang. Returns (tool_calls_in_openai_shape, error_msg).

        ``error_msg`` is non-None when parsing failed (or returned a tool name
        outside the allowed set). Caller uses it both to surface a corrective
        message back to the model and to mark the assistant turn ``loss=False``.
        """
        wrapped_content = content.split("</think>")[-1]
        parsed_calls, error_msg = self._tool_call_parser.parse_tool_calls(wrapped_content)
        errors: list[str] = [error_msg] if error_msg else []

        tool_calls: list[dict] = []
        for call in parsed_calls:
            name = call.get("name") or ""
            if "." in name:  # strip namespace: "browser.web_search" → "web_search"
                name = name.rsplit(".", 1)[-1]
            args = call.get("arguments", {})

            arg_error = self._validate_args(name, args)
            if arg_error:
                errors.append(f"tool '{name}': {arg_error}")
                continue

            if isinstance(args, (dict, list)):
                args_str = json.dumps(args, ensure_ascii=False)
            elif args is None:
                args_str = "{}"
            else:
                args_str = str(args)
            tool_calls.append({
                "id": f"call_{len(tool_calls)}",
                "type": "function",
                "function": {"name": name, "arguments": args_str},
            })

        combined_error = "; ".join(errors) if errors else None
        return tool_calls, combined_error

    async def _execute_tool(self, raw_tc: dict,
                            fetch_session: FetchSession) -> dict:
        fn = raw_tc.get("function", raw_tc)
        name = fn.get("name", "")
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except Exception:
            args = {}

        if name == "web_search":
            return await self._do_search(args)
        if name == "fetch":
            return await self._do_fetch(args, fetch_session)
        return {"name": name, "response": f"unknown tool: {name}"}

    async def _do_search(self, args: dict) -> dict:
        queries = args.get("queries", [])
        if not queries:
            return {"name": "web_search", "response": "queries required"}
        try:
            result = await web_search(
                queries,
                self.search_api_endpoint,
                self.search_api_key,
                timeout=self.tool_timeout,
            )
            return {"name": "web_search", "response": result}
        except Exception as e:
            return {"name": "web_search", "response": f"search failed: {e}"}

    async def _do_fetch(self, args: dict, session: FetchSession) -> dict:
        url = args.get("url", "")
        if not url:
            return {"name": "fetch", "response": "url required"}
        try:
            result = await session.fetch(url, args.get("page", 1))
            return {"name": "fetch", "response": result}
        except Exception as e:
            return {"name": "fetch", "response": f"fetch failed: {e}"}

    @staticmethod
    def _format_tool_results(results: list[dict]) -> str:
        parts = [r.get("response", "No result") for r in results]
        return "<tool_response>\n" + "\n".join(parts) + "\n</tool_response>"

    async def _call_llm(self, messages: list[dict]) -> str:
        """Send the conversation as proper multi-turn messages."""
        return await agenerate_chat(messages, self._config) or ""

    @staticmethod
    def _conversation_to_steps(conversation: list[dict]) -> list[Step]:
        steps: list[Step] = []
        for msg in conversation:
            step = Step(role=msg["role"], content=msg.get("content", ""))
            if msg.get("tool_calls"):
                step.tool_calls = msg["tool_calls"]
            if "loss" in msg:
                step.metadata["loss"] = msg["loss"]
            steps.append(step)
        return steps

    async def arollout(self, example: dict) -> Trajectory:
        assert self._config is not None, "setup() must be called before arollout()"

        question = example["questions"][0]["question"]
        conversation: list[dict] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": question},
        ]
        segments: list[list[dict]] = []
        omit_count = 0
        iteration = 0
        appended_segment_this_turn = False
        rollout_error = None

        fetch_session = FetchSession(
            self.fetch_api_endpoint,
            self.fetch_api_key,
            timeout=self.tool_timeout,
        )

        for iteration in range(1, self.max_iterations + 1):
            print(f"iteration: {iteration}-{question[:50]}")
            appended_segment_this_turn = False

            try:
                content = await self._call_llm(conversation)
            except Exception as e:
                logger.error("LLM call failed: %s", e)
                rollout_error = repr(e)
                break

            has_tool_call_request = self._has_tool_call_request(content)
            tool_calls, parse_error = self._parse_tool_calls(content)
            parse_failed_with_tag = (
                has_tool_call_request and (parse_error is not None or not tool_calls)
            )

            msg: dict = {"role": "assistant", "content": content}
            if tool_calls:
                msg["tool_calls"] = tool_calls
            # When the assistant tried to call a tool but the parser couldn't
                # extract a usable call, exclude this turn from training loss
                # (but keep it in context so the model can self-correct).
            if parse_failed_with_tag:
                msg["loss"] = False
            conversation.append(msg)

            token_count = self._count_tokens(conversation)
            if token_count > self.threshold:
                print(f"  [omit] iter {iteration}: {token_count} tokens > {self.threshold}")
                self._mark_default_loss(conversation)
                segments.append(deepcopy(conversation))
                appended_segment_this_turn = True
                self._omit_tool_responses(conversation)
                omit_count += 1

            if not has_tool_call_request:
                break

            if iteration >= self.max_iterations:
                break

            if not tool_calls:
                error_text = parse_error or "invalid tool_call format"
                conversation.append({
                    "role": "tool",
                    "content": (
                        "<tool_response>\n"
                        f"Tool call request format error: {error_text}. "
                        "Please reissue the tool call using the exact format "
                        "shown in the system prompt.\n"
                        "</tool_response>"
                    ),
                })
                continue

            MAX_TOOL_CALLS = 2
            executed = tool_calls[:MAX_TOOL_CALLS]
            tool_results = [
                await self._execute_tool(tc, fetch_session) for tc in executed
            ]
            response_content = self._format_tool_results(tool_results)
            if len(tool_calls) > MAX_TOOL_CALLS:
                skipped = [tc.get("function", tc).get("name", "?")
                           for tc in tool_calls[MAX_TOOL_CALLS:]]
                response_content += (
                    f"\n\nNote: Only the first {MAX_TOOL_CALLS} tool calls were "
                    f"executed. {len(tool_calls) - MAX_TOOL_CALLS} call(s) skipped: "
                    f"{', '.join(skipped)}. Please issue them in the next turn."
                )
            conversation.append({
                "role": "tool",
                "content": response_content,
            })

        if not appended_segment_this_turn or (conversation and conversation[-1]["role"] == "tool"):
            self._mark_default_loss(conversation)
            segments.append(deepcopy(conversation))

        return Trajectory(
            steps=self._conversation_to_steps(conversation),
            metadata={
                "model": self._config.model,
                "iterations": iteration,
                "omit_count": omit_count,
                "question": question,
                "segments": segments,
                "rollout_error": rollout_error,
                "tool_call_parser": self.tool_call_parser_type,
            },
        )
