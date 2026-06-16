# 01 — Architecture Overview

## 1.1 System Diagram (Conceptual)

```
                    ┌─────────────────────────────────────────┐
                    │              Master Agent                │
                    │  (Orchestrator / Planner / Router)       │
                    └────┬──────┬──────┬──────┬──────┬──────┬──┘
                         │      │      │      │      │      │
                    ┌────┘  ┌───┘  ┌───┘  ┌───┘  ┌───┘  ┌───┘
                    ▼       ▼      ▼      ▼      ▼      ▼
                ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐
                │Retr.│ │Repr.│ │Anl. │ │Fix  │ │Val. │ │Rev. │
                │Agent│ │Agent│ │Agent│ │Agent│ │Agent│ │Agent│
                └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘
                   │       │       │       │       │       │
                   └───────┴───────┴───────┴───────┴───────┴────┐
                                                                │
                    ┌───────────────────────────────────────────┘
                    ▼
          ┌─────────────────────┐
          │   Message Bus       │  (in-process event queue)
          │   + Context Store   │  (shared state for the run)
          └────────┬────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌────────┐
   │  SQL   │ │Vector  │ │  File  │
   │  Store │ │  Store │ │  Cache │
   └────────┘ └────────┘ └────────┘
```

## 1.2 Core Components

### Master Agent (Orchestrator)
- Entry point for every bug-fixing session
- Receives an issue from `SWEBenchLiteSource`
- Plans the workflow dynamically based on the issue
- Delegates tasks to sub-agents, monitors their progress
- Decides when to retry, escalate, or abort
- Records the final outcome (success/failure, patch generated)
- Supports **Human-in-the-Loop (HITL)**: pauses before finalizing a fix to request human approval
- Can run as a **long-running service**: polls issue sources on a schedule, respects concurrency limits

### Sub-Agents
Six specialized agents, each with:
- A **single responsibility**
- A **defined input/output contract** (see [data models](07_data_models.md))
- Access to the **message bus** for communication
- Access to the **knowledge base** for persistent data
- The ability to **request LLM calls** via the model router

### Message Bus
- In-process, lightweight publish-subscribe system
- Agents post **events** (with payloads) to named channels
- Agents can **listen** for events from other agents
- The Master orchestrator can also send **directives** (commands) to agents
- Enables the dynamic workflow without hard-coded pipelines

### Knowledge Base (Persistent Memory)
Three storage layers:
1. **SQLite** — Structured data: issues, runs, results, agent logs, costs
2. **Vector Store** (FAISS-based) — Semantic search over past issues, code snippets, learnings. Uses FAISS `IndexFlatL2` for exact nearest-neighbor search, with metadata stored alongside via pickle.
3. **File Cache** — Cloned repos, build artifacts, generated patches

### LLM Router
- Abstracts access to different models (all Ollama for now)
- Routes requests based on task complexity:
  - **Lite models** (e.g., `llama3.2:1b`) — simple classification, formatting
  - **Medium models** (e.g., `qwen2.5-coder:7b`) — code generation, analysis
  - **Heavy models** (e.g., `llama3.1:8b`) — planning, root cause analysis, review
- Tracks token usage and cost (even if local = $0, we track "effort units")
- Supports configurable timeouts, retries, fallback

## 1.3 Request Flow (Typical Bug-Fix Session)

```
1. User / Scheduler calls run(issue)
2. Master Agent:
   a. Receives the issue
   b. Consults knowledge base for similar past issues
   c. Creates a Context object for this run
   d. Begins dynamic orchestration

3. Typical workflow (MVP = Reproduction → Fix → Validation):
   Master → Reproduction Agent: "Reproduce the bug"
     Reproduction Agent → Master: {success: True, error_log: "..."}
   Master → Fix Agent: "Generate a fix"
     Fix Agent → Master: {patch: "diff --git ..."}
   Master → Validation Agent: "Validate this patch"
     Validation Agent → Master: {tests_passed: True, ...}
   Master → Knowledge Base: Record outcome

4. Master reports final result
```

## 1.4 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Communication | In-process pub/sub bus | Simple, no network overhead, easy to debug. Can be swapped for distributed bus later. |
| Agent isolation | Classes + explicit interfaces | No separate processes needed for MVP. Each agent = a class with a `run(context)` method. |
| State persistence | SQLite + FAISS vector store + filesystem | Zero setup, portable, production-grade vector search from day one. Can migrate to Postgres + pgvector later. |
| LLM access | Single wrapper over Ollama HTTP API | Abstraction layer makes it easy to add OpenAI/Anthropic later. |
| Dynamic orchestration | Master uses LLM + rules to plan | Most flexible. Master can adapt to issue complexity. |
| Extensibility | Plugin-style agent registration | New agents can be added by implementing an interface. |

## 1.5 Non-Goals (for now)

- Distributed agents across machines
- Real-time streaming agent outputs
- Web UI / dashboard
- Automated PR creation
- Integration with CI/CD pipelines
- Multi-language support beyond Python repos
- Full containerized sandboxing (added post-MVP — see `02_agent_orchestration.md` for service mode)