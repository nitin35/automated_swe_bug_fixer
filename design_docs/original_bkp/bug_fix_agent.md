# Autonomous Bug-Fixer Agent
Agentic AI
## Overview
Design and build a long-running autonomous agent that fixes bugs in an open-source system-software project.
The agent should understand the codebase, propose validated fixes, prepare merge requests, improve over time, and remain cost-aware.
## Problem Statement
Poll a bug source continuously for actionable bugs.
Build and maintain a codebase index for efficient retrieval.
Reproduce, localize, patch, and validate bugs.
Prepare a merge request (MR/PR) description and diff.
Learn from outcomes and improve over time.
## Bug Source – SWE-bench
Use SWE-bench (preferably SWE-bench Lite) as the incoming bug queue.
Treat benchmark instances as arriving bugs.
Scope may be limited to a subset of projects or instances with justification.
Use ground-truth tests to validate fixes.
## Design Constraints
Minimal human intervention.
Cost-aware model routing.
Parallelism through multiple agents.
Efficient code understanding and indexing.
Persistent memory and self-improvement.
Long-running service behavior.
Safety and guardrails.
## Architecture Expectations
Agent topology is intentionally unspecified.
Justify decomposition, orchestration, indexing, model routing, and feedback loops.
Explain parallel execution and conflict avoidance.
## Focus Items:-
Agent design maturity.
Cost vs capability judgment.
Decomposition and orchestration.
Code-understanding strategy.
Self-improvement mechanism.
Communication quality and trade-off reasoning.

## References
SWE-bench project site and documentation.
SWE-bench GitHub repository.
SWE-bench Lite dataset on Hugging Face.
Research paper: SWE-bench: Can Language Models Resolve Real-World GitHub Issues.
Ollama and Continue.dev documentation.
