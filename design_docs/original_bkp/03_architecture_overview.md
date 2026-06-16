# Architecture Overview

### Input & Trigger Sources
* Jira defects, CI/CD failures, user reports, logs, and monitoring alerts.
* Issues are normalized into a common task format.

### Orchestrator Agent
* Central coordinator of the system.
* Decomposes complex engineering problems into smaller, manageable tasks.
* Assigns work to specialized agents.
* Tracks progress and manages execution workflows.

### Specialized Agent Pool
* **Retrieval Agent**: Finds relevant code, documentation, and historical cases.
* **Reproduction Agent**: Recreates the failure/bug in a controlled, isolated environment.
* **Analysis Agent**: Performs root-cause analysis on stack traces and logs.
* **Fix Generator Agent**: Generates candidate software fixes, runs tests, and performs quality/maintainability checks.

### Knowledge & Memory Layer
* Code embeddings inside a vector database.
* Dependency relationship graphs.
* Historical records of bugs, pull requests, and operational playbooks.

### Runtime Environment
* Containerized sandboxes for safe experimentation.
* Isolated build and deployment environments.

### Continuous Learning
* Captures outcomes of every bug-fix attempt (both successful and failed).
* Extracts reusable fix strategies to continuously improve agent decision-making.

### Human-in-the-Loop (HITL)
* Propose, modify, or reject recommended fixes.
* Provides a feedback loop to raise future agent accuracy.

### Key Value Proposition
* Shifts engineering from reactive bug fixing to a collaborative, intelligent team of automated software agents working seamlessly at scale.