# Automated SWE Bug Fixer — Design Documents

This folder contains the complete design specification for a multi-agent system that automatically fixes software bugs from the SWE-bench Lite dataset.

## Design Philosophy

- **Learn by building:** Minimize heavy abstractions; prefer standard library and explicit code.
- **Extensible first:** Every component is designed to be replaced or augmented.
- **Cost-aware:** Multi-model LLM routing from day one, even if all models run on Ollama locally.
- **Persistent memory:** The system improves over time by storing every outcome.

## Document Index

| # | Document | Description |
|---|----------|-------------|
| 1 | [01_architecture_overview.md](01_architecture_overview.md) | High-level system architecture + service mode + HITL note |
| 2 | [02_agent_orchestration.md](02_agent_orchestration.md) | Master agent, dynamic orchestration, lifecycle, HITL, service mode |
| 3 | [03_communication_system.md](03_communication_system.md) | Message bus, agent contracts, event types (+ HITL events) |
| 4 | [04_knowledge_base.md](04_knowledge_base.md) | Memory stores: SQL, vector DB, file cache + code understanding strategy |
| 5 | [05_llm_integration.md](05_llm_integration.md) | Model routing, cost tracking, prompt management |
| 6 | [06_agent_specifications.md](06_agent_specifications.md) | Detailed specs for all 6 sub-agents (+ AST capability) |
| 7 | [07_data_models.md](07_data_models.md) | Core data models, schemas, contracts (+ HITL fields) |
| 8 | [08_build_plan.md](08_build_plan.md) | Incremental build plan, milestone by milestone (+ phase map, HITL, Retrieval in MVP, AST roadmap) |

## How to Read

Start with [01_architecture_overview.md](01_architecture_overview.md) for the big picture, then dive into specifics as needed. The [build plan](08_build_plan.md) is your roadmap for implementation.

## Glossary

| Term | Definition |
|------|------------|
| **Context (RunContext)** | The `RunContext` dataclass — shared metadata for a single bug-fix session |
| **Context (LLM)** | The token window available to the language model for a single request |
| **Context (Code)** | Source code snippets assembled and sent to the LLM as part of a prompt |
| **Directive** | A command message sent from the Master Agent to a sub-agent via the message bus |
| **Event** | A notification message published by any agent to the message bus |
| **Issue** | A SWE-bench Lite entry representing a real-world bug with a known fix |
| **Plan** | An ordered list of `PlanStep` objects created by the Master Agent to orchestrate a bug-fix session |
| **Patch** | A git-format unified diff (`diff --git ...`) that fixes a bug |
| **Cost** | Relative "effort units" tracking LLM token usage — even for local models |
| **Agent** | A Python class implementing `BaseAgent` with an `execute()` method, receiving directives from the Master |
| **Master Agent** | The orchestrator — does NOT extend `BaseAgent`; drives the plan loop and dispatches work |
| **Tier** | LLM model category: `lite` (fast/cheap), `medium` (balanced), `heavy` (best quality) |
| **HITL** | Human-in-the-Loop — a pause point where the system requests human approval before finalizing a fix |
| **KB** | Knowledge Base — the persistent memory layer (SQLite + FAISS + file cache) |

## Conventions

- **File paths**: Always relative to the repo root unless stated otherwise
- **Agent names**: Lowercase, single-word identifiers (e.g., `reproduction`, `fix`, `validation`)
- **Patches**: Stored as `diff --git` format strings; also saved to `cache/patches/` as files
- **Logging**: Python `logging` module with JSON-structured output for machine parsing
- **Python version**: 3.11+ (for `list[str]` syntax, `match` statements, `asyncio` improvements)
- **Canonical data models**: [07_data_models.md](07_data_models.md) is the single source of truth for all dataclass definitions