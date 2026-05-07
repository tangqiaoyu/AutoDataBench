# Debugging Challenge: The Phantom Dependency Conflict

You are a senior developer at a data science startup. Your team has a Python project that passes all tests when run individually, but fails when the full test suite is executed with `pytest`. The failure appears to be related to version conflicts between two critical libraries: `transformers==4.40.0` and `datascience-utils==2.1.0`.

The project is located in `/app/project`. The structure is:
```
project/
├── main.py
├── requirements.txt
├── tests/
│   ├── test_transformers.py
│   ├── test_datascience.py
│   └── test_integration.py
└── environment.log (generated after test failures)
```

## The Problem
When you run individual tests:
- `pytest tests/test_transformers.py` → PASS
- `pytest tests/test_datascience.py` → PASS
- `pytest tests/test_integration.py` → PASS

But when you run the full suite:
- `pytest tests/` → FAIL (with cryptic error in `environment.log`)

The error message in `/app/project/environment.log` mentions:
```
AttributeError: 'SomeClass' object has no attribute 'new_feature'
ImportError: cannot import name 'optimized_loader' from 'datascience_utils'
```

## Your Investigation
You suspect a **version conflict** where:
1. Each test suite loads dependencies in a different order
2. The global Python environment gets into an inconsistent state
3. Different tests require incompatible versions of a shared transitive dependency

## Your Task

1. **Analyze the dependency conflict**
   - Examine `/app/project/requirements.txt` and identify all direct dependencies
   - Use `pipdeptree` or manual analysis to build a dependency graph
   - Identify which transitive dependency causes the version conflict

2. **Reproduce and diagnose the failure**
   - Run the failing test suite to see the error
   - Examine the test files to understand what each test expects
   - Create a minimal reproduction script that demonstrates the conflict

3. **Find a resolution**
   - Determine if there's a version of the conflicting package that satisfies all constraints
   - If no perfect solution exists, propose a workaround (environment isolation, mocking, etc.)
   - Document your findings with clear evidence

4. **Create the required outputs**
   - Save your analysis to `/app/output/analysis.txt`
   - Save a working `requirements_resolved.txt` to `/app/project/` with compatible versions
   - Create a script `/app/output/reproduce.py` that demonstrates the issue

## Expected Outputs

### 1. Analysis Report (`/app/output/analysis.txt`)
Format:
```
ROOT CAUSE:
[Explain the specific version conflict, naming the problematic package(s)]

DEPENDENCY GRAPH:
[Show the conflicting constraints in tree format]

COMPATIBLE VERSION FOUND:
[Yes/No] - [If yes, which version; if no, why not]

WORKAROUND:
[Describe your proposed solution]

EVIDENCE:
- Test that fails: [test name]
- Error: [exact error]
- Reproduction: [command to reproduce]
```

### 2. Resolved Requirements (`/app/project/requirements_resolved.txt`)
- A valid `requirements.txt` file with version constraints that allow ALL tests to pass
- Must include ALL original dependencies (no removals)
- Can modify version constraints to resolve conflicts

### 3. Reproduction Script (`/app/output/reproduce.py`)
- A standalone Python script that demonstrates the conflict
- Should run without pytest and show the error
- Should include comments explaining what's happening

## Constraints
- You CANNOT modify the test files (they must remain as-is)
- You CAN install additional packages for analysis
- The solution must work in the current Docker environment (Python 3.12)
- All three test files must pass when run together