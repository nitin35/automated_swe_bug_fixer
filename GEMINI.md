# Developer & Agent Guidelines — Automated SWE Bug Fixer

This file defines the strict development process and constraints that all AI agents and developers working on this codebase must follow. It ensures the codebase is built incrementally, maintains high quality, adheres to the specifications in [design_docs](design_docs), and that every step is fully understood before moving forward.

---

## 🚀 Core Directives

1. **Step-by-Step Execution**: You must implement code incrementally. Do not skip milestones or combine tasks from different milestones into a single step.
2. **Deep Comprehension**: Before making or proposing a change, analyze the design docs, verify the existing files, and explain the code details in the chat or design notes. You must fully understand the code in details before moving to the next stage.
3. **No Placeholders**: Never write TODOs or placeholder code in core functionality unless explicitly outlined as an MVP stub in the design documents.
4. **Test-Driven Verification**: Every milestone contains success criteria. You must verify those criteria by implementing and running corresponding tests before proceeding to the subsequent milestone.
5. **Preserve Integrity**: Maintain all docstrings, existing logic, comments, and imports unless they are explicitly being refactored.

---

## 🗺️ Build Roadmap

Here is the sequential roadmap based on [08_build_plan.md](design_docs/08_build_plan.md). You must work on these one by one:

### [Milestone 0: Project Scaffold & Test Harness](design_docs/08_build_plan.md#L26)
- Create the target folder structure.
- Write configuration loading (`src/config.py` and `config.yaml`).
- Implement core data models (`src/models.py`) based on [07_data_models.md](design_docs/07_data_models.md).
- Setup the entry point (`src/main.py`) and initial tests.

### [Milestone 1: Message Bus + BaseAgent](design_docs/08_build_plan.md#L162)
- Implement communication bus (`src/bus.py`).
- Implement the async execution loop in `BaseAgent` (`src/agents/base.py`).
- Add tests verifying subscriber routes and agent execution loops.

### [Milestone 2: LLM Router & Prompt Management](design_docs/08_build_plan.md)
- Build the LLM Router (`src/llm.py`) with support for tier routing and fallback.
- Setup standard prompt template loading (`prompts/`).
- Add token tracking, cost limits, and mock LLM tests.

### [Milestone 3: Knowledge Base & Memory Stores](design_docs/08_build_plan.md)
- Implement SQLite storage for agent history, run contexts, and patches.
- Implement vector search store (FAISS-based or similar) for code snippets and issues.
- Setup file cache management.

### [Milestone 4: Core Sub-Agents (Retrieval & Reproduction)](design_docs/08_build_plan.md)
- Build the Retrieval Agent to search repositories and locate relevant files.
- Build the Reproduction Agent to set up environments, run test commands, and extract failure traces.

### [Milestone 5: The Master Agent Loop (Execution Engine)](design_docs/08_build_plan.md)
- Build the Master Agent orchestrator.
- Implement step execution, replanning, and state machine transitions.

### [Milestone 6: Generating & Validating Fixes (Fix & Validation Agents)](design_docs/08_build_plan.md)
- Build the Fix Generation Agent to output patches.
- Build the Validation Agent to apply patches and verify reproduction tests.

### [Milestone 7: Human-in-the-Loop (HITL) & Service Mode](design_docs/08_build_plan.md)
- Integrate HITL pause/resume points and approvals.
- Enable service mode to run continuously against a queue.

### [Milestone 8: Collaborative & Multi-File (V2 Architecture)](design_docs/08_build_plan.md)
- AST analyzer and advanced multi-file capabilities.

---

## 🛠️ Design Reference Index

Refer to these specifications in order to guide the implementation:
1. **Architecture:** [01_architecture_overview.md](design_docs/01_architecture_overview.md)
2. **Orchestration & Master:** [02_agent_orchestration.md](design_docs/02_agent_orchestration.md)
3. **Communication Bus:** [03_communication_system.md](design_docs/03_communication_system.md)
4. **Knowledge Base:** [04_knowledge_base.md](design_docs/04_knowledge_base.md)
5. **LLM Routing:** [05_llm_integration.md](design_docs/05_llm_integration.md)
6. **Agent Specifications:** [06_agent_specifications.md](design_docs/06_agent_specifications.md)
7. **Data Models:** [07_data_models.md](design_docs/07_data_models.md)
8. **Build Roadmap Detail:** [08_build_plan.md](design_docs/08_build_plan.md)

---

## 📊 Workflow Tracker

This table tracks the implementation status of each milestone. Agents should update this status and add notes as tasks are completed.

| Milestone | Description | Status | Current Focus / Notes |
|---|---|---|---|
| **M0** | [Project Scaffold & Test Harness](design_docs/08_build_plan.md#L26) | ✅ Completed | Structure, config loading, core models and unit tests successfully implemented |
| **M1** | [Message Bus + BaseAgent](design_docs/08_build_plan.md#L162) | ⏳ Not Started | Ready to start implementing communication bus & BaseAgent |
| **M2** | LLM Router & Prompt Management | ⏳ Not Started | |
| **M3** | Knowledge Base & Memory Stores | ⏳ Not Started | |
| **M4** | Core Sub-Agents (Retrieval & Reproduction) | ⏳ Not Started | |
| **M5** | The Master Agent Loop (Execution Engine) | ⏳ Not Started | |
| **M6** | Generating & Validating Fixes | ⏳ Not Started | |
| **M7** | Human-in-the-Loop (HITL) & Service Mode | ⏳ Not Started | |
| **M8** | Collaborative & Multi-File (V2 Architecture) | ⏳ Not Started | |


