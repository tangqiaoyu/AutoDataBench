#!/usr/bin/env bash
# BrowseComp — example invocation.
#
# Requires env vars or CLI overrides for tool APIs:
#   SEARCH_API_ENDPOINT / --search_api_endpoint
#   SEARCH_API_KEY      / --search_api_key
#   FETCH_API_ENDPOINT  / --fetch_api_endpoint
#   FETCH_API_KEY       / --fetch_api_key
#
# Usage:
#   bash scripts/bc.sh                          # test mode (rollout_n=1)
#   bash scripts/bc.sh --rollout_n 4 --concurrency 4   # distill mode

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"

bash "${SCRIPT_DIR}/run.sh" \
    --benchmark browse_comp \
    --data_path "${PROJECT_DIR}/data/browse_comp.jsonl" \
    --submission_dir "${PROJECT_DIR}" \
    --output_dir "${PROJECT_DIR}/output/browse_comp" \
    --mode distill \
    --rollout_n 1 \
    --concurrency 20 \
    --end 5 \
    --max_iterations 50 \
    --threshold 50000 \
    --max_tokens 32768 \
    --model qwen36_27b \
    --thinking \
    --thinking_budget 4096 \
    "$@"

