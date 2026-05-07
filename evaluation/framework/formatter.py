"""Output formatter — shapes a (kept) trajectory into the final training-data row.

Separated from Rollout because the same trajectory may be written in different
formats for different downstream consumers (plain messages, tool-call format,
function-calling schema, …). Formatters also have full access to the example
and judge result so they can add auxiliary fields.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .judge import JudgeResult
from .trajectory import Trajectory


class BaseFormatter(ABC):
    @abstractmethod
    def format(self, example: dict, trajectory: Trajectory,
               judge_result: JudgeResult) -> dict:
        """Return the dict to be written as one line of data.jsonl."""
