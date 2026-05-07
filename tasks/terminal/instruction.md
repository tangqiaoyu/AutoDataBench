# Task: Synthetic Data Generation for Autonomous Terminal Task Completion


## 1. Objective

This is a research-oriented task. Your primary deliverable is a self-contained, reproducible data generation system.

Your goal is to produce training data that improves an autonomous agent's ability to complete realistic, end-to-end technical tasks in command-line terminal environments — where the agent interacts with a live shell inside a sandboxed container to accomplish a goal stated in natural language, with success determined by automated tests run against the final container state.

Terminal-based task completion draws on any technical domain where work is performed through a command-line interface. What makes this capability substantively challenging is not shell syntax or any single domain skill in isolation, but the combination of long-horizon planning (many tasks require dozens to hundreds of interdependent actions), error recovery (the agent must diagnose and repair unexpected failures without human intervention), state reasoning (the container's state evolves continuously as each command executes), and the absence of a fixed script (the agent must decide what to do based on what it observes at each step). The full space of terminal tasks, the environments they require, and the skill combinations they exercise is large and open-ended.

A request to `ls /tmp` or to print `Hello, World!` imposes no realistic technical demand and exercises no meaningful terminal-agent capability. A representative target is a task that requires the agent to navigate an existing container state, diagnose a non-obvious problem from evidence distributed across multiple files or processes, and apply a fix that drives the container to a verifiably correct final state — checked by a test suite that fails before the fix and passes after. Tasks of this shape can span from quick debugging sessions to multi-hour engineering projects, and the problem space extends well beyond this particular example.

Your system should produce data at scale, where each example consists of a query and a corresponding verification mechanism that can be used to objectively assess the quality of a model's response. In this task, each example is a self-contained task package — a natural-language instruction, a reproducible container environment where the agent will act, and an automated test suite that determines whether the final container state satisfies the task's completion criteria.


## 2. Evaluation Contract

### How Your Data Will Be Used

Your generated data will be consumed by a downstream pipeline that you do not control. The downstream pipeline will:

1. Execute your data generation system to produce 2,000 task packages
2. For each task package, build the container, launch a language-model-driven agent inside it with your instruction, and allow the agent to interact with the shell until it terminates or the timeout elapses
3. Execute your test suite against the final container state to determine whether the task was completed
4. Use the results to construct training signal for model training

Data quality is the primary objective. The value of your pipeline is determined by the correctness, diversity, and difficulty calibration of the examples it produces.

The accuracy of your verification mechanism is critical. If your test suite produces incorrect judgments — accepting incomplete work or rejecting correct solutions — the downstream pipeline cannot construct reliable training signal. Some noise is acceptable when the task is inherently difficult, but you should maximize verification accuracy as much as possible. Equally important: tasks must actually be solvable. A task whose tests cannot pass under any agent behavior provides no training signal.

Your data should fall within a productive difficulty range. Tasks whose completion can be achieved by any model through a single command provide no training signal; tasks whose completion is unreachable by any model are equally useless. The most valuable examples are challenging enough that models do not consistently succeed, yet tractable enough that a correct execution path exists and can be reached by a competent terminal agent.

Each task package in your submission's `tasks/` directory will be consumed directly by the downstream pipeline: `task.toml` supplies the runtime limits, `instruction.md` supplies the natural-language task description shown to the agent, `environment/Dockerfile` defines the initial container, and `tests/test.sh` together with `tests/test_outputs.py` define the verification that determines task success.

### Evaluation

The primary in-domain evaluation is Terminal-Bench 2.0. The Terminal-Bench paper is provided at `/home/agent/resources/terminal-bench_paper.pdf`. This benchmark revealed that current frontier models and agents resolve only a minority of realistic terminal tasks, with performance degrading sharply on long-horizon and expert-level problems. Your task is to improve this capability — not to reverse-engineer or overfit to this benchmark's specific design choices.

The evaluation will also test whether the trained agent can handle task horizons, technical domains, and environment complexities that go beyond what the in-domain benchmark covers.

The majority of your data should cover difficulty levels comparable to the target benchmark, with some examples extending slightly easier or harder to ensure coverage across the capability spectrum.


## 3. Output Specification

### 3.1 Pipeline Repository

Your primary deliverable is a self-contained pipeline repository under `/home/agent/submission/`. The repository must include:

```
/home/agent/submission/
├── run_pipeline.sh
├── pipeline_description.md
├── src/
├── tasks/                       # Required: one subdirectory per generated task
│   └── <task_id>/
│       ├── task.toml
│       ├── instruction.md
│       ├── environment/
│       │   └── Dockerfile
│       ├── tests/
│       │   ├── test.sh
│       │   └── test_outputs.py
│       └── solution/
│           └── solve.sh
└── (any other files your pipeline needs)
```

### 3.2 Entry-Point Script

`run_pipeline.sh` is the single entry-point for your entire pipeline. It must:

1. Be executable via `bash run_pipeline.sh` from within the submission directory
2. Handle all dependency installation (pip install, etc.)
3. Accept the following required parameters:
   - `--output_dir <path>`: Directory where generated tasks will be written (default: `./output/`)
   - `--num_examples <int>`: Number of task packages to generate (default: 5000)
   - `--default_model <name>`: The primary model used for generation (default: agent's choice, documented in `pipeline_description.md`)
   - `--max_concurrency <int>`: Maximum number of concurrent LLM API requests or parallel workers (default: agent's choice, documented in `pipeline_description.md`)
   - `--seed <int>`: Random seed (default: 42). The downstream pipeline runs your generator multiple times in parallel with **different seeds** and aggregates the outputs with cross-run de-duplication. Therefore: (a) different seeds should produce substantively **non-overlapping** example sets; (b) the pipeline must have enough internal randomness that this property holds across at least a few dozen distinct seeds.
4. Support resumption: if interrupted, re-running with the same `--output_dir` and `--num_examples` should continue generating new examples until the total number of emitted task packages reaches the target count. The pipeline must not overwrite or duplicate previously emitted task packages. Intermediate work (e.g., candidate examples that were filtered out) need not be persisted.
5. Run to completion and produce the output under `<output_dir>/tasks/`, containing one subdirectory per generated task package.

You may define additional parameters as needed. Document all custom parameters in your `pipeline_description.md`.

Your pipeline will be executed from a clean state on a fresh machine. Do not rely on any files or state outside your submission directory.

### 3.3 Output Data Format

Each generated task package is a subdirectory under `tasks/` and must follow the Harbor task format used by Terminal-Bench 2.0. The directory name is the task identifier (`task_id`), which must be unique within the submission and filesystem-safe (no slashes or whitespace). Each directory must contain the following files at the paths shown:

- `task.toml` — TOML metadata file. Must contain at minimum:
  - `[metadata] difficulty` (string): one of `easy`, `medium`, `hard`.
  - `[metadata] category` (string): a domain label.
  - `[verifier] timeout_sec` (float): maximum seconds the test suite may run.
  - `[agent] timeout_sec` (float): maximum seconds the agent may interact with the container.
  - The instruction text MUST NOT be embedded here; it lives in `instruction.md`.
- `instruction.md` — Markdown file with the natural-language task description shown to the agent. May span multiple paragraphs and include code blocks, file paths, and explicit success criteria.
- `environment/Dockerfile` — defines the initial container state the agent encounters. The build context is `environment/`, so any additional files referenced by `COPY` directives must live alongside the Dockerfile under `environment/`.
- `tests/test.sh` — the test entrypoint. The downstream pipeline invokes this after the agent terminates, with `$TEST_DIR` pointing to the mounted `tests/` directory. The script must install any test-specific dependencies inline, run `pytest $TEST_DIR/test_outputs.py`, and propagate the pytest exit code.
- `tests/test_outputs.py` — pytest module with one or more `test_*` functions, each asserting a property of the final container state. A task passes iff all test functions pass.
- `solution/solve.sh` — an oracle solution. When executed in the task container from a fresh state, it must drive the container to a state where `tests/test.sh` exits `0`. The downstream pipeline may use this to verify solvability; the agent under evaluation never sees it.

You may include additional files under `environment/` (data assets, reference binaries, configuration) and reference them from the `Dockerfile`.

### 3.4 Pipeline Description

`pipeline_description.md` should document your approach, design decisions, and known limitations.

### 3.5 Preparatory Assets

Your pipeline may include preparatory assets — resources that you build in advance to support data generation. These should be placed in `assets/` within your submission directory.

Preparatory assets are inputs to your pipeline, not outputs of it. Your pipeline's core data generation logic must be implemented in your code and executed by `run_pipeline.sh`.


## 4. Seed Data

Example task packages are provided under `/home/agent/resources/seed_tasks/`. These examples demonstrate the required per-task directory format and a small number of content patterns. Your pipeline should produce tasks that conform to this format but are not limited to the patterns shown.

The seed examples represent a narrow slice of the terminal-task space — a small set of categories, a limited range of environment complexities, primarily medium-difficulty tasks, and short-to-moderate task horizons. The full range of domains, container configurations, verification patterns, and difficulty levels that terminal-agent capability encompasses extends well beyond what the seed examples demonstrate.


## 5. Rules

### External Resources

The prohibition in this task targets **pre-constructed terminal-task corpora** — datasets and codebases that have already been synthesized or curated specifically to serve as training data for terminal agents, as well as released terminal-agent evaluation benchmarks. Using these resources would replicate prior work rather than demonstrate autonomous pipeline design.

**Raw human-generated sources are permitted.** Natural language content, open-source code repositories, documentation, issue trackers, tutorials, man pages, and similar primary sources that exist as unprocessed human artifacts may be used as raw input material. Constructing training data from such sources is a legitimate pipeline design choice.

Specifically prohibited:

- Do not use any existing dataset that has been constructed or curated to serve as training data for terminal-agent task completion.
- Do not use any existing codebase designed for generating such training data.
- Do not replicate methodologies from papers that specifically address training data construction for this capability.

You may use the Terminal-Bench paper (provided at `/home/agent/resources/terminal-bench_paper.pdf`) to understand the problem definition. However, any work that proposes solutions for improving model performance on this capability through data construction is off-limits.

All other resources are permitted, including datasets and tools from other domains, general-purpose resources, and standard open-source libraries. Resources in the same broad domain but serving a different purpose or targeting a lower difficulty level are also permitted.

Known examples of prohibited resources include:

- Terminal-Bench test sets — all versions (1.0, 2.0, the full original-tasks collection, any mirror) and any dataset derived from them
- Nemotron-Terminal-Corpus / Nemotron-Terminal-Synthetic-Tasks — existing terminal-task training data
- TerminalTraj and TerminalTraj-5k-instances — existing terminal-task training data with Docker environments

This list is not exhaustive — the principle above applies to any resource fitting the criteria, whether listed here or not.

### Evaluation Integrity

- Do not download or use the Terminal-Bench 2.0 task set (the 89 tasks used for scoring) or any other Terminal-Bench task collection, including `terminal-bench-core` v0.1.0, v0.1.1, the full `original-tasks/` directory, or any public mirror thereof.
- You may access and reference the target benchmark's evaluation infrastructure, including verification code, evaluation scripts, environment setup, and data schemas.
- Reading the Terminal-Bench paper for reference is permitted.
- You may use the Terminal-Bench harness code (the `terminal_bench/` Python package and `tb` CLI) to validate that your generated task packages conform to the expected format. You may not use it to download any Terminal-Bench task dataset.

### Pipeline Integrity

- Do not hardcode large quantities of pre-written task packages as output. Your system must contain programmatic generation logic.
- Do not implement your system as a thin wrapper around an external data generation service or existing dataset. The core generation logic must be your own.
- Do not train, fine-tune, or evaluate language models within your pipeline. Your task is to produce training data only; model training and evaluation are handled by the downstream pipeline.

### Execution

- Do not execute the full data generation run. Your deliverable is the pipeline code itself, not the generated data. The full-scale generation will be executed by the downstream pipeline. Small test batches for development and validation (as described in Section 7) are expected and do not violate this rule.


## 6. Available Resources

### Computing Environment

You have access to a sandboxed Linux computing environment (Ubuntu 24.04) with:
- Python 3.11+ with pip
- Standard command-line tools (bash, git, curl, wget, apt-get, etc.)
- Docker and Docker Compose (for building and testing the task environments you generate)
- CPU-only (tasks that exercise specialized hardware such as GPUs are valid, but your pipeline itself runs CPU-only)
- Persistent filesystem under your working directory `/home/agent/`

You may install additional packages using pip or apt-get. Your `run_pipeline.sh` must handle all dependency installation.

### LLM API

A language model API is available for use within your pipeline code. API usage is not cost-constrained — use it as liberally as needed for generation, testing, verification, and filtering. See `/home/agent/resources/llm_api_doc.md` for usage documentation.

### Internet Access

You have internet access. You may use your agent environment's built-in tools (e.g., web search, browsing) during development.

Additionally, a programmatic web search and fetch API is provided for use within your pipeline code. See `/home/agent/resources/web_api_doc.md` for usage documentation.

### Provided Reference Materials

The following resources are available in `/home/agent/resources/`:

- `terminal-bench_paper.pdf` — The Terminal-Bench paper
- `llm_api.py` — Python wrapper for the LLM API
- `llm_api_doc.md` — LLM API usage documentation
- `web_api_doc.md` — Web search and fetch API usage documentation
- `docker_api_doc.md` — Docker-in-Docker usage guide for this sandbox
- `seed_tasks/` — Directory of example task packages demonstrating the required output format


## 7. Development Guidelines

These are recommended practices, not hard rules.


### Leveraging External Grounding and Pipeline Diversity

Two simple pipeline architectures sit at opposite extremes, and **both produce weak data — neither should be treated as a target**:

- **Single-shot LLM generation.** One prompt asks a model to produce the entire example end-to-end. Outputs cluster tightly around the model's prior distribution regardless of how varied the surface looks, and any judgment signal the model emits about its own output is unreliable because the model is approximating rather than computing the property being checked. 
- **Pure rule/template generation.** A hand-written grammar slots values into fixed scaffolds. Outputs are mechanically consistent but feel synthetic and unnatural, and coverage is bounded by whatever the author thought to template. Diversity is illusory: surface randomization over a fixed schema is not real coverage.

The target is a **multi-stage pipeline that aggressively composes tools and external grounding** to produce data that is simultaneously realistic and correct. Treat every available tool as fair game and combine them freely: the LLM API, the web API, programmatic logic, and external corpora are all in scope, and any resource not explicitly prohibited in Section 5 can be used.

Productive directions include:

- **Grounding in real artifacts.** Use encyclopedic content, real-user query corpora, datasets curated for adjacent purposes, or live web pages as the substrate the pipeline builds on — rather than asking a model to invent substrate from its priors. Real artifacts carry distributional properties (topical breadth, stylistic variation, factual grounding) that LLM sampling alone cannot reproduce.
- **Downloading auxiliary data via the web API.** The web API is not just for search — your pipeline can also fetch existing corpora, lexicons, domain-specific lists, structured open data, reference material, or any other external resource it can transform into either the input or the ground-truth side of an example. Pulling in external data at pipeline runtime is a primary source of topical and structural coverage that internal generation cannot match.
- **Decomposing the pipeline so each stage uses the tool that fits it.** LLMs for natural language and open-ended judgment, code for deterministic computation, web retrieval for fresh or out-of-distribution material, hand-written rules where they are genuinely the right tool. A strong pipeline typically separates substrate selection, example composition, surface phrasing, ground-truth construction, and self-checking into distinct stages — not a single prompt that fuses all of them.
- **Closing the loop with executable checks.** Where the task allows, run candidate examples through automatic checks before emitting them — execute the ground-truth signal, use cross-model agreement, or apply other programmatic filters to remove examples that are wrong, ambiguous, or trivially solvable. Self-checking is what bridges "the LLM said this is correct" and "this is actually correct."

The throughline: pipelines that combine LLM calls, web retrieval, programmatic logic, and external corpora — and that check their own output before emitting it — reach data properties that no single component, no matter how cleverly prompted or templated, can produce on its own.

### Iterative Development

During development, generate small test batches (e.g., 5–10 task packages) to validate your pipeline. Inspect the outputs, identify issues, fix them, and re-run. Repeat this cycle multiple times — a pipeline that has gone through several rounds of inspection and refinement will produce substantially better data than one written and submitted without iteration.

### Testing with LLM Responses

Use the provided LLM API to run actual agent trajectories against your generated task packages, then check whether your test suite correctly accepts successful trajectories and rejects failed ones. If multiple models are available, test with models of different capability levels — this helps calibrate difficulty across the spectrum and ensures your verification logic is robust. If every agent trajectory passes or every trajectory fails across all models, your tasks may be too easy or too hard.

### Post-Processing and Filtering

When your pipeline produces data at scale, not every task package will meet quality standards. Consider implementing filtering or post-processing stages that automatically remove or flag low-quality task packages.

### Self-Validation

Before finalizing your submission, verify that your test outputs satisfy:

- **Format correctness**: each task package contains every required file at the specified path, and `task.toml` parses successfully with all required fields populated.
- **Build correctness**: every `environment/Dockerfile` builds successfully using only files inside its `environment/` directory.
- **Solvability**: running `solution/solve.sh` from a fresh container state drives it to a state where `tests/test.sh` exits `0`.
- **Specificity**: a trivial or no-op agent behavior — an empty command sequence, an agent that immediately exits — causes `tests/test.sh` to fail. Tasks that pass regardless of agent behavior carry no training signal.
- **Verification accuracy**: your test suite correctly accepts correct final states and rejects incorrect ones. Test with both positive (oracle) and negative (trivial) cases.
- **Diversity**: task packages are meaningfully different from each other. If you generated 10 test tasks, do they span different domains, environment configurations, and verification patterns, or are they minor variations of the same template?
- **Naturalness**: instructions read as coherent, realistic requests — not as mechanical concatenations of requirements.

### When to Stop

Once you are confident that your pipeline produces correct, diverse, and high-quality outputs on small test runs, stop. Commit your final code and documentation. Do not proceed to large-scale generation.
