# Dockerfile Authoring Contract for SWE Environments

This document defines what a `Dockerfile` + `test_cmd` pair under `submission/environments/<env_id>/` must satisfy so the downstream distill harness can run any `generated_data.jsonl` instance whose `env_id` points at it.

The contract replaces the earlier declarative `environment_specs.json` schema — under the new design, the agent is responsible for writing a Dockerfile that reaches a runnable state, not for populating a fixed set of fields and letting the harness generate the Dockerfile.

This pipeline targets **Python repositories with `pytest`-based test suites**. Other languages and test frameworks are out of scope.

## Invariants

One `<env_id>/` directory must produce exactly one Docker image shared by every `generated_data.jsonl` record whose `env_id` equals that directory name. All records sharing an `env_id` must be runnable from the same build — they differ only in `base_commit` / `test_patch` / the candidate patch applied at run time.

## What the Harness Does at Build Time

For each unique `env_id` in `generated_data.jsonl`:

```sh
docker build -t <env_id> submission/environments/<env_id>/
```

That is the only build-time action. The harness passes no build args. Network access inside the build is available — use it for `git clone`, `apt-get`, `pip install`, etc.

## What the Harness Does at Run Time

For each instance with that `env_id`, the harness launches the image roughly like:

```sh
docker run --rm <env_id> bash -c '
    cd /testbed                                 # (1) working dir
    git checkout <base_commit>                    # (2) pin the repo to the instance's commit
    echo "$TEST_PATCH"      | git apply -         # (3) apply the benchmark's test patch
    echo "$CANDIDATE_PATCH" | git apply -         # (4) apply the solver model's patch (skipped when measuring F2P baseline)
    $(cat /harness/test_cmd)                      # (5) run the suite and print parseable output
'
```

Run-time network access is not guaranteed; design the Dockerfile so that every dependency needed by `git checkout`, the test suite, and the Python runtime is baked into the image.

## Dockerfile Requirements

Required properties of the image produced by `docker build`:

1. **`/testbed` is the repository root.** The Dockerfile must `git clone https://github.com/<repo>.git /testbed` (or an equivalent that populates `/testbed` with a working git checkout). Downstream steps like `git checkout`, `git apply`, and `pytest` assume the cwd is a git repo rooted here.
2. **`git` must be on `PATH`** in the final image (needed for `git checkout` + `git apply` at run time). Most base images do not include it by default — install it explicitly.
3. **All Python runtime, system libraries, and project dependencies required for the test suite must be installed.** The image must be self-contained; run-time network may be absent.
4. **`bash` (or at minimum `sh` with `cat` and `cd`) must be available.** The harness's `docker run` wrapper uses POSIX shell primitives.
5. **Do not `git checkout <base_commit>` inside the Dockerfile.** Pin-commit selection is per-instance and done at run time. A fresh clone at the repo's default branch is the expected starting state.
6. **Do not depend on files outside the `<env_id>/` build context.** The harness passes only that directory as the build context. The `test_cmd` file in the same directory is read by the harness, not by the build.
7. **Image size should be reasonable.** `python:<ver>-slim` is preferred over the full-fat variant. Target ≤ 2 GB per image; larger images are allowed but slow the harness.

There are no mandatory `ENV`, `ENTRYPOINT`, or `CMD` directives. The harness overrides entrypoint via `docker run bash -c '...'`.

## `test_cmd` Requirements

`<env_id>/test_cmd` is a plain-text file (no shebang needed) whose content the harness substitutes into step (5) above.

The expected form is a `pytest` invocation. The canonical example:

```
pytest --no-header -rA --tb=no
```

Rules:

- **Output must be pytest-style line-parseable**, i.e. each test emits a line like `PASSED <test_id>` or `FAILED <test_id>` matching entries in `FAIL_TO_PASS` / `PASS_TO_PASS`. The `-rA` flag in pytest produces this format.
- **Exit code** can be anything — the harness uses the stdout parser, not the exit code, to determine per-test verdicts.
- **cwd** when `test_cmd` runs is `/testbed`.
- Project-specific pytest flags (markers, plugins, config files) are fine as long as the output remains pytest-parseable.

## Agent Freedoms

Within the contract above, the agent chooses everything else:

- Base image (`python:3.9-slim`, `python:3.11-slim`, `debian:bookworm-slim` + `apt install python3`, etc.)
- System package manager (apt, apk, etc.)
- Dependency-installation order and caching strategy (`COPY requirements.txt` before `COPY .` for pip-layer caching, etc.)
- Whether to `git clone` vs. `COPY .` (since the build context is `<env_id>/`, `git clone` is the natural choice for a self-contained image; `COPY` only works if the agent pre-populates `<env_id>/` with repo files)
- Extra helper scripts inside `<env_id>/` (invoked from the Dockerfile or from `test_cmd`)

## What to Put Where

| Concern | Belongs in |
|---|---|
| Cloning the repo | `Dockerfile` |
| Pinning the Python runtime version | `Dockerfile` (`FROM python:3.9-slim` etc.) |
| Installing apt / system packages | `Dockerfile` |
| Installing Python dependencies | `Dockerfile` |
| Editable-installing the project | `Dockerfile` (`RUN pip install -e .[all]` etc.) |
| Running the test suite | `test_cmd` |
| Test-suite arguments / reporter flags | `test_cmd` |
| Per-instance `base_commit`, `test_patch`, candidate patch | `generated_data.jsonl` + harness run-time (never baked into Dockerfile) |
| Per-instance `FAIL_TO_PASS` / `PASS_TO_PASS` identifiers | `generated_data.jsonl` (the harness parses `test_cmd` output against these) |

## Relationship to Legacy SWE-Bench-Style `install_spec`

Prior SWE-bench-family datasets (SWE-Gym, SWE-smith, SWE-rebench) describe environments via declarative fields (`install`, `pip_packages`, `test_cmd`, `python_version`, ...) and let a harness generate the Dockerfile. Under the new design, the agent converts those declarative fields into a concrete Dockerfile itself — this shifts the responsibility of "figure out how to make the environment work" from the harness to the agent. Existing declarative specs (e.g., a SWE-rebench row's `install_config` struct) can be used by the agent as an intermediate representation during generation, but the submission must emit Dockerfiles, not declarative specs.

See `design/swe/seed_environments/` for 6 worked examples, each derived from a real declarative spec or `install_config` row.
