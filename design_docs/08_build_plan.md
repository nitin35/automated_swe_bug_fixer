# 08 — Build Plan

## 8.1 Overview

This plan builds the system incrementally over **8 milestones**. Each milestone is:
- **Self-contained**: Working code you can run and test
- **Extensible**: Designed so the next milestone can plug in
- **Testable**: Has a clear success criterion

**Total estimated effort:** ~2-3 weeks of focused work (less if you have significant Python async experience).

### Phase Mapping

These 8 milestones map to the 5 development phases from the original design brief:

| Phase (from original brief) | Our Milestones | Key Additions Needed |
|------------------------------|----------------|---------------------|
| **Phase 1: Assisted Bug Fixing** (MVP) | Milestones 0-7 | Single repo, HITL, basic Retrieval, core agents |
| **Phase 2: Multi-file & Collaborative** | Milestone 8+ | Analysis Agent, parallel steps, AST-based call graphs |
| **Phase 3: Continuous Learning** | Post-M8 (future) | Learning loop, playbook synthesis, pattern mining |
| **Phase 4: Proactive Prevention** | Future | Pre-commit hooks, risk prediction, regression test recommendation |
| **Phase 5: Autonomous Platform** | Future | Full autonomy, cross-architecture reasoning, zero human intervention |

---

## Milestone 0: Project Scaffold & Test Harness
**Goal:** A working project skeleton that imports cleanly and has a test suite ready.

**Estimated time:** 1 session

### Structure
```
automated_swe_bug_fixer/
├── design_docs/              # (already exists)
├── src/
│   ├── __init__.py
│   ├── main.py               # Entry point
│   ├── config.py              # Configuration loading
│   ├── models.py              # Data models (from 07_data_models.md)
│   ├── bus.py                 # Message bus (from 03_communication.md)
│   ├── llm.py                 # LLM router (from 05_llm_integration.md)
│   ├── knowledge_base.py      # Knowledge base (from 04_knowledge_base.md)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py            # BaseAgent class
│   │   ├── master.py          # Master Agent
│   │   ├── reproduction.py    # Reproduction Agent
│   │   ├── fix.py             # Fix Generation Agent
│   │   └── validation.py      # Validation Agent
│   └── bug_source/            # Symlink or import from existing
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_bus.py
│   ├── test_llm.py
│   └── test_reproduction.py
├── prompts/                   # LLM prompt templates
├── cache/
│   ├── repos/
│   ├── logs/
│   └── vectors/
├── config.yaml
├── requirements.txt
└── setup.py
```

### Tasks

1. **Create directory structure** (as above)
2. **Write `config.py`**
   - Load from `config.yaml` using `pyyaml` (or just a plain dict for now)
   - Hold model names, timeouts, paths, cost limits
   - Example:
     ```python
     import yaml
     from pathlib import Path

     CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

     def load_config(path=CONFIG_PATH) -> dict:
         with open(path) as f:
             return yaml.safe_load(f)
     ```
3. **Write `models.py`**
   - All dataclasses from [07_data_models.md](07_data_models.md)
   - Include `model_to_json()` / `json_to_model()` helpers
   - Unit tests: test creation, serialization, deserialization

4. **Write `config.yaml`**
   ```yaml
   models:
     lite: "llama3.2:1b"
     medium: "qwen2.5-coder:7b"
     heavy: "llama3.1:8b"
     embedding: "llama3.2:1b"

   timeouts:
     lite: 30
     medium: 120
     heavy: 300

   cost_weights:
     lite: 1
     medium: 5
     heavy: 10

   paths:
     cache_dir: "cache"
     db_path: "swebench_lite.db"
     prompts_dir: "prompts"

   ollama:
     base_url: "http://localhost:11434"

   master:
     max_retries: 2
     daily_cost_limit: 100.0

   hitl:
     required: true
     timeout: 3600          # Seconds to wait for human decision

   service:
     enabled: false         # Enable for daemon mode
     poll_interval: 300
     max_concurrent_runs: 1
   ```

5. **Write `requirements.txt`**
   ```text
   pyyaml>=6.0
   httpx>=0.27.0
   pytest>=8.0
   datasets>=2.14.0
   numpy>=1.24.0
   faiss-cpu>=1.7.0
   ```

6. **Write `src/main.py`** — minimal entry point:
   ```python
   async def main():
       print("Automated SWE Bug Fixer — v0.1")
       # For now, just test that everything imports
       from src.models import RunContext
       print("All imports OK")

   if __name__ == "__main__":
       import asyncio
       asyncio.run(main())
   ```

### Success Criteria
- [ ] `python -m src.main` runs without errors
- [ ] `pytest tests/` passes (all model tests)
- [ ] All imports work cleanly

---

## Milestone 1: Message Bus + BaseAgent
**Goal:** A working communication infrastructure. Agents can send/receive messages.

**Estimated time:** 1 session

### Tasks

1. **Implement `src/bus.py`** — `MessageBus` class
   - `register_agent(name, agent_instance)`
   - `send_directive(directive)`
   - `publish_event(event)`
   - `listen_for(agent_name, event_type=None)`
   - `subscribe(event_type, callback)`
   - `get_history(filter_type=None)`
   - Use `asyncio.Queue` internally
   - (Full spec in [03_communication_system.md](03_communication_system.md))

2. **Implement `src/agents/base.py`** — `BaseAgent`
   - `__init__(self, name, bus, llm, kb)`
   - `run_loop()` — async loop that listens for directives
   - `abstract execute(directive)` — subclasses implement this
   - Error handling: catch exceptions and publish `task.failed` events

3. **Write tests**
   - Test bus: register agents, send directive, receive directive
   - Test bus: publish event, subscribe, verify receipt
   - Test base agent: create mock agent, send directive, verify execution

4. **Create a dummy "EchoAgent"** to verify end-to-end:
   ```python
   class EchoAgent(BaseAgent):
       async def execute(self, directive):
           return {"echo": directive.payload}
   ```

### Success Criteria
- [ ] Bus correctly routes directives to named agents
- [ ] Bus delivers events to subscribers
- [ ] BaseAgent loop works: receives directive → executes → publishes result
- [ ] All tests pass

---

## Milestone 2: LLM Router
**Goal:** System can talk to Ollama and route requests to appropriate models.

**Estimated time:** 1 session

### Tasks

1. **Verify Ollama is running**
   ```bash
   curl http://localhost:11434/api/tags
   ```
   Pull required models:
   ```bash
   ollama pull llama3.2:1b
   ollama pull qwen2.5-coder:7b
   ollama pull llama3.1:8b
   ```

2. **Implement `src/llm.py`** — `LLMRouter` class
   - `query(task_type, system_prompt, user_prompt, tier, ...)`
   - `query_with_retry(...)` — with exponential backoff
   - `get_embedding(text)` — for vector store
   - `get_cost_report()` — summary
   - Auto-tier selection via `_choose_tier(task_type)`
   - (Full spec in [05_llm_integration.md](05_llm_integration.md))

3. **Write a simple test**
   ```python
   async def test_llm_basic():
       router = LLMRouter(load_config())
       response = await router.query(
           task_type="simple_judgment",
           system_prompt="Answer yes or no.",
           user_prompt="Is water wet?",
           tier="lite"
       )
       print(response.text)  # Should print "Yes" or "No"
       assert len(response.text) > 0
       print(f"Model: {response.model}, Cost: {response.cost}")
   ```

4. **Create prompt directory structure**
   ```
   prompts/
     common/
       system_preamble.txt
     fix/
       generate_patch.txt
     reproduction/
       reproduce_bug.txt
     validation/
       run_tests.txt
     analysis/
       root_cause.txt
     review/
       review_patch.txt
   ```
   (For MVP, prompts can be simple. Improve later.)

### Success Criteria
- [ ] `LLMRouter.query()` works with Ollama (all three tiers)
- [ ] `LLMRouter.get_embedding()` works
- [ ] Auto-tier selection maps task types correctly
- [ ] Cost tracking works and accumulates correctly
- [ ] All tests pass

---

## Milestone 3: Knowledge Base (MVP)
**Goal:** System can persist runs, track steps, and cache repos.

**Estimated time:** 1-2 sessions

### Tasks

1. **Implement SQLite store** — `src/knowledge_base.py` or separate module
   - `create_run(issue)` → returns `run_id`
   - `complete_run(run_id, status, patch)`
   - `record_step(run_id, agent, action, status, output)`
   - `record_llm_call(...)`
   - `add_learning(category, content, source_run, source_issue)`
   - `get_learnings(category=None)`
   - Create tables on init (see schema in [04_knowledge_base.md](04_knowledge_base.md))

2. **Implement repo cache**
   - `get_repo_path(repo_name)` → returns path or None
   - `cache_repo(repo_name, local_path)`
   - Simple git clone wrapper:
     ```python
     async def clone_repo(repo_url: str, repo_name: str, base_commit: str) -> str:
         cache_dir = Path("cache/repos") / repo_name.replace("/", "__")
         if cache_dir.exists():
             # Already cloned, just checkout the commit
             run_cmd(["git", "-C", str(cache_dir), "checkout", base_commit])
             return str(cache_dir)
         run_cmd(["git", "clone", repo_url, str(cache_dir)])
         run_cmd(["git", "-C", str(cache_dir), "checkout", base_commit])
         return str(cache_dir)
     ```

3. **Implement FAISSVectorStore** (using `faiss-cpu`)
   - `add(embedding, metadata)` — single vector insert
   - `add_batch(embeddings, metadatas)` — batch insert (more efficient)
   - `search(query_embedding, k=5)` — FAISS-based nearest-neighbor search
   - `get_total_count()` — number of indexed vectors
   - Index persisted to `index.faiss` on disk, metadata to `metadata.pkl`
   - Start with `IndexFlatL2` (exact search, perfect for MVP)
   - See full implementation in `04_knowledge_base.md` §4.3

4. **Test the FAISS store**
   ```python
   import numpy as np

   def test_faiss_store(tmp_path):
       store = FAISSVectorStore(str(tmp_path / "vectors"))

       # Add some test vectors
       store.add([0.1, 0.2, 0.3], {"id": "doc1", "text": "hello"})
       store.add([0.4, 0.5, 0.6], {"id": "doc2", "text": "world"})
       store.add([0.7, 0.8, 0.9], {"id": "doc3", "text": "foo"})

       assert store.get_total_count() == 3

       # Search with a query vector close to doc2
       results = store.search([0.41, 0.51, 0.61], k=2)
       assert len(results) == 2
       assert results[0]["id"] == "doc2"  # Closest match
       assert results[0]["similarity"] > 0.9  # High similarity

       # Persistence test
       store2 = FAISSVectorStore(str(tmp_path / "vectors"))
       assert store2.get_total_count() == 3
       results2 = store2.search([0.41, 0.51, 0.61], k=1)
       assert results2[0]["id"] == "doc2"
   ```

4. **Wire everything into a `KnowledgeBase` facade class**
   - `db`, `vectors`, `cache` attributes
   - Convenience methods: `find_similar_issues()`, `record_run()`

### Success Criteria
- [ ] SQLite tables created on first run
- [ ] Creating and completing a run works
- [ ] Recording steps and LLM calls works
- [ ] Repo cloning/caching works
- [ ] FAISSVectorStore add/search/persistence works
- [ ] FAISS index survives save/load cycle (serialization test)
- [ ] Batch add works correctly
- [ ] Empty store returns empty results (edge case) without crashing
- [ ] All tests pass

---

## Milestone 4: Reproduction Agent (MVP)
**Goal:** Agent that can clone a repo, set it up, and reproduce a bug.

**Estimated time:** 1-2 sessions

### Tasks

1. **Implement `src/agents/reproduction.py`**
   - Extends `BaseAgent`
   - `execute(directive)` handles `action="reproduce_bug"`
   - Steps:
     a. Clone repo at base_commit (use KB cache)
     b. Install dependencies (pip)
     c. Run failing tests via `pytest`
     d. Parse output to extract failures
     e. Return `ReproductionResult`
   - Use `asyncio.create_subprocess_exec` for subprocess calls
   - Set strict timeouts (configurable)
   - Handle common failure modes (repo not found, build fails, test not found)

   ```python
   class ReproductionAgent(BaseAgent):
       async def execute(self, directive: Directive) -> dict:
           params = directive.payload
           repo = params["repo"]
           base_commit = params["base_commit"]

           # Step 1: Clone
           repo_path = await self.kb.cache.get_repo(
               repo_name=repo,
               repo_url=f"https://github.com/{repo}",
               commit=base_commit
           )

           # Step 2: Install
           await self._run_cmd(["pip", "install", "-e", "."], cwd=repo_path)

           # Step 3: Run failing tests
           fail_tests = json.loads(params.get("fail_to_pass", "[]"))
           result = await self._run_pytest(repo_path, fail_tests)

           return ReproductionResult(
               success=result.returncode != 0,  # Tests SHOULD fail
               error_log=result.stderr,
               failing_tests=self._parse_failures(result.stdout),
               ...
           ).__dict__
   ```

2. **Test with the test issue** (from `SWEBenchLiteSource.get_test_issue()`)
   ```python
   async def test_reproduce_test_issue():
       agent = ReproductionAgent(...)
       issue = SWEBenchLiteSource().get_test_issue()
       directive = Directive(
           target="reproduction",
           action="reproduce_bug",
           message_id="test-1",
           payload={
               "repo": "nitin35/test_bug_fix",
               "base_commit": "9f611af203a546fd9fed83e5d3d8f9a7510325f2",
               "fail_to_pass": '["test_calculator.py::test_divide"]',
           }
       )
       result = await agent.execute(directive)
       assert result["success"] == True  # Bug was reproduced
       assert "test_divide" in str(result["failing_tests"])
   ```
   **Note:** The test repo `nitin35/test_bug_fix` is a real GitHub repo. If it doesn't exist, create a minimal test repo locally.

3. **Error handling**
   - Timeout: kill subprocess after N seconds
   - Clone failure: return error, Master can skip to Retrieval
   - No tests found: parse project structure to find test files

### Success Criteria
- [ ] Reproduction Agent can clone a repo
- [ ] Can install dependencies (pip install)
- [ ] Can run pytest and parse results
- [ ] Correctly identifies failing tests
- [ ] Handles timeouts gracefully
- [ ] Works with the hardcoded test issue

---

## Milestone 5: Fix Generation Agent (MVP)
**Goal:** Agent that generates a git patch to fix the bug.

**Estimated time:** 1-2 sessions

### Tasks

1. **Implement `src/agents/fix.py`**
   - Extends `BaseAgent`
   - Handle `action="generate_fix"`
   - Reads problem statement, error log, code context
   - Sends a well-crafted prompt to the LLM (medium tier, code model)
   - Parses the LLM response to extract a valid `diff --git` patch
   - Applies the patch to the repo (using `git apply`)
   - Returns the patch and application status

2. **Create prompt template** `prompts/fix/generate_patch.txt`
   ```text
   System: You are an expert Python developer fixing a bug.
   Given the problem, error, and code, generate a minimal git patch.

   Problem:
   {problem_statement}

   Error:
   {error_log}

   Code context:
   {code_context}

   Instructions:
   - Output ONLY the git diff (diff --git format).
   - The patch must be minimal and correct.
   - Include proper error handling.
   ```

3. **Implement patch extraction logic**
   ```python
   def extract_patch(llm_response: str) -> str | None:
       """Extract the git diff patch from LLM response."""
       # Look for diff --git ... blocks
       lines = llm_response.split('\n')
       in_diff = False
       patch_lines = []
       for line in lines:
           if line.startswith('diff --git'):
               in_diff = True
           if in_diff:
               patch_lines.append(line)
       return '\n'.join(patch_lines) if patch_lines else None
   ```

4. **Implement patch application**
   ```python
   async def apply_patch(repo_path: str, patch: str) -> bool:
       """Apply a git patch to the repo."""
       proc = await asyncio.create_subprocess_exec(
           'git', 'apply', '--check', '-',
           stdin=asyncio.subprocess.PIPE,
           stdout=asyncio.subprocess.PIPE,
           stderr=asyncio.subprocess.PIPE,
           cwd=repo_path
       )
       stdout, stderr = await proc.communicate(patch.encode())
       if proc.returncode != 0:
           return False  # Patch doesn't apply cleanly
       # Actually apply
       proc = await asyncio.create_subprocess_exec(
           'git', 'apply', '-',
           stdin=asyncio.subprocess.PIPE,
           cwd=repo_path
       )
       await proc.communicate(patch.encode())
       return proc.returncode == 0
   ```

5. **Test with the test issue**
   ```python
   async def test_fix_test_issue():
       agent = FixGenerationAgent(...)
       # First reproduce to get error context
       repo_path = await clone_test_repo()
       directive = Directive(
           target="fix",
           action="generate_fix",
           payload={
               "repo_path": repo_path,
               "problem_statement": issue["problem_statement"],
               "error_log": "ZeroDivisionError: division by zero",
               "code_context": {"calculator.py": open(f"{repo_path}/calculator.py").read()},
           }
       )
       result = await agent.execute(directive)
       assert result["success"] == True
       assert "diff --git" in result["patch"]
       # Verify it applies
       applied = await apply_patch(repo_path, result["patch"])
       assert applied == True
   ```

6. **Build a minimal Retrieval Agent (grep-based)**
   - Even a simple `grep -r "keyword" src/` wrapper dramatically improves Fix Agent accuracy
   - Create `src/agents/retrieval.py` with a `search_code` action:
     ```python
     class RetrievalAgent(BaseAgent):
         async def execute(self, directive):
             params = directive.payload
             query = params.get("query", "")
             repo_path = params.get("repo_path")
             # Extract keywords from the query
             keywords = self._extract_keywords(query)
             results = {}
             for keyword in keywords:
                 proc = await asyncio.create_subprocess_exec(
                     'grep', '-r', '-l', keyword, '--include=*.py', '.',
                     stdout=asyncio.subprocess.PIPE, cwd=repo_path
                 )
                 stdout, _ = await proc.communicate()
                 for path in stdout.decode().split('\n'):
                     if path.strip():
                         with open(f"{repo_path}/{path}") as f:
                             results[path] = f.read()[:2000]  # First 2000 chars
             return {"relevant_files": results}
     ```

### Success Criteria
- [ ] Fix Agent generates valid git patches
- [ ] Patch extraction works (handles LLM markdown noise)
- [ ] Patch application works (`git apply`)
- [ ] Works correctly on the test issue (adds zero-division check)
- [ ] Handles LLM failures gracefully (retry)

---

## Milestone 6: Validation Agent (MVP)
**Goal:** Agent that runs tests to verify the fix works.

**Estimated time:** 1 session

### Tasks

1. **Implement `src/agents/validation.py`**
   - Extends `BaseAgent`
   - Handle `action="validate_fix"`
   - Steps:
     a. Ensure the patch is applied to the repo
     b. Run the previously failing tests (should pass now)
     c. Run the previously passing tests (should still pass)
     d. Run linting (optional, configurable)
     e. Return `ValidationResult`

2. **Implement pytest runner**
   ```python
   async def run_tests(repo_path: str, test_names: list[str]) -> dict:
       """Run specific pytest tests and return results."""
       proc = await asyncio.create_subprocess_exec(
           'pytest', *test_names, '-v', '--tb=short',
           stdout=asyncio.subprocess.PIPE,
           stderr=asyncio.subprocess.PIPE,
           cwd=repo_path
       )
       stdout, stderr = await proc.communicate()

       # Parse output
       passed = []
       failed = []
       for line in stdout.decode().split('\n'):
           if ' PASSED' in line:
               passed.append(line.split()[0])
           elif ' FAILED' in line:
               failed.append(line.split()[0])

       return {
           "returncode": proc.returncode,
           "stdout": stdout.decode(),
           "stderr": stderr.decode(),
           "passed": passed,
           "failed": failed,
       }
   ```

3. **Test with the test issue**
   ```python
   async def test_validation():
       agent = ValidationAgent(...)
       repo_path = await prepare_repo_with_fix()  # Repo with fix already applied
       directive = Directive(
           target="validation",
           action="validate_fix",
           payload={
               "repo_path": repo_path,
               "failing_tests": ["test_calculator.py::test_divide"],
               "passing_tests": [...all other tests...],
           }
       )
       result = await agent.execute(directive)
       assert result["all_tests_pass"] == True
       assert "test_divide" in result["failing_tests_now_pass"]
   ```

### Success Criteria
- [ ] Validation Agent runs specified tests
- [ ] Correctly identifies passing/failing tests
- [ ] Compares against FAIL_TO_PASS and PASS_TO_PASS lists
- [ ] Reports clear results
- [ ] Works on the test issue (test_divide now passes, other tests still pass)

---

## Milestone 7: Master Agent + Full MVP Pipeline
**Goal:** The complete MVP pipeline: Master → Reproduction → Fix → Validation.

**Estimated time:** 2 sessions

### Tasks

1. **Implement `src/agents/master.py`** — `MasterAgent`
   - Extends `BaseAgent`
   - `async run(issue: dict) -> RunResult`
   - Dynamic orchestration (initially simple rule-based):

     ```python
     async def build_plan(self, context: RunContext) -> list[PlanStep]:
         """Build a plan for the current issue."""
         plan = []

         # Step 0: Lightweight Retrieval (grep code context to aid Fix agent)
         if "retrieval" in self.agents:
             plan.append(PlanStep(
                 step_id="retr-0",
                 agent="retrieval",
                 action="search_code",
                 params={
                     "repo": context.issue["repo"],
                     "query": context.issue["problem_statement"],
                 },
                 depends_on=[],
             ))

         # Step 1: Reproduce
         plan.append(PlanStep(
             step_id="repro-1",
             agent="reproduction",
             action="reproduce_bug",
             params={
                 "repo": context.issue["repo"],
                 "base_commit": context.issue["base_commit"],
                 "fail_to_pass": context.issue["fail_to_pass"],
                 "environment_setup_commit": context.issue.get("environment_setup_commit"),
             },
             depends_on=["retr-0"] if "retrieval" in self.agents else [],
         ))
         # Step 2: Fix
         plan.append(PlanStep(
             step_id="fix-1",
             agent="fix",
             action="generate_fix",
             params={},  # Filled in based on reproduction output
             depends_on=["repro-1"],
         ))
         # Step 3: Validate
         plan.append(PlanStep(
             step_id="val-1",
             agent="validation",
             action="validate_fix",
             params={},
             depends_on=["fix-1"],
         ))
         return plan
     ```

   - **Execution loop:**
     ```python
     async def run(self, issue: dict) -> RunResult:
         context = RunContext(run_id=uuid4().hex, instance_id=issue["instance_id"], issue=issue)
         plan = await self.build_plan(context)

         while not self._plan_complete(plan):
             ready = [s for s in plan if s.status == "pending" and
                      all(p.status == "completed" for p in plan if p.step_id in s.depends_on)]

             for step in ready:
                 step.status = "running"
                 directive = Directive(
                     target=step.agent, action=step.action,
                     message_id=step.step_id, payload=step.params,
                     timeout=step.timeout
                 )
                 await self.bus.send_directive(directive)

             # Wait for task completion events
             event = await self._wait_for_agent_completion(plan)
             self._process_event(event, plan, context)

             # Check for failures and adapt
             if self._should_replan(context):
                 plan = await self.build_plan(context)

         context.status = RunStatus.SUCCESS if context.validation_passed else RunStatus.FAILED

         # HITL: pause for human approval if validation passed
         if context.hitl_required and context.validation_passed:
             await self.bus.publish_event(Event(
                 source=self.name, type="hitl.review_needed",
                 message_id=context.run_id,
                 payload={"patch": context.generated_patch, "test_results": context.test_details}
             ))
             human_event = await self.bus.wait_for_event(
                 event_type="hitl.decision", timeout=config.hitl_timeout
             )
             if human_event and human_event.payload.get("decision") == "rejected":
                 context.hitl_approved = False
                 context.status = RunStatus.HITL_REJECTED
             else:
                 context.hitl_approved = True

         await self.kb.record_run(context)
         return context
     ```

2. **Wire everything together in `src/main.py`**
   ```python
   async def main():
       config = load_config()
       bus = MessageBus()
       llm = LLMRouter(config)
       kb = KnowledgeBase(...)

       # Create agents
       master = MasterAgent("master", bus, llm, kb)
       reproduction = ReproductionAgent("reproduction", bus, llm, kb)
       fix = FixGenerationAgent("fix", bus, llm, kb)
       validation = ValidationAgent("validation", bus, llm, kb)

       # Optional: register Retrieval if implemented
       # from src.agents.retrieval import RetrievalAgent
       # retrieval = RetrievalAgent("retrieval", bus, llm, kb)
       # master.register_agent("retrieval", retrieval)

       # Get issue
       source = SWEBenchLiteSource()
       issue = source.get_test_issue()  # Use test issue for development

       # Run
       result = await master.run(issue)

       # Report
       print(f"\n{'='*60}")
       print(f"Run {result.run_id}: {result.status.value}")
       print(f"Duration: {result.duration_seconds:.1f}s")
       print(f"Total LLM calls: {result.total_llm_calls}")
       print(f"Total cost: {result.total_cost:.2f} units")
       if result.generated_patch:
           print(f"\nGenerated patch:\n{result.generated_patch[:500]}...")
       print(f"{'='*60}")

       # Save run
       if result.status == RunStatus.SUCCESS:
           source.mark_as_solved(issue["instance_id"])
           print(f"Issue {issue['instance_id']} marked as solved!")
   ```

3. **Run the full pipeline on the test issue**
   ```bash
   python -m src.main
   ```

4. **Test error recovery**
   - What happens if reproduction fails? (Master should log, report failure)
   - What happens if fix generation fails? (Master should retry)
   - What happens if validation fails? (Master should loop back to fix)

5. **HITL integration**
   - Implement `hitl.review_needed` / `hitl.decision` event handling in Master
   - Write a simple CLI callback that prints the patch and asks for approval
   - Test both approval and rejection paths

### Success Criteria
- [ ] Full MVP pipeline runs end-to-end on the test issue
- [ ] Master correctly builds and executes a plan
- [ ] Reproduction → Fix → Validation executes in order
- [ ] Results are stored in the knowledge base
- [ ] The test issue is fixed (zero-division check added, tests pass)
- [ ] Error scenarios are handled gracefully (not crashing)

---

## Milestone 8: Real Dataset + Analysis Agent + Polishing
**Goal:** System works on real SWE-bench Lite issues. Analysis Agent added.

**Estimated time:** 2-3 sessions

### Tasks

1. **Add Analysis Agent** (`src/agents/analysis.py`)
   - Full root cause analysis using heavy LLM model
   - Reads reproduction output + code context
   - Generates root cause, impact analysis, fix hypothesis
   - Master includes it in the plan: Reproduction → Analysis → Fix → Validation

2. **Run against real SWE-bench Lite issues**
   - Start with 5-10 easy issues (select by repo size, test count)
   - Log results, fix rate, cost per issue
   - Identify patterns of failure

3. **Improve prompts based on real results**
   - Analyze where the system fails
   - Add better examples to prompts (few-shot prompting)
   - Add system preamble with coding standards

4. **Add cost tracking and reporting**
   - Cost report at end of each run
   - Log to SQLite `llm_calls` table
   - Summary statistics per session

5. **Add the Retrival and Review Agents as optional add-ons**
   - Retrieval Agent: simple file search + similar issue lookup
   - Review Agent: LLM-based code review on generated patch

6. **Add AST-based code understanding (Retrieval Agent upgrade)**
   - Use Python's `ast` module to parse repo source and build a call graph
   - Enhance Retrieval Agent to return function-level context (who calls what)
   - Integrate with Analysis Agent for more precise root cause localization

7. **Implement the 4-pillar code understanding strategy** (from original design brief)
   - **Structural**: Add AST parsing to map functions, classes, and dependencies
   - **Semantic**: Enhance vector store with function-level code embeddings
   - **Runtime**: Correlate stack trace locations with AST-derived code locations
   - **Historical**: Mine past successful patches for reusable fix patterns
   - See `04_knowledge_base.md` §4.6 for full details on each pillar

8. **Add service mode**
   - Implement `MasterService` wrapper (see `02_agent_orchestration.md`)
   - Add `poll_interval`, `max_concurrent_runs`, `hitl_timeout` to config
   - Test running 2-3 issues in sequence via the service loop

8. **Improve error handling and logging**
   - Structured logging (JSON format for machine parsing)
   - Better timeout handling
   - Parallel execution of independent steps

### Success Criteria
- [ ] Analysis Agent works and improves fix quality
- [ ] System runs on real SWE-bench Lite issues
- [ ] At least 30-40% fix rate on easy issues (reasonable for MVP)
- [ ] Cost/effort tracking works
- [ ] All 6 agents are implemented (even if basic)
- [ ] Service mode runs without errors
- [ ] HITL flow works (approve and reject paths)

---

## 8.2 Summary Roadmap

### Phase Mapping to Original Design

| Their Phase | Our Milestones | Status |
|-------------|----------------|--------|
| Phase 1: Assisted Bug Fixing | Milestones 0-7 | MVP target |
| Phase 2: Multi-file & Collaborative | Milestone 8 | Next step |
| Phase 3: Continuous Learning | Post-Milestone 8 | Future work |
| Phase 4: Proactive Prevention | Future | Future work |
| Phase 5: Autonomous Platform | Future | Future work |

```
Milestone 0: Project scaffold & test harness       [Day 1]
Milestone 1: Message Bus + BaseAgent               [Day 2]
Milestone 2: LLM Router                            [Day 3]
Milestone 3: Knowledge Base (MVP)                  [Day 4-5]
Milestone 4: Reproduction Agent                    [Day 5-6]
Milestone 5: Fix Generation Agent                  [Day 7-8]
Milestone 6: Validation Agent                      [Day 9]
Milestone 7: Master Agent + Full MVP Pipeline      [Day 10-11]
Milestone 8: Real Dataset + Analysis + Polish      [Day 12-15]
```

## 8.3 Quick Wins & Pitfalls to Avoid

### Quick Wins
- Start with the test issue (calculator.py) — it's simple and fast to iterate on
- Use `llama3.2:1b` for all model calls during development (faster iteration)
- Mock the LLM in unit tests (return canned responses) to test logic without network calls
- Use `asyncio.gather` for independent operations (e.g., cloning + analysis)
- **Implement a minimal Retrieval Agent early** — even a `grep`-based file finder dramatically improves Fix Agent accuracy
- **Keep HITL simple** — a CLI `input()` prompt is fine for MVP; upgrade to a web UI later

### Pitfalls
- **Don't over-engineer the bus**: Start simple, add features only when needed
- **Don't ignore subprocess management**: Use `asyncio.create_subprocess_exec` with timeouts
- **Don't hardcode paths**: Use config everywhere
- **Don't skip error handling**: Every async call, every subprocess, every LLM call needs error handling
- **Don't make the LLM prompts too complex initially**: Start simple, improve based on failures
- **Don't run on real issues until the test issue works perfectly**

## 8.4 Testing Strategy

| Layer | Tool | What to Test |
|-------|------|-------------|
| Unit | pytest | Data models, bus, patch extraction, test output parsing |
| Integration | pytest + asyncio | LLM routing, subprocess commands, repo cloning |
| End-to-end | Script | Full pipeline on test issue |
| Benchmark | Script | Fix rate, cost, duration on real issues |