# 06 — Agent Specifications

## 6.1 Overview

Six specialized agents, each with a single responsibility. All agents inherit from `BaseAgent` and follow the same lifecycle.

> **Canonical types:** All agent input/output dataclasses are defined in [07_data_models.md](07_data_models.md) §7.6. The types shown inline below are summaries.

```
BaseAgent
├── RetrievalAgent
├── ReproductionAgent
├── AnalysisAgent
├── FixGenerationAgent
├── ValidationAgent
└── ReviewAgent
```

## 6.2 Common Interface

```python
class BaseAgent(ABC):
    """Base class for all sub-agents (NOT the Master).
    See 03_communication_system.md for the run_loop() implementation."""

    def __init__(self, name: str, bus: MessageBus, llm: LLMRouter, kb: KnowledgeBase):
        self.name = name
        self.bus = bus
        self.llm = llm
        self.kb = kb
        bus.register_agent(name, self)

    @abstractmethod
    async def execute(self, directive: Directive) -> dict:
        """Execute the given directive. Returns a result dict.
        
        The directive contains:
          - action: str — what to do (e.g., "reproduce_bug", "generate_fix")
          - payload: dict — action-specific parameters
          - message_id: str — unique ID for tracking
          - timeout: int — max execution time in seconds
        """
        pass

    async def run_loop(self):
        """Main event loop — listens for directives on the bus.
        See 03_communication_system.md §3.6 for full implementation."""
        ...
```

---

## 6.3 Retrieval Agent

**Purpose:** Find relevant information: code context, similar issues, documentation, build instructions.

**Capabilities:**
- Search the repo's codebase for relevant files/functions
- Find similar issues in the knowledge base (past solved issues)
- Retrieve documentation or README content
- Understand repo structure and identify relevant modules
- **(Future) AST-based call graph analysis:** Parse Python source into ASTs to map function definitions, calls, and imports — enabling precise scope analysis beyond keyword search
- **(Future) Dependency graph:** Build and query a graph of module-level dependencies to assess impact scope

**When invoked:**
- Before reproduction (to understand the repo)
- Before fix generation (to provide context)
- When other agents flag "insufficient context"

**Inputs:**
```python
{
    "action": "search_code" | "find_similar_issues" | "get_repo_structure" | "get_file_content",
    "params": {
        "repo": "django/django",
        "query": "function that handles division",
        "files": ["calculator.py", "test_calculator.py"],
        "issue_statement": "When calling divide(a,b) with b=0...",
    }
}
```

**Outputs:**
```python
{
    "relevant_files": [
        {"path": "calculator.py", "snippets": ["def divide(a, b):..."]},
        ...
    ],
    "similar_issues": [
        {"instance_id": "django__django-12345", "patch": "diff --git ...", "similarity": 0.87},
        ...
    ],
    "repo_structure": "calculator.py, test_calculator.py, utils.py, ...",
    "context_notes": "The divide function is in calculator.py. Tests are in test_calculator.py."
}
```

**LLM usage:** Medium model for code search/analysis, Lite for classification.

---

## 6.4 Reproduction Agent

**Purpose:** Reproduce the bug locally to get concrete error logs and failure details.

**Capabilities:**
- Clone the repo at the specific base commit
- Set up the environment (pip install, etc.)
- Run the failing tests
- Capture error output, stack traces, test results
- Try multiple reproduction strategies if the first fails

**When invoked:**
- First step in MVP pipeline
- When re-verifying a fix

**Inputs:**
```python
{
    "action": "reproduce_bug",
    "params": {
        "repo": "django/django",
        "base_commit": "abc123def",
        "repo_url": "https://github.com/django/django",
        "fail_to_pass_tests": ["tests/test_divide.py::test_divide_zero"],
        "environment_setup_commit": "xyz789",
        "setup_commands": ["pip install -e ."],
    }
}
```

**Outputs:**
```python
{
    "bug_reproduced": True,       # Was the bug successfully reproduced? (True = tests failed as expected)
    "error_log": "ZeroDivisionError: division by zero\n  File calculator.py:12 ...",
    "failing_tests": ["test_calculator.py::test_divide"],
    "passing_tests": ["test_calculator.py::test_add", ...],
    "test_output": "....F....",   # Full test runner output
    "reproduced_at": "/tmp/repos/django__django",
    "repro_steps": [
        "Cloned repo at abc123def",
        "Installed dependencies",
        "Ran: pytest test_calculator.py::test_divide",
        "Result: FAILED - ZeroDivisionError"
    ]
}
```

**Implementation Notes:**
- Uses `git clone` + `git checkout` for repo setup
- Uses `subprocess` to run build/test commands
- Sets a strict timeout on all subprocess calls (e.g., 5 minutes)
- Caches cloned repos to avoid re-cloning
- **Naming note:** `bug_reproduced=True` means the bug was confirmed (tests failed as expected). This avoids confusion with `success=True` which could be misread as "tests passed."

---

## 6.5 Analysis Agent

**Purpose:** Root cause analysis. Understands why the bug happens and generates hypotheses.

**Capabilities:**
- Read the failing test and understand what it expects
- Trace through the code to find the root cause
- Generate hypotheses about the fix
- Assess impact (what other parts of the code might be affected)
- Dependency analysis (what imports/modules are involved)

**When invoked:**
- After reproduction, before fix generation (in full pipeline)
- When fix generation fails (to provide better analysis)

**Inputs:**
```python
{
    "action": "root_cause_analysis",
    "params": {
        "repo_path": "/tmp/repos/django__django",
        "problem_statement": "When calling divide(a,b) with b=0...",
        "error_log": "ZeroDivisionError: division by zero\n  File calculator.py:12 ...",
        "failing_tests": ["test_calculator.py::test_divide"],
        "relevant_files": {
            "calculator.py": "def divide(a, b):\n    return a / b\n...",
            "test_calculator.py": "def test_divide():\n    with pytest.raises(ValueError):\n        divide(5, 0)\n..."
        }
    }
}
```

**Outputs:**
```python
{
    "root_cause": "The divide() function does not handle division by zero. "
                  "It lets Python raise a raw ZeroDivisionError instead of "
                  "raising a ValueError with a custom message.",
    "affected_code": [
        {"file": "calculator.py", "line": 12, "function": "divide"}
    ],
    "fix_hypothesis": "Add a check at the start of divide(): if b == 0: raise ValueError(...)",
    "impact_analysis": "Low impact. Only the divide function is affected. "
                       "No other functions depend on divide raising ZeroDivisionError.",
    "confidence": 0.95
}
```

**LLM usage:** Heavy model for root cause analysis.

---

## 6.6 Fix Generation Agent

**Purpose:** Generate the actual code fix (git patch) that resolves the bug.

**Capabilities:**
- Read the root cause analysis
- Generate a minimal, correct git diff patch
- Ensure the patch applies cleanly
- Handle multiple-file changes if needed
- Generate updated tests if the test_patch is missing

**When invoked:**
- After reproduction (MVP) or after analysis (full pipeline)
- After validation failure (to re-attempt fix)

**Inputs:**
```python
{
    "action": "generate_fix",
    "params": {
        "repo_path": "/tmp/repos/django__django",
        "problem_statement": "...",
        "error_log": "...",
        "root_cause_analysis": { ... },    # From Analysis Agent (if available)
        "failing_tests": ["test_calculator.py::test_divide"],
        "code_context": {                   # From Retrieval Agent (if available)
            "calculator.py": "def divide(a, b):\n    return a / b\n..."
        }
    }
}
```

**Outputs:**
```python
{
    "success": True,
    "patch": "diff --git a/calculator.py b/calculator.py\nindex 9381144..1dba21d 100644\n--- a/calculator.py\n+++ b/calculator.py\n@@ -10,6 +10,8 @@ def multiply(a, b):\n     return a * b\n \n def divide(a, b):\n+    if b == 0:\n+        raise ValueError(\"Cannot divide by zero.\")\n     return a / b\n",
    "applied": True,                    # Was the patch applied to the repo?
    "modified_files": ["calculator.py"],
    "explanation": "Added a zero-division check at the start of divide() "
                   "that raises ValueError instead of letting Python raise ZeroDivisionError.",
    "llm_iterations": 1                 # How many LLM attempts
}
```

**LLM usage:** Medium model (code-specialized like `qwen2.5-coder:7b`).

---

## 6.7 Validation Agent

**Purpose:** Verify the fix works correctly by running tests and checking constraints.

**Capabilities:**
- Run the failing tests to confirm they now pass
- Run the full test suite to check for regressions (PASS_TO_PASS tests)
- Check code style / lint
- Verify the patch applies cleanly
- Validate against any constraints (format, size, etc.)

**When invoked:**
- After fix generation
- After any code modification

**Inputs:**
```python
{
    "action": "validate_fix",
    "params": {
        "repo_path": "/tmp/repos/django__django",
        "patch": "diff --git ...",
        "failing_tests": ["test_calculator.py::test_divide"],
        "passing_tests": ["test_calculator.py::test_add", ...],
        "lint_config": ".pylintrc",
        "constraints": {
            "patch_size_max": "50 lines",
            "must_not_change": ["API signatures"],
            "required_imports": ["ValueError"]
        }
    }
}
```

**Outputs:**
```python
{
    "success": True,
    "all_tests_pass": True,
    "failing_tests_now_pass": ["test_calculator.py::test_divide"],
    "previously_passing_still_pass": ["test_calculator.py::test_add", ...],
    "test_results": {
        "total": 12,
        "passed": 12,
        "failed": 0,
        "errors": 0,
        "details": [
            {"test": "test_divide", "status": "PASSED"},
            ...
        ]
    },
    "lint_passed": True,
    "lint_output": "",
    "patch_applies_cleanly": True,
    "constraints_satisfied": True
}
```

**Implementation Notes:**
- Runs `pytest` (or equivalent) via subprocess
- Parses pytest output (JUnit XML preferred)
- Uses the test lists from SWE-bench Lite (FAIL_TO_PASS, PASS_TO_PASS)

---

## 6.8 Review Agent

**Purpose:** Code review — quality, security, best practices, edge cases.

**Capabilities:**
- Review the generated patch for code quality
- Check for security vulnerabilities
- Verify coding standards and best practices
- Check for edge cases not covered by existing tests
- Suggest improvements

**When invoked:**
- After validation passes (final step)
- Can be skipped for quick runs
- Controlled by `config.yaml` setting: `review: { enabled: true }`. Master's `build_plan()` checks this flag.

**Inputs:**
```python
{
    "action": "review_patch",
    "params": {
        "repo_path": "/tmp/repos/django__django",
        "patch": "diff --git ...",
        "modified_files": ["calculator.py"],
        "original_code": "def divide(a, b):\n    return a / b\n...",
        "modified_code": "def divide(a, b):\n    if b == 0:\n        raise ValueError(...)\n    return a / b\n...",
        "problem_statement": "...",
        "test_results": { "passed": 12, "failed": 0 }
    }
}
```

**Outputs:**
```python
{
    "approved": True,
    "review_summary": "The fix is correct and minimal. It handles the edge case "
                      "of division by zero appropriately.",
    "issues_found": [],
    "suggestions": [
        "Consider adding a type hint: def divide(a: float, b: float) -> float"
    ],
    "security_check": "PASSED - No security concerns",
    "best_practices": "PASSED - Follows project conventions"
}
```

**LLM usage:** Heavy model for thorough review.

---

## 6.9 Summary: Agent Configuration

| Agent | Model Tier | Timeout | Retries | When to Run |
|-------|-----------|---------|---------|-------------|
| Retrieval | Medium | 120s | 1 | Optional pre-step |
| Reproduction | N/A (subprocess) | 300s | 1 | MVP (first step) |
| Analysis | Heavy | 300s | 1 | After reproduction |
| Fix | Medium | 120s | 2 | After reproduction/analysis |
| Validation | N/A (subprocess) | 300s | 0 (no retry) | After fix |
| Review | Heavy | 300s | 0 | Final step |