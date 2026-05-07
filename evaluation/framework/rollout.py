"""Rollout interface — turns an example into a Trajectory.

This is the only place that differs between "pure LLM" benchmarks and
benchmarks that drive external code. The framework does not know or care
which is which: a Rollout's job is just `example -> Trajectory`.

Shared capabilities (dynamic import of external code, timeouts, subprocess
helpers) live as plain functions in `framework.utils`, not as mixins or
base-class machinery.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from .config import DistillConfig
from .trajectory import Trajectory


class BaseRollout(ABC):
    """Abstract rollout. Subclasses implement at least `arollout`."""

    def setup(self, config: DistillConfig) -> None:
        """One-time initialisation (sys.path patching, loading fixtures,
        opening a sandbox). Default: no-op.
        """

    @abstractmethod
    async def arollout(self, example: dict) -> Trajectory:
        """Async rollout. Must be safe to call concurrently — any shared
        mutable state should be guarded by the implementation.
        """

    def rollout(self, example: dict) -> Trajectory:
        """Sync fallback. Runs `arollout` in a fresh event loop.

        Overridden by implementations that want a truly sync path.
        """
        return asyncio.run(self.arollout(example))
