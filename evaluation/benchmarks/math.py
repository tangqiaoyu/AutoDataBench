"""Math benchmark: composition declaration for math500 / gsm8k etc."""

from __future__ import annotations

import argparse
from collections import defaultdict

from ..formatters.messages import MessagesFormatter
from ..framework.config import DistillConfig
from ..framework.judge import JudgeResult
from ..framework.registry import BenchmarkSpec, register_benchmark
from ..judges.math_verify import MathVerifyJudge
from ..rollouts.single_turn_llm import SingleTurnLLMRollout


def _add_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--system_prompt", type=str, default="",
                        help="Optional system prompt prepended to every rollout")
    parser.add_argument("--prompt_field", type=str, default="problem",
                        help="Which example field to use as the LLM prompt")
    parser.add_argument("--answer_field", type=str, default="answer",
                        help="Which example field holds the ground-truth answer")


def _build(args: argparse.Namespace, config: DistillConfig):
    rollout = SingleTurnLLMRollout(
        prompt_field=args.prompt_field,
        system_prompt=args.system_prompt,
    )
    judge = MathVerifyJudge(answer_field=args.answer_field)
    judge.load(config)
    formatter = MessagesFormatter()
    return rollout, judge, formatter


def _stats(judge_results: list[JudgeResult]) -> dict:
    total = len(judge_results)
    passed = sum(1 for jr in judge_results if jr.passed)
    errors = 0
    error_types: dict[str, int] = defaultdict(int)
    for jr in judge_results:
        for d in jr.details:
            if d.get("error"):
                errors += 1
                error_types[d["error"][:80]] += 1

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": round(passed / total, 4) if total else 0.0,
        "parse_or_verify_errors": errors,
        "top_errors": dict(sorted(error_types.items(), key=lambda x: -x[1])[:5]),
    }


register_benchmark(BenchmarkSpec(
    name="math",
    build_fn=_build,
    add_args_fn=_add_args,
    stats_fn=_stats,
))
