# evaluation

Generic distillation / evaluation pipeline for the IF, math, and BrowseComp (deep-search) tasks. SWE and terminal are intentionally excluded — both depend on heavy sandbox / Docker-in-Docker infrastructure that doesn't translate cleanly to a public release.

The flow is **rollout → judge → format → output**: roll out a model on each example, judge whether the trajectory is correct, keep the passing ones, and emit a JSONL of (prompt, trajectory) pairs plus a pass@k report.

## Layout

```
evaluation/
├── framework/         # generic Pipeline; do not edit when adding a new benchmark
├── rollouts/          # how a single example becomes a Trajectory
│   ├── single_turn_llm.py     # one-shot prompt → answer (math, IF)
│   └── browse_comp.py         # multi-turn agent with web tools (BrowseComp)
├── judges/            # turn (example, trajectory) into pass / fail
│   ├── instruction_following.py / ifbench.py / if_multi_constraints.py / rlvr_ifeval.py
│   ├── math_verify.py
│   ├── autoif.py
│   └── browse_comp.py         # LLM-as-judge with exact-match fallback
├── formatters/        # serialize a passing Trajectory to a training-data row
├── benchmarks/        # one file per benchmark — wires Rollout + Judge + Formatter
├── tools/             # web_search / fetch helpers shared by agent rollouts
├── prompts/           # benchmark-specific system prompts
├── scripts/           # bash wrappers (run.sh + per-benchmark examples)
└── llm_api.py         # placeholder — see "LLM gateway" below
```

## Adding a benchmark

1. (If needed) write a `Rollout` and a `Judge` under `rollouts/` and `judges/`.
2. Add one file under `benchmarks/` that registers a `BenchmarkSpec` combining your Rollout + Judge + a Formatter from `formatters/`.
3. Optionally add a wrapper script under `scripts/`.

No subclassing of `Pipeline` is needed; the registry pattern keeps the framework code untouched.

## Running

```bash
# Math example
bash scripts/math500.sh --end 50

# Instruction-following (IFBench)
bash scripts/ifbench.sh

# BrowseComp (requires SEARCH/FETCH endpoints)
bash scripts/bc.sh
```

Each script delegates to `scripts/run.sh`, which is a thin argparse-forwarding launcher. See `scripts/run.sh` itself for the full list of overridable env vars and CLI flags.

## LLM gateway

`llm_api.py` shipped here is a **placeholder** that raises `NotImplementedError`. The pipeline expects a real `llm_call` / `allm_call` pair speaking to an OpenAI-compatible gateway. Two ways to wire it up:

1. **Replace** `llm_api.py` at the repo root with your own implementation, or
2. **Set** `DISTILL_LLM_API_DIR=/path/to/dir/containing/llm_api.py`.

The expected interface is documented in `tasks/<task>/environment/llm_api_doc.md` (in the sibling task release).

## Required environment

| Var | Purpose |
|---|---|
| `API_KEY` | LLM API key (required) |
| `API_BASE` | LLM endpoint (default: placeholder; override) |
| `JUDGE_API_BASE` / `JUDGE_API_KEY` / `JUDGE_MODEL` | Optional separate judge endpoint |
| `SEARCH_API_ENDPOINT` / `SEARCH_API_KEY` | Web search service (BrowseComp only) |
| `FETCH_API_ENDPOINT` / `FETCH_API_KEY` | Web fetch service (BrowseComp only) |
| `DISTILL_LLM_API_DIR` | Override location of `llm_api.py` |
