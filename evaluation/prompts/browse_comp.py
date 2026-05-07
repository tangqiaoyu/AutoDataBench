"""BrowseComp system prompts.

Two flavours, one per SGLang `tool_call_parser`:

* ``qwen`` / ``qwen25``  — JSON tool calls inside ``<tool_call>...</tool_call>``
  (matches the chat template shipped with Qwen3-4B-Thinking-2507).
* ``qwen3_coder``         — XML tool calls with ``<function=...>`` /
  ``<parameter=...>`` blocks inside ``<tool_call>...</tool_call>``
  (matches the chat template shipped with Qwen3.6-27B).

Use :func:`get_system_prompt` to fetch the right one.
"""

from __future__ import annotations

import json

# Tool schemas advertised in <tools>...</tools>. Kept in sync with
# ``tools/tool_call_parser.py``'s ``DEFAULT_TOOLS``.
_TOOLS: list[dict] = [
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
                    "page": {"type": "integer", "default": 1},
                },
                "required": ["url"],
            },
        },
    },
]

_TOOLS_BLOCK = "\n".join(json.dumps(t, ensure_ascii=False) for t in _TOOLS)

_INTRO = (
    "You are a professional retrieval assistant. You need to find the answer "
    "to a complex retrieval problem through a complex process with two tools: "
    "web_search and fetch. You should use the provided tools in a planned "
    "manner and validate all constraints with evidence. If more information "
    "is needed, request tool calls. Once you have found and validated the "
    "answer, provide the final answer directly and do not request any tool "
    "call."
)

_OUTRO = (
    "After generating the tool call request, stop and wait for the tool "
    "responses. Do not generate fake tool responses, because the user will "
    "return the tool response to you."
)


# ---------------------------------------------------------------------------
# JSON tool-call style — matches SGLang ``qwen`` / ``qwen25`` parser
# (Qwen3-4B-Thinking-2507 chat template).
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_QWEN = f"""\
{_INTRO}

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{_TOOLS_BLOCK}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</tool_call>

{_OUTRO}"""


# ---------------------------------------------------------------------------
# XML tool-call style — matches SGLang ``qwen3_coder`` parser
# (Qwen3.6-27B chat template).
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_QWEN3_CODER = f"""\
{_INTRO}

# Tools

You have access to the following functions:

<tools>
{_TOOLS_BLOCK}
</tools>

If you choose to call a function ONLY reply in the following format with NO suffix:

<tool_call>
<function=example_function_name>
<parameter=example_parameter_1>
value_1
</parameter>
<parameter=example_parameter_2>
This is the value for the second parameter
that can span
multiple lines
</parameter>
</function>
</tool_call>

<IMPORTANT>
Reminder:
- Function calls MUST follow the specified format: an inner <function=...></function> block must be nested within <tool_call></tool_call> XML tags
- Required parameters MUST be specified
- You may provide optional reasoning for your function call in natural language BEFORE the function call, but NOT after
- If there is no function call available, answer the question like normal with your current knowledge and do not tell the user about function calls
</IMPORTANT>

{_OUTRO}"""


# Backwards-compat alias — the rollout used ``SYSTEM_PROMPT`` as the only
# variant; it now defaults to the JSON / qwen style.
SYSTEM_PROMPT = SYSTEM_PROMPT_QWEN


def get_system_prompt(tool_call_parser: str) -> str:
    """Return the system prompt matching ``tool_call_parser``.

    Falls back to the JSON / qwen variant for unknown parser types.
    """
    key = (tool_call_parser or "").lower()
    if key == "qwen3_coder":
        return SYSTEM_PROMPT_QWEN3_CODER
    return SYSTEM_PROMPT_QWEN
