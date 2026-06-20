import asyncio
import time
import httpx
from pathlib import Path
from src.models import LLMResponse, LLMCallRecord

class LLMError(Exception):
    """Exception raised when an LLM call fails."""
    pass

class LLMRouter:
    """Routes LLM requests to the appropriate model based on task type.
    All models are accessed via Ollama's HTTP API.
    """

    def __init__(self, config: dict, ollama_base_url: str = None):
        self.config = config
        self.base_url = ollama_base_url or config.get("ollama", {}).get("base_url", "http://localhost:11434")
        self.call_history: list[LLMCallRecord] = []
        self.total_cost: float = 0.0
        
        # Load limits
        master_cfg = config.get("master", {})
        self.daily_cost_limit: float = master_cfg.get("daily_cost_limit", 100.0)

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
        """Send a query to the appropriate LLM."""
        if self.total_cost >= self.daily_cost_limit:
            raise LLMError(f"Daily cost limit of {self.daily_cost_limit} exceeded (current cost: {self.total_cost})")

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

    async def query_with_retry(
        self,
        task_type: str,
        system_prompt: str,
        user_prompt: str,
        tier: str = "auto",
        temperature: float = 0.2,
        max_tokens: int = 2048,
        agent_name: str = "unknown",
        run_id: str = None,
        retries: int = 2,
        fallback_tier: str = None
    ) -> LLMResponse:
        """Query with automatic retry and optional fallback to lower tier."""
        last_error = None
        for attempt in range(1 + retries):
            try:
                current_tier = tier
                if fallback_tier and attempt == retries:
                    current_tier = fallback_tier
                return await self.query(
                    task_type=task_type,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    tier=current_tier,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    agent_name=agent_name,
                    run_id=run_id
                )
            except LLMError as e:
                last_error = e
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        raise last_error

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
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": model, "prompt": text}
                )
                response.raise_for_status()
                return response.json()["embedding"]
        except Exception as e:
            raise LLMError(f"Ollama embedding request failed: {e}") from e

    def get_cost_report(self) -> dict:
        """Return a summary of costs for the current session."""
        tier_counts = {}
        for c in self.call_history:
            tier = self._get_tier_for_model(c.model)
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        return {
            "total_cost": self.total_cost,
            "total_calls": len(self.call_history),
            "by_tier": tier_counts,
            "by_agent": {
                agent: sum(1 for c in self.call_history if c.agent_name == agent)
                for agent in set(c.agent_name for c in self.call_history)
            },
        }

    def _get_tier_for_model(self, model: str) -> str:
        """Reverse-lookup tier from model name."""
        for tier in ("lite", "medium", "heavy"):
            if self.config["models"].get(tier) == model:
                return tier
        return "unknown"

    def load_prompt(self, category: str, template_name: str, **kwargs) -> str:
        """Load a prompt template and format it using kwargs."""
        prompts_dir = Path(self.config.get("paths", {}).get("prompts_dir", "prompts"))
        template_path = prompts_dir / category / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")
        with open(template_path, "r") as f:
            template = f.read()
        return template.format(**kwargs)
