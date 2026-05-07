# Task: Synthetic Data Generation for Repository-Level Software Engineering


## 1. Objective

This is a research-oriented task. Your primary deliverable is a self-contained, reproducible data generation system.

Your goal is to produce training data that improves a language model's ability to autonomously resolve real-world software engineering tasks — navigating a code repository, understanding an issue or task description, and producing correct code changes that are verified by test execution.

Repository-level software engineering is challenging because it requires far more than generating correct code in isolation. Resolving an issue in a real codebase demands understanding project structure, tracing control flow and data dependencies across files, localizing the relevant code among potentially thousands of files, and producing precise edits that fix the target problem without breaking existing functionality. The space of possible tasks is vast — it encompasses any real-world software project, any type of code change, and any level of complexity.

A task like "fix a typo in a comment" requires no reasoning about code behavior and is far below the target difficulty. A representative target is a task where the issue description alone does not point directly to the affected code — resolving it requires understanding the project's architecture, tracing the reported behavior to its root cause across multiple files, and producing a patch that addresses the underlying problem while preserving all existing tests.

Your system should produce data at scale, where each example consists of a task situated in a real software repository, along with a verification mechanism based on test execution. In this task, each example consists of a repository snapshot at a specific state, a natural-language problem statement describing an issue or task, a reference solution as a code patch, and an executable test-based verification mechanism that determines whether a candidate solution correctly resolves the issue.


## 2. Evaluation Contract

### How Your Data Will Be Used

Your generated data will be consumed by a downstream pipeline that you do not control. The downstream pipeline will:

1. Execute your data generation system to produce 2,000 task instances along with their environment specifications
2. For each instance, use the environment specifications to deploy the repository at the specified state with dependencies installed
3. Present the problem statement to an agent (a language model with access to the repository environment), which will navigate the codebase and produce code modifications
4. Run the test suite to determine whether the agent's modifications resolve the issue — specifically, all `FAIL_TO_PASS` tests must pass and all `PASS_TO_PASS` tests must remain passing
5. Use the results to construct training signal for model training

At minimum, the generated data file and the environment specifications file will be consumed directly by the downstream pipeline's evaluation harness to deploy environments and evaluate agent solutions.

Data quality is the primary objective. The value of your pipeline is determined by the correctness, diversity, and difficulty calibration of the task instances it produces.

The reliability of your environment specifications is critical. If environments cannot be reliably deployed from your specifications, or if the test-based verification produces incorrect judgments, the downstream pipeline cannot construct reliable training signal.

The evaluation will test the trained model across a range of difficulty levels. Tasks that any model can resolve trivially provide no training signal, and tasks that no model can resolve are equally useless.

### Evaluation

The primary in-domain evaluation is SWE-bench Verified. The SWE-bench paper is provided at `/home/agent/resources/swebench_paper.pdf`. This benchmark revealed that current models struggle with autonomously resolving real-world software engineering tasks that require repository-level understanding and precise code modifications. Your task is to improve this capability — not to reverse-engineer or overfit to this benchmark's specific design choices.

The evaluation will also test whether the trained model can handle software engineering tasks across task types, repository scales, and complexity levels that go beyond what the in-domain benchmark covers.

The majority of your data should cover difficulty levels comparable to the target benchmark, with some examples extending slightly easier or harder to ensure coverage across the capability spectrum.


## 3. Output Specification

### 3.1 Pipeline Repository

Your primary deliverable is a self-contained pipeline repository under `/home/agent/submission/`. The repository must include:

```
/home/agent/submission/
├── run_pipeline.sh
├── pipeline_description.md
├── src/
├── environments/                # one subdirectory per unique env_id
│   └── <env_id>/
│       ├── Dockerfile
│       └── test_cmd
└── (any other files your pipeline needs)
```

### 3.2 Entry-Point Script

`run_pipeline.sh` is the single entry-point for your entire pipeline. It must:

1. Be executable via `bash run_pipeline.sh` from within the submission directory
2. Handle all dependency installation (pip install, etc.)
3. Accept the following required parameters:
   - `--output_dir <path>`: Directory where generated data will be written (default: `./output/`)
   - `--num_examples <int>`: Number of examples to generate (default: 5000)
   - `--default_model <name>`: The primary model used for generation (default: agent's choice, documented in `pipeline_description.md`)
   - `--max_concurrency <int>`: Maximum number of concurrent LLM API requests or parallel workers (default: agent's choice, documented in `pipeline_description.md`)
   - `--seed <int>`: Random seed (default: 42). The downstream pipeline runs your generator multiple times in parallel with **different seeds** and aggregates the outputs with cross-run de-duplication. Therefore: (a) different seeds should produce substantively **non-overlapping** example sets; (b) the pipeline must have enough internal randomness that this property holds across at least a few dozen distinct seeds.
4. Support resumption: if interrupted, re-running with the same `--output_dir` and `--num_examples` should continue generating new examples until the total number of emitted examples (lines in `generated_data.jsonl`) reaches the target count. The pipeline must not overwrite or duplicate previously emitted examples. Intermediate work (e.g., candidate examples that were filtered out) need not be persisted.
5. Run to completion and produce:
   - `<output_dir>/generated_data.jsonl` — the task instances
   - `<output_dir>/environments/<env_id>/Dockerfile` and `<output_dir>/environments/<env_id>/test_cmd` — one directory per unique `env_id` referenced in `generated_data.jsonl`

You may define additional parameters as needed. Document all custom parameters in your `pipeline_description.md`.

Your pipeline will be executed from a clean state on a fresh machine. Do not rely on any files or state outside your submission directory.

### 3.3 Output Data Format

Each line of `generated_data.jsonl` must be a valid JSON object with the following required fields:

- `instance_id` (string): A unique identifier for this task instance (e.g., `"owner__repo-12345"`).
- `env_id` (string): Identifier of the executable environment this instance runs in. Must match a directory name under `environments/`. All instances sharing the same `(repo, version)` pair must share one `env_id`. Recommended naming: `<repo_owner>__<repo_name>__<version>`.
- `repo` (string): The repository identifier in `owner/repo` format (e.g., `"astropy/astropy"`). The repository must be publicly accessible on GitHub.
- `version` (string): A version identifier for the project at this commit (e.g., `"4.3"`). Kept in the record for readability; the executable state is determined by `env_id`.
- `base_commit` (string): The commit hash at which the repository should be checked out to create the initial (pre-fix) state. This is the state the agent will work from.
- `problem_statement` (string): A natural-language description of the issue or task. This is the only information presented to the agent about what needs to be fixed or implemented.
- `test_patch` (string): A unified diff that adds or modifies test files, if additional tests beyond the repository's existing test suite are needed for verification. May be an empty string if the existing test suite is sufficient.
- `FAIL_TO_PASS` (array of strings): A JSON array of test identifiers that must fail on the `base_commit` state and pass after a correct solution is applied. There must be at least one.
- `PASS_TO_PASS` (array of strings): A JSON array of test identifiers that must pass both before and after a solution is applied. This verifies that the solution does not introduce regressions.

Optional fields (consumed downstream only if present):

- `patch` (string): A reference/gold solution as a unified diff that, when applied to the repository at `base_commit`, resolves the issue. **Not used for grading** — correctness is judged purely by `FAIL_TO_PASS` / `PASS_TO_PASS` outcomes — but may be retained for distillation supervision, trajectory bootstrapping, or quality auditing.
- `hints_text` (string): Issue-thread comments or discussion that preserve real-world context cues. May be empty.

You may include additional fields beyond those listed above.

### 3.4 Environments

For every unique `env_id` in `generated_data.jsonl`, produce a directory `environments/<env_id>/` containing two required files:

- `Dockerfile` — a standard Dockerfile that, when built with `docker build -t <env_id> environments/<env_id>/`, produces an image in which the repository is cloned into `/testbed` and all language runtimes, system libraries, and project dependencies needed to run the test suite for this `(repo, version)` are installed. Do **not** `git checkout <base_commit>` inside the Dockerfile — commit selection is per-instance and done at run time by the downstream harness.
- `test_cmd` — a plain-text file whose contents are a shell command that runs the project's test suite from `/testbed` and prints output that can be parsed into per-test PASS / FAIL verdicts. Example: `pytest --no-header -rA --tb=no`.

The downstream harness will, for each unique `env_id`, build the image once and then, per instance, launch it with `docker run`, `cd /testbed`, `git checkout <base_commit>`, apply `test_patch`, apply the candidate patch, and run `$(cat test_cmd)`. It parses stdout through a pytest-style `PASSED`/`FAILED` log parser to check every identifier in `FAIL_TO_PASS` and `PASS_TO_PASS`.

See `/home/agent/resources/environment_schema.md` for the full authoring contract and the exact run-time invocation.

You do not need to wire the harness itself — the harness handles building, running, patch application, and log parsing. Your responsibility is that the image builds successfully, the test suite runs under `test_cmd`, and the output format is recognizable.

### 3.5 Pipeline Description

`pipeline_description.md` should document your approach, design decisions, and known limitations.

### 3.6 Preparatory Assets

Your pipeline may include preparatory assets — resources that you build in advance to support data generation. These should be placed in `assets/` within your submission directory.

Preparatory assets are inputs to your pipeline, not outputs of it. Your pipeline's core data generation logic must be implemented in your code and executed by `run_pipeline.sh`.


## 4. Seed Data

Example data is provided at `/home/agent/resources/seed_data.jsonl` and `/home/agent/resources/seed_environments/` (one subdirectory per `env_id` referenced in the seed data, each containing a runnable `Dockerfile` and `test_cmd`). These examples demonstrate the required output format and one valid content pattern. Your pipeline should produce data that conforms to this format but is not limited to the patterns shown in these examples.

The seed examples are drawn from a small number of Python repositories. Focus on Python repositories with `pytest`-based test suites — your pipeline does not need to cover other programming languages or test frameworks. Your pipeline should still extend well beyond what the seed examples demonstrate in terms of project types, task complexity, and repository scale.


## 5. Rules

### External Resources

The prohibition in this task targets **pre-constructed training resources** — datasets and codebases that have already been synthesized or curated specifically to serve as training data for improving repository-level software engineering capability. Using these resources would replicate prior work rather than demonstrate autonomous pipeline design.

**Real-world software repositories are permitted.** Public repositories that exist as unprocessed human artifacts — open-source projects, libraries, frameworks, and applications — may be used as raw input material. These are the primary source from which software engineering tasks can be derived.

Specifically prohibited:

- Do not use any existing dataset that has been constructed or curated to serve as training data for repository-level software engineering.
- Do not use any existing codebase designed for generating such training data or for constructing SWE task environments at scale.
- Do not replicate methodologies from papers that specifically address training data construction for this capability.

You may use evaluation benchmark papers to understand the problem definition. However, any work that proposes solutions for improving model performance on this capability through data construction is off-limits.

All other resources are permitted, including datasets and tools from other domains, general-purpose resources, and standard open-source libraries. Resources in the same broad domain but serving a different purpose or targeting a lower difficulty level are also permitted.

Known examples of prohibited resources include: SWE-Gym, SWE-smith, SWE-rebench (V1 and V2), Multi-SWE-bench / Multi-SWE-RL, and similar datasets or codebases constructed for SWE training data.

This list is not exhaustive — the principle above applies to any resource fitting the criteria, whether listed here or not.

### Evaluation Integrity

- Do not download or use any SWE-bench test instances (the 500 Verified instances or the 300 Lite instances).
- You may access and reference the target benchmark's evaluation infrastructure, including verification code, evaluation scripts, environment setup, and data schemas.
- Reading the SWE-bench paper for reference is permitted.

### Pipeline Integrity

- Do not hardcode large quantities of pre-written examples as output. Your system must contain programmatic generation logic.
- Do not implement your system as a thin wrapper around an external data generation service or existing dataset. The core generation logic must be your own.
- Do not train, fine-tune, or evaluate language models within your pipeline. Your task is to produce training data only; model training and evaluation are handled by the downstream pipeline.

### Execution

- Do not execute the full data generation run. Your deliverable is the pipeline code itself, not the generated data. The full-scale generation will be executed by the downstream pipeline. Small test batches for development and validation (as described in Section 7) are expected and do not violate this rule.


## 6. Available Resources

### Computing Environment

You have access to a sandboxed Linux computing environment (Ubuntu 24.04) with:
- Python 3.11+ with pip
- Standard command-line tools (bash, git, curl, wget, apt-get, etc.)
- No GPU access (CPU-only)
- Persistent filesystem under your working directory `/home/agent/`

You may install additional packages using pip or apt-get. Your `run_pipeline.sh` must handle all dependency installation.

### LLM API

A language model API is available for use within your pipeline code. API usage is not cost-constrained — use it as liberally as needed across all stages of your pipeline. See `/home/agent/resources/llm_api_doc.md` for usage documentation.

### Internet Access

You have internet access. You may use your agent environment's built-in tools (e.g., web search, browsing) during development.

Additionally, a programmatic web search and fetch API is provided for use within your pipeline code. See `/home/agent/resources/web_api_doc.md` for usage documentation.

### Provided Reference Materials

The following resources are available in `/home/agent/resources/`:

- `swebench_paper.pdf` — The SWE-bench paper
- `environment_schema.md` — Dockerfile + `test_cmd` authoring contract (per-env_id directory requirements, harness run-time behavior)
- `llm_api.py` — Python wrapper for the LLM API
- `llm_api_doc.md` — LLM API usage documentation
- `web_api_doc.md` — Web search and fetch API usage documentation
- `docker_api_doc.md` — Docker-in-Docker usage guide for this sandbox
- `seed_data.jsonl` — Example task instances demonstrating the required output format
- `seed_environments/` — One subdirectory per `env_id` in `seed_data.jsonl`, each containing a runnable `Dockerfile` + `test_cmd`


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

During development, generate small test batches (e.g., 3–5 instances) to validate your pipeline. Because each instance involves a full repository environment, testing at even small scale is more resource-intensive than in other tasks. Inspect the outputs, verify that environments can be set up and tests can be run, then iterate.

### Testing with LLM Responses

Use the provided LLM API to simulate the downstream agent workflow: set up an environment from your generated instance, present the problem statement to the model, and let it attempt to produce a patch. Then verify the model's patch against the test suite. This end-to-end test is the strongest signal for data quality.

### Post-Processing and Filtering

When your pipeline produces data at scale, not every instance will meet quality standards. Consider implementing filtering or post-processing stages that automatically remove or flag low-quality instances.

### Self-Validation

Before finalizing your submission, verify that your test outputs satisfy:

- **Format correctness**: each output conforms to the required schema and can be parsed by the downstream pipeline.
- **Environment reliability**: the environment specifications allow the downstream harness to successfully deploy the environment for your test instances, install dependencies, and run the test suite.
- **Verification accuracy**: if a `patch` is provided with an instance, it should cause all `FAIL_TO_PASS` tests to pass while `PASS_TO_PASS` tests remain passing. A trivially wrong patch (e.g., empty patch) should not pass verification.
- **Diversity**: outputs are meaningfully different from each other — different repositories, different types of tasks, different levels of complexity.

### When to Stop

Once you are confident that your pipeline produces correct, diverse, and high-quality outputs on small test runs, stop. Commit your final code and documentation. Do not proceed to large-scale generation.
