# llm_api.py Usage Guide

A unified LLM invocation interface that routes requests through an OpenAI-compatible LLM gateway to reach multiple model families (Qwen, OpenAI/GPT, Claude, Gemini). It handles per-model protocol differences, thinking/reasoning modes, and retry logic automatically.

> **Important**: This document is the **interface specification** for `llm_api.py`. The implementation module itself is **not shipped with the task**; the evaluation harness is expected to inject a compatible `llm_api` module (or any equivalent OpenAI-compatible wrapper) into the agent sandbox at run time. Agents may also implement their own LLM invocation logic against the same `LLM_API_BASE` / `LLM_API_KEY` env vars if they prefer — the function signatures below are a contract, not a hard dependency.

> **Note (current project setup)**: `LLM_API_KEY` and `LLM_API_BASE` are already provided via environment variables, so you do **not** need to pass `api_key=` or `base_url=` at call time.

> **For data construction, thinking mode is recommended**: pass `thinking=True`, and supply `thinking_budget` (Qwen / vertex_ai.claude\*) or `thinking_effort` (other Claude / GPT / Gemini) according to the model family. See [Available Model List](#3-available-model-list) below for available models, and [§6 Thinking / Reasoning Mode](#6-thinking--reasoning-mode) for parameter routing rules.

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Quick Start](#2-quick-start)
3. [Available Model List](#3-available-model-list)
4. [Model Routing & Channels](#4-model-routing--channels)
5. [Public API Reference](#5-public-api-reference)
6. [Thinking / Reasoning Mode](#6-thinking--reasoning-mode)
7. [Sampling Parameters](#7-sampling-parameters)
8. [Multi-turn Conversation (history)](#8-multi-turn-conversation-history)
9. [Streaming vs. Non-streaming](#9-streaming-vs-non-streaming)
10. [Advanced Usage](#10-advanced-usage)
11. [Per-model Examples](#11-per-model-examples)
12. [Return Value Format](#12-return-value-format)
13. [Error Handling & Retry](#13-error-handling--retry)
14. [Debugging](#14-debugging)
15. [FAQ](#15-faq)

---

## 1. Environment Setup

### Install Dependencies

```bash
pip install openai httpx requests
```

### Set API Key

The API key is read from the `LLM_API_KEY` environment variable:

```bash
export LLM_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

You can also pass `api_key=` explicitly at call time to override the environment variable.

> ⚠️ If `LLM_API_KEY` is not set and no `api_key=` is passed, `DEFAULT_API_KEY` will be `None` and the OpenAI SDK will raise immediately (`OpenAIError: The api_key client option must be set...`). The code **no longer** ships with a hardcoded fallback key.

### Default Base URL

Read from the `LLM_API_BASE` environment variable; if unset, defaults to a generic OpenAI-compatible gateway placeholder:

```
http://llm-gateway.local:8080/v1
```

You can also switch to any other OpenAI-compatible endpoint (e.g. a self-hosted proxy) via the `base_url=` parameter at call time.

---

## 2. Quick Start

### Synchronous Call

```python
from llm_api import llm_call

# Qwen with thinking (budget mode)
response = llm_call(
    "Explain quantum entanglement",
    model="qwen3.5-122b-a10b",
    thinking=True,
    thinking_budget=4096,
)
print(response)

# Qwen without thinking
response = llm_call(
    "Write a quicksort in Python",
    model="qwen3.5-122b-a10b",
    system="You are a coding assistant",
    temperature=0.7,
    max_tokens=2048,
)
```

### Asynchronous Call

```python
import asyncio
from llm_api import allm_call

async def main():
    response = await allm_call(
        "1+1=?",
        model="qwen3.5-122b-a10b",
        thinking=True,
        thinking_budget=2048,
    )
    print(response)

asyncio.run(main())
```

---

## 3. Available Model List

- openai.gpt-5.4-2026-03-05
- aws.claude-sonnet-4-6
- qwen3.6-plus
- aws.claude-haiku-4-5-20251001
- qwen3.6-flash
- qwen3-30b-a3b-thinking-2507
- qwen3-30b-a3b-instruct-2507

---

## 4. Model Routing & Channels

The **prefix** of the model name determines which protocol channel is used:

| Prefix | Channel | Protocol | Example |
|---|---|---|---|
| `aws.*` / `bedrock.*` | `claude` | Claude-native SSE | `aws.claude-sonnet-4-5-20250929` |
| `vertex_ai.claude*` | `claude` | Claude-native SSE (Anthropic-native thinking) | `vertex_ai.claude-sonnet-4-5-20250929` |
| `vertex_ai.*` (non-claude) / `ai_studio.*` | `gemini` | Gemini-native | `ai_studio.gemini-3.1-pro-preview` |
| everything else | `openai` | OpenAI-compatible | `qwen3.5-122b-a10b`, `openai.gpt-5.4-2026-03-05` |

**Qwen-family models** (`qwen*`, `qwq*`, `qvq*`) go through the `openai` channel, with the following quirks handled internally:
- `enable_thinking` / `thinking_budget` are placed into `extra_body`
- `top_k` / `repetition_penalty` are placed into `extra_body` (the upstream gateway requires non-standard params to go through `extra_body`)

---

## 5. Public API Reference

`llm_call` and `allm_call` share the exact same parameters; the only difference is that the latter is `async`.

### Function Signature

```python
def llm_call(
    prompt,                          # str, required — user input
    base_url=DEFAULT_BASE_URL,       # str — API endpoint
    system="",                       # str — system prompt
    temperature=1.0,                 # float — sampling temperature
    max_tokens=32768,                # int — max output tokens
    model="",                        # str — model name (see §4)
    top_p=1,                         # float — nucleus sampling threshold
    n=1,                             # int — number of completions (most models only support 1)
    history=None,                    # list[dict] — multi-turn conversation history
    stop=None,                       # str|list — stop sequences
    completion=False,                # bool — use the legacy completions endpoint
    thinking=False,                  # bool — enable thinking mode (see §6)
    thinking_budget=None,            # int — thinking token budget (see §6)
    thinking_effort=None,            # str — thinking level "low"/"medium"/"high" (see §6)
    timeout=600,                     # int — per-request timeout in seconds
    max_retry=10,                    # int — max retries (default 10)
    debug=False,                     # bool — print request/response debug info
    return_completion=False,         # bool — return the raw SDK response object
    echo=False,                      # bool — echo the prompt (completion mode only)
    extra_body=None,                 # dict — extra_body forwarded to the SDK
    top_k=None,                      # int — Top-K sampling
    repetition_penalty=None,         # float — repetition penalty
    presence_penalty=None,           # float — presence penalty
    api_key=DEFAULT_API_KEY,         # str — override the default API key
    stream=True,                     # bool — use a streaming request
    **kwargs,                        # other pass-through parameters
) -> str | None
```

### Return Value

- **Success**: returns a `str`, the model-generated text. When the model emits thinking content, it is wrapped in `<think>...</think>` and prepended to the main body.
- **Failure** (retries exhausted, content-moderation block): returns `None`.

---

## 6. Thinking / Reasoning Mode

Thinking mode is controlled by **three independent parameters**:

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `thinking` | `bool` | `False` | Master switch. `False` = no thinking; budget/effort are ignored. |
| `thinking_budget` | `int \| None` | `None` | Thinking token budget. **Used by the Qwen family.** |
| `thinking_effort` | `str \| None` | `None` | Thinking level: `"low"` / `"medium"` / `"high"`. **Used by Claude / GPT / Gemini.** |

### Rules

1. `thinking=False` → no thinking parameters are sent (default behavior).
2. `thinking=True` → you **must** pass at least one of `thinking_budget` or `thinking_effort`; otherwise an `AssertionError` is raised.
3. Passing `thinking_budget` or `thinking_effort` while `thinking=False` → `AssertionError` (contradictory flags).
4. `thinking_effort` must be one of `"low"` / `"medium"` / `"high"`, otherwise `AssertionError`.
5. **Budget-only models** (Qwen) silently ignore `thinking_effort`.
6. **Effort-only models** (Claude / GPT / Gemini) silently ignore `thinking_budget`.

### Per-model Behavior

| Model Family | Parameter Used | Actual Payload |
|---|---|---|
| **Qwen3/3.5/3.6, QwQ, QvQ** | reads `thinking_budget`, ignores `thinking_effort` | `extra_body={"enable_thinking": true, "thinking_budget": N}` |
| **Claude (claude-\*)** | reads `thinking_effort`, ignores `thinking_budget` | `extra_body={"reasoning_effort": "low/medium/high"}` |
| **Claude (aws.\*)** | reads `thinking_effort`, ignores `thinking_budget` | `output_config={"effort": "low/medium/high"}` |
| **Claude (vertex_ai.claude\*)** | reads `thinking_budget`, ignores `thinking_effort` | `thinking={"type": "enabled", "budget_tokens": N}` |
| **OpenAI o1/o3/o4/gpt-5** | reads `thinking_effort`, ignores `thinking_budget` | `extra_body={"reasoning": {"effort": "low/medium/high"}}` |
| **Gemini (vertex_ai.\*, ai_studio.\*)** | reads `thinking_effort`, ignores `thinking_budget` | `thinkingConfig={"includeThoughts": true, "thinkingLevel": "low/medium/high"}` |

### Output Format

When the model emits thinking content, the return value is:

```
<think>
The model's reasoning process...
</think>

The model's final reply...
```

If there is no thinking content (or `thinking=False`), only the final reply text is returned.

---

## 7. Sampling Parameters

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `temperature` | float | `1.0` | Sampling temperature; higher = more random. Range [0, 2). |
| `top_p` | float | `1` | Nucleus sampling cutoff. Range (0, 1]. |
| `top_k` | int | `None` | Number of candidate tokens. Auto-routed into `extra_body` for Qwen. |
| `repetition_penalty` | float | `None` | Repetition penalty; `1.0` = no penalty. Auto-routed into `extra_body` for Qwen. |
| `presence_penalty` | float | `None` | Presence penalty. Range [-2.0, 2.0]. |
| `n` | int | `1` | Number of responses to generate. Only some models support `>1`. |
| `stop` | str/list | `None` | Stop sequence(s). |

---

## 8. Multi-turn Conversation (history)

Pass conversation history via the `history` parameter as a standard OpenAI-style messages array:

```python
history = [
    {"role": "system", "content": "You are a math teacher"},
    {"role": "user", "content": "What is calculus?"},
    {"role": "assistant", "content": "Calculus is a branch of mathematics..."},
]

response = llm_call(
    prompt="Can you give a concrete example?",
    model="qwen3.5-122b-a10b",
    history=history,
)
```

**Notes**:
- If the **last** entry in `history` is a `user` message, it is automatically dropped (since the new `prompt` will be appended as the latest user turn).
- If you pass a `system=` argument **and** `history` also contains `system` messages, the `system` messages inside `history` are **automatically filtered out** to avoid duplicate system turns.
- If you do **not** pass `system=`, any `system` messages originally in `history` are preserved.

---

## 9. Streaming vs. Non-streaming

```python
# Streaming (default) — recommended; lowers the risk of timeout
response = llm_call("...", model="qwen3.5-122b-a10b", stream=True)

# Non-streaming
response = llm_call("...", model="qwen3.5-122b-a10b", stream=False)
```

In streaming mode, if the stream yields empty content, the call automatically falls back to a single non-streaming retry.

---

## 10. Advanced Usage

### Get the raw SDK response object

```python
completion = llm_call(
    "...",
    model="qwen3.5-122b-a10b",
    return_completion=True,
    stream=False,    # stream must be False when return_completion=True
)
print(completion.usage)          # token usage
print(completion.choices[0])     # full choice object
```

### Pass through `extra_body`

Forward arbitrary non-standard parameters to the upstream gateway:

```python
response = llm_call(
    "...",
    model="qwen3.5-122b-a10b",
    extra_body={
        "enable_search": True,                       # enable online search
        "response_format": {"type": "json_object"},  # JSON output
    },
)
```

### Use a custom API endpoint

```python
response = llm_call(
    "...",
    model="my-model",
    base_url="http://localhost:8000/v1",
    api_key="my-key",
)
```

### Batched async concurrency

```python
import asyncio
from llm_api import allm_call

async def batch():
    prompts = ["question 1", "question 2", "question 3"]
    tasks = [
        allm_call(p, model="qwen3.5-122b-a10b", max_tokens=1024)
        for p in prompts
    ]
    results = await asyncio.gather(*tasks)
    return results

results = asyncio.run(batch())
```

---

## 11. Per-model Examples

### Qwen (thinking_budget)

```python
response = llm_call(
    "Prove that sqrt(2) is irrational",
    model="qwen3.5-122b-a10b",
    thinking=True,
    thinking_budget=4096,
    max_tokens=8192,
)
```

### Qwen (thinking off)

```python
response = llm_call(
    "Hello",
    model="qwen3.5-122b-a10b",
    # thinking=False is the default; you can omit it
)
```

### OpenAI GPT (thinking_effort)

```python
response = llm_call(
    "Write a haiku about coding",
    model="openai.gpt-5.4-2026-03-05",
    thinking=True,
    thinking_effort="medium",
    max_tokens=2048,
)
# GPT reasoning models do NOT surface a <think> block in the text, but
# reasoning_tokens shows up in `usage`. Use return_completion=True with
# stream=False to inspect usage.reasoning_tokens.
```

### Claude (aws.*)

```python
response = llm_call(
    "Explain quantum computing",
    model="aws.claude-sonnet-4-5-20250929",
    thinking=True,
    thinking_effort="high",
    max_tokens=4096,
)
```

### Claude (vertex_ai.*)

```python
response = llm_call(
    "Explain quantum computing",
    model="vertex_ai.claude-sonnet-4-5-20250929",
    thinking=True,
    thinking_budget=4096,     # Anthropic-native thinking uses budget_tokens, not effort
    max_tokens=8192,
)
```

### Claude (OpenAI-compatible channel)

```python
response = llm_call(
    "Explain quantum computing",
    model="claude-sonnet-4-5-20250929",
    thinking=True,
    thinking_effort="low",
    max_tokens=4096,
)
```

### Gemini (vertex_ai.*)

```python
response = llm_call(
    "Summarize this paper",
    model="ai_studio.gemini-3.1-pro-preview",
    thinking=True,
    thinking_effort="low",
    max_tokens=4096,
)
```

---

## 12. Return Value Format

### Response with thinking (Qwen-family thinking mode)

```text
<think>
Let me work through this step by step...
1. First, ...
2. Then, ...
</think>

The answer is 42.
```

### Response without thinking

```text
The answer is 42.
```

### Parsing the thinking content

If you need to split thinking and body apart:

```python
import re

response = llm_call(
    "...", model="qwen3.5-122b-a10b",
    thinking=True, thinking_budget=4096,
)

match = re.match(r"<think>\n(.*?)\n</think>\n\n(.*)", response, re.DOTALL)
if match:
    thinking_content = match.group(1)
    answer = match.group(2)
else:
    thinking_content = ""
    answer = response
```

---

## 13. Error Handling & Retry

- **Automatic retry**: up to 10 retries by default (`max_retry=10`). Uses **exponential backoff**: starts at 5s, doubles each attempt, capped at 60s (5 → 10 → 20 → 40 → 60 → 60 → …); each sleep has ±30% jitter to avoid thundering-herd on concurrent retries.
- **Content moderation**: if the response contains `data_inspection_failed`, the call returns `None` immediately without retrying.
- **Content filter**: if `finish_reason == "content_filter"`, returns `None`.
- **Empty streamed response**: automatically falls back to a single non-streaming retry.
- **All retries exhausted**: returns `None`.

```python
response = llm_call("...", model="qwen3.5-122b-a10b", max_retry=3, timeout=60)
if response is None:
    print("call failed")
```

---

## 14. Debugging

Set `debug=True` to print the full outgoing request parameters, parse details, and retry flow:

```python
response = llm_call(
    "test",
    model="qwen3.5-122b-a10b",
    thinking=True,
    thinking_budget=4096,
    debug=True,
)
```

### Request body dump

The full outgoing payload is printed before every request (the most common diagnostic use case):

```
[llm_api debug] openai stream qwen3.5-122b-a10b -> http://llm-gateway.local:8080/v1
{
  "model": "qwen3.5-122b-a10b",
  "messages": [{"role": "user", "content": "test"}],
  "temperature": 1.0,
  "max_tokens": 4096,
  "stream": true,
  "extra_body": {
    "enable_thinking": true,
    "thinking_budget": 4096
  }
}
```

The tag prefix (`openai stream` / `openai nonstream` / `openai completion` / `claude stream` / `claude nonstream` / `gemini stream` / `gemini nonstream`) tells you which path was taken.

### Diagnostic log reference

When the call returns `None` or content looks empty, read the debug log bottom-up to locate the cause. Common lines and what they mean:

| Log prefix | Meaning |
|---|---|
| `_extract_response: empty choices, raw=...` | Response has no `choices` field — provider returned empty. |
| `_extract_response: content_filter triggered, raw=...` | `finish_reason == "content_filter"`; retries aborted, `None` returned. |
| `_extract_response: empty content after wrap, message=...` | Choice exists but `message.content` is empty (often thinking budget too small, output truncated). |
| `openai stream: content_filter, returning None` | Stream aggregation hit content filter; **does not** fall back to non-stream. |
| `openai stream: empty result, falling back to non-stream` | Stream returned empty; a single non-streaming retry is issued. |
| `openai nonstream: got None, will not retry (no exception)` | Non-stream returned OK but body was empty; not an exception, so no retry. |
| `openai exception (will retry): ...` | A retryable exception was caught; entering exponential backoff. |
| `fatal error, aborting retries: ...` | Non-retryable error (401/403/404/422 or `data_inspection_failed`); returns `None` immediately. |
| `openai: all {N} retries exhausted, returning None` | All retries used up. |
| `empty parse, first raw SSE lines: ...` | Native-channel SSE parsed empty; also dumps the first 8 raw lines. |
| `empty parse, raw response: ...` | Native-channel non-stream parsed empty; also dumps the first 1500 chars of the response. |

Native-channel (`claude` / `gemini`) logs use `claude ...` / `gemini ...` prefixes accordingly.

### Quick triage

- **Returned `None`** → look at the last debug line; it falls into one of `fatal error` / `retries exhausted` / `content_filter` — each has a different handling path.
- **Non-None but content looks missing** → check `_extract_response: empty content after wrap`; the `message=...` dump carries the provider's raw fields. Usually caused by a too-small `thinking_budget` truncating the output.
- **Native-channel empty parse** → `first raw SSE lines` reveals exactly what the proxy wrote on the wire, usually a protocol mismatch.

---

## 15. FAQ

### Q: Why does the call return `None`?

Common causes:
1. `LLM_API_KEY` is not set or invalid.
2. Misspelled model name.
3. Content triggered moderation (`data_inspection_failed`).
4. Network timeout with all retries exhausted.

Use `debug=True` to investigate.

### Q: What happens if `thinking=True` but I forgot to pass budget or effort?

You get an `AssertionError` immediately — there is no silent fallback:

```
AssertionError: thinking=True requires at least one of thinking_budget or thinking_effort
```

When `thinking=True`, you **must** pass at least one of `thinking_budget` or `thinking_effort` (see §6 rule 2). It is safe to pass both — models that only recognize one will ignore the other.

### Q: What happens if I pass both `thinking_budget` and `thinking_effort`?

Each model reads only the parameter it understands; the other is silently ignored:
- **Qwen**: reads `thinking_budget`, ignores `thinking_effort`.
- **Claude / GPT / Gemini**: reads `thinking_effort`, ignores `thinking_budget`.

### Q: Why do `top_k` / `repetition_penalty` for Qwen go into `extra_body`?

The upstream OpenAI-compatible protocol requires non-standard parameters to be passed via `extra_body`. `llm_api.py` auto-detects Qwen models and does the routing for you — callers do not need to think about it.

### Q: How do I use `extra_body` and thinking together?

They are merged automatically:

```python
response = llm_call(
    "...",
    model="qwen3.5-122b-a10b",
    thinking=True,
    thinking_budget=4096,
    extra_body={"enable_search": True},
    # actual payload: extra_body={"enable_thinking": True, "thinking_budget": 4096, "enable_search": True}
)
```

### Q: Which Qwen thinking models are supported?

Models whose name starts with any of the following prefixes get the thinking adaptation automatically:
- `qwen3` — includes qwen3, qwen3.5, qwen3.6 series
- `qwq`
- `qvq`
