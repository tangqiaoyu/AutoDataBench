# AutoDataBench

Open-source release of **AutoDataBench**, a benchmark for evaluating LLM agents on autonomously designing and executing synthetic-data-generation pipelines for a target capability.

The repo has two parts:

| Dir | Content |
|---|---|
| [`tasks/`](tasks/) | The five tasks the agent is given — one sandbox per target capability (instruction following, math, software engineering, deep web search, terminal). Each is a self-contained Docker environment with task instructions, seed data, and a verifier. |
| [`evaluation/`](evaluation/) | The downstream evaluation pipeline (rollout → judge → format → output). Used to score the data the agent produced against held-out benchmarks (math, IF, BrowseComp). SWE / terminal evaluation depends on heavy sandbox infra and is not included here. |

We use [Harbor](https://github.com/harbor-framework/harbor) as the agent framework — it provides the scaffolding (sandbox build, agent rollout, verifier, reward collection) for running the tasks.

See each subdirectory's `README.md` for details.
