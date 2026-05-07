#!/usr/bin/env bash
# IFBench (Instruction Following) — example invocation.
#
# Usage:
#   bash scripts/ifbench.sh                 # test mode (rollout_n=1)
#   bash scripts/ifbench.sh --rollout_n 4   # distill mode (override any default)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"

bash "${SCRIPT_DIR}/run.sh" \
    --benchmark instruction_following \
    --judge_type ifbench \
    --data_path "${PROJECT_DIR}/data/IFBench.jsonl" \
    --submission_dir "${PROJECT_DIR}/data/IFBench" \
    --output_dir "${PROJECT_DIR}/output/ifbench" \
    --rollout_n 1 \
    --concurrency 10 \
    --model claude-sonnet-4-5-20250929 \
    "$@"
