import json
from src.models import (
    RunContext,
    RunStatus,
    PlanStep,
    Issue,
    Directive,
    Event,
    LLMResponse,
    model_to_json,
    json_to_model
)

def test_run_context_serialization():
    # Create a PlanStep
    step = PlanStep(
        step_id="step_0",
        agent="reproduction",
        action="reproduce_bug",
        params={"test_command": "pytest"},
        depends_on=[],
        status="pending"
    )
    
    # Create RunContext
    context = RunContext(
        run_id="run_123",
        instance_id="django__django-11111",
        issue={"key": "val"},
        status=RunStatus.RUNNING,
        plan=[step],
        repo_path="/path/to/repo"
    )
    
    # Serialize
    json_str = model_to_json(context)
    assert "run_123" in json_str
    assert "django__django-11111" in json_str
    assert "reproduce_bug" in json_str
    assert "running" in json_str
    
    # Deserialize
    deserialized = json_to_model(RunContext, json_str)
    assert deserialized.run_id == "run_123"
    assert deserialized.instance_id == "django__django-11111"
    assert deserialized.status == RunStatus.RUNNING
    assert len(deserialized.plan) == 1
    assert deserialized.plan[0].step_id == "step_0"
    assert deserialized.plan[0].params == {"test_command": "pytest"}
    assert deserialized.repo_path == "/path/to/repo"

def test_issue_dataclass():
    issue = Issue(
        instance_id="id_1",
        repo="repo_1",
        base_commit="abc",
        patch="diff1",
        test_patch="diff2",
        problem_statement="prob",
        hints_text="hint",
        created_at="time",
        version="1.0",
        fail_to_pass='["test_a", "test_b"]',
        pass_to_pass='["test_c"]',
        environment_setup_commit="xyz",
        solved=1
    )
    
    assert issue.failing_tests == ["test_a", "test_b"]
    assert issue.passing_tests == ["test_c"]

def test_directive_and_event():
    d = Directive(
        target="reproduction",
        action="run",
        message_id="msg_1",
        payload={"param": 42},
        run_id="run_1"
    )
    
    json_d = model_to_json(d)
    deserialized_d = json_to_model(Directive, json_d)
    assert deserialized_d.target == "reproduction"
    assert deserialized_d.payload == {"param": 42}
    
    e = Event(
        source="reproduction",
        type="task.completed",
        message_id="msg_2",
        payload={"status": "ok"},
        run_id="run_1"
    )
    
    json_e = model_to_json(e)
    deserialized_e = json_to_model(Event, json_e)
    assert deserialized_e.source == "reproduction"
    assert deserialized_e.type == "task.completed"
    assert deserialized_e.payload == {"status": "ok"}

def test_missing_and_optional_fields():
    # Test loading context from json with missing fields. Should use defaults/missing logic.
    raw_json = '{"run_id": "run_999", "instance_id": "inst_999", "issue": {}}'
    context = json_to_model(RunContext, raw_json)
    
    assert context.run_id == "run_999"
    assert context.instance_id == "inst_999"
    assert context.issue == {}
    # Check default values are populated correctly
    assert context.status == RunStatus.PENDING
    assert context.plan == []
    assert context.repo_path is None
    assert context.reproduced_successfully is False

def test_result_models_serialization():
    from src.models import (
        ReproductionResult,
        AnalysisResult,
        FixResult,
        ValidationResult,
        ReviewResult
    )
    
    # 1. ReproductionResult
    repro = ReproductionResult(
        success=True,
        error_log=None,
        failing_tests=["test_1"],
        passing_tests=["test_2"],
        test_output="all green",
        repo_path="/repo",
        repro_steps=["step1", "step2"]
    )
    repro_deser = json_to_model(ReproductionResult, model_to_json(repro))
    assert repro_deser.success is True
    assert repro_deser.error_log is None
    assert repro_deser.failing_tests == ["test_1"]
    assert repro_deser.repro_steps == ["step1", "step2"]

    # 2. AnalysisResult
    analysis = AnalysisResult(
        root_cause="Divided by zero",
        affected_code=[{"file": "math.py", "line": 10, "function": "div"}],
        fix_hypothesis="Check denominator",
        impact_analysis="Low risk",
        confidence=0.95
    )
    analysis_deser = json_to_model(AnalysisResult, model_to_json(analysis))
    assert analysis_deser.root_cause == "Divided by zero"
    assert len(analysis_deser.affected_code) == 1
    assert analysis_deser.affected_code[0]["file"] == "math.py"
    assert analysis_deser.confidence == 0.95

    # 3. ValidationResult
    validation = ValidationResult(
        success=False,
        all_tests_pass=False,
        failing_tests_now_pass=[],
        previously_passing_still_pass=["test_x"],
        test_results={"total": 10, "passed": 9, "failed": 1, "errors": 0, "details": "fail info"},
        lint_passed=True,
        lint_output=None,
        constraints_satisfied=False
    )
    val_deser = json_to_model(ValidationResult, model_to_json(validation))
    assert val_deser.success is False
    assert val_deser.test_results["total"] == 10
    assert val_deser.test_results["details"] == "fail info"
    assert val_deser.lint_passed is True

