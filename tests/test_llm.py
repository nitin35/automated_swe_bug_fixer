import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.llm import LLMRouter, LLMError
from src.config import load_config
from src.models import RunContext

def test_choose_tier():
    router = LLMRouter(load_config())
    assert router._choose_tier("classify") == "lite"
    assert router._choose_tier("generate_patch") == "medium"
    assert router._choose_tier("plan") == "heavy"
    assert router._choose_tier("unknown_task") == "medium"  # fallback

def test_load_prompt(tmp_path):
    # Setup mock prompt templates
    prompts_dir = tmp_path / "prompts"
    category_dir = prompts_dir / "fix"
    category_dir.mkdir(parents=True)
    template_file = category_dir / "test_template.txt"
    template_file.write_text("Hello {name}, welcome to {project}!")

    config = {
        "paths": {
            "prompts_dir": str(prompts_dir)
        }
    }
    router = LLMRouter(config)
    prompt = router.load_prompt("fix", "test_template.txt", name="Agent", project="SWE Fixer")
    assert prompt == "Hello Agent, welcome to SWE Fixer!"

def test_calculate_cost():
    config = {
        "cost_weights": {
            "lite": 1,
            "medium": 5,
            "heavy": 10
        }
    }
    router = LLMRouter(config)
    # Total tokens = 1500, tier weight = 5, cost = (1500 / 1000) * 5 = 7.5
    assert router._calculate_cost("medium", 1000, 500) == 7.5

@pytest.mark.anyio
@patch("httpx.AsyncClient.post")
async def test_query_success(mock_post):
    config = load_config()
    router = LLMRouter(config)

    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": " This is a test fix response. ",
        "prompt_eval_count": 100,
        "eval_count": 200
    }
    mock_post.return_value = mock_response

    response = await router.query(
        task_type="generate_patch",
        system_prompt="sys",
        user_prompt="user",
        tier="medium",
        agent_name="fix_agent",
        run_id="run_test"
    )

    assert response.text == "This is a test fix response."
    assert response.model == config["models"]["medium"]
    assert response.tier == "medium"
    assert response.tokens_in == 100
    assert response.tokens_out == 200
    # Cost = (300 / 1000) * 5 = 1.5
    assert response.cost == 1.5
    assert router.total_cost == 1.5
    assert len(router.call_history) == 1

@pytest.mark.anyio
@patch("httpx.AsyncClient.post")
async def test_query_cost_limit(mock_post):
    config = load_config()
    # Set limit very low
    config["master"]["daily_cost_limit"] = 0.5
    router = LLMRouter(config)
    router.total_cost = 0.6  # Already exceeded

    with pytest.raises(LLMError, match="Daily cost limit of 0.5 exceeded"):
        await router.query("classify", "sys", "user", tier="lite")

@pytest.mark.anyio
@patch("httpx.AsyncClient.post")
async def test_query_with_retry_and_fallback(mock_post):
    config = load_config()
    router = LLMRouter(config)

    # First and second calls fail, third call succeeds with fallback_tier
    mock_fail = MagicMock()
    mock_fail.raise_for_status.side_effect = Exception("Connection error")
    
    mock_success = MagicMock()
    mock_success.status_code = 200
    mock_success.json.return_value = {
        "response": "Lite fallback response",
        "prompt_eval_count": 10,
        "eval_count": 20
    }

    mock_post.side_effect = [mock_fail, mock_fail, mock_success]

    # Patch asyncio.sleep to speed up tests
    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        response = await router.query_with_retry(
            task_type="generate_patch",
            system_prompt="sys",
            user_prompt="user",
            tier="medium",
            retries=2,
            fallback_tier="lite"
        )

        assert response.text == "Lite fallback response"
        assert response.tier == "lite"  # Fallback worked
        assert mock_sleep.call_count == 2
        # Backoff intervals: 2^0 = 1, 2^1 = 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

@pytest.mark.anyio
@patch("httpx.AsyncClient.post")
async def test_get_embedding(mock_post):
    config = load_config()
    router = LLMRouter(config)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "embedding": [0.1, 0.2, 0.3]
    }
    mock_post.return_value = mock_response

    embedding = await router.get_embedding("test text")
    assert embedding == [0.1, 0.2, 0.3]
    mock_post.assert_called_once()
