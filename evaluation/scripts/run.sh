#!/usr/bin/env bash
# ============================================================================
# run.sh — unified launcher
#
# All defaults live here; CLI args override any default.
# Per-benchmark wrappers (math500.sh, ifbench.sh, bc.sh, ...) call this script
# with extra args.
# ============================================================================

set -euo pipefail

# ============================================================================
# Defaults (overridable via env var or CLI arg)
# ============================================================================

# --- LLM ---
: "${MODEL:=aws.claude-sonnet-4-5-20250929}"                          # model name
: "${API_BASE:=http://llm-gateway.local:8080/v1}"                     # OpenAI-compatible endpoint (placeholder)
: "${API_KEY:?ERROR: API_KEY env var is required}"                    # API key (must be set in env)
: "${TEMPERATURE:=1.0}"                                                # sampling temperature
: "${STREAM:=true}"
: "${MAX_TOKENS:=8192}"
: "${THINKING:=false}"                                                 # enable thinking mode
: "${THINKING_BUDGET:=}"                                               # Qwen3/QwQ/QvQ thinking budget tokens
: "${THINKING_EFFORT:=}"                                               # OpenAI/Claude/Gemini reasoning effort: low/medium/high

# --- Judge LLM (optional, falls back to main model) ---
: "${JUDGE_MODEL:=qwen3.6-plus}"                                       # judge model name (empty = reuse --model)
: "${JUDGE_API_BASE:=http://llm-gateway.local:8080/v1}"                # judge endpoint (placeholder)
: "${JUDGE_API_KEY:=${API_KEY}}"                                       # judge API key (defaults to API_KEY)

# --- Run control ---
: "${MODE:=test}"            # test = run rollout_n times per example; distill = stop at first correct
: "${ROLLOUT_N:=1}"          # max rollouts per example
: "${CONCURRENCY:=20}"       # async worker count

# ============================================================================
# Argument list (full reference — forwarded to Python argparse)
# ============================================================================
#
#   Required:
#     --benchmark NAME         benchmark name (math, instruction_following, ...)
#     --submission_dir PATH    submission dir (contains generated_data.jsonl, or use --data_path)
#
#   Data:
#     --data_path PATH         explicit data file (overrides submission_dir lookup)
#     --output_dir PATH        output dir (default: ./output)
#     --start N                start index, 0-based (default: 0)
#     --end N                  end index, exclusive (default: full)
#
#   Run mode:
#     --mode {test,distill}    test = run all rollout_n; distill = stop on first correct (default: test)
#     --rollout_n N            max rollouts per example (default: 1)
#     --keep_per_example K     how many passing trajectories to keep per example: "all" or int (default: 1)
#     --target_count N         total cap on data.jsonl rows; 0 = unlimited (default: 0)
#     --target_num N           (distill) random subsample of N from passing trajectories; 0 = no subsample (default: 0)
#     --concurrency N          async worker count (default: 20)
#     --seed N                 random seed (default: 42)
#     --force_rewrite          wipe output_dir and rerun
#     --min_pass_rate F        early-terminate if pass rate falls below this (default: 0.0 = never)
#
#   LLM:
#     --model NAME             model name
#     --api_base URL           OpenAI-compatible endpoint
#     --api_key KEY            API key
#     --temperature F          sampling temperature (default: 1.0)
#     --max_tokens N           per-response max tokens (default: 8192)
#     --thinking               enable thinking (flag; true requires --thinking_budget or --thinking_effort)
#     --thinking_budget N      thinking budget tokens (Qwen3/QwQ/QvQ)
#     --thinking_effort LEVEL  reasoning effort (OpenAI/Claude/Gemini): low/medium/high
#     --api_max_retries N      per-call retry count (default: 3)
#     --debug                  print LLM call logs
#
#   Judge LLM (optional separate endpoint/model):
#     --judge_model NAME       judge model name (env: JUDGE_MODEL); empty reuses --model
#     --judge_api_base URL     judge endpoint (env: JUDGE_API_BASE)
#     --judge_api_key KEY      judge API key (env: JUDGE_API_KEY; default: API_KEY)
#
#   run.sh-only (not forwarded):
#     --venv PATH              activate venv before running
#     --conda_env NAME         activate conda env before running
#
#   Benchmark-specific args vary by --benchmark; see --help.
#
# ============================================================================

# ============================================================================
# Parse run.sh-only args; forward everything else to Python.
# ============================================================================
CONDA_ENV=""
VENV=""
FORWARD=()

# --- data ---
BENCHMARK=""
SUBMISSION_DIR=""
DATA_PATH=""
OUTPUT_DIR="./output"
START="0"
END=""

# --- run control ---
KEEP_PER_EXAMPLE=1
TARGET_COUNT="0"
TARGET_NUM="0"
SEED="42"
FORCE_REWRITE=""
MIN_PASS_RATE="0.0"

# --- LLM ---
API_MAX_RETRIES="3"
DEBUG=""

# --- benchmark-specific (math / instruction_following) ---
SYSTEM_PROMPT=""
PROMPT_FIELD=""
ANSWER_FIELD=""

# --- benchmark-specific (instruction_following) ---
JUDGE_TYPE=""

# --- benchmark-specific (browse_comp) ---
MAX_ITERATIONS=""
THRESHOLD=""
TOOL_TIMEOUT=""
TOOL_CALL_PARSER=""
SEARCH_API_ENDPOINT=""
SEARCH_API_KEY=""
FETCH_API_ENDPOINT=""
FETCH_API_KEY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        # run.sh-only (not forwarded)
        --conda_env)    CONDA_ENV="$2";       shift 2 ;;
        --conda_env=*)  CONDA_ENV="${1#*=}";  shift   ;;
        --venv)         VENV="$2";            shift 2 ;;
        --venv=*)       VENV="${1#*=}";       shift   ;;
        --api_key)      API_KEY="$2";         shift 2 ;;  # not forwarded; Python reads API_KEY env var

        # LLM
        --model)            MODEL="$2";            FORWARD+=("$1" "$2"); shift 2 ;;
        --api_base)         API_BASE="$2";         FORWARD+=("$1" "$2"); shift 2 ;;
        --temperature)      TEMPERATURE="$2";      FORWARD+=("$1" "$2"); shift 2 ;;
        --stream)           STREAM="$2";           shift 2 ;;
        --max_tokens)       MAX_TOKENS="$2";       FORWARD+=("$1" "$2"); shift 2 ;;
        --thinking)         THINKING="true";       FORWARD+=("$1");      shift   ;;
        --thinking_budget)  THINKING_BUDGET="$2";  FORWARD+=("$1" "$2"); shift 2 ;;
        --thinking_effort)  THINKING_EFFORT="$2";  FORWARD+=("$1" "$2"); shift 2 ;;
        --api_max_retries)  API_MAX_RETRIES="$2";  FORWARD+=("$1" "$2"); shift 2 ;;
        --debug)            DEBUG="true";          FORWARD+=("$1");      shift   ;;

        # Judge LLM
        --judge_model)      JUDGE_MODEL="$2";      FORWARD+=("$1" "$2"); shift 2 ;;
        --judge_api_base)   JUDGE_API_BASE="$2";   FORWARD+=("$1" "$2"); shift 2 ;;
        --judge_api_key)    JUDGE_API_KEY="$2";    shift 2 ;;  # not forwarded; Python reads JUDGE_API_KEY env var

        # data
        --benchmark)      BENCHMARK="$2";      FORWARD+=("$1" "$2"); shift 2 ;;
        --submission_dir) SUBMISSION_DIR="$2";  FORWARD+=("$1" "$2"); shift 2 ;;
        --data_path)      DATA_PATH="$2";      FORWARD+=("$1" "$2"); shift 2 ;;
        --output_dir)     OUTPUT_DIR="$2";     shift 2 ;;  # appended to FORWARD after MODEL is resolved
        --start)          START="$2";          FORWARD+=("$1" "$2"); shift 2 ;;
        --end)            END="$2";            FORWARD+=("$1" "$2"); shift 2 ;;

        # run control
        --mode)              MODE="$2";              FORWARD+=("$1" "$2"); shift 2 ;;
        --rollout_n)         ROLLOUT_N="$2";         FORWARD+=("$1" "$2"); shift 2 ;;
        --keep_per_example)  KEEP_PER_EXAMPLE="$2";  FORWARD+=("$1" "$2"); shift 2 ;;
        --target_count)      TARGET_COUNT="$2";      FORWARD+=("$1" "$2"); shift 2 ;;
        --target_num)        TARGET_NUM="$2";        FORWARD+=("$1" "$2"); shift 2 ;;
        --concurrency)       CONCURRENCY="$2";       FORWARD+=("$1" "$2"); shift 2 ;;
        --seed)              SEED="$2";              FORWARD+=("$1" "$2"); shift 2 ;;
        --force_rewrite)     FORCE_REWRITE="true";   FORWARD+=("$1");      shift   ;;
        --min_pass_rate)     MIN_PASS_RATE="$2";     FORWARD+=("$1" "$2"); shift 2 ;;

        # benchmark-specific (math / instruction_following)
        --system_prompt)  SYSTEM_PROMPT="$2";  FORWARD+=("$1" "$2"); shift 2 ;;
        --prompt_field)   PROMPT_FIELD="$2";   FORWARD+=("$1" "$2"); shift 2 ;;
        --answer_field)   ANSWER_FIELD="$2";   FORWARD+=("$1" "$2"); shift 2 ;;
        --judge_type)     JUDGE_TYPE="$2";     FORWARD+=("$1" "$2"); shift 2 ;;

        # benchmark-specific (browse_comp)
        --max_iterations)       MAX_ITERATIONS="$2";       FORWARD+=("$1" "$2"); shift 2 ;;
        --threshold)            THRESHOLD="$2";            FORWARD+=("$1" "$2"); shift 2 ;;
        --tool_timeout)         TOOL_TIMEOUT="$2";         FORWARD+=("$1" "$2"); shift 2 ;;
        --tool_call_parser)     TOOL_CALL_PARSER="$2";     FORWARD+=("$1" "$2"); shift 2 ;;
        --search_api_endpoint)  SEARCH_API_ENDPOINT="$2";  FORWARD+=("$1" "$2"); shift 2 ;;
        --search_api_key)       SEARCH_API_KEY="$2";       FORWARD+=("$1" "$2"); shift 2 ;;
        --fetch_api_endpoint)   FETCH_API_ENDPOINT="$2";   FORWARD+=("$1" "$2"); shift 2 ;;
        --fetch_api_key)        FETCH_API_KEY="$2";        FORWARD+=("$1" "$2"); shift 2 ;;

        # forward unknown args verbatim
        *)  FORWARD+=("$1"); shift ;;
    esac
done

# Append model name to output_dir so concurrent runs of different models don't collide.
MODEL_SLUG="${MODEL//\//_}"
OUTPUT_DIR="${OUTPUT_DIR}/${MODEL_SLUG}"
FORWARD+=(--output_dir "${OUTPUT_DIR}")

# ============================================================================
# Activate environment if requested
# ============================================================================
if [[ -n "${CONDA_ENV}" ]]; then
    if ! command -v conda >/dev/null 2>&1; then
        echo "[run.sh] conda not on PATH but --conda_env=${CONDA_ENV} was given" >&2
        exit 1
    fi
    # shellcheck disable=SC1091
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "${CONDA_ENV}"
    echo "[run.sh] activated conda env: ${CONDA_ENV}"
fi

if [[ -n "${VENV}" ]]; then
    if [[ ! -f "${VENV}/bin/activate" ]]; then
        echo "[run.sh] venv not found at ${VENV}" >&2
        exit 1
    fi
    # shellcheck disable=SC1091
    source "${VENV}/bin/activate"
    echo "[run.sh] activated venv: ${VENV}"
fi

# ============================================================================
# Locate project & launch
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
PARENT_DIR="$(dirname "${PROJECT_DIR}")"
PROJECT_NAME="$(basename "${PROJECT_DIR}")"

export PYTHONPATH="${PARENT_DIR}:${PYTHONPATH:-}"

# ============================================================================
# Print resolved config
# ============================================================================
echo "============================================================"
echo " Run config"
echo "============================================================"
echo " Data:"
echo "   benchmark       = ${BENCHMARK}"
echo "   submission_dir  = ${SUBMISSION_DIR}"
echo "   data_path       = ${DATA_PATH:--(use submission_dir lookup)}"
echo "   output_dir      = ${OUTPUT_DIR}"
echo "   start           = ${START}"
echo "   end             = ${END:-all}"
echo " LLM:"
echo "   model           = ${MODEL}"
echo "   api_base        = ${API_BASE}"
echo "   api_key         = ****${API_KEY: -4}"
echo "   temperature     = ${TEMPERATURE}"
echo "   stream          = ${STREAM}"
echo "   max_tokens      = ${MAX_TOKENS}"
echo "   thinking        = ${THINKING}"
echo "   thinking_budget = ${THINKING_BUDGET:-(unset)}"
echo "   thinking_effort = ${THINKING_EFFORT:-(unset)}"
echo "   api_max_retries = ${API_MAX_RETRIES}"
echo "   debug           = ${DEBUG:-false}"
echo " Judge LLM:"
echo "   judge_model     = ${JUDGE_MODEL:-(reuse --model)}"
echo "   judge_api_base  = ${JUDGE_API_BASE}"
if [[ -n "${JUDGE_API_KEY}" ]]; then
echo "   judge_api_key   = ****${JUDGE_API_KEY: -4}"
else
echo "   judge_api_key   = (reuse --api_key)"
fi
echo " Run control:"
echo "   mode            = ${MODE}"
echo "   rollout_n       = ${ROLLOUT_N}"
echo "   keep_per_example= ${KEEP_PER_EXAMPLE}"
echo "   target_count    = ${TARGET_COUNT}"
echo "   target_num      = ${TARGET_NUM}"
echo "   concurrency     = ${CONCURRENCY}"
echo "   seed            = ${SEED}"
echo "   force_rewrite   = ${FORCE_REWRITE:-false}"
echo "   min_pass_rate   = ${MIN_PASS_RATE}"
echo " Environment:"
[[ -n "${VENV}" ]]      && echo "   venv            = ${VENV}"
[[ -n "${CONDA_ENV}" ]] && echo "   conda_env       = ${CONDA_ENV}"
# --- benchmark-specific args (only print when set) ---
_has_bench_args=""
[[ -n "${SYSTEM_PROMPT}" ]]        && echo "   system_prompt   = ${SYSTEM_PROMPT}" && _has_bench_args=1
[[ -n "${PROMPT_FIELD}" ]]         && echo "   prompt_field    = ${PROMPT_FIELD}" && _has_bench_args=1
[[ -n "${ANSWER_FIELD}" ]]         && echo "   answer_field    = ${ANSWER_FIELD}" && _has_bench_args=1
[[ -n "${JUDGE_TYPE}" ]]           && echo "   judge_type      = ${JUDGE_TYPE}" && _has_bench_args=1
[[ -n "${MAX_ITERATIONS}" ]]       && echo "   max_iterations  = ${MAX_ITERATIONS}" && _has_bench_args=1
[[ -n "${THRESHOLD}" ]]            && echo "   threshold       = ${THRESHOLD}" && _has_bench_args=1
[[ -n "${TOOL_TIMEOUT}" ]]         && echo "   tool_timeout    = ${TOOL_TIMEOUT}" && _has_bench_args=1
[[ -n "${TOOL_CALL_PARSER}" ]]     && echo "   tool_call_parser= ${TOOL_CALL_PARSER}" && _has_bench_args=1
[[ -n "${SEARCH_API_ENDPOINT}" ]]  && echo "   search_api_endpoint = ${SEARCH_API_ENDPOINT}" && _has_bench_args=1
[[ -n "${SEARCH_API_KEY}" ]]       && echo "   search_api_key  = ****${SEARCH_API_KEY: -4}" && _has_bench_args=1
[[ -n "${FETCH_API_ENDPOINT}" ]]   && echo "   fetch_api_endpoint  = ${FETCH_API_ENDPOINT}" && _has_bench_args=1
[[ -n "${FETCH_API_KEY}" ]]        && echo "   fetch_api_key   = ****${FETCH_API_KEY: -4}" && _has_bench_args=1
if [[ -z "${_has_bench_args}" ]]; then
echo " Benchmark-specific args: (none)"
fi
echo "============================================================"

# Inject defaults (prepended); CLI args appear later, so argparse last-wins.
DEFAULTS=(
    --model "${MODEL}"
    --api_base "${API_BASE}"
    --temperature "${TEMPERATURE}"
    --max_tokens "${MAX_TOKENS}"
    --concurrency "${CONCURRENCY}"
    --rollout_n "${ROLLOUT_N}"
    --mode "${MODE}"
)


if [[ "${STREAM}" == "true" || "${STREAM}" == "1" ]]; then
    DEFAULTS+=(--stream)
fi

# Thinking: --thinking is a flag; only prepend when true. Budget/effort prepended only when set.
if [[ "${THINKING}" == "true" || "${THINKING}" == "1" ]]; then
    DEFAULTS+=(--thinking)
fi
if [[ -n "${THINKING_BUDGET}" ]]; then
    DEFAULTS+=(--thinking_budget "${THINKING_BUDGET}")
fi
if [[ -n "${THINKING_EFFORT}" ]]; then
    DEFAULTS+=(--thinking_effort "${THINKING_EFFORT}")
fi


# Judge LLM env propagation: --judge_api_key isn't forwarded on the CLI to
# avoid leaking it through `ps`; export it so run.py's env-var default picks
# it up. Export the others too for symmetry.
export JUDGE_MODEL JUDGE_API_BASE JUDGE_API_KEY


python -m "${PROJECT_NAME}.framework.run" "${DEFAULTS[@]}" "${FORWARD[@]}"
