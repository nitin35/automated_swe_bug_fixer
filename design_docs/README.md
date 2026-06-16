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