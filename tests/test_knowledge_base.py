import pytest
import sqlite3
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.knowledge_base import SQLiteStore, FAISSVectorStore, FileCache, KnowledgeBase

def test_sqlite_store_init(tmp_path):
    db_file = tmp_path / "test.db"
    store = SQLiteStore(str(db_file))
    
    # Verify tables exist
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    assert "runs" in tables
    assert "run_steps" in tables
    assert "llm_calls" in tables
    assert "learnings" in tables
    assert "repo_cache" in tables

@pytest.mark.anyio
async def test_sqlite_store_crud(tmp_path):
    db_file = tmp_path / "test.db"
    store = SQLiteStore(str(db_file))
    
    # 1. Create Run
    await store.create_run(run_id="run_1", instance_id="inst_1", status="running")
    
    # 2. Record Step
    await store.record_step(
        step_id="step_1",
        run_id="run_1",
        agent_name="fix",
        action="generate_patch",
        status="completed",
        started_at="start_time",
        completed_at="end_time"
    )
    
    # 3. Add learning
    await store.add_learning(
        learning_id="learn_1",
        category="build_tip",
        content="Tip description",
        source_run_id="run_1"
    )
    
    # 4. Read learnings
    learnings = await store.get_learnings()
    assert len(learnings) == 1
    assert learnings[0]["learning_id"] == "learn_1"
    
    # Filtered learnings
    assert len(await store.get_learnings(category="nonexistent")) == 0
    assert len(await store.get_learnings(category="build_tip")) == 1

def test_faiss_vector_store(tmp_path):
    store = FAISSVectorStore(str(tmp_path / "vectors"))
    
    # Search on empty index
    assert store.search([0.1, 0.2, 0.3], k=5) == []

    # Add test vectors
    store.add([0.1, 0.2, 0.3], {"id": "doc1", "text": "hello"})
    store.add([0.4, 0.5, 0.6], {"id": "doc2", "text": "world"})
    store.add([0.7, 0.8, 0.9], {"id": "doc3", "text": "foo"})

    assert store.get_total_count() == 3

    # Search closest match
    results = store.search([0.41, 0.51, 0.61], k=2)
    assert len(results) == 2
    assert results[0]["id"] == "doc2"
    assert results[0]["similarity"] > 0.9

    # Persistence verification
    store2 = FAISSVectorStore(str(tmp_path / "vectors"))
    assert store2.get_total_count() == 3
    results2 = store2.search([0.41, 0.51, 0.61], k=1)
    assert results2[0]["id"] == "doc2"

def test_faiss_vector_store_batch(tmp_path):
    store = FAISSVectorStore(str(tmp_path / "vectors"))
    
    embeddings = [
        [1.0, 0.0],
        [0.0, 1.0]
    ]
    metadatas = [
        {"name": "x"},
        {"name": "y"}
    ]
    store.add_batch(embeddings, metadatas)
    assert store.get_total_count() == 2
    assert store.search([1.0, 0.0], k=1)[0]["name"] == "x"

@pytest.mark.anyio
@patch("src.knowledge_base._run_git_cmd")
async def test_file_cache_clone(mock_git_cmd, tmp_path):
    cache = FileCache(str(tmp_path / "cache"))
    
    # Mock checkout/clone commands
    mock_git_cmd.return_value = "Success"
    
    # Perform clone
    path = await cache.clone_repo(
        repo_url="https://github.com/django/django.git",
        repo_name="django/django",
        base_commit="abc"
    )
    
    # Path should end with django__django
    assert Path(path).name == "django__django"
    assert mock_git_cmd.call_count == 2
    
    # Re-call clone (already existing directory)
    # Target directory is created now
    Path(path).mkdir(exist_ok=True, parents=True)
    path2 = await cache.clone_repo(
        repo_url="https://github.com/django/django.git",
        repo_name="django/django",
        base_commit="abc"
    )
    assert path == path2
