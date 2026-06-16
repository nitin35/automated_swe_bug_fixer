# Architecture Diagram

```markdown

+-------------------------------------------------------------------------------------------------------------------------------+
|                                                1. ORCHESTRATOR AGENT (Task Manager)                                           |
|[Intake & Prioritization] ->[Task Decomposition & Planning] ->[Agent Selection & Scheduling] ->[Progress Tracking & Re-plan]   |
|  * Decides what to fix, breaks down the problem, delegates to specialized agents, monitors, and adapts.                       |
+-------------------------------------------------------------------------------------------------------------------------------+
         ^                                                      |                                                       ^
         | (Data / Control Flow)                                v (Data / Control Flow)                                 |
         v                                                                                                              v
+------------------+     +-----------------------------------------------------------------------------------+     +------------+
|  INPUT SOURCES   |     |                             2. SPECIALIZED AGENT POOL                             |     |   AGENT    |
|                  |     |                                                                                   |     |  COMM. BUS |
| * Issue Trackers |     | +-----------------+  +-----------------+  +-----------------+  +----------------+ |     |            |
|   (Jira, GitHub) |---->| | Retrieval Agent |  |Reproduction Agt |  | Analysis Agent  |  |Fix Gen. Agent  | |<===>| (Message   |
| * CI/CD Failures |     | | - Code Search   |  | - Repro Locally |  | - Root Cause    |  | - Gen Fix(Code)| |     |  Queue /   |
|   (Build/Test)   |     | | - Similar Issues|  | - Build / Run   |  | - Dep/Impact    |  | - Refactor     | |     |  Event Bus)|
| * User Reports   |     | | - Docs & Context|  | - Collect Signals|  | - Hypothesis Gen| | - Add/Upd Tests| |     | e.g., Redis|
| * Logs & Monitor |     | +-----------------+  +-----------------+  +-----------------+  +----------------+ |     | Streams,   |
|   (Sentry, DD)   |     |          |                    |                    |                    |         |     | Kafka,     |
| +----------------+     |          v                    v                    v                    v         |     | RabbitMQ   |
                         | +-----------------+  +-----------------+                                          |     +------------+
+------------------+     | | Validation Agt  |  |  Review Agent   |                                          |           ^
| CODE REPOSITORY  |     | | - Run Tests     |  | - Code Review   |                                          |           |
|                  |     | | - Lint/SAST/Chks|  | - Best Practices|                                          |           v
| * Git / VCS      |---->| | - Verify Fix    |  | - Security Rev  |                                          |     +------------+
| * Source Code    |     | +-----------------+  +-----------------+                                          |     |   TOOLS &  |
|   History        |     +-----------------------------------------------------------------------------------+     | INTEGRAT-  |
+------------------+                                              |                                                |    IONS    |
         |                                                                                                         |            |
         |                               +--------------------------------------------------+                      | * Code Srch|
         +------------------------------>|        3. EXECUTION ENVIRONMENT (Sandbox)        |                      |   (Ripgrep)|
         |                               |                                                  |                      | * Sandbox  |
         |                               | * Isolated Workspaces   * Secure Execution       |                      |   (Docker) |
         |                               | * Resource Limits       * Network Controls       |                      | * Test Run |
         |                               +--------------------------------------------------+                      |   (PyTest) |
         |                                                        ^                                                | * Linters  |
         |                                                        | (Read / Write)                                 |   (Ruff)   |
         v                                                        v                                                | * SAST     |
+---------------------------------------------------------------------------------------------------+              | (SonarQube)|
|                                      4. MEMORY & DATA LAYER                                       |              | * Dep Scan |
|                                                                                                   |              |   (Snyk)   |
|  [Vector DB]          [Issue / Task DB]     [Agent Memory]      [Artifacts Store]   [Knowledge BB]|              | * Docs     |
|  (Code Embeddings)    (Postgres)            (Redis)             (Patches/Logs/S3)   (Playbooks)   |              +------------+
+---------------------------------------------------------------------------------------------------+                    |
         ^                                                        ^                                                      |
         |                                                        |                                                      v
         v                                                        v                                                +------------+
+---------------------------------------------------------------------------------------------------+              |  OUTPUT &  |
|                                    6. OBSERVABILITY & GOVERNANCE                                  |              | INTEGRATION|
|                                                                                                   |<-------------|            |
|  * Monitoring         * Tracing             * Audit Logs        * Cost / Token      * Alerts      |              | * Proposed |
|   (Prometheus)         (OpenTelemetry)       & Events            Tracking            & Watchdogs  |              |   Patch(PR)|
+---------------------------------------------------------------------------------------------------+              | * Explanat-|
                                                                                                                   |   ion/Summ |
                                                                                                                   | * Evidence |
                                                                                                                   +------------+
                                                                                                                         |
                                                                                                                         v
                                                                                                                   +------------+
                                                                                                                   |  HUMAN IN  |
                                                                                                                   |  THE LOOP  |
                                                                                                                   |            |
                                                                                                                   | * Developer|
                                                                                                                   |   Review   |
                                                                                                                   | * Approve/ |
                                                                                                                   | * Merge    |
                                                                                                                   +------------+
```

## Detailed Architectural Breakdown

### 1. Orchestrator Agent (Task Manager)
Acting as the central command system, the Orchestrator manages the end-to-end processing pipeline. It steps through four critical operational phases:
* **Intake & Prioritization:** Receives inbound bug signals, sanitizes raw issues, and evaluates urgency levels.
* **Task Decomposition & Planning:** Breaks high-level problem statements down into small, distinct, logical operational objectives.
* **Agent Selection & Scheduling:** Matches specific duties to appropriate sub-agents based on their functional specialization.
* **Progress Tracking & Re-planning:** Actively monitors current execution flows, stepping in to modify strategies dynamically if initial fix attempts stall.

### 2. Specialized Agent Pool
A highly coordinated group of dedicated sub-agents that collaborate over an **Agent Communication Bus** (driven by event streams like Kafka, Redis Streams, or RabbitMQ):
* **Retrieval Agent:** Responsible for sweeping codebases, parsing document spaces, extracting contextual data, and surfacing structurally similar historical issues.
* **Reproduction Agent:** Focuses exclusively on spinning up test cases to replicate the failure locally inside isolated runtimes, capturing crash signals directly.
* **Analysis Agent:** Conducts system-level dependency mapping, forms bug root-cause theories, and models crash dependencies.
* **Fix Generation Agent:** Writes the functional patch code, refactors surrounding implementations if required, and crafts supporting test logic.
* **Validation Agent:** Executes regression test frameworks, sanity-checks patch styling, and strictly enforces functional code gates.
* **Review Agent:** Evaluates code safety, checks for patterns matching security vulnerabilities, and evaluates adherence to system-wide best practices.

### 3. Execution Environment (Sandbox)
To guarantee execution safety and isolation, the active workload is processed inside strict containerized environments (such as Docker or Firecracker):
* **Isolated Workspaces:** Spreads specific agents and separate repository task tracks into securely partitioned domains.
* **Secure Execution:** Leverages strictly confined hypervisors and VMs to block arbitrary system access paths.
* **Resource Limits:** Hard-caps memory, processing cycles, and transaction window times to contain rogue runtime executions.
* **Network Controls & Permissions:** Imposes secure firewall policies to prevent untrusted data outbound leaks during untrusted validation blocks.

### 4. Memory & Data Layer
The persistent foundation of the agent pool, providing historical context and cross-agent memory synchronization:
* **Vector DB:** Houses semantic codebase definitions via multi-file relational embeddings.
* **Issue / Task DB:** Managed on relational frameworks like Postgres to coordinate active states, assign updates, and record structural jobs.
* **Agent Memory:** Employs high-throughput caching (Redis) to maintain volatile agent operational states and cross-agent communication sessions.
* **Artifacts Store:** Secure cloud storage (S3/MinIO) archiving regression patch histories, diagnostics dumps, and verbose evaluation logs.
* **Knowledge Base:** Central index containing localized playbooks, past fix configurations, and standardized operational rulesets.

### 5. Tools & Integrations
Exposes external developer tooling explicitly via integrated interfaces to bolster agent execution capability:
* **Code Search:** Leverages highly efficient search configurations like Ripgrep or SourceGraph to navigate extensive structures.
* **Runtimes & Sanity Suites:** Direct interaction with test tooling frameworks (PyTest, JUnit) alongside syntax checkers (ESLint, Ruff, Black).
* **Static Analysis & SAST:** Integrates platforms like SonarQube or Semgrep to identify security oversights early.
* **Dependency Scanners:** Integrates security utilities like Snyk or OWASP to prevent downstream library supply chain injections.

### 6. Observability & Governance
Monitors system boundaries, cost parameters, and execution telemetry:
* **Telemetry & Tracking:** Standardized metrics logging over Prometheus, Grafana dashboards, and OpenTelemetry spans.
* **Audit Logs & Events:** Collects complete, immutable execution logs capturing exact command strings run by agents.
* **Cost / Token Tracking:** Monitors real-time runtime token balances and infrastructure compute usage to prevent unbounded costs.
* **Safety & Guardrails:** Enforces operational access parameters, blocking unsafe workspace mutations automatically.

### 7. Output, Integration & HITL
Once a candidate fix successfully passes validation checks, it is package-compiled under the **Output & Integration** layer as a Proposed Patch (PR), alongside a concise summary, testing evidence, and contextual metrics.

This moves into the **Human-in-the-Loop (HITL)** workspace:
1. **Developer Review:** Software engineers inspect the proposed fix and review the validation logs.
2. **Approve / Request Changes:** Developers can merge the fix immediately or instruct the Orchestrator to attempt an alternate patch strategy.
3. **Merge & CI/CD Pipeline:** Approved changes trigger automated merges and feed into the live build pipeline for deployment.

