# 04 — Knowledge Base (Persistent Memory)

## 4.1 Overview

The knowledge base is the system's long-term memory. Every run, every decision, every result is recorded so the system improves over time.

Three storage layers, each serving a different purpose:

| Layer | Technology | What It Stores | Query Pattern |
|-------|-----------|----------------|---------------|
| Structured | SQLite | Issues, runs, agent logs, costs, results | SQL queries, aggregation |
| Semantic | FAISS vector store (IndexFlatL2) | Issue embeddings, code snippet embeddings, learned patterns | Similarity search (L2 distance → similarity score) |
| Artifacts | File system | Cloned repos, patches, build logs, test outputs | File path lookup |

## 4.2 SQLite Schema

### `issues` table (from SWEBenchLiteSource)
Already exists in the bug source. We keep it as-is.

### `runs` table
Records every bug-fix attempt.

```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL,         -- Which issue was targeted
    status TEXT NOT NULL,              -- success | failed | partial
    started_at TEXT NOT NULL,
    completed_at TEXT,
    master_plan TEXT,                  -- JSON serialized plan
    final_patch TEXT,                  -- Generated patch (if any)
    error_summary TEXT,
    total_cost REAL DEFAULT 0,         -- Total "effort units" for this run
    FOREIGN KEY (instance_id) REFERENCES issues(instance_id)
);
```

### `run_steps` table
Records each agent's execution within a run.

```sql
CREATE TABLE run_steps (
    step_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,              -- completed | failed | skipped
    started_at TEXT NOT NULL,
    completed_at TEXT,
    input_summary TEXT,                -- Key input params (JSON)
    output_summary TEXT,               -- Key output data (JSON)
    error TEXT,
    llm_calls INTEGER DEFAULT 0,
    llm_cost REAL DEFAULT 0,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
```

### `llm_calls` table
Tracks every LLM request for cost/usage analysis.

```sql
CREATE TABLE llm_calls (
    call_id TEXT PRIMARY KEY,
    run_id TEXT,
    agent_name TEXT,
    model TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    task_type TEXT,                    -- planning | coding | analysis | review | etc.
    success INTEGER DEFAULT 1,
    error TEXT,
    created_at TEXT NOT NULL
);
```

### `learnings` table
Things the system learned that might help future runs.

```sql
CREATE TABLE learnings (
    learning_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,            -- build_tip | fix_pattern | test_insight | etc.
    content TEXT NOT NULL,
    source_run_id TEXT,
    source_issue_id TEXT,
    confidence REAL DEFAULT 1.0,       -- How reliable is this learning?
    created_at TEXT NOT NULL,
    last_used_at TEXT
);
```

### `repo_cache` table
Tracks which repos we've cloned and their state.

```sql
CREATE TABLE repo_cache (
    repo_name TEXT PRIMARY KEY,        -- e.g., "django/django"
    local_path TEXT NOT NULL,
    last_cloned_at TEXT NOT NULL,
    clone_count INTEGER DEFAULT 1,
    total_size_bytes INTEGER,
    last_commit_checked TEXT
);
```

## 4.3 Vector Store

For semantic search, we use **FAISS** (Facebook AI Similarity Search) — a production-grade vector similarity search library. FAISS handles indexing and search efficiently, supports different index types for different scale/accuracy trade-offs, and is the industry standard for vector search.

For MVP we use `IndexFlatL2` — the simplest FAISS index type. It performs exact (brute-force) L2 distance search and is perfect for the scale of embeddings we'll generate (thousands, not millions). It can be swapped for an IVF index later for faster search on larger collections.

### Implementation Sketch

```python
import faiss
import numpy as np
import pickle
from pathlib import Path

class FAISSVectorStore:
    """
    Vector store using FAISS for efficient similarity search.
    - FAISS IndexFlatL2 for exact nearest-neighbor search
    - Pickle for metadata storage alongside vectors
    - L2 distance converted to similarity score on output
    """

    def __init__(self, path: str, dimension: int = None):
        """Initialize the vector store.
        
        Args:
            path: Directory to store the index files.
            dimension: Embedding dimension. If None, auto-detected from
                       the first vector added. Must match your embedding
                       model (e.g., 384 for all-MiniLM-L6-v2, 2048 for
                       llama3.2:1b, 768 for nomic-embed-text).
        """
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
            self.dimension = self.index.d  # Read dimension from saved index
        elif self.dimension is not None:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
        else:
            # Dimension will be set on first add()
            self.index = None
            self.metadata = []

    def _save(self):
        faiss.write_index(self.index, str(self.index_path))
        with open(self.metadata_path, "wb") as f:
            pickle.dump(self.metadata, f)

    def add(self, embedding: list[float], metadata: dict, auto_save: bool = True):
        """Add a single vector with associated metadata."""
        vec = np.array([embedding], dtype=np.float32)
        if self.index is None:
            # Auto-detect dimension from first vector
            self.dimension = len(embedding)
            self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(vec)
        self.metadata.append(metadata)
        if auto_save:
            self._save()

    def add_batch(self, embeddings: list[list[float]], metadatas: list[dict]):
        """Add multiple vectors at once (more efficient). Always saves after."""
        vecs = np.array(embeddings, dtype=np.float32)
        if self.index is None:
            self.dimension = vecs.shape[1]
            self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(vecs)
        self.metadata.extend(metadatas)
        self._save()

    def search(self, query_embedding: list[float], k: int = 5) -> list[dict]:
        """Find k most similar items. Returns metadata + similarity score."""
        if self.index is None or self.index.ntotal == 0:
            return []

        query = np.array([query_embedding], dtype=np.float32)
        distances, indices = self.index.search(query, k)

        results = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            # Convert L2 distance to similarity score in [0, 1]
            similarity = 1.0 / (1.0 + float(distances[0][i]))
            results.append({
                **self.metadata[idx],
                "similarity": similarity,
                "distance": float(distances[0][i]),
            })

        return results

    def get_total_count(self) -> int:
        """Return the number of vectors in the index."""
        return self.index.ntotal
```

### Why FAISS over NumPy-only?

| Factor | FAISS | NumPy-only |
|--------|-------|------------|
| Search speed | C++ backend, SIMD-optimized | Pure Python, slow at scale |
| Index types | Flat, IVF, HNSW, PQ — trade speed for accuracy | Only brute-force |
| Production path | Industry standard, used at scale | Toy implementation |
| Learning value | Teaches real vector DB concepts | Teaches numpy basics |
| Dependencies | `faiss-cpu` (single pip install) | None extra |
| MVP suitability | Excellent — simple API, works out of the box | Works, but limited |

### FAISS Index Types — Future Upgrades

| Index | Type | When to Use |
|-------|------|-------------|
| `IndexFlatL2` | Exact search (brute-force) | MVP — small datasets (<100K vectors) |
| `IndexIVFFlat` | Approximate search with inverted files | Phase 2 — larger datasets, needs speed |
| `IndexHNSWFlat` | Graph-based approximate search | Phase 3+ — best speed/accuracy trade-off |
        ]
```

### What to Store as Vectors

- Issue problem statements (for similarity matching)
- Code snippets from repos (for context retrieval)
- Past patches (for pattern matching)
- Agent learnings (for knowledge reuse)

### Embedding Generation

Since we're using Ollama, we can use it for embeddings too:
```
POST /api/embeddings
{"model": "llama3.2:1b", "prompt": "some text to embed"}
```

## 4.4 File Cache

### Structure

```
cache/
  repos/
    django__django/
      <cloned repo contents>
    pytest-dev__pytest/
      <cloned repo contents>
    ...
  patches/
    <run_id>__<instance_id>.patch
  logs/
    <run_id>/
      master.log
      reproduction.log
      fix.log
      validation.log
  builds/
    <run_id>/
      build_output.txt
      test_output.xml
```

### Cache Policies

- **Git repos**: Cloned once per repo. Updated (git fetch) if older than 7 days.
- **Patches**: Generated per run, kept indefinitely for analysis.
- **Logs**: Kept for 30 days, then compressed.

## 4.5 Knowledge Sharing Between Agents

The knowledge base is not just for storage — it's also a communication medium:

1. **Agent A** stores intermediate results → **Agent B** reads them
2. If Reproduction fails, it writes `build_issues` → Fix Agent reads them for context
3. If Validation finds patterns, it writes to `learnings` → future runs benefit

## 4.6 Code Understanding Strategy (Future Expansion)

The user's original design specifies a four-pillar code understanding strategy that our system should grow into:

### Pillar 1: Structural Analysis (AST)
- Parse source code into Abstract Syntax Trees using Python's `ast` module (or `tree-sitter` for multi-language support)
- Map classes, functions, and dependencies into a relational graph
- Enables precise scope analysis: "What functions does `divide()` call? What calls `divide()`?"
- **Future integration point:** The Retrieval Agent uses AST to build a call graph, improving root cause localization

### Pillar 2: Semantic Search (Vector)
- Already covered by our `FAISSVectorStore`
- Generate embeddings for code chunks (function-level, file-level) and issue descriptions
- Search by meaning, not just keywords

### Pillar 3: Runtime Intelligence
- Already covered by our Reproduction Agent (error logs, stack traces, test output)
- Enhancement: correlate runtime locations (file:line from stack traces) with AST-derived code locations

### Pillar 4: Historical Context
- Already covered by our `learnings` table and similar-issue search
- Enhancement: synthesize patterns from successful patches into reusable "fix playbooks"

**Implementation Roadmap:**
| Phase | Capability | Mechanism |
|-------|------------|-----------|
| MVP (M0-M7) | Semantic search + basic file listing | `FAISSVectorStore` (IndexFlatL2) + `grep`/`rg` |
| Phase 2 (M8+) | AST-based call graphs | Python `ast` module |
| Phase 3 | Dependency graphs + impact analysis | AST + runtime traces |
| Phase 4 | Playbook synthesis from historical patches | LLM + pattern extraction |

## 4.7 KnowledgeBase Class (Unified Interface)

```python
class KnowledgeBase:
    def __init__(self, db_path, vector_store_path, cache_path):
        self.db = SQLiteStore(db_path)         # Wraps SQLite
        self.vectors = FAISSVectorStore(vector_store_path)
        self.cache = FileCache(cache_path)

    # Run tracking
    async def create_run(self, issue) -> str: ...
    async def complete_run(self, run_id, status, patch): ...
    async def record_step(self, run_id, agent, action, status, output): ...
    async def record_llm_call(self, run_id, agent, model, tokens, duration): ...

    # Learning
    async def add_learning(self, category, content, source_run, source_issue): ...
    async def get_learnings(self, category=None): ...

    # Similarity
    async def find_similar_issues(self, issue, k=5) -> list[dict]: ...
    async def find_similar_patches(self, problem_statement, k=3) -> list[dict]: ...

    # Repo cache
    async def get_repo_path(self, repo_name) -> str | None: ...
    async def cache_repo(self, repo_name, local_path): ...
```

**Implementation note:** SQLite operations are synchronous. For the async interface, use `aiosqlite` or wrap calls with `asyncio.to_thread()` to avoid blocking the event loop.