"""Instruction-following benchmark: composition declaration."""

from __future__ import annotations

import argparse
from collections import defaultdict

from ..formatters.messages import MessagesFormatter
from ..framework.config import DistillConfig
from ..framework.judge import JudgeResult
from ..framework.registry import BenchmarkSpec, register_benchmark
from ..judges.if_multi_constraints import IFMultiConstraintsJudge
from ..judges.ifbench import IFBenchJudge
from ..judges.instruction_following import IFJudge
from ..judges.rlvr_ifeval import RLVRIFevalJudge
from ..rollouts.single_turn_llm import SingleTurnLLMRollout


def _add_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--judge_type",
                        choices=["default", "ifbench", "rlvr_ifeval",
                                 "if_multi_constraints"],
                        default="default",
                        help="'default' = IFEval verifiers (from submission_dir/src/constraints); "
                             "'ifbench' = IFEvalG checkers; "
                             "'rlvr_ifeval' = vendored open_instruct.if_functions; "
                             "'if_multi_constraints' = IFEvalG full registry for "
                             "IF_multi_constraints_upto5 training data")
    parser.add_argument("--system_prompt", type=str, default="",
                        help="Optional system prompt prepended to every rollout")
    parser.add_argument("--prompt_field", type=str, default="instruction",
                        help="Which example field to use as the LLM prompt")


def _build(args: argparse.Namespace, config: DistillConfig):
    rollout = SingleTurnLLMRollout(
        prompt_field=args.prompt_field,
        system_prompt=args.system_prompt,
    )
    if args.judge_type == "ifbench":
        judge = IFBenchJudge()
    elif args.judge_type == "rlvr_ifeval":
        judge = RLVRIFevalJudge()
    elif args.judge_type == "if_multi_constraints":
        judge = IFMultiConstraintsJudge()
    else:
        judge = IFJudge()
    judge.load(config)
    formatter = MessagesFormatter()
    return rollout, judge, formatter


def _stats(judge_results: list[JudgeResult]) -> dict:
    """Per-constraint-type pass-rate breakdown."""
    per_type: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "pass": 0, "fail": 0})
    for jr in judge_results:
        for detail in jr.details:
            ct = detail.get("type", "unknown")
            per_type[ct]["total"] += 1
            if detail.get("passed"):
                per_type[ct]["pass"] += 1
            else:
                per_type[ct]["fail"] += 1

    criteria_stats = {}
    for ct, s in sorted(per_type.items()):
        total = s["total"]
        criteria_stats[ct] = {
            "total": total,
            "pass": s["pass"],
            "fail": s["fail"],
            "pass_rate": round(s["pass"] / total, 3) if total > 0 else 0.0,
        }
    return {"criteria_stats": criteria_stats}


register_benchmark(BenchmarkSpec(
    name="instruction_following",
    build_fn=_build,
    add_args_fn=_add_args,
    stats_fn=_stats,
))
