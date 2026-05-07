"""Rebuild data.jsonl/parquet from an existing full_data.jsonl.

This is safe for completed rollout directories: it never calls rollout workers
and never clears full_data.jsonl, even if the saved args.json had
``force_rewrite=true``.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from argparse import Namespace
from pathlib import Path
from typing import Any

from .config import DistillConfig
from .pipeline import Pipeline
from .registry import get_benchmark
from .run import _build_config


def _parent_package() -> str:
    pkg = __package__ or ""
    return pkg.rsplit(".", 1)[0] if "." in pkg else pkg


def _import_benchmark(name: str) -> None:
    parent = _parent_package()
    dotted = f"{parent}.benchmarks.{name}" if parent else f"benchmarks.{name}"
    importlib.import_module(dotted)


def _load_saved_args(output_dir: Path) -> dict[str, Any]:
    args_path = output_dir / "args.json"
    if not args_path.exists():
        raise FileNotFoundError(f"args.json not found: {args_path}")
    with args_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _namespace_from_saved(saved: dict[str, Any]) -> Namespace:
    defaults = {
        "data_path": "",
        "target_count": 0,
        "target_num": 0,
        "mode": "distill",
        "rollout_n": 1,
        "keep_per_example": "all",
        "seed": 42,
        "concurrency": 1,
        "force_rewrite": False,
        "min_pass_rate": 0.0,
        "start": 0,
        "end": None,
        "model": "",
        "api_base": "",
        "api_key": "",
        "temperature": 1.0,
        "stream": False,
        "max_tokens": 8192,
        "thinking": False,
        "thinking_budget": None,
        "thinking_effort": "",
        "api_max_retries": 3,
        "debug": False,
    }
    defaults.update(saved)
    defaults["force_rewrite"] = False
    defaults["concurrency"] = 1
    return Namespace(**defaults)


def _count_detail_stats(detail_path: Path) -> tuple[int, int, int]:
    total = 0
    passed = 0
    attempted_hashes: set[str] = set()
    with detail_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            h = rec.get("example_hash")
            if h is not None:
                attempted_hashes.add(str(h))
            if rec.get("passed"):
                passed += 1
    return total, passed, len(attempted_hashes)


def _update_report(config: DistillConfig, kept_trajectories: int,
                   kept_rows: int) -> None:
    report_path = Path(config.report_path)
    if not report_path.exists():
        return
    try:
        with report_path.open("r", encoding="utf-8") as f:
            report = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    config_section = report.setdefault("config", {})
    config_section["target_count"] = config.target_count
    config_section["target_num"] = getattr(config, "target_num", 0)
    config_section["keep_per_example"] = config.keep_per_example
    config_section["seed"] = config.seed

    results = report.setdefault("results", {})
    results["kept_trajectories"] = kept_trajectories
    results["kept_rows"] = kept_rows

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def rebuild(output_dir: Path, target_num: int | None, target_count: int | None,
            seed: int | None, keep_per_example: str | None) -> dict[str, int]:
    saved = _load_saved_args(output_dir)
    saved["output_dir"] = str(output_dir)
    if target_num is not None:
        saved["target_num"] = target_num
    if target_count is not None:
        saved["target_count"] = target_count
    if seed is not None:
        saved["seed"] = seed
    if keep_per_example is not None:
        saved["keep_per_example"] = keep_per_example

    args = _namespace_from_saved(saved)
    benchmark = args.benchmark
    _import_benchmark(benchmark)
    spec = get_benchmark(benchmark)
    config: DistillConfig = _build_config(args)

    detail_path = Path(config.detail_path)
    if not detail_path.exists():
        raise FileNotFoundError(f"full_data.jsonl not found: {detail_path}")

    _, judge, formatter = spec.build_fn(args, config)
    pipeline = Pipeline(config, rollout=None, judge=judge, formatter=formatter, spec=spec)  # type: ignore[arg-type]

    total_rollouts, total_passed, attempted = _count_detail_stats(detail_path)
    kept_trajectories, kept_rows = pipeline._build_data_jsonl()
    pipeline._write_parquet()
    _update_report(config, kept_trajectories, kept_rows)

    summary = {
        "detail_rollouts": total_rollouts,
        "detail_passed": total_passed,
        "detail_attempted_examples": attempted,
        "kept_trajectories": kept_trajectories,
        "kept_rows": kept_rows,
    }
    print(
        f"Rebuilt {config.output_path}: {kept_trajectories} trajectories / "
        f"{kept_rows} rows from {total_passed}/{total_rollouts} passed rollouts."
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild data.jsonl/parquet from an existing full_data.jsonl"
    )
    parser.add_argument("output_dirs", nargs="+", help="Completed output directories")
    parser.add_argument("--target_num", type=int, default=None,
                        help="Override saved target_num; sampling unit is trajectory")
    parser.add_argument("--target_count", type=int, default=None,
                        help="Override saved target_count; sampling unit is trajectory")
    parser.add_argument("--seed", type=int, default=None,
                        help="Override saved random seed")
    parser.add_argument("--keep_per_example", type=str, default=None,
                        help='Override saved keep_per_example: "all" or an int')
    args = parser.parse_args()

    for output_dir in args.output_dirs:
        rebuild(Path(output_dir), args.target_num, args.target_count,
                args.seed, args.keep_per_example)


if __name__ == "__main__":
    main()
