"""CLI entry point for the generic distillation pipeline.

Usage:
    python -m distill.framework.run \\
        --benchmark instruction_following \\
        --submission_dir /path/to/submission \\
        --output_dir ./out \\
        --target_count 1000 --rollout_n 4 --concurrency 20

The benchmark name resolves to a module under `<top_package>.benchmarks.<name>`;
importing that module registers a `BenchmarkSpec` in `framework.registry`, which
is then used to add benchmark-specific args and build components.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os

from .config import DistillConfig
from .pipeline import Pipeline
from .registry import BENCHMARKS, get_benchmark


def _parent_package() -> str:
    """Return the top-level package name housing `framework/` and `benchmarks/`.

    `__package__` is e.g. `"distill.framework"` or `"distill_code.framework"`;
    we strip the last segment to get the parent.
    """
    pkg = __package__ or ""
    return pkg.rsplit(".", 1)[0] if "." in pkg else pkg


def _import_benchmark(name: str) -> None:
    """Import `<parent>.benchmarks.<name>`, or plain `benchmarks.<name>` if
    this module wasn't imported as part of a package.
    """
    parent = _parent_package()
    dotted = f"{parent}.benchmarks.{name}" if parent else f"benchmarks.{name}"
    importlib.import_module(dotted)


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--benchmark", type=str, required=True,
                        help="Benchmark name (matches a module under benchmarks/)")
    parser.add_argument("--submission_dir", type=str, required=True,
                        help="Path to submission directory (contains generated_data.jsonl)")
    parser.add_argument("--output_dir", type=str, default="./output",
                        help="Output directory")
    parser.add_argument("--data_path", type=str, default="",
                        help="Optional explicit data jsonl path (overrides submission_dir lookup)")

    parser.add_argument("--target_count", type=int, default=0,
                        help="Cap on kept trajectories. 0 = no cap.")
    parser.add_argument("--target_num", type=int, default=0,
                        help="(distill mode) After collecting all passing trajectories, "
                             "randomly sample this many trajectories before formatting. "
                             "0 = keep all. Uses --seed for reproducibility.")
    parser.add_argument("--mode", type=str, choices=["test", "distill"], default="test",
                        help="'test' = rollout all N per example; "
                             "'distill' = stop after first passing rollout per example")
    parser.add_argument("--rollout_n", type=int, default=1,
                        help="Trajectories to run per example (no early stop on pass)")
    parser.add_argument("--keep_per_example", type=str, default="all",
                        help='How many passing trajectories to keep per example: "all" or an int')
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--concurrency", type=int, default=20,
                        help="Async worker count. 0 uses the sync path.")
    parser.add_argument("--force_rewrite", action="store_true",
                        help="Clear output_dir before running")
    parser.add_argument("--min_pass_rate", type=float, default=0.0,
                        help="Early-stop if pass rate falls below this after 100 rollouts")
    parser.add_argument("--start", type=int, default=0,
                        help="Start index in data (0-indexed, applied before shuffle)")
    parser.add_argument("--end", type=int, default=None,
                        help="End index in data (exclusive, applied before shuffle)")

    parser.add_argument("--model", type=str, default="",
                        help="Model name (e.g. openai.gpt-5.4-2026-03-05)")
    parser.add_argument("--api_base", type=str, 
                        default=os.environ.get("API_BASE", ""),
                        help="API base URL")
    parser.add_argument("--api_key", type=str,
                        default=os.environ.get("API_KEY", ""),
                        help="API key (prefer env var API_KEY to avoid ps leaks)")
    parser.add_argument("--temperature", type=float, default=1.0,
                        help="Sampling temperature (default: 1.0)")
    parser.add_argument("--stream", action="store_true",
                        help="Sampling stream")
    parser.add_argument("--max_tokens", type=int, default=8192,
                        help="Max tokens per response (default: 8192)")
    parser.add_argument("--thinking", action="store_true",
                        help="Enable thinking/reasoning mode. Requires "
                             "--thinking_budget or --thinking_effort.")
    parser.add_argument("--thinking_budget", type=int, default=None,
                        help="Thinking token budget (Qwen3/QwQ/QvQ family)")
    parser.add_argument("--thinking_effort", type=str, default="",
                        choices=["", "low", "medium", "high"],
                        help="Thinking effort level (OpenAI reasoning / Claude / "
                             "Gemini). Empty = not set.")
    parser.add_argument("--api_max_retries", type=int, default=3,
                        help="Transient-error retries per LLM call (default: 3)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging for LLM calls")

    # Judge LLM: optional separate endpoint/model. When omitted, judge reuses
    # the rollout's model/api_base/api_key.
    parser.add_argument("--judge_model", type=str,
                        default=os.environ.get("JUDGE_MODEL", ""),
                        help="Judge model name (env: JUDGE_MODEL). Empty = use --model.")
    parser.add_argument("--judge_api_base", type=str,
                        default=os.environ.get("JUDGE_API_BASE", ""),
                        help="Judge API base URL (env: JUDGE_API_BASE). Empty = use --api_base.")
    parser.add_argument("--judge_api_key", type=str,
                        default=os.environ.get("JUDGE_API_KEY", ""),
                        help="Judge API key (env: JUDGE_API_KEY). Empty = use --api_key.")


def _build_config(args: argparse.Namespace) -> DistillConfig:
    keep = args.keep_per_example
    if keep != "all":
        try:
            keep = int(keep)
        except ValueError:
            raise SystemExit(f"--keep_per_example must be 'all' or an int, got {keep!r}")
    return DistillConfig(
        benchmark=args.benchmark,
        submission_dir=args.submission_dir,
        output_dir=args.output_dir,
        data_path=args.data_path,
        mode=args.mode,
        target_count=args.target_count,
        target_num=args.target_num,
        rollout_n=args.rollout_n,
        keep_per_example=keep,
        seed=args.seed,
        concurrency=args.concurrency,
        force_rewrite=args.force_rewrite,
        min_pass_rate=args.min_pass_rate,
        start=args.start,
        end=args.end,
        model=args.model,
        api_base=args.api_base,
        api_key=args.api_key,
        stream=args.stream,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        thinking=args.thinking,
        thinking_budget=args.thinking_budget,
        thinking_effort=args.thinking_effort,
        api_max_retries=args.api_max_retries,
        debug=args.debug,
        judge_model=args.judge_model,
        judge_api_base=args.judge_api_base,
        judge_api_key=args.judge_api_key,
    )


def main() -> None:
    # Pass 1: extract --benchmark so we know which module to import.
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--benchmark", type=str, required=True)
    pre_args, _ = pre.parse_known_args()
    _import_benchmark(pre_args.benchmark)
    spec = get_benchmark(pre_args.benchmark)

    # Pass 2: full parser with common + benchmark-specific args.
    parser = argparse.ArgumentParser(description="Distillation / test pipeline")
    _add_common_args(parser)
    spec.add_args_fn(parser)
    args = parser.parse_args()

    config = _build_config(args)

    # Persist the full args for reproducibility.
    os.makedirs(config.output_dir, exist_ok=True)
    with open(config.args_path, "w", encoding="utf-8") as f:
        json.dump(vars(args), f, indent=2, ensure_ascii=False)

    rollout, judge, formatter = spec.build_fn(args, config)
    pipeline = Pipeline(config, rollout, judge, formatter, spec=spec)

    report = asyncio.run(pipeline.arun(concurrency=max(1, config.concurrency)))

    kept_trajectories = report["results"].get("kept_trajectories", 0)
    kept_rows = report["results"]["kept_rows"]
    target = args.target_count
    target_num = getattr(args, "target_num", 0)
    suffix = ""
    if target_num > 0 and args.mode == "distill":
        suffix = f", target_num={target_num}"
    print(f"\nDone. Kept {kept_trajectories} trajectories / {kept_rows} rows "
          f"(target: {target or 'unlimited'}{suffix}). "
          f"pass@1={report['results']['pass_at_1']}, "
          f"pass@{config.rollout_n}={report['results'].get(f'pass_at_{config.rollout_n}')}")


if __name__ == "__main__":
    main()
