# 02 — Agent Orchestration

## 2.1 Master Agent Responsibilities

The Master Agent is the brain of the system. It:

1. **Accepts an issue** from `SWEBenchLiteSource` (or any other source)
2. **Plans the workflow** — decides which agents to invoke, in what order, with what parameters
3. **Executes the plan** — dispatches tasks to sub-agents via the message bus
4. **Monitors progress** — listens for events from sub-agents
5. **Adapts dynamically** — can change the plan based on intermediate results (e.g., if reproduction fails, try retrieval for context first)
6. **Handles errors** — retries, fallbacks, escalation
7. **Supports Human-in-the-Loop (HITL)** — can pause before finalizing a fix to request human review and approval
8. **Records outcomes** — writes results to the knowledge base
9. **Service mode** — can run as a long-lived daemon, polling issue sources on a schedule

## 2.2 Dynamic Orchestration Model

The Master does **not** use a hard-coded pipeline. Instead, it maintains a **plan** — a list of steps — that it builds and modifies as the session progresses.

### Plan Representation

```python
@dataclass
class PlanStep:
    step_id: str                  # Unique identifier for this step
    agent: str                    # Agent name (e.g., "reproduction", "fix")
    action: str                   # Action to perform
    params: dict                  # Parameters for the agent
    depends_on: list[str]        # Step IDs that must complete first
    status: str = "pending"      # pending | running | completed | failed | skipped
    timeout: int = 300            # Max execution time in seconds
    retries: int = 0              # Current retry count
    max_retries: int = 2          # Maximum retries allowed
    result: Any = None
    error: Optional[str] = None   # Error message if failed
```

### Planning Strategies

The Master can plan in several ways:

**Strategy A: Rule-based (MVP)**
- Simple if-then rules encoded in Python
- E.g.: Build plan with Retrieval (grep code context) → Reproduction (collect errors) → Fix (generate patch) → Validation (run tests) → HITL (human review)
- If an agent is unavailable or skipped, the plan shortens accordingly
- Fast, deterministic, easy to debug

**Strategy B: LLM-based (Advanced)**
- Master asks an LLM (heavy model) to analyze the issue and propose a plan
- The LLM returns a sequence of steps
- Master executes the plan, and can go back to the LLM for re-planning if something fails

**Strategy C: Hybrid (Recommended)**
- Start with rule-based defaults
- If a step fails or the issue is complex, escalate to LLM for re-planning

## 2.3 Agent Lifecycle

Each agent follows this lifecycle:

```
REGISTERED → RUNNING → COMPLETED | FAILED
                ↑                    |
                └──── (retry) ──────┘
```

- **REGISTERED**: Agent is known to the system (registered on the bus)
- **RUNNING**: Agent is executing a directive
- **COMPLETED**: Agent finished successfully
- **FAILED**: Agent encountered an error (Master may retry or skip)

## 2.4 Master Agent Pseudocode

```python
class MasterAgent:
    """Orchestrates the bug-fix pipeline. Does NOT extend BaseAgent —
    it drives the plan loop rather than listening for directives."""

    def __init__(self, message_bus, knowledge_base, llm_router):
        self.bus = message_bus
        self.kb = knowledge_base
        self.llm = llm_router
        self.agents = {}  # name -> Agent instance

    def register_agent(self, name, agent_instance):
        self.agents[name] = agent_instance

    async def run(self, issue: dict) -> RunResult:
        # 1. Create context for this run
        context = RunContext(
            run_id=uuid4().hex,
            instance_id=issue["instance_id"],
            issue=issue
        )

        # 2. Check knowledge base for similar past issues
        similar = await self.kb.find_similar_issues(issue)
        context.similar_issues = similar

        # 3. Build initial plan
        plan = await self.build_plan(context)

        # 4. Execute plan dynamically
        while not plan.is_complete():
            ready_steps = plan.get_ready_steps()
            for step in ready_steps:
                step.status = "running"
                agent = self.agents[step.agent]
                # Dispatch via message bus
                directive = Directive(
                    target=step.agent,
                    action=step.action,
                    message_id=step.step_id,
                    payload=step.params,
                    timeout=step.timeout,
                    run_id=context.run_id,
                )
                await self.bus.send_directive(directive)

            # Wait for results (via bus events)
            result = await self.bus.listen_for("master", timeout=300)
            self._handle_result(plan, result, context)

            # Optionally re-plan
            if self.should_replan(result, context):
                plan = await self.build_plan(context)

        # 5. Human-in-the-Loop check
        if context.hitl_required and context.validation_passed:
            await self.bus.publish_event(Event(
                source=self.name, type="hitl.review_needed",
                message_id=context.run_id,
                payload={
                    "patch": context.generated_patch,
                    "test_results": context.test_details,
                    "instance_id": context.instance_id,
                }
            ))
            # Wait for human decision
            human_event = await self.bus.wait_for_event(
                event_type="hitl.decision",
                timeout=config.hitl_timeout
            )
            if human_event and human_event.payload.get("decision") == "rejected":
                context.hitl_approved = False
                context.status = RunStatus.HITL_REJECTED
            else:
                context.hitl_approved = True

        # 6. Record outcome
        await self.kb.record_run(context)
        return context.result
```

## 2.5 Dynamic Adaptation Examples

| Situation | Master's Response |
|-----------|-------------------|
| Reproduction fails (can't build) | Skip to Retrieval Agent to find build instructions |
| Fix Agent produces invalid patch | Retry with more context from Analysis Agent |
| Validation finds failing tests | Loop back to Fix Agent with test output |
| All tests pass | Proceed to Review Agent |
| Review finds security issue | Loop back to Fix Agent with review comments |
| Multiple retries fail | Mark as unsolved, log full trace for learning |

### Re-Planning Logic (Rule-Based MVP)

```python
def _should_replan(self, event, context: RunContext) -> bool:
    """Decide whether to rebuild the plan based on an agent result."""
    if event.type == "task.failed":
        failed_agent = event.source
        step = self._find_step(event.message_id)
        if step and step.retries < step.max_retries:
            step.retries += 1
            step.status = "pending"  # Re-queue the same step
            return False             # No full re-plan needed
        if failed_agent == "reproduction" and "retrieval" in self.agents:
            # Reproduction failed — try retrieval for build context
            return True
        if failed_agent == "fix":
            # Fix failed — escalate to analysis for better context
            return True
    if event.type == "task.completed" and event.source == "validation":
        if not event.payload.get("all_tests_pass"):
            # Tests still failing — loop back to fix with test output
            return True
    return False

def _handle_result(self, plan, event, context: RunContext):
    """Process an agent completion/failure event."""
    step = self._find_step(event.message_id)
    if not step:
        return
    if event.type == "task.completed":
        step.status = "completed"
        step.result = event.payload
        self._update_context(context, step, event.payload)
    elif event.type == "task.failed":
        step.status = "failed"
        step.error = event.payload.get("error", "Unknown error")
```

## 2.6 Concurrency Model (MVP)

For the MVP, agents run **sequentially** within the Master's event loop. This keeps things simple:

```
Master: step1 → wait → handle → step2 → wait → handle → ...
```

Later, independent steps can run in parallel (e.g., Retrieval + Reproduction could run simultaneously).

## 2.7 Service Mode (Long-Running Daemon)

Beyond single-run mode, the Master can run as a **service** that continuously polls for new issues:

```python
class MasterService:
    """Wraps MasterAgent into a long-running daemon."""

    def __init__(self, master_agent, issue_source, config):
        self.master = master_agent
        self.source = issue_source
        self.poll_interval = config.get("poll_interval", 300)  # seconds
        self.max_concurrent = config.get("max_concurrent_runs", 1)
        self.active_runs: dict[str, asyncio.Task] = {}

    async def run_forever(self):
        """Main service loop."""
        while True:
            if len(self.active_runs) < self.max_concurrent:
                issue = self.source.get_issue()
                if issue:
                    task = asyncio.create_task(
                        self.master.run(issue)
                    )
                    self.active_runs[issue["instance_id"]] = task
                    task.add_done_callback(
                        lambda t, iid=issue["instance_id"]: self._cleanup(t, iid)
                    )
            await asyncio.sleep(self.poll_interval)

    def _cleanup(self, task, instance_id):
        self.active_runs.pop(instance_id, None)
```

**Configuration for service mode:**
```yaml
service:
  enabled: true
  poll_interval: 300          # Check every 5 minutes
  max_concurrent_runs: 2      # Fix up to 2 bugs in parallel
  hitl_timeout: 3600          # Wait 1 hour for human review
  hitl_required: true         # Require human approval before finalizing
```

## 2.8 Agent Registry

The Master maintains a registry of all available agents:

```python
agent_registry = {
    "retrieval": RetrievalAgent,
    "reproduction": ReproductionAgent,
    "analysis": AnalysisAgent,
    "fix": FixGenerationAgent,
    "validation": ValidationAgent,
    "review": ReviewAgent,
}
```

Each agent class implements:

```python
class BaseAgent(ABC):
    """Base class for all sub-agents (NOT the Master)."""

    def __init__(self, name: str, bus: MessageBus, llm: LLMRouter, kb: KnowledgeBase):
        self.name = name
        self.bus = bus
        self.llm = llm
        self.kb = kb
        bus.register_agent(name, self)

    @abstractmethod
    async def execute(self, directive: Directive) -> dict:
        """Execute a task given by the Master. Returns a result dict."""
        pass

    @property
    def capabilities(self) -> list[str]:
        """What this agent can do (e.g., ["code_search", "similar_issue_lookup"])."""
        return []
```