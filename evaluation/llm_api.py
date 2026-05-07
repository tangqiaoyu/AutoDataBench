"""Placeholder ``llm_api`` module.

The real implementation is intentionally not shipped with this codebase.
Replace this file (or point ``DISTILL_LLM_API_DIR`` at a directory containing
your own implementation) before running the pipeline.

The expected interface is documented in
``tasks/<task>/environment/llm_api_doc.md``. At minimum, two functions:

    llm_call(prompt: str, *, model: str, **kwargs) -> str | None
    allm_call(prompt: str, *, model: str, **kwargs) -> Awaitable[str | None]

Both should talk to an OpenAI-compatible LLM gateway and return the assistant
text (or ``None`` on failure).
"""

from __future__ import annotations


_MSG = (
    "llm_api is a placeholder. Provide a real implementation by setting "
    "DISTILL_LLM_API_DIR to a directory containing llm_api.py, or by "
    "replacing this file. See tasks/<task>/environment/llm_api_doc.md for "
    "the expected interface."
)


def llm_call(prompt: str, **kwargs) -> str | None:  # pragma: no cover
    raise NotImplementedError(_MSG)


async def allm_call(prompt: str, **kwargs) -> str | None:  # pragma: no cover
    raise NotImplementedError(_MSG)
