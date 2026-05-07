"""Instruction-Following judge: loads and calls the submission's constraint verifiers."""

from __future__ import annotations

import importlib.util
import os
import sys

from ..framework.config import DistillConfig
from ..framework.judge import BaseJudge, JudgeResult
from ..framework.trajectory import Trajectory, final_assistant_text
from ..framework.utils.timeout import TimeoutExpired, run_with_timeout

VERIFIER_TIMEOUT = 10  # seconds per verifier call


class IFJudge(BaseJudge):
    """Verifies `example["constraints"]` using the submission's
    `src/constraints/registry.get_constraint_verifier` factory."""

    def __init__(self) -> None:
        self._get_verifier = None

    def load(self, config: DistillConfig) -> None:
        submission_dir = os.path.abspath(config.submission_dir)
        registry_dir = os.path.join(submission_dir, "src", "constraints")
        registry_path = os.path.join(registry_dir, "registry.py")

        if not os.path.exists(registry_path):
            raise FileNotFoundError(f"registry.py not found at {registry_path}")

        src_dir = os.path.join(submission_dir, "src")
        if submission_dir not in sys.path:
            sys.path.insert(0, submission_dir)

        if "src" not in sys.modules:
            src_init = os.path.join(src_dir, "__init__.py")
            src_spec = importlib.util.spec_from_file_location(
                "src", src_init, submodule_search_locations=[src_dir])
            src_mod = importlib.util.module_from_spec(src_spec)
            sys.modules["src"] = src_mod
            if os.path.exists(src_init):
                src_spec.loader.exec_module(src_mod)

        if "src.constraints" not in sys.modules:
            constraints_init = os.path.join(registry_dir, "__init__.py")
            constraints_spec = importlib.util.spec_from_file_location(
                "src.constraints", constraints_init,
                submodule_search_locations=[registry_dir])
            constraints_mod = importlib.util.module_from_spec(constraints_spec)
            constraints_mod.__package__ = "src.constraints"
            sys.modules["src.constraints"] = constraints_mod
            if os.path.exists(constraints_init):
                constraints_spec.loader.exec_module(constraints_mod)

        spec = importlib.util.spec_from_file_location(
            "src.constraints.registry", registry_path)
        module = importlib.util.module_from_spec(spec)
        module.__package__ = "src.constraints"
        sys.modules["src.constraints.registry"] = module
        spec.loader.exec_module(module)

        if not hasattr(module, "get_constraint_verifier"):
            raise AttributeError(
                "registry.py must define get_constraint_verifier(constraint_type)")
        self._get_verifier = module.get_constraint_verifier

    def judge(self, example: dict, trajectory: Trajectory) -> JudgeResult:
        response = final_assistant_text(trajectory)
        criteria = example.get("constraints", [])
        details: list[dict] = []
        all_passed = True

        for criterion in criteria:
            ct = criterion.get("constraint_type", "unknown")
            params = criterion.get("params", {})
            detail = {"type": ct, "passed": False, "error": None}

            try:
                verifier_fn = self._get_verifier(ct)
            except Exception as e:
                detail["error"] = f"verifier not found: {e}"
                all_passed = False
                details.append(detail)
                continue

            try:
                result = run_with_timeout(
                    verifier_fn, VERIFIER_TIMEOUT, response, params)
                detail["passed"] = bool(result)
                if not result:
                    all_passed = False
            except TimeoutExpired:
                detail["error"] = "verifier timed out"
                all_passed = False
            except Exception as e:
                detail["error"] = str(e)
                all_passed = False

            details.append(detail)

        return JudgeResult(passed=all_passed, details=details)
