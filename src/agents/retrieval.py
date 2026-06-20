import asyncio
import os
import re
from pathlib import Path
from src.agents.base import BaseAgent
from src.models import Directive

class RetrievalAgent(BaseAgent):
    async def execute(self, directive: Directive) -> dict:
        action = directive.action
        params = directive.payload
        repo_path = params.get("repo_path")
        
        if action == "search_code":
            query = params.get("query", "")
            keywords = self._extract_keywords(query)
            results = {}
            if repo_path and os.path.exists(repo_path):
                for keyword in keywords:
                    if not keyword.strip():
                        continue
                    # Run grep to find files containing keyword
                    proc = await asyncio.create_subprocess_exec(
                        "grep", "-r", "-l", "--include=*.py", keyword, ".",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=repo_path
                    )
                    stdout, _ = await proc.communicate()
                    for path in stdout.decode().splitlines():
                        path = path.strip()
                        # Remove leading ./
                        if path.startswith("./"):
                            path = path[2:]
                        if path and path not in results:
                            # Read first 2000 chars of matching files
                            full_path = os.path.join(repo_path, path)
                            if os.path.exists(full_path):
                                try:
                                    with open(full_path, "r", encoding="utf-8") as f:
                                        results[path] = f.read(2000)
                                except Exception:
                                    pass
            return {"relevant_files": results}

        elif action == "get_repo_structure":
            structure = []
            if repo_path and os.path.exists(repo_path):
                for root, dirs, files in os.walk(repo_path):
                    # Skip git and hidden files/dirs
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    for file in files:
                        if file.endswith(".py"):
                            rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                            structure.append(rel_path)
            return {"repo_structure": "\n".join(structure)}

        elif action == "find_similar_issues":
            # Requires embedding calculation, or we can mock/delegate to KB
            # Expects query_embedding in parameters, or calculate it via LLM
            query_embedding = params.get("query_embedding")
            if not query_embedding and self.llm:
                problem_statement = params.get("problem_statement", "")
                try:
                    query_embedding = await self.llm.get_embedding(problem_statement)
                except Exception:
                    pass
            
            similar_issues = []
            if query_embedding:
                similar_issues = await self.kb.find_similar_issues(query_embedding, k=params.get("k", 5))
            return {"similar_issues": similar_issues}

        elif action == "get_file_content":
            files = params.get("files", [])
            contents = {}
            if repo_path and os.path.exists(repo_path):
                for path in files:
                    full_path = os.path.join(repo_path, path)
                    if os.path.exists(full_path):
                        try:
                            with open(full_path, "r", encoding="utf-8") as f:
                                contents[path] = f.read()
                        except Exception as e:
                            contents[path] = f"Error reading file: {e}"
            return {"relevant_files": contents}

        else:
            raise ValueError(f"Unknown action '{action}' for RetrievalAgent")

    def _extract_keywords(self, query: str) -> list[str]:
        # Filter alphanumeric words longer than 3 characters, exclude common stopwords
        words = re.findall(r"\b\w{3,}\b", query.lower())
        stopwords = {
            "the", "and", "for", "with", "this", "that", "from", "here", "there",
            "what", "when", "where", "how", "who", "which", "than", "then", "them"
        }
        return [w for w in words if w not in stopwords]
