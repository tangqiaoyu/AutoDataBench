"""Timeout helpers for Judge/Rollout implementations.

Use cases:
  - judge verifiers that may hang on adversarial input → `run_with_timeout`
  - async rollouts that must cap tool-call wall time → `await_with_timeout`
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any, Callable


class TimeoutExpired(Exception):
    """Raised when a wrapped call exceeds its budget."""


def run_with_timeout(fn: Callable[..., Any], timeout_s: float,
                     *args, **kwargs) -> Any:
    """Run a sync callable with a wall-clock cap.

    Uses a ThreadPoolExecutor (1 worker) so cancellation is best-effort — the
    underlying Python call may continue running after we return. Prefer this
    for short verifier calls, not for long-running subprocess work.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError as exc:
            raise TimeoutExpired(
                f"{fn.__name__} exceeded {timeout_s}s") from exc


async def await_with_timeout(coro, timeout_s: float):
    """Await `coro` with a wall-clock cap; raises TimeoutExpired on overrun."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except asyncio.TimeoutError as exc:
        raise TimeoutExpired(f"coroutine exceeded {timeout_s}s") from exc
