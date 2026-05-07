"""IF_multi_constraints_upto5 judge.

Verifies IFEvalG-style constraint IDs (e.g. `change_case:english_capital`,
`keywords:existence`, `detectable_format:sentence_hyphens`) using the checker
classes shipped with the upstream dataset.

Two registries are merged so that any training row's constraint is covered:

  1. `external/IF_multi_constraints_upto5/instructions_registry.INSTRUCTION_DICT`
     — the 58 *new* OOD test constraints published alongside the dataset.
  2. `external/RLVR-IFeval/open_instruct/IFEvalG/instructions_registry
     .INSTRUCTION_DICT` — the full classic-IFEval + new-IFEvalG registry that
     actually validates the training rows' ground-truth instruction IDs.

The two dicts have disjoint keys, so the merge is unambiguous.
"""

from __future__ import annotations

import logging
import os
import sys

from ..framework.config import DistillConfig
from ..framework.judge import BaseJudge, JudgeResult
from ..framework.trajectory import Trajectory, final_assistant_text
from ..framework.utils.timeout import TimeoutExpired, run_with_timeout

logging.getLogger("absl").setLevel(logging.WARNING)

VERIFIER_TIMEOUT = 10


def _add_path(path: str) -> None:
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)


class IFMultiConstraintsJudge(BaseJudge):
    """Dispatches each constraint to its IFEvalG checker class."""

    def __init__(self) -> None:
        self._registry: dict = {}

    def load(self, config: DistillConfig) -> None:
        framework_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # The shipped IF_multi_constraints_upto5 code uses top-level
        # `import instructions` — put its dir on sys.path first.
        shipped_dir = os.path.join(
            framework_dir, "external", "IF_multi_constraints_upto5")
        _add_path(shipped_dir)

        # The full IFEvalG registry (classic + new) lives inside RLVR-IFeval.
        rlvr_dir = os.path.join(framework_dir, "external", "RLVR-IFeval")
        _add_path(rlvr_dir)

        registry: dict = {}

        # Shipped OOD-only registry (58 entries).
        try:
            import importlib
            if "instructions_registry" in sys.modules:
                del sys.modules["instructions_registry"]
            if "instructions" in sys.modules:
                del sys.modules["instructions"]
            shipped_mod = importlib.import_module("instructions_registry")
            registry.update(shipped_mod.INSTRUCTION_DICT)
        except Exception as e:
            if config.debug:
                print(f"[if_multi_constraints] shipped registry unavailable: {e}")

        # Full classic + new IFEvalG registry from open-instruct.
        from open_instruct.IFEvalG.instructions_registry import (
            INSTRUCTION_DICT as FULL_DICT,
        )
        for k, v in FULL_DICT.items():
            registry.setdefault(k, v)

        self._registry = registry
        if config.debug:
            print(f"[if_multi_constraints] loaded {len(registry)} checkers")

    def _check_one(self, ct: str, params: dict, response: str) -> bool:
        cls = self._registry[ct]
        inst = cls(ct)
        clean = {k: v for k, v in params.items() if v is not None}
        inst.build_description(**clean)
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

            if ct not in self._registry:
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
                detail["error"] = f"{type(e).__name__}: {e}"
                all_passed = False

            details.append(detail)

        return JudgeResult(passed=all_passed, details=details)
