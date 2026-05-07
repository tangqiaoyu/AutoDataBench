"""Math judge using HuggingFace math-verify for answer verification."""

from __future__ import annotations

import re

from ..framework.judge import BaseJudge, JudgeResult
from ..framework.trajectory import Trajectory, final_assistant_text


def _patch_math_verify_timeout():
    """Replace math_verify's signal-based timeout with a no-op decorator.

    math_verify uses signal.SIGALRM which only works in the main thread.
    Since the pipeline runs judges in worker threads via asyncio.to_thread,
    we replace the timeout decorator with a pass-through.
    """
    import math_verify.utils as mv_utils

    def noop_timeout(timeout_seconds=10):
        def decorator(func):
            return func
        return decorator

    mv_utils.timeout = noop_timeout

    for mod_name in ("math_verify.parser", "math_verify.grader"):
        try:
            import importlib
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "timeout"):
                mod.timeout = noop_timeout
        except ImportError:
            pass


_patch_math_verify_timeout()


def _extract_boxed(text: str) -> str | None:
    """Extract content from the last \\boxed{...} in text, handling nested braces."""
    matches = list(re.finditer(r"\\boxed\s*\{", text))
    if not matches:
        return None
    start = matches[-1].end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    if depth == 0:
        return text[start : i - 1]
    return None


class MathVerifyJudge(BaseJudge):
    """Verifies math answers using math-verify's parse+verify pipeline.

    Expects:
      - example["answer"] or example["gt_ans"]: ground-truth answer string
      - trajectory's last assistant message: model response (should contain \\boxed{})
    """

    def __init__(self, answer_field: str = "answer") -> None:
        self.answer_field = answer_field

    def judge(self, example: dict, trajectory: Trajectory) -> JudgeResult:
        from math_verify import parse, verify

        response = final_assistant_text(trajectory)
        gold_str = example.get(self.answer_field) or example.get("gt_ans") or example.get("answer", "")

        detail: dict = {"type": "math_verify", "passed": False, "error": None}

        if not response or not response.strip():
            detail["error"] = "empty response"
            return JudgeResult(passed=False, details=[detail])

        try:
            gold_wrapped = f"\\boxed{{{gold_str}}}"
            gold_parsed = parse(gold_wrapped)
        except Exception as e:
            detail["error"] = f"failed to parse gold answer: {e}"
            return JudgeResult(passed=False, details=[detail])

        pred_boxed = _extract_boxed(response)
        if pred_boxed is not None:
            parse_target = f"\\boxed{{{pred_boxed}}}"
        else:
            parse_target = response

        try:
            pred_parsed = parse(parse_target)
        except Exception as e:
            detail["error"] = f"failed to parse prediction: {e}"
            return JudgeResult(passed=False, details=[detail])

        try:
            passed = verify(gold_parsed, pred_parsed)
        except Exception as e:
            detail["error"] = f"verify error: {e}"
            return JudgeResult(passed=False, details=[detail])

        detail["passed"] = bool(passed)
        detail["gold"] = gold_str
        detail["predicted"] = pred_boxed or "(no boxed found)"
        return JudgeResult(passed=bool(passed), details=[detail])
