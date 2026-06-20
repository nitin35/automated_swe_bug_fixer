import sqlite3
import json
import asyncio
import time
import pickle
import subprocess
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import faiss

# Subprocess helper for git operations
def _run_git_cmd(cmd: list[str]):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Git command failed: {' '.join(cmd)}\nStdout: {result.stdout}\nStderr: {result.stderr}")
    return result.stdout

class SQLiteStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            instance_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            master_plan TEXT,
            final_patch TEXT,
            error_summary TEXT,
            total_cost REAL DEFAULT 0
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS run_steps (
            step_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            input_summary TEXT,
            output_summary TEXT,
            error TEXT,
            llm_calls INTEGER DEFAULT 0,
            llm_cost REAL DEFAULT 0,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS llm_calls (
            call_id TEXT PRIMARY KEY,
            run_id TEXT,
            agent_name TEXT,
            model TEXT NOT NULL,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0,
            task_type TEXT,
            success INTEGER DEFAULT 1,
            error TEXT,
            created_at TEXT NOT NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS learnings (
            learning_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            source_run_id TEXT,
            source_issue_id TEXT,
            confidence REAL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            last_used_at TEXT
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS repo_cache (
            repo_name TEXT PRIMARY KEY,
            local_path TEXT NOT NULL,
            last_cloned_at TEXT NOT NULL,
            clone_count INTEGER DEFAULT 1,
            total_size_bytes INTEGER,
            last_commit_checked TEXT
        );
        """)
        
        conn.commit()
        conn.close()

    async def create_run(self, run_id: str, instance_id: str, status: str = "pending", plan: list = None) -> str:
        def _insert():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO runs (run_id, instance_id, status, started_at, master_plan) VALUES (?, ?, ?, ?, ?)",
                (run_id, instance_id, status, datetime.now(timezone.utc).isoformat(), json.dumps(plan or []))
            )
            conn.commit()
            conn.close()
        await asyncio.to_thread(_insert)
        return run_id

    async def complete_run(self, run_id: str, status: str, patch: str = None, error_summary: str = None, total_cost: float = 0.0):
        def _update():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE runs SET status = ?, completed_at = ?, final_patch = ?, error_summary = ?, total_cost = ? WHERE run_id = ?",
                (status, datetime.now(timezone.utc).isoformat(), patch, error_summary, total_cost, run_id)
            )
            conn.commit()
            conn.close()
        await asyncio.to_thread(_update)

    async def record_step(self, step_id: str, run_id: str, agent_name: str, action: str, status: str, started_at: str, completed_at: str = None, input_summary: dict = None, output_summary: dict = None, error: str = None, llm_calls: int = 0, llm_cost: float = 0.0):
        def _insert_or_replace():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO run_steps 
                (step_id, run_id, agent_name, action, status, started_at, completed_at, input_summary, output_summary, error, llm_calls, llm_cost) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (step_id, run_id, agent_name, action, status, started_at, completed_at, 
                 json.dumps(input_summary or {}), json.dumps(output_summary or {}), error, llm_calls, llm_cost)
            )
            conn.commit()
            conn.close()
        await asyncio.to_thread(_insert_or_replace)

    async def record_llm_call(self, call_id: str, run_id: str, agent_name: str, model: str, prompt_tokens: int, completion_tokens: int, duration_ms: int, task_type: str, success: bool, error: str = None):
        def _insert():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO llm_calls 
                (call_id, run_id, agent_name, model, prompt_tokens, completion_tokens, duration_ms, task_type, success, error, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (call_id, run_id, agent_name, model, prompt_tokens, completion_tokens, duration_ms, task_type, 1 if success else 0, error, datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
            conn.close()
        await asyncio.to_thread(_insert)

    async def add_learning(self, learning_id: str, category: str, content: str, source_run_id: str = None, source_issue_id: str = None, confidence: float = 1.0):
        def _insert():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO learnings (learning_id, category, content, source_run_id, source_issue_id, confidence, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (learning_id, category, content, source_run_id, source_issue_id, confidence, datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
            conn.close()
        await asyncio.to_thread(_insert)

    async def get_learnings(self, category: str = None) -> list[dict]:
        def _query():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if category:
                cursor.execute("SELECT * FROM learnings WHERE category = ?", (category,))
            else:
                cursor.execute("SELECT * FROM learnings")
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        return await asyncio.to_thread(_query)

class FAISSVectorStore:
    def __init__(self, path: str, dimension: int = None):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.dimension = dimension
        self.index_path = self.path / "index.faiss"
        self.metadata_path = self.path / "metadata.pkl"
        self._load()

    def _load(self):
        if self.index_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            with open(self.metadata_path, "rb") as f:
                self.metadata = pickle.load(f)
            self.dimension = self.index.d
        elif self.dimension is not None:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
        else:
            self.index = None
            self.metadata = []

    def _save(self):
        faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, "wb") as f:
            pickle.dump(self.metadata, f)

    def add(self, embedding: list[float], metadata: dict, auto_save: bool = True):
        vec = np.array([embedding], dtype=np.float32)
        if self.index is None:
            self.dimension = len(embedding)
            self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(vec)
        self.metadata.append(metadata)
        if auto_save:
            self._save()

    def add_batch(self, embeddings: list[list[float]], metadatas: list[dict]):
        vecs = np.array(embeddings, dtype=np.float32)
        if self.index is None:
            self.dimension = vecs.shape[1]
            self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(vecs)
        self.metadata.extend(metadatas)
        self._save()

    def search(self, query_embedding: list[float], k: int = 5) -> list[dict]:
        if self.index is None or self.index.ntotal == 0:
            return []

        query = np.array([query_embedding], dtype=np.float32)
        distances, indices = self.index.search(query, k)

        results = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            similarity = 1.0 / (1.0 + float(distances[0][i]))
            results.append({
                **self.metadata[idx],
                "similarity": similarity,
                "distance": float(distances[0][i]),
            })

        return results

    def get_total_count(self) -> int:
        return self.index.ntotal if self.index is not None else 0

class FileCache:
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.repos_dir = self.cache_dir / "repos"
        self.repos_dir.mkdir(parents=True, exist_ok=True)

    async def get_repo_path(self, repo_name: str) -> str | None:
        target_dir = self.repos_dir / repo_name.replace("/", "__")
        if target_dir.exists():
            return str(target_dir)
        return None

    async def clone_repo(self, repo_url: str, repo_name: str, base_commit: str) -> str:
        target_dir = self.repos_dir / repo_name.replace("/", "__")
        
        def _clone_and_checkout():
            if target_dir.exists():
                _run_git_cmd(["git", "-C", str(target_dir), "checkout", base_commit])
                return str(target_dir)
            _run_git_cmd(["git", "clone", repo_url, str(target_dir)])
            _run_git_cmd(["git", "-C", str(target_dir), "checkout", base_commit])
            return str(target_dir)

        return await asyncio.to_thread(_clone_and_checkout)

class KnowledgeBase:
    def __init__(self, db_path: str, vector_store_path: str, cache_path: str):
        self.db = SQLiteStore(db_path)
        self.vectors = FAISSVectorStore(vector_store_path)
        self.cache = FileCache(cache_path)

    async def find_similar_issues(self, query_embedding: list[float], k: int = 5) -> list[dict]:
        return await asyncio.to_thread(self.vectors.search, query_embedding, k)
