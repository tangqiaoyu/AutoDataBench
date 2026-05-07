# Task: Synthetic Data Generation for Verifiable Instruction Following


## 1. Objective

This is a research-oriented task. Your primary deliverable is a self-contained, reproducible data generation system.

Your goal is to produce training data that improves a language model's ability to precisely follow natural-language instructions that embed explicitly verifiable constraints — requirements whose satisfaction by a response can be assessed objectively.

Verifiable instruction following spans a wide range of constraint dimensions and complexity levels. A constraint may govern any attribute of a response that can be assessed without ambiguity. What makes this capability substantively challenging is not satisfying any single constraint in isolation, but producing responses that simultaneously satisfy multiple constraints while still fulfilling the substantive communicative goal of the instruction — especially when those constraints interact, conflict, or require precise compliance across the full response. The full space of constraint types, their combinations, their difficulty gradations, and the contexts in which they appear is large and open-ended.

A request like "Write a short paragraph about the ocean" imposes no verifiable constraints and exercises no constraint-following capability. A representative target is an instruction that simultaneously imposes several independent or interacting requirements on the response while also specifying a substantive communicative task.

Your system should produce data at scale, where each example consists of a query and a corresponding verification mechanism that can be used to objectively assess the quality of a model's response. In this task, each example consists of a natural-language instruction embedding verifiable constraints, along with a structured representation of those constraints and executable verification logic.


## 2. Evaluation Contract

### How Your Data Will Be Used

Your generated data will be consumed by a downstream pipeline that you do not control. The downstream pipeline will:

1. Execute your data generation system to produce 100,000 examples
2. Generate responses to your instructions using a language model
3. Use your verification mechanism to evaluate whether each response satisfies the constraints
4. Use the results to construct training signal for model training

Data quality is the primary objective. The value of your pipeline is determined by the correctness, diversity, and difficulty calibration of the examples it produces.

The accuracy of your verification mechanism is critical. If your verification produces incorrect judgments — accepting non-compliant responses or rejecting compliant ones — the downstream pipeline cannot construct reliable training signal. Some noise is acceptable when the task is inherently difficult, but you should maximize verification accuracy as much as possible.

Your data should fall within a productive difficulty range. The evaluation will test whether the trained model can handle instructions ranging from those whose constraints are straightforward to those where simultaneous satisfaction of all constraints is non-trivial. Instructions whose constraints are trivially satisfiable by any model provide no training signal, and instructions whose constraints cannot be satisfied by any model are equally useless.

At minimum, the generated data file and the constraint verifier registry implemented in `src/constraints/registry.py` will be consumed directly by the downstream pipeline to construct training signal.

### Evaluation

The primary in-domain evaluation is IFEval. The IFEval paper is provided at `/home/agent/resources/ifeval_paper.pdf`. This benchmark revealed that current models struggle with reliably following verifiable constraints embedded in instructions. Your task is to improve this capability — not to reverse-engineer or overfit to this benchmark's specific design choices.

The evaluation will also test whether the trained model can handle constraint types, complexity levels, and instruction structures that go beyond what the in-domain benchmark covers.

The majority of your data should cover difficulty levels comparable to the target benchmark, with some examples extending slightly easier or harder to ensure coverage across the capability spectrum.


## 3. Output Specification

### 3.1 Pipeline Repository

Your primary deliverable is a self-contained pipeline repository under `/home/agent/submission/`. The repository must include:

```
/home/agent/submission/
├── run_pipeline.sh
├── pipeline_description.md
├── src/
│   └── constraints/
│       └── registry.py       # Required: constraint verifier registry
└── (any other files your pipeline needs)
```

### 3.2 Entry-Point Script

`run_pipeline.sh` is the single entry-point for your entire pipeline. It must:

1. Be executable via `bash run_pipeline.sh` from within the submission directory
2. Handle all dependency installation (pip install, etc.)
3. Accept the following required parameters:
   - `--output_dir <path>`: Directory where generated data will be written (default: `./output/`)
   - `--num_examples <int>`: Number of examples to generate (default: 10000)
   - `--default_model <name>`: The primary model used for generation (default: agent's choice, documented in `pipeline_description.md`)
   - `--max_concurrency <int>`: Maximum number of concurrent LLM API requests or parallel workers (default: agent's choice, documented in `pipeline_description.md`)
   - `--seed <int>`: Random seed (default: 42). The downstream pipeline runs your generator multiple times in parallel with **different seeds** and aggregates the outputs with cross-run de-duplication. Therefore: (a) different seeds should produce substantively **non-overlapping** example sets; (b) the pipeline must have enough internal randomness that this property holds across at least a few dozen distinct seeds.

4. Support resumption: if interrupted, re-running with the same `--output_dir` and `--num_examples` should continue generating new examples until the total number of emitted examples (lines in `generated_data.jsonl`) reaches the target count. The pipeline must not overwrite or duplicate previously emitted examples. Intermediate work (e.g., candidate examples that were filtered out) need not be persisted.
5. Run to completion and produce the output data file at `<output_dir>/generated_data.jsonl`

You may define additional parameters as needed. Document all custom parameters in your `pipeline_description.md`.

Your pipeline will be executed from a clean state on a fresh machine. Do not rely on any files or state outside your submission directory.

### 3.3 Output Data Format

Each line of `generated_data.jsonl` must be a valid JSON object with the following required fields:

- `instruction` (string): A natural-language instruction containing one or more verifiable constraints.
- `constraints` (array): A list of constraint objects. Each constraint object contains:
  - `constraint_id` (string): An identifier that maps to a verifier registered in `src/constraints/registry.py`.
  - `kwargs` (object): Parameters passed to the verifier when evaluating a response against this constraint.

You may include additional fields beyond the required ones.

### 3.4 Constraint Verifier Registry

Your submission must include `src/constraints/registry.py`, which implements the following interface:

```python
def get_constraint_verifier(constraint_id: str) -> Callable[[str, dict], bool]:
    ...
```

Given a `constraint_id` string, this function returns a verifier callable. The returned callable accepts two arguments — `response: str` and `kwargs: dict` — and returns a boolean indicating whether the response satisfies the constraint under those parameters.

The downstream pipeline will invoke `get_constraint_verifier` to retrieve verifiers and apply them to model-generated responses. The interface must be implemented exactly as specified above.

### 3.5 Pipeline Description

`pipeline_description.md` should document your approach, design decisions, and known limitations.

### 3.6 Preparatory Assets

Your pipeline may include preparatory assets — resources that you build in advance to support data generation. These should be placed in `assets/` within your submission directory.

Preparatory assets are inputs to your pipeline, not outputs of it. Your pipeline's core data generation logic must be implemented in your code and executed by `run_pipeline.sh`.


## 4. Seed Data

Example data is provided at `/home/agent/resources/seed_data.jsonl`. These examples demonstrate the required output format and a small number of content patterns. Your pipeline should produce data that conforms to this format but is not limited to the patterns shown in these examples.

The seed examples represent a narrow slice of the verifiable constraint space. The full range of constraint types, their combinations, and the instruction contexts in which they appear extends well beyond what the seed examples demonstrate.


## 5. Rules

### External Resources

The prohibition in this task targets **pre-constructed training resources** — datasets and codebases that have already been synthesized or curated specifically to serve as training data for improving verifiable instruction following. Using these resources would replicate prior work rather than demonstrate autonomous pipeline design.

Raw human-generated text artifacts not specifically curated for verifiable instruction following are permitted as input material.

Specifically prohibited:

- Do not use any existing dataset that has been constructed or curated to serve as training data for verifiable instruction following.
- Do not use any existing codebase designed for generating such training data.
- Do not replicate methodologies from papers that specifically address training data construction for this capability.

You may use evaluation benchmark papers to understand the problem definition. However, any work that proposes solutions for improving model performance on this capability through data construction is off-limits.

All other resources are permitted, including datasets and tools from other domains, general-purpose resources, and standard open-source libraries. Resources in the same broad domain but serving a different purpose or targeting a lower difficulty level are also permitted.

Known examples of prohibited resources include: Conifer, AutoIF-instruct-61k, CRAB, and similar datasets or codebases constructed for verifiable instruction-following training.

This list is not exhaustive — the principle above applies to any resource fitting the criteria, whether listed here or not.

### Evaluation Integrity

- Do not download, access, or use the IFEval test set (the 541 evaluation prompts used for scoring).
- You may access and reference the target benchmark's evaluation infrastructure, including verification code, constraint definitions, evaluation scripts, environment setup, and data schemas.
- Reading the IFEval paper for reference is permitted.

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

A language model API is available for use within your pipeline code. API usage is not cost-constrained — use it as liberally as needed for generation, testing, verification, and filtering. See `/home/agent/resources/llm_api_doc.md` for usage documentation.

### Internet Access

You have internet access. You may use your agent environment's built-in tools (e.g., web search, browsing) during development.

Additionally, a programmatic web search and fetch API is provided for use within your pipeline code. See `/home/agent/resources/web_api_doc.md` for usage documentation.

### Provided Reference Materials

The following resources are available in `/home/agent/resources/`:

- `ifeval_paper.pdf` — The IFEval paper
- `llm_api.py` — Python wrapper for the LLM API
- `llm_api_doc.md` — LLM API usage documentation
- `web_api_doc.md` — Web search and fetch API usage documentation
- `seed_data.jsonl` — Example data demonstrating the required output format


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

During development, generate small test batches (e.g., 10–20 examples) to validate your pipeline. Inspect the outputs, identify issues, fix them, and re-run. Repeat this cycle multiple times — a pipeline that has gone through several rounds of inspection and refinement will produce substantially better data than one written and submitted without iteration.

### Testing with LLM Responses

Use the provided LLM API to generate actual responses to your test instructions, then run your verification mechanism against these responses. If multiple models are available, test with models of different capability levels — this helps calibrate difficulty across the spectrum and ensures your verification logic is robust to varying response quality. If every response passes or every response fails across all models, your instructions may be too easy or too hard.

### Post-Processing and Filtering

When your pipeline produces data at scale, not every example will meet quality standards. Consider implementing filtering or post-processing stages that automatically remove or flag low-quality examples.

### Self-Validation

Before finalizing your submission, verify that your test outputs satisfy:

- **Format correctness**: each output conforms to the required schema and can be parsed by the downstream pipeline.
- **Verification accuracy**: your verification mechanism correctly accepts compliant responses and rejects non-compliant ones. Test with both positive and negative cases.
- **Diversity**: outputs are meaningfully different from each other. If you generated 20 test examples, do they cover different patterns, or are they minor variations of the same template?
- **Naturalness**: instructions read as coherent, realistic requests — not as mechanical concatenations of constraint specifications.
- **Verifier–data alignment**: every `constraint_id` appearing in your generated data has a corresponding entry in `src/constraints/registry.py`, and the `kwargs` fields match what the verifier expects.

### When to Stop

Once you are confident that your pipeline produces correct, diverse, and high-quality outputs on small test runs, stop. Commit your final code and documentation. Do not proceed to large-scale generation.
