"""Segments formatter for multi-turn agent benchmarks.

Each conversation segment becomes a separate training row::

    {
        "messages": [{"role": "system", ...}, {"role": "user", ...}, ...],
        "enable_thinking": true
    }

Assistant messages include ``loss`` so compressed-history assistant turns can
be retained as context without contributing training loss.
"""

from __future__ import annotations

import json

from ..framework.formatter import BaseFormatter
from ..framework.judge import JudgeResult
from ..framework.trajectory import Trajectory

_ARG_VALIDATORS: dict[str, dict[str, type]] = {
    "web_search": {"queries": list},
    "fetch": {"url": str},
}


def _has_malformed_tool_args(msg: dict) -> bool:
    """Check whether any tool_call in *msg* has arguments that don't match
    the expected schema (e.g. queries should be list but got str)."""
    for tc in msg.get("tool_calls", []):
        fn = tc.get("function", tc)
        name = fn.get("name", "")
        raw = fn.get("arguments", "{}")
        try:
            args = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return True
        if not isinstance(args, dict):
            return True
        schema = _ARG_VALIDATORS.get(name)
        if schema is None:
            continue
        for field, expected_type in schema.items():
            if field in args and not isinstance(args[field], expected_type):
                return True
    return False


class SegmentsFormatter(BaseFormatter):
    def format(self, example: dict, trajectory: Trajectory,
               judge_result: JudgeResult) -> list[dict]:
        raw_segments = trajectory.metadata.get("segments")

        if raw_segments:
            rows: list[dict] = []
            for seg in raw_segments:
                msgs = _sanitize_segment(seg)
                if msgs:
                    rows.append({
                        "messages": msgs,
                        "enable_thinking": True,
                    })
            return rows

        all_messages = _steps_to_messages(trajectory.steps)
        return [{
        "messages": all_messages,
        "enable_thinking": True,
    }]


def _sanitize_segment(segment: list[dict]) -> list[dict]:
    """Convert a segment (list of plain message dicts) to training format.
    Maps role: "tool" → role: "user", and strips trailing non-assistant
    messages so the sequence ends on an assistant turn.

    Assistant messages whose tool_call arguments are malformed are forced to
    loss=False so SFT does not learn the broken output.
    """
    messages: list[dict] = []
    for msg in segment:
        role = msg["role"]
        if role == "tool":
            role = "user"
        m: dict = {"role": role, "content": msg.get("content", "")}
        if msg.get("role") == "assistant":
            if _has_malformed_tool_args(msg):
                m["loss"] = False
            else:
                m["loss"] = bool(msg.get("loss", True))
        messages.append(m)
    while messages and messages[-1]["role"] != "assistant":
        messages.pop()
    return messages


def _steps_to_messages(steps) -> list[dict]:
    """Fallback: convert Step objects to training format."""
    messages: list[dict] = []
    for step in steps:
        role = step.role
        if role == "tool":
            role = "user"
        msg: dict = {"role": role, "content": step.content}
        if step.role == "assistant":
            raw_msg = {"tool_calls": step.tool_calls} if getattr(step, "tool_calls", None) else {}
            if _has_malformed_tool_args(raw_msg):
                msg["loss"] = False
            else:
                msg["loss"] = bool(step.metadata.get("loss", True))
        messages.append(msg)
    return messages
