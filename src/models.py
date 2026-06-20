import json
from dataclasses import dataclass, field, asdict, fields
from typing import Any, Optional, get_type_hints, get_origin, get_args
from datetime import datetime, timezone
from enum import Enum

class RunStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # Fix generated but not all tests pass
    HITL_REJECTED = "hitl_rejected"  # Fix was rejected by human reviewer

@dataclass
class PlanStep:
    step_id: str
    agent: str                     # e.g., "reproduction", "fix"
    action: str                    # e.g., "reproduce_bug", "generate_fix"
    params: dict = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"        # pending | running | completed | failed | skipped
    timeout: int = 300
    retries: int = 0
    max_retries: int = 2
    result: Any = None
    error: Optional[str] = None

@dataclass
class RunContext:
    """Shared state for one bug-fix session."""
    run_id: str
    instance_id: str
    issue: dict                          # Raw issue from SWEBenchLiteSource
    status: RunStatus = RunStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Set by Master
    plan: list[PlanStep] = field(default_factory=list)

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

    @property
    def failing_tests(self) -> list[str]:
        return json.loads(self.fail_to_pass)

    @property
    def passing_tests(self) -> list[str]:
        return json.loads(self.pass_to_pass)

@dataclass
class Directive:
    """Command from Master to an Agent."""
    target: str
    action: str
    message_id: str
    payload: dict = field(default_factory=dict)
    priority: int = 0
    timeout: int = 300
    run_id: Optional[str] = None

@dataclass
class Event:
    """Notification from an Agent."""
    source: str
    type: str                      # See event types in 03_communication_system.md
    message_id: str
    payload: dict = field(default_factory=dict)
    timestamp: float = 0.0
    run_id: Optional[str] = None

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

@dataclass
class LearningEntry:
    learning_id: str
    category: str                  # build_tip | fix_pattern | test_insight | etc.
    content: str
    source_run_id: Optional[str]
    source_issue_id: Optional[str]
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
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

def model_to_json(model) -> str:
    """Serialize any dataclass model to JSON."""
    def custom_serializer(obj):
        if isinstance(obj, Enum):
            return obj.value
        return str(obj)
    return json.dumps(asdict(model), indent=2, default=custom_serializer)

def json_to_model(cls, json_str: str):
    """Deserialize JSON back to a dataclass, handling nested dataclasses."""
    data = json.loads(json_str)
    return _from_dict(cls, data)

def _from_dict(cls, data: dict):
    """Recursively convert a dict to a dataclass, handling nested types."""
    if not hasattr(cls, '__dataclass_fields__'):
        return data  # Not a dataclass, return as-is
    
    # Handle Enum types if data is raw string
    if issubclass(cls, Enum):
        return cls(data)
        
    hints = get_type_hints(cls)
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        field_type = hints[f.name]
        
        # Handle Union / Optional types
        origin = get_origin(field_type)
        args = get_args(field_type)
        
        # Determine the non-None type for Optional fields
        if origin is Any or field_type is Any:
            kwargs[f.name] = value
            continue
            
        # Optional[X] is represented as Union[X, NoneType]
        from typing import Union
        if origin is Union:
            non_none_types = [a for a in args if a is not type(None)]
            if non_none_types:
                field_type = non_none_types[0]
                origin = get_origin(field_type)
                args = get_args(field_type)
        
        # Handle list of nested structures
        if origin is list and value is not None:
            if args and hasattr(args[0], '__dataclass_fields__'):
                value = [_from_dict(args[0], item) for item in value]
        # Handle nested dataclass
        elif hasattr(field_type, '__dataclass_fields__') and isinstance(value, dict):
            value = _from_dict(field_type, value)
        # Handle Enum
        elif isinstance(field_type, type) and issubclass(field_type, Enum) and value is not None:
            value = field_type(value)
            
        kwargs[f.name] = value
    return cls(**kwargs)
