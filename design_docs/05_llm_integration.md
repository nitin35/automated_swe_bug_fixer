# 05 — LLM Integration

## 5.1 Design Principles

- **Model-agnostic:** The system should work the same regardless of which model is underneath
- **Task-appropriate routing:** Simple tasks use small/fast models; complex tasks use large/slow models
- **Cost-aware:** Every call is tracked; the system can refuse to proceed if costs exceed thresholds
- **Observable:** Every prompt, response, and token count is logged

## 5.2 Model Tiers

We define three tiers, mapping to Ollama models:

| Tier | Example Model | Use Case | Speed | Quality |
|------|--------------|----------|-------|---------|
| **Lite** | `llama3.2:1b` | Classification, formatting, keyword extraction, simple yes/no decisions | Fastest | Low |
| **Medium** | `qwen2.5-coder:7b` or `codellama:7b` | Code generation, code analysis, test writing, patch generation | Fast | Good |
| **Heavy** | `llama3.1:8b` or `qwen2.5:14b` | Planning, root cause analysis, complex reasoning, security review | Slow | Best |

**Configuration (config.yaml or env vars):**

```yaml
models:
  lite: "llama3.2:1b"
  medium: "qwen2.5-coder:7b"
  heavy: "llama3.1:8b"
  embedding: "llama3.2:1b"  # For vector embeddings

timeouts:
  lite: 30
  medium: 120
  heavy: 300

cost_weights:  # Relative "cost" units (since all local for now)
  lite: 1
  medium: 5
  heavy: 10
```

## 5.3 LLM Router

```python
class LLMRouter:
    """
    Routes LLM requests to the appropriate model based on task type.
    All models are accessed via Ollama's HTTP API.
    """

    def __init__(self, config: dict, ollama_base_url: str = "http://localhost:11434"):
        self.config = config
        self.base_url = ollama_base_url
        self.call_history: list[LLMCallRecord] = []
        self.total_cost: float = 0.0
        self.daily_cost_limit: float = config.get("daily_cost_limit", 100.0)

    async def query(
        self,
        task_type: str,
        system_prompt: str,
        user_prompt: str,
        tier: str = "auto",        # "lite" | "medium" | "heavy" | "auto"
        temperature: float = 0.2,
        max_tokens: int = 2048,
        agent_name: str = "unknown",
        run_id: str = None,
    ) -> LLMResponse:
        """
        Send a query to the appropriate LLM.

        Args:
            task_type: What kind of task (planning, coding, analysis, review, etc.)
            tier: Explicit model tier, or "auto" to let the router decide
            ...
        """
        if tier == "auto":
            tier = self._choose_tier(task_type)

        model = self.config["models"][tier]
        timeout = self.config["timeouts"][tier]

        # Build request
        payload = {
            "model": model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            self._record_call(model, task_type, 0, 0, False, str(e), agent_name, run_id)
            raise LLMError(f"Ollama request failed: {e}") from e

        duration = int((time.time() - start_time) * 1000)

        # Parse response
        result = data.get("response", "")
        tokens_in = data.get("prompt_eval_count", 0)
        tokens_out = data.get("eval_count", 0)

        self._record_call(model, task_type, tokens_in, tokens_out, True, None, agent_name, run_id)

        cost = self._calculate_cost(tier, tokens_in, tokens_out)
        self.total_cost += cost

        return LLMResponse(
            text=result.strip(),
            model=model,
            tier=tier,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            duration_ms=duration,
        )

    def _choose_tier(self, task_type: str) -> str:
        """Map task types to model tiers."""
        tier_map = {
            # Lite tasks
            "classify": "lite",
            "format": "lite",
            "extract_keywords": "lite",
            "simple_judgment": "lite",

            # Medium tasks
            "generate_code": "medium",
            "generate_patch": "medium",
            "analyze_code": "medium",
            "write_test": "medium",
            "parse_error": "medium",

            # Heavy tasks
            "plan": "heavy",
            "root_cause_analysis": "heavy",
            "security_review": "heavy",
            "complex_reasoning": "heavy",
            "design": "heavy",
        }
        return tier_map.get(task_type, "medium")

    def _calculate_cost(self, tier: str, tokens_in: int, tokens_out: int) -> float:
        """Calculate relative cost units."""
        weight = self.config["cost_weights"][tier]
        total_tokens = tokens_in + tokens_out
        return (total_tokens / 1000) * weight  # Cost per 1K tokens

    def _record_call(self, model, task_type, tokens_in, tokens_out,
                     success, error, agent_name, run_id):
        """Record the call for tracking."""
        record = LLMCallRecord(
            model=model,
            task_type=task_type,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            success=success,
            error=error,
            agent_name=agent_name,
            run_id=run_id,
            timestamp=time.time(),
        )
        self.call_history.append(record)

    async def get_embedding(self, text: str) -> list[float]:
        """Get text embedding from Ollama."""
        model = self.config["models"]["embedding"]
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": text}
            )
            response.raise_for_status()
            return response.json()["embedding"]

    def get_cost_report(self) -> dict:
        """Return a summary of costs for the current session."""
        return {
            "total_cost": self.total_cost,
            "total_calls": len(self.call_history),
            "by_tier": {
                tier: sum(1 for c in self.call_history if c.model.startswith(tier))
                for tier in ["llama3.2:1b", "qwen2.5-coder:7b", "llama3.1:8b"]
            },
            "by_agent": {
                agent: sum(1 for c in self.call_history if c.agent_name == agent)
                for agent in set(c.agent_name for c in self.call_history)
            },
        }
```

## 5.4 Prompt Management

Prompts are stored as templates, not hard-coded strings:

### Prompt Templates (prompts/ directory)

```
prompts/
  fix/
    generate_patch.txt       # Template for Fix Agent
    generate_patch_v2.txt    # Versioned templates
  reproduction/
    reproduce_bug.txt
  validation/
    run_tests.txt
  common/
    system_preamble.txt      # Shared system message
    thinking_framework.txt   # Step-by-step thinking guide
```

### Example Template (Jinja2-like, using f-strings)

```python
# prompts/fix/generate_patch.txt

System: You are a skilled software engineer fixing a bug.
Given the problem statement and error logs, generate a git patch.

Problem: {problem_statement}

Error Log: {error_log}

Repository structure:
{repo_structure}

Relevant code context:
{code_context}

Instructions:
1. Analyze the root cause of the bug.
2. Generate a minimal, correct fix.
3. Output ONLY the git diff patch (diff --git format).
4. The patch MUST be valid and directly applicable.
```

## 5.5 Error Handling & Retries

```python
class LLMError(Exception): ...

class LLMRouter:
    async def query_with_retry(self, ..., retries=2, fallback_tier=None):
        """Query with automatic retry and optional fallback to lower tier."""
        last_error = None
        for attempt in range(1 + retries):
            try:
                return await self.query(...)
            except LLMError as e:
                last_error = e
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    if fallback_tier and attempt == retries:
                        # Fall back to a lower tier on last retry
                        tier = fallback_tier
        raise last_error
```

## 5.6 Usage Example

```python
router = LLMRouter(config)

# Analysis agent requests root cause analysis
response = await router.query(
    task_type="root_cause_analysis",
    system_prompt="You are a debugging expert...",
    user_prompt=f"Analyze this error: {error_log}",
    tier="auto",  # Router picks "heavy"
    agent_name="analysis",
    run_id=current_run_id,
)

print(response.text)       # The analysis
print(response.model)      # "llama3.1:8b"
print(response.cost)       # e.g., 0.45 cost units
print(response.duration_ms) # e.g., 12500
```

## 5.7 Thinking Effort

Even within the same model, we can vary "thinking effort" by adjusting:

- **Temperature**: Low (0.0-0.2) for precise code generation; High (0.7-1.0) for creative exploration
- **max_tokens**: Higher for analysis/reasoning tasks
- **System prompt instructions**: "Think step by step" vs "Be concise and direct"

This maps roughly to:
- **Low effort**: temperature=0.0, concise prompts → classification, formatting
- **Medium effort**: temperature=0.2, step-by-step → code generation, analysis
- **High effort**: temperature=0.5, detailed reasoning → planning, root cause