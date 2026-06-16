# Autonomous Repository-Scale Bug Fixing

### Problem Statement
Existing AI coding assistants can generate code snippets but cannot reliably perform end-to-end software maintenance. Real-world bug fixing requires:
* Repository-level understanding
* Failure reproduction
* Root-cause analysis
* Patch generation
* Validation and continuous improvement across large and evolving codebases.

### Goal
Build a long-running bug-fixing system that can:
* Analyze issues and generate development-ready, merge-ready changes.
* Learn from historical outcomes.
* Operate cost-effectively at scale.

### Primary Target
* SWE-bench Lite (MVP)
* Extend to full SWE-bench and deploy in live production environments.

### Key Challenges
* Multi-file dependencies
* Ambiguous bug reports
* Limited LLM context windows
* Expensive evaluation/test cycles
* Regression prevention
* Cost optimization