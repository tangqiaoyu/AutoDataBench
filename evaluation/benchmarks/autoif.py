"""AutoIF benchmark: composition declaration.

Data schema (per line, produced by `format_data/autoif.py`):
    {
      "instruction": "<user prompt>",
      "eval_funcs":  ["def evaluate(response): ...", ...]
    }

Pipeline:
    prompt -> SingleTurnLLMRollout -> AutoIFJudge (exec+verify) -> MessagesFormatter
"""

from __future__ import annotations

import argparse
from collections import defaultdict

from ..formatters.messages import MessagesFormatter
from ..framework.config import DistillConfig
from ..framework.judge import JudgeResult
from ..framework.registry import BenchmarkSpec, register_benchmark
from ..judges.autoif import AutoIFJudge
from ..rollouts.single_turn_llm import SingleTurnLLMRollout


def _add_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prompt_field", type=str, default="instruction",
                        help="Which example field to use as the LLM prompt")
    parser.add_argument("--system_prompt", type=str, default="",
                        help="Optional system prompt prepended to every rollout")


def _build(args: argparse.Namespace, config: DistillConfig):
    rollout = SingleTurnLLMRollout(
        prompt_field=args.prompt_field,
        system_prompt=args.system_prompt,
    )
    judge = AutoIFJudge()
    judge.load(config)
    formatter = MessagesFormatter()
    return rollout, judge, formatter


def _stats(judge_results: list[JudgeResult]) -> dict:
    """Aggregate per-example pass rate + verifier error breakdown."""
    total = len(judge_results)
    passed = sum(1 for jr in judge_results if jr.passed)
    scores = [jr.score for jr in judge_results if jr.score is not None]

    error_types: dict[str, int] = defaultdict(int)
    total_verifier_calls = 0
    verifier_errors = 0
    for jr in judge_results:
        for d in jr.details:
            total_verifier_calls += 1
            err = d.get("error")
            if err:
                verifier_errors += 1
                error_types[str(err)[:80]] += 1

    return {
        "total_examples": total,
        "passed_examples": passed,
        "failed_examples": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "mean_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "verifier_calls": total_verifier_calls,
        "verifier_errors": verifier_errors,
        "top_errors": dict(sorted(error_types.items(),
                                  key=lambda x: -x[1])[:5]),
    }


register_benchmark(BenchmarkSpec(
    name="autoif",
    build_fn=_build,
    add_args_fn=_add_args,
    stats_fn=_stats,
))
