"""Messages formatter: emits `{"messages": [...]}` (OpenAI chat-completion shape).

Only steps whose role the consumer cares about are kept. We preserve tool calls
and tool outputs as-is so tool-using benchmarks can use this formatter without
modification — for IF / single-turn tasks, these fields are simply absent.
"""

from __future__ import annotations

from ..framework.formatter import BaseFormatter
from ..framework.judge import JudgeResult
from ..framework.trajectory import Trajectory


class MessagesFormatter(BaseFormatter):
    def format(self, example: dict, trajectory: Trajectory,
               judge_result: JudgeResult) -> list[dict]:
        messages: list[dict] = []
        for step in trajectory.steps:
            if not step.content and not step.tool_calls:
                continue
            msg: dict = {"role": step.role, "content": step.content}
            if step.tool_calls:
                msg["tool_calls"] = step.tool_calls
            if step.tool_call_id is not None:
                msg["tool_call_id"] = step.tool_call_id
            if step.name is not None:
                msg["name"] = step.name
            messages.append(msg)
        # Drop records where the last assistant turn has no content
        last_assistant = next(
            (m for m in reversed(messages) if m["role"] == "assistant"), None
        )
        if not last_assistant or not last_assistant.get("content"):
            return []
        return [{"messages": messages}]
