import os
import re
import json
from typing import Any, Optional

# Set this before importing sglang so that unknown tool names are returned as
# tool_index=-1 instead of being silently dropped.
os.environ.setdefault("SGLANG_FORWARD_UNKNOWN_TOOLS", "true")

from sglang.srt.entrypoints.openai.protocol import Function, Tool
from sglang.srt.function_call.function_call_parser import FunctionCallParser


DEFAULT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Perform 1~3 web searches and return titles, URLs, and snippets. "
                "Supports all Google search syntax."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 3,
                    }
                },
                "required": ["queries"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch",
            "description": (
                "Fetch and extract content from a web page. "
                "If content is too long, increase the page number."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "page": {
                        "type": "integer",
                        "default": 1,
                    },
                },
                "required": ["url"],
            },
        },
    },
]


class SGLangToolCallParser:
    def __init__(
        self,
        tools: Optional[list[dict[str, Any] | Tool]] = DEFAULT_TOOLS,
        parser_type: str = "qwen",
    ):
        """
        tools:
            Defaults to web_search / fetch. Accepts both OpenAI tools dicts
            and SGLang Tool objects.

        parser_type:
            Defaults to "qwen". Other valid values include "qwen25",
            "qwen3_coder", "deepseekv3", "glm", "gpt-oss", etc.
        """
        self.parser_type = parser_type
        self.tools = self._normalize_tools(tools)
        self.allowed_tool_names = {
            tool.function.name
            for tool in self.tools
            if getattr(tool, "function", None) is not None
        }

        self.parser = FunctionCallParser(
            tools=self.tools,
            tool_call_parser=self.parser_type,
        )

    def parse_tool_calls(self, response: str) -> tuple[list[dict[str, Any]], Optional[str]]:
        """
        Returns:
            tool_calls:
                [
                    {
                        "name": "...",
                        "arguments": {...} or raw string,
                        "tool_index": 0,
                    }
                ]

            error_msg:
                None means no error.
                str means a parse or validation error.
        """
        errors: list[str] = []

        has_tool_call_tag = self._has_tool_call_tag(response)

        try:
            normalized_response = self._canonicalize_tool_call_tag(response)
            _, parsed_calls = self.parser.parse_non_stream(normalized_response)
        except Exception as e:
            if has_tool_call_tag:
                return [], f"<tool_call> tag detected but SGLang parser raised: {type(e).__name__}: {e}"
            return [], f"SGLang parser raised: {type(e).__name__}: {e}"

        tool_calls: list[dict[str, Any]] = []

        for call in parsed_calls:
            name = getattr(call, "name", None)
            parameters = getattr(call, "parameters", None)
            tool_index = getattr(call, "tool_index", None)

            arguments = self._parse_arguments(parameters)

            tool_calls.append(
                {
                    "name": name,
                    "arguments": arguments,
                    "tool_index": tool_index,
                }
            )

            if name not in self.allowed_tool_names:
                errors.append(
                    f"invalid tool name: {name!r}. allowed: {sorted(self.allowed_tool_names)}"
                )

        if has_tool_call_tag and not tool_calls:
            errors.append("<tool_call> tag detected but no tool call could be parsed.")

        error_msg = "\n".join(errors) if errors else None
        return tool_calls, error_msg

    def _normalize_tools(self, tools: list[dict[str, Any] | Tool]) -> list[Tool]:
        normalized: list[Tool] = []

        for tool in tools:
            if isinstance(tool, Tool):
                normalized.append(tool)
                continue

            # OpenAI tool schema:
            # {
            #   "type": "function",
            #   "function": {"name": ..., "description": ..., "parameters": {...}}
            # }
            if isinstance(tool, dict) and "function" in tool:
                normalized.append(Tool(**tool))
                continue

            # Simplified schema:
            # {"name": ..., "description": ..., "parameters": {...}}
            if isinstance(tool, dict) and "name" in tool:
                normalized.append(
                    Tool(
                        function=Function(
                            name=tool["name"],
                            description=tool.get("description"),
                            parameters=tool.get("parameters", {}),
                        )
                    )
                )
                continue

            raise ValueError(f"Unsupported tool format: {tool!r}")

        return normalized

    def _parse_arguments(self, parameters: Any) -> Any:
        """
        SGLang's ToolCallItem.parameters is usually a JSON string, but not
        every parser guarantees standard JSON, so:
          - if json.loads succeeds, return dict/list
          - otherwise return the raw string
        """
        if parameters is None:
            return {}

        if isinstance(parameters, (dict, list)):
            return parameters

        if isinstance(parameters, str):
            text = parameters.strip()
            if not text:
                return {}

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

        return parameters

    def _has_tool_call_tag(self, response: str) -> bool:
        return bool(
            re.search(r"<tool_call\b[^>]*>", response)
            or re.search(r"</tool_call>", response)
        )

    def _canonicalize_tool_call_tag(self, response: str) -> str:
        """
        Mainly for qwen / qwen25 parsers that are sensitive to newlines.

        Rewrites:
            <tool_call>{"name": ...}</tool_call>

        into:
            <tool_call>
            {"name": ...}
            </tool_call>

        Other parsers (e.g. qwen3_coder) are unaffected.
        """
        response = re.sub(r"<tool_call>\s*", "<tool_call>\n", response)
        response = re.sub(r"\s*</tool_call>", "\n</tool_call>", response)
        return response

if __name__ == "__main__":
    response = """
I need to search first.
<tool_call>
{"name": "search", "arguments": {"queries": ["sglang tool call parser"]}}
</tool_call>
"""
    parser = SGLangToolCallParser()
    tool_calls, error_msg = parser.parse_tool_calls(response)
    print(tool_calls)
    print(error_msg)
