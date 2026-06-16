# 07 — Data Models

## 7.1 Design Principles

- **Explicit:** No hidden state; everything is a named dataclass
- **Serializable:** All models can be serialized to/from JSON for persistence and debugging
- **Minimal:** Only the fields needed; add more as requirements emerge
- **Typed:** Full type annotations for clarity and IDE support

## 7.2 Core Data Models

### RunContext
The shared state for a single bug-fix session. Passed to (or accessible by) all agents.

```python
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime
from enum import Enum

class RunStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # Fix generated but not all tests pass
    HITL_REJECTED = "hitl_rejected"  # Fix was rejected by human reviewer

@dataclass
class RunContext:
    """Shared state for one bug-fix session."""
    run_id: str
    instance_id: str
    issue: dict                          # Raw issue from SWEBenchLiteSource
    status: RunStatus = RunStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Set by Master
    plan: list["PlanStep"] = field(default_factory=list)

    # Set by Reproduction Agent
    repo_path: Optional[str] = None
    error_log: Optional[str] = None
    failing_tests: list[str] = field(default_factory=list)
    passing_tests: list[str] = field(default_factory=list)
    test_output: Optional[str] = None
    reproduced_successfully: bool = False

    # Set by Retrieval Agent
    similar_issues: list[dict] = field(default_factory=list)
    relevant_files: dict = field(default_factory=dict)  # filename -> content
    repo_structure: Optional[str] = None

    # Set by Analysis Agent
    root_cause: Optional[str] = None
    fix_hypothesis: Optional[str] = None
    impact_analysis: Optional[str] = None

    # Set by Fix Agent
    generated_patch: Optional[str] = None
    patch_applied: bool = False
    modified_files: list[str] = field(default_factory=list)

    # Set by Validation Agent
    validation_passed: bool = False
    test_details: list[dict] = field(default_factory=list)
    lint_passed: bool = False

    # Set by Review Agent
    review_approved: bool = False
    review_issues: list[str] = field(default_factory=list)
    review_suggestions: list[str] = field(default_factory=list)

    # Human-in-the-Loop
    hitl_required: bool = True
    hitl_approved: bool = False
    hitl_decision_time: Optional[str] = None
    hitl_reviewer_notes: Optional[str] = None

    # Tracking
    steps_completed: list[str] = field(default_factory=list)
    total_llm_calls: int = 0
    total_cost: float = 0.0
    duration_seconds: float = 0.0
```

### Issue (from SWEBenchLiteSource)
```python
@dataclass
class Issue:
    instance_id: str
    repo: str
    base_commit: str
    patch: str                     # Ground-truth fix
    test_patch: str                # Test changes
    problem_statement: str
    hints_text: str
    created_at: str
    version: str
    fail_to_pass: str              # JSON-encoded list of test names
    pass_to_pass: str              # JSON-encoded list of test names
    environment_setup_commit: str
    solved: int                    # 0 or 1
    # NOTE: fail_to_pass and pass_to_pass are JSON-encoded strings from the dataset.
    # Parse them with json.loads() on construction or provide a property:
    #   @property
    #   def failing_tests(self) -> list[str]:
    #       return json.loads(self.fail_to_pass)
```

### Plan (Orchestration)
```python
@dataclass
class PlanStep:
    step_id: str
    agent: str                     # e.g., "reproduction", "fix"
    action: str                    # e.g., "reproduce_bug", "generate_fix"
    params: dict
    depends_on: list[str]          # step_ids
    status: str = "pending"        # pending | running | completed | failed | skipped
    timeout: int = 300
    retries: int = 0
    max_retries: int = 2
    result: Any = None
    error: Optional[str] = None
```

## 7.3 Communication Models

```python
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class Directive:
    """Command from Master to an Agent."""
    target: str
    action: str
    message_id: str
    payload: dict
    priority: int = 0
    timeout: int = 300
    run_id: Optional[str] = None

@dataclass
class Event:
    """Notification from an Agent."""
    source: str
    type: str                      # See event types in 03_communication_system.md
    message_id: str
    payload: dict
    timestamp: float = 0.0
    run_id: Optional[str] = None

# Query message type — designed but deferred to post-MVP.
# See 03_communication_system.md §3.8 for future plans.
```

## 7.4 LLM Models

```python
@dataclass
class LLMResponse:
    text: str
    model: str
    tier: str                      # lite | medium | heavy
    tokens_in: int
    tokens_out: int
    cost: float
    duration_ms: int
    error: Optional[str] = None

@dataclass
class LLMCallRecord:
    model: str
    task_type: str
    tokens_in: int
    tokens_out: int
    success: bool
    error: Optional[str]
    agent_name: str
    run_id: Optional[str]
    timestamp: float
```

## 7.5 Knowledge Base Models

```python
@dataclass
class LearningEntry:
    learning_id: str
    category: str                  # build_tip | fix_pattern | test_insight | etc.
    content: str
    source_run_id: Optional[str]
    source_issue_id: Optional[str]
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_used_at: Optional[str] = None

@dataclass
class RepoCacheEntry:
    repo_name: str
    local_path: str
    last_cloned_at: str
    clone_count: int = 1
    total_size_bytes: Optional[int] = None

@dataclass
class VectorEntry:
    """Entry in the vector store."""
    id: str
    text: str                      # Original text
    embedding: list[float]         # Vector embedding
    metadata: dict                 # Source, issue_id, etc.
    similarity: float = 0.0        # Populated at search time
```

## 7.6 Agent Result Models

```python
@dataclass
class ReproductionResult:
    success: bool
    error_log: Optional[str]
    failing_tests: list[str]
    passing_tests: list[str]
    test_output: Optional[str]
    repo_path: str
    repro_steps: list[str]

@dataclass
class AnalysisResult:
    root_cause: str
    affected_code: list[dict]      # [{file, line, function}]
    fix_hypothesis: str
    impact_analysis: str
    confidence: float

@dataclass
class FixResult:
    success: bool
    patch: Optional[str]
    applied: bool
    modified_files: list[str]
    explanation: str
    llm_iterations: int

@dataclass
class ValidationResult:
    success: bool
    all_tests_pass: bool
    failing_tests_now_pass: list[str]
    previously_passing_still_pass: list[str]
    test_results: dict             # {total, passed, failed, errors, details}
    lint_passed: bool
    lint_output: Optional[str]
    constraints_satisfied: bool

@dataclass
class ReviewResult:
    approved: bool
    review_summary: str
    issues_found: list[str]
    suggestions: list[str]
    security_check: str
    best_practices: str
```

## 7.7 JSON Serialization

All dataclasses should support JSON serialization:

```python
import json
from dataclasses import dataclass, asdict, fields
from typing import get_type_hints, get_origin, get_args

def model_to_json(model) -> str:
    """Serialize any dataclass model to JSON."""
    return json.dumps(asdict(model), indent=2, default=str)

def json_to_model(cls, json_str: str):
    """Deserialize JSON back to a dataclass, handling nested dataclasses.
    
    For deeply nested or complex models, consider using the `dacite` library
    or migrating to Pydantic's `BaseModel` which handles this natively.
    """
    data = json.loads(json_str)
    return _from_dict(cls, data)

def _from_dict(cls, data: dict):
    """Recursively convert a dict to a dataclass, handling nested types."""
    if not hasattr(cls, '__dataclass_fields__'):
        return data  # Not a dataclass, return as-is
    hints = get_type_hints(cls)
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        field_type = hints[f.name]
        # Handle List[SomeDataclass]
        origin = get_origin(field_type)
        if origin is list and value is not None:
            args = get_args(field_type)
            if args and hasattr(args[0], '__dataclass_fields__'):
                value = [_from_dict(args[0], item) for item in value]
        # Handle nested dataclass
        elif hasattr(field_type, '__dataclass_fields__') and isinstance(value, dict):
            value = _from_dict(field_type, value)
        kwargs[f.name] = value
    return cls(**kwargs)
```

## 7.8 Schema Versioning

- All persistent models carry a `schema_version` field (starting at 1)
- The knowledge base tracks the schema version in a metadata table
- Migration scripts live in `db/migrations/v1_to_v2.py`
- This allows the system to evolve without losing data

```python
# Add to SQLite on init:
# CREATE TABLE IF NOT EXISTS schema_meta (
#     key TEXT PRIMARY KEY,
#     value TEXT
# );
# INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('schema_version', '1');
```