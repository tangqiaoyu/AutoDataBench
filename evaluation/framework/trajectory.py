"""Trajectory data types — the unit of work produced by a Rollout.

A Trajectory is a sequence of Steps. Single-turn LLM calls are length-2
trajectories (user prompt + assistant reply). Multi-turn / tool-using rollouts
add more steps. The framework treats them uniformly.

Rollouts that run external commands and already know the verdict (e.g.
SWE-bench running pytest) may attach a `prejudged` JudgeResult; a
`PassthroughJudge` will surface it without re-judging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .judge import JudgeResult


@dataclass
class Step:
    """One turn in a trajectory. Follows OpenAI chat-completion shape."""
    role: str                                  # "user" | "assistant" | "tool" | "system"
    content: str = ""
    tool_calls: Optional[list[dict]] = None    # assistant-issued tool calls
    tool_call_id: Optional[str] = None         # set when role == "tool"
    name: Optional[str] = None                 # tool name when role == "tool"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Trajectory:
    steps: list[Step]
    metadata: dict[str, Any] = field(default_factory=dict)
    prejudged: Optional["JudgeResult"] = None


def last_assistant_text(trajectory: Trajectory) -> str:
    """Convenience: pull the last assistant step's text content.

    Single-turn LLM judges care about this; multi-turn judges typically inspect
    the full trajectory themselves.
    """
    for step in reversed(trajectory.steps):
        if step.role == "assistant":
            return step.content or ""
    return ""


def strip_thinking(text: str) -> str:
    """Remove chain-of-thought ``<think>...</think>`` content from a model
    response, returning only the final answer.

    Strategy (matches open-instruct's chat-template convention,
    ``content.split('</think>')[-1]``, so IFEvalG / RLVR-IFeval checkers see
    what they were designed to see):

    1. If ``</think>`` appears anywhere, return everything after the **last**
       ``</think>`` — this covers the common ``<think>reasoning</think>answer``
       case and also the multi-think case.
    2. If only ``<think>`` appears (output truncated by ``max_tokens`` before
       the model closed its reasoning), return an empty string — the model
       never produced an answer, so verifiers should see nothing and fail.
    3. Otherwise return the input unchanged (non-thinking model).

    Surrounding whitespace is trimmed.

    Preserve the raw trajectory for training-data emission; only strip when
    scoring.
    """
    if "</think>" in text:
        return text.rsplit("</think>", 1)[-1].strip()
    if "<think>" in text:
        return ""
    return text.strip()


def final_assistant_text(trajectory: Trajectory) -> str:
    """Like :func:`last_assistant_text` but with ``<think>...</think>`` stripped.

    Convenience wrapper for judges that should grade only the final answer.
    """
    return strip_thinking(last_assistant_text(trajectory))
