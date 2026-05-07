"""RLVR-IFeval judge: uses IF_FUNCTIONS_MAP from the vendored open-instruct code."""

from __future__ import annotations

import os
import sys

from ..framework.config import DistillConfig
from ..framework.judge import BaseJudge, JudgeResult
from ..framework.trajectory import Trajectory, final_assistant_text
from ..framework.utils.timeout import TimeoutExpired, run_with_timeout

VERIFIER_TIMEOUT = 10


class RLVRIFevalJudge(BaseJudge):
    """Dispatches each constraint to open_instruct.if_functions.IF_FUNCTIONS_MAP."""

    def __init__(self) -> None:
        self._func_map = None

    def load(self, config: DistillConfig) -> None:
        # Locate the vendored RLVR-IFeval code under <project>/external/RLVR-IFeval.
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            os.path.join(project_dir, "external", "RLVR-IFeval"),
        ]
        if config.submission_dir:
            candidates.append(
                os.path.join(os.path.abspath(config.submission_dir),
                             "external", "RLVR-IFeval"))
        for root in candidates:
            if os.path.isfile(os.path.join(root, "open_instruct", "if_functions.py")):
                if root not in sys.path:
                    sys.path.insert(0, root)
                break
        else:
            raise FileNotFoundError(
                "RLVR-IFeval code not found. Expected "
                "<project>/external/RLVR-IFeval/open_instruct/if_functions.py")

        from open_instruct.if_functions import IF_FUNCTIONS_MAP
        self._func_map = IF_FUNCTIONS_MAP

    def _check_one(self, func_name: str, params: dict, response: str) -> bool:
        fn = self._func_map[func_name]
        clean = {k: v for k, v in params.items() if v is not None}
        result = fn(response, **clean)
        # A few functions return (bool, extra); most return bool.
        if isinstance(result, tuple):
            return bool(result[0])
        return bool(result)

    def judge(self, example: dict, trajectory: Trajectory) -> JudgeResult:
        response = final_assistant_text(trajectory)
        criteria = example.get("constraints", [])
        details: list[dict] = []
        all_passed = True

        for criterion in criteria:
            func_name = criterion.get("constraint_type", "unknown")
            params = criterion.get("params", {})
            detail = {"type": func_name, "passed": False, "error": None}

            if func_name not in self._func_map:
                detail["error"] = f"unknown func_name: {func_name}"
                all_passed = False
                details.append(detail)
                continue

            try:
                result = run_with_timeout(
                    self._check_one, VERIFIER_TIMEOUT, func_name, params, response)
                detail["passed"] = bool(result)
                if not result:
                    all_passed = False
            except TimeoutExpired:
                detail["error"] = "verifier timed out"
                all_passed = False
            except Exception as e:
                detail["error"] = f"{type(e).__name__}: {e}"
                all_passed = False

            details.append(detail)

        return JudgeResult(passed=all_passed, details=details)
