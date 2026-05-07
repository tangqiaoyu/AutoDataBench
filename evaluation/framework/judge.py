"""Judge interface — scores a trajectory against its source example.

A Judge does not care how the trajectory was produced (LLM call, external
command, multi-turn tool use). It receives `(example, trajectory)` and returns
a `JudgeResult`.

`PassthroughJudge` covers the case where the Rollout itself already determined
the outcome (e.g. pytest exit code) and stashed it on `trajectory.prejudged`.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from .config import DistillConfig
from .trajectory import Trajectory


@dataclass
class JudgeResult:
    """Outcome of judging one trajectory.

    Attributes:
        passed: overall pass/fail.
        score: optional scalar for partial-credit / weighted aggregation.
        details: list of per-criterion dicts. Structure is benchmark-specific;
            the framework only aggregates `detail["type"]` / `detail["passed"]`
            for default per-type stats.
        metadata: free-form (timings, error traces, …).
    """
    passed: bool
    score: Optional[float] = None
    details: list[dict] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseJudge(ABC):
    """Abstract judge. Implementations must be idempotent and raise-free."""

    def load(self, config: DistillConfig) -> None:
        """One-time setup (load checkers, open databases, …). Default: no-op."""

    @abstractmethod
    def judge(self, example: dict, trajectory: Trajectory) -> JudgeResult:
        """Score `trajectory` against `example`. Must not raise on normal
        verification failure — catch verifier crashes and record them in
        `details` / `metadata`.
        """

    async def ajudge(self, example: dict, trajectory: Trajectory) -> JudgeResult:
        """Async wrapper. Default dispatches the sync `judge` to a thread."""
        return await asyncio.to_thread(self.judge, example, trajectory)


class PassthroughJudge(BaseJudge):
    """Use when the Rollout already produced a verdict.

    The Rollout attaches a JudgeResult to `trajectory.prejudged`; this judge
    just surfaces it. If missing, falls back to a failed result with an error
    note rather than raising.
    """

    def judge(self, example: dict, trajectory: Trajectory) -> JudgeResult:
        if trajectory.prejudged is not None:
            return trajectory.prejudged
        return JudgeResult(
            passed=False,
            details=[{"type": "passthrough", "passed": False,
                      "error": "rollout did not attach a prejudged result"}],
        )
