# Code Understanding Strategy

Build repository-level understanding by combining structural, semantic, runtime, and historical knowledge.

### 1. Structural Analysis
* Parse source code into Abstract Syntax Trees (ASTs).
* Map classes, functions, and codebase dependencies into a relational graph.
* **Purpose**: Understand exactly how the codebase is organized and interconnected.

### 2. Semantic Search
* Generate multi-file embeddings for comprehensive documentation.
* Perform semantic code search across the repository to retrieve relevant files matching a given issue.

### 3. Runtime Intelligence
* Analyze logs, stack traces, crash dumps, and execution test failures.
* Correlate runtime observations with code locations to pinpoint potential root causes.

### 4. Historical Context
* Store previous bug resolution patterns and lessons learned from similar issues.
* Reuse successful resolution patterns to avoid repeating past engineering mistakes.

> **Key Takeaway**: The system is engineered to build a comprehensive view of the codebase, continuously improving bug-fix accuracy over time.