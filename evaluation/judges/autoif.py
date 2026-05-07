"""AutoIF judge: executes the `eval_funcs` shipped with each example.

The verification pattern is ported from AutoIF's original
``external/AutoIF/code/code/7_query_vertification.py``:

* each ``eval_func`` is a string of source code defining ``def evaluate(response)``;
* ``exec()`` it, pull the callable out of the local scope, call it on the
  model's response, coerce the result to ``int``;
* the response passes overall when the mean of the per-func results is
  ``> 0`` (i.e. at least one verifier returned a truthy value).

Deviations from the upstream script:

1. The original uses ``signal.SIGALRM`` for per-call timeout, which only works
   in the main thread. The pipeline runs judges in worker threads via
   :func:`asyncio.to_thread`, so we route through
   :func:`framework.utils.timeout.run_with_timeout` (ThreadPoolExecutor-based).
2. ``<think>...</think>`` reasoning blocks are stripped from the response
   before grading, via :func:`framework.trajectory.final_assistant_text`. The
   upstream was written before reasoning models were common; without
   stripping, keyword-based verifiers spuriously match on the chain-of-thought
   (e.g. "contains a personal anecdote" triggered by "I remember..." inside
   ``<think>``).
3. Verifier crashes are swallowed (same as upstream) but recorded in
   ``details`` so failures surface in the report. ``None`` returns and
   non-coercible results are skipped from the mean — same as upstream's
   ``try/except: continue`` around ``acc.append(int(res))``.
"""

from __future__ import annotations

from typing import Any, Callable

from ..framework.judge import BaseJudge, JudgeResult
from ..framework.trajectory import Trajectory, final_assistant_text
from ..framework.utils.timeout import TimeoutExpired, run_with_timeout

VERIFIER_TIMEOUT_S = 5.0


def _compile_eval_func(src: str) -> Callable[[str], Any]:
    """Exec ``src`` (which defines ``def evaluate(response):``) and return the
    callable. Raises if the source doesn't define ``evaluate``.
    """
    local_vars: dict = {}
    exec(src, globals(), local_vars)
    fn = local_vars.get("evaluate")
    if not callable(fn):
        raise ValueError("eval_func source does not define callable `evaluate`")
    return fn


class AutoIFJudge(BaseJudge):
    """Runs all ``eval_funcs`` from an AutoIF-style example against the
    assistant's final (post-``<think>``) text. Pass semantics: any verifier
    returns truthy ``→`` overall pass.
    """

    def judge(self, example: dict, trajectory: Trajectory) -> JudgeResult:
        response = final_assistant_text(trajectory)
        eval_funcs: list[str] = example.get("eval_funcs") or []

        details: list[dict] = []
        results: list[int] = []

        if not eval_funcs:
            return JudgeResult(
                passed=False,
                details=[{"type": "autoif", "passed": False,
                          "error": "example has no eval_funcs"}],
            )

        for i, src in enumerate(eval_funcs):
            detail: dict = {"type": "autoif", "index": i,
                            "passed": False, "error": None}
            try:
                fn = _compile_eval_func(src)
            except Exception as e:
                detail["error"] = f"compile error: {e}"
                details.append(detail)
                continue

            try:
                raw = run_with_timeout(fn, VERIFIER_TIMEOUT_S, response)
            except TimeoutExpired:
                detail["error"] = f"verifier timed out after {VERIFIER_TIMEOUT_S}s"
                details.append(detail)
                continue
            except Exception as e:
                detail["error"] = f"runtime error: {e!r}"
                details.append(detail)
                continue

            # Match upstream exactly: None → skip; int() failure → skip.
            if raw is None:
                detail["error"] = "verifier returned None"
                details.append(detail)
                continue
            try:
                coerced = int(raw)
            except Exception as e:
                detail["error"] = f"non-coercible result: {raw!r} ({e})"
                details.append(detail)
                continue

            detail["passed"] = bool(coerced)
            results.append(coerced)
            details.append(detail)

        score = sum(results) / len(results) if results else 0.0
        passed = score > 0

        return JudgeResult(passed=passed, score=score, details=details)
