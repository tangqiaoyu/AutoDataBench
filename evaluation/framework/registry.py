"""Benchmark registry — where each benchmark declares its composition.

A benchmark file (under `benchmarks/`) imports `register_benchmark` and calls
it at module-import time. `framework.run` imports `benchmarks.<name>` after
parsing `--benchmark` so only one registration fires per run.

Registration is kept to a plain dict keyed by name; no decorator magic.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Callable, Optional

from .config import DistillConfig
from .formatter import BaseFormatter
from .judge import BaseJudge, JudgeResult
from .rollout import BaseRollout


BuildFn = Callable[
    [argparse.Namespace, DistillConfig],
    tuple[BaseRollout, BaseJudge, BaseFormatter],
]
AddArgsFn = Callable[[argparse.ArgumentParser], None]
StatsFn = Callable[[list[JudgeResult]], dict]


@dataclass
class BenchmarkSpec:
    """One benchmark's composition declaration."""
    name: str
    build_fn: BuildFn
    add_args_fn: AddArgsFn = field(default=lambda p: None)
    stats_fn: Optional[StatsFn] = None           # optional benchmark-specific report stats
    default_conda_env: str = ""                  # empty = inherit current env


BENCHMARKS: dict[str, BenchmarkSpec] = {}


def register_benchmark(spec: BenchmarkSpec) -> None:
    if spec.name in BENCHMARKS:
        raise ValueError(f"Benchmark '{spec.name}' already registered")
    BENCHMARKS[spec.name] = spec


def get_benchmark(name: str) -> BenchmarkSpec:
    if name not in BENCHMARKS:
        raise KeyError(
            f"Benchmark '{name}' not registered. "
            f"Known: {sorted(BENCHMARKS)}"
        )
    return BENCHMARKS[name]
