# Tasks

Five tasks, one per subdirectory. Each asks the agent to generate synthetic training data targeting a specific capability:

| Dir | Target capability |
|---|---|
| `if/` | Verifiable instruction following |
| `math/` | Competition-level mathematical reasoning |
| `swe/` | Repository-level software engineering |
| `deep_search/` | Deep web information retrieval |
| `terminal/` | Autonomous terminal task completion |

## Layout

```
<task>/
├── task.toml          # resource limits + timeouts
├── instruction.md     # task description shown to the agent
├── environment/       # Dockerfile + interface specs + seed data
└── tests/test.sh      # verifier; writes reward to /logs/verifier/reward.txt
```

## Agent framework

We use [Harbor](https://github.com/harbor-framework/harbor) as the agent framework — it provides all the scaffolding needed to run these tasks out of the box.

`llm_api_doc.md` is the LLM gateway interface spec — the implementation module is **not** shipped; the harness injects a compatible client at run time, or the agent implements its own.
