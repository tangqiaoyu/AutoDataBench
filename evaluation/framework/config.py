"""Shared config dataclass for a distillation / test run.

All fields are required or have structural defaults only (empty string, None, 0).
Environment-specific defaults (model, api_base, api_key, …) live in run.sh.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Union


@dataclass
class DistillConfig:
    # --- identity ---
    benchmark: str

    # --- data ---
    submission_dir: str
    output_dir: str
    data_path: str = ""

    # --- loop control ---
    mode: str = "test"
    target_count: int = 0
    target_num: int = 0
    rollout_n: int = 1
    keep_per_example: Union[int, str] = "all"
    seed: int = 42
    concurrency: int = 20
    timeout:int = 600
    force_rewrite: bool = False
    min_pass_rate: float = 0.0
    start: int = 0
    end: int | None = None

    # --- LLM ---
    model: str = ""
    api_base: str = ""
    api_key: str = ""
    temperature: float = 1.0
    stream: bool = True
    max_tokens: int = 8192
    api_max_retries: int = 3
    thinking: bool = False
    thinking_budget: int | None = None
    thinking_effort: str = ""
    debug: bool = False

    # --- Judge LLM (optional separate endpoint/model from rollout) ---
    # When unset, the judge falls back to the rollout's model/api_base/api_key.
    judge_model: str = ""
    judge_api_base: str = ""
    judge_api_key: str = ""

    # --- derived paths ---
    @property
    def output_path(self) -> str:
        return os.path.join(self.output_dir, "data.jsonl")

    @property
    def detail_path(self) -> str:
        return os.path.join(self.output_dir, "full_data.jsonl")

    @property
    def report_path(self) -> str:
        return os.path.join(self.output_dir, "report.json")

    @property
    def args_path(self) -> str:
        return os.path.join(self.output_dir, "args.json")

    def normalized_keep(self) -> Union[int, str]:
        k = self.keep_per_example
        if isinstance(k, str):
            if k.lower() == "all":
                return "all"
            return int(k)
        return int(k)
