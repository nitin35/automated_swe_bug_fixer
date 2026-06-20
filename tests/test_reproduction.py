import pytest
import os
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.bus import MessageBus
from src.models import Directive
from src.agents.reproduction import ReproductionAgent
from src.agents.retrieval import RetrievalAgent
from src.knowledge_base import KnowledgeBase

@pytest.fixture
def test_repo_path():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures", "test_repo"))
    git_dir = os.path.join(path, ".git")
    if not os.path.exists(git_dir):
        import subprocess
        subprocess.run(["git", "init"], cwd=path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=path, capture_output=True)
    return path


@pytest.fixture
def mock_kb(test_repo_path):
    kb = MagicMock(spec=KnowledgeBase)
    kb.cache = MagicMock()
    # Mock clone_repo to return our local test_repo fixture path
    kb.cache.clone_repo = AsyncMock(return_value=test_repo_path)
    kb.find_similar_issues = AsyncMock(return_value=[{"instance_id": "issue_1", "similarity": 0.88}])
    return kb

@pytest.mark.anyio
async def test_reproduction_agent(mock_kb, test_repo_path):
    bus = MessageBus()
    agent = ReproductionAgent(name="reproduction", bus=bus, kb=mock_kb)
    
    directive = Directive(
        target="reproduction",
        action="reproduce_bug",
        message_id="msg_repro",
        payload={
            "repo": "NitIn35/test_bug_fix",
            "base_commit": "2b28a6e",
            "fail_to_pass": '["test_calculator.py::test_divide"]'
        },
        timeout=30
    )
    
    result = await agent.execute(directive)
    
    assert result["success"] == True  # Bug was reproduced (tests failed)
    assert "test_calculator.py::test_divide" in result["failing_tests"]
    assert result["repo_path"] == test_repo_path
    assert len(result["repro_steps"]) > 0

@pytest.mark.anyio
async def test_retrieval_agent(mock_kb, test_repo_path):
    bus = MessageBus()
    agent = RetrievalAgent(name="retrieval", bus=bus, kb=mock_kb)
    
    # 1. Test get_repo_structure
    directive_structure = Directive(
        target="retrieval",
        action="get_repo_structure",
        message_id="msg_struct",
        payload={"repo_path": test_repo_path}
    )
    res_struct = await agent.execute(directive_structure)
    assert "calculator.py" in res_struct["repo_structure"]
    assert "test_calculator.py" in res_struct["repo_structure"]

    # 2. Test get_file_content
    directive_content = Directive(
        target="retrieval",
        action="get_file_content",
        message_id="msg_content",
        payload={
            "repo_path": test_repo_path,
            "files": ["calculator.py"]
        }
    )
    res_content = await agent.execute(directive_content)
    assert "def divide(a, b):" in res_content["relevant_files"]["calculator.py"]

    # 3. Test search_code
    directive_search = Directive(
        target="retrieval",
        action="search_code",
        message_id="msg_search",
        payload={
            "repo_path": test_repo_path,
            "query": "Find the divide function"
        }
    )
    res_search = await agent.execute(directive_search)
    assert "calculator.py" in res_search["relevant_files"]

    assert "divide" in res_search["relevant_files"]["calculator.py"]

    # 4. Test find_similar_issues
    directive_similar = Directive(
        target="retrieval",
        action="find_similar_issues",
        message_id="msg_similar",
        payload={
            "problem_statement": "Division by zero fails",
            "query_embedding": [0.1, 0.2]
        }
    )
    res_similar = await agent.execute(directive_similar)
    assert len(res_similar["similar_issues"]) == 1
    assert res_similar["similar_issues"][0]["instance_id"] == "issue_1"
