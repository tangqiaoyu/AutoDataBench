"""LLM call helpers — thin wrapper around an external `llm_api` module.

The actual `llm_api.py` is **not shipped** with this codebase. A minimal
placeholder lives next to this package (see `llm_api.py` at the repo root)
that raises `NotImplementedError` on call. To run the pipeline, point
`DISTILL_LLM_API_DIR` at a directory containing your own `llm_api.py`
(an OpenAI-compatible wrapper exposing `llm_call` / `allm_call`); see
`tasks/<task>/environment/llm_api_doc.md` for the expected interface.
"""

from __future__ import annotations

import os
import sys

from .config import DistillConfig

_FRAMEWORK_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_FRAMEWORK_DIR)
_CANDIDATES = [
    os.environ.get("DISTILL_LLM_API_DIR", ""),
    _PROJECT_DIR,  # placeholder ships at the package root
]
for _cand in _CANDIDATES:
    if _cand and os.path.isfile(os.path.join(_cand, "llm_api.py")):
        if _cand not in sys.path:
            sys.path.insert(0, _cand)
        break

from llm_api import allm_call, llm_call  # noqa: E402  (after sys.path patch)

# Sentinel that means "let llm_api pick its own default" without us having to
# mirror that default here. Forwarded as-is when the config doesn't specify one.
_USE_LLM_API_DEFAULT = object()


def _call_kwargs(config: DistillConfig) -> dict:
    """Build the kwargs shared by generate / agenerate.

    Only forwards fields that have a meaningful (non-empty) value so that
    llm_api's own defaults are preserved when the config doesn't specify one.
    """
    kwargs = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "max_retry": config.api_max_retries,
        "debug": config.debug,
    }
    if config.api_base:
        kwargs["base_url"] = config.api_base
    if config.api_key:
        kwargs["api_key"] = config.api_key

    # Thinking: llm_api asserts budget/effort must be None when thinking=False,
    # so only forward budget/effort when thinking is actually enabled.
    if config.thinking:
        kwargs["thinking"] = True
        if config.thinking_budget is not None:
            kwargs["thinking_budget"] = config.thinking_budget
        if config.thinking_effort:
            kwargs["thinking_effort"] = config.thinking_effort

    for attr in ("top_p", "top_k", "stop", "system", "stream",
                 "timeout", "extra_body"):
        val = getattr(config, attr, _USE_LLM_API_DEFAULT)
        if val is _USE_LLM_API_DEFAULT:
            continue
        if val == "" or val is None:
            continue
        kwargs[attr] = val
    if config.debug:
        print(kwargs)
    return kwargs


def generate(prompt: str, config: DistillConfig) -> str | None:
    return llm_call(prompt=prompt, **_call_kwargs(config))


async def agenerate(prompt: str, config: DistillConfig) -> str | None:
    return await allm_call(prompt=prompt, **_call_kwargs(config))


def _judge_call_kwargs(config: DistillConfig) -> dict:
    """kwargs for the judge LLM call.

    Overrides only model/base_url/api_key with the judge_* fields when set;
    every other knob (temperature, max_tokens, thinking, ...) is inherited
    from the rollout config so the judge stays a pure endpoint swap.
    """
    kwargs = _call_kwargs(config)
    if config.judge_model:
        kwargs["model"] = config.judge_model
    if config.judge_api_base:
        kwargs["base_url"] = config.judge_api_base
    if config.judge_api_key:
        kwargs["api_key"] = config.judge_api_key
    return kwargs


def generate_judge(prompt: str, config: DistillConfig) -> str | None:
    return llm_call(prompt=prompt, **_judge_call_kwargs(config))


async def agenerate_judge(prompt: str, config: DistillConfig) -> str | None:
    return await allm_call(prompt=prompt, **_judge_call_kwargs(config))


async def agenerate_chat(messages: list[dict], config: DistillConfig) -> str | None:
    """Call the LLM with an explicit multi-turn message list.

    Splits *messages* into ``system`` / ``history`` / ``prompt`` for
    :func:`allm_call`.  Messages with ``role="tool"`` are mapped to
    ``role="user"`` so every API channel sees a valid conversation.
    """
    system = ""
    history: list[dict] = []
    for msg in messages:
        if msg["role"] == "system":
            system = msg.get("content", "")
            continue
        history.append({
            "role": "user" if msg["role"] == "tool" else msg["role"],
            "content": msg.get("content", ""),
        })

    prompt = history.pop()["content"] if history else ""

    kw = _call_kwargs(config)
    kw["system"] = system
    kw["history"] = history
    return await allm_call(prompt=prompt, **kw)
