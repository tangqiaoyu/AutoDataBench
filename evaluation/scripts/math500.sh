#!/usr/bin/env bash
# MATH-500 benchmark — example invocation.
#
# Usage:
#   bash scripts/math500.sh                 # test mode (first 10, rollout_n=1)
#   bash scripts/math500.sh --end 500       # full dataset
#   bash scripts/math500.sh --rollout_n 4   # distill mode (override any default)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"

bash "${SCRIPT_DIR}/run.sh" \
    --venv "${PROJECT_DIR}/.venv_math" \
    --benchmark math \
    --data_path "${PROJECT_DIR}/data/math500.jsonl" \
    --submission_dir "${PROJECT_DIR}" \
    --output_dir "${PROJECT_DIR}/output/math500" \
    --prompt_field problem \
    --answer_field answer \
    --rollout_n 1 \
    --concurrency 10 \
    --start 0 --end 10 \
    --model openai.gpt-5.4-2026-03-05 \
    "$@"
