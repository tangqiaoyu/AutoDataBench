"""IFBench judge: uses IFEvalG checkers from open-instruct."""

from __future__ import annotations

import logging
import os
import sys

from ..framework.config import DistillConfig
from ..framework.judge import BaseJudge, JudgeResult
from ..framework.trajectory import Trajectory, final_assistant_text
from ..framework.utils.timeout import TimeoutExpired, run_with_timeout

# Quiet noisy langdetect / absl warnings (e.g. "No features in text")
logging.getLogger("absl").setLevel(logging.WARNING)

VERIFIER_TIMEOUT = 10


class IFBenchJudge(BaseJudge):
    """Wraps IFEvalG's `INSTRUCTION_DICT` registry."""

    def __init__(self) -> None:
        self._instruction_dict = None

    def load(self, config: DistillConfig) -> None:
        # IFEvalG/ lives under the submission directory; fall back to the
        # directory containing the data file if submission_dir doesn't have it.
        candidates = []
        if config.submission_dir:
            candidates.append(os.path.abspath(config.submission_dir))
        if config.data_path:
            candidates.append(os.path.dirname(os.path.abspath(config.data_path)))
        for data_dir in candidates:
            if os.path.isdir(os.path.join(data_dir, "IFEvalG")):
                if data_dir not in sys.path:
                    sys.path.insert(0, data_dir)
                break
        from IFEvalG.instructions_registry import INSTRUCTION_DICT
        self._instruction_dict = INSTRUCTION_DICT

    def _check_one(self, constraint_type: str, params: dict, response: str) -> bool:
        cls = self._instruction_dict[constraint_type]
        inst = cls(constraint_type)
        clean_params = {k: v for k, v in params.items() if v is not None}
        inst.build_description(**clean_params)
        return inst.check_following(response)

    def judge(self, example: dict, trajectory: Trajectory) -> JudgeResult:
        response = final_assistant_text(trajectory)
        criteria = example.get("constraints", [])
        details: list[dict] = []
        all_passed = True

        for criterion in criteria:
            ct = criterion.get("constraint_type", "unknown")
            params = criterion.get("params", {})
            detail = {"type": ct, "passed": False, "error": None}

            if ct not in self._instruction_dict:
                detail["error"] = f"unknown constraint type: {ct}"
                all_passed = False
                details.append(detail)
                continue

            try:
                result = run_with_timeout(
                    self._check_one, VERIFIER_TIMEOUT, ct, params, response)
                detail["passed"] = bool(result)
                if not result:
                    all_passed = False
            except TimeoutExpired:
                detail["error"] = "checker timed out"
                all_passed = False
            except Exception as e:
                detail["error"] = str(e)
                all_passed = False

            details.append(detail)

        return JudgeResult(passed=all_passed, details=details)
