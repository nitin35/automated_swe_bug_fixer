import asyncio
import json
import time
from typing import Optional
from src.agents.base import BaseAgent
from src.models import Directive, ReproductionResult

class ReproductionAgent(BaseAgent):
    async def execute(self, directive: Directive) -> dict:
        params = directive.payload
        repo = params.get("repo")
        base_commit = params.get("base_commit")
        repo_url = params.get("repo_url", f"https://github.com/{repo}.git")
        fail_to_pass = params.get("fail_to_pass", "[]")
        
        # Parse list of failing tests
        if isinstance(fail_to_pass, str):
            try:
                fail_tests = json.loads(fail_to_pass)
            except Exception:
                fail_tests = [fail_to_pass] if fail_to_pass else []
        else:
            fail_tests = fail_to_pass

        repro_steps = []
        
        # Step 1: Clone/Checkout repo
        repro_steps.append(f"Cloning/checking out repo {repo} at commit {base_commit}")
        try:
            repo_path = await self.kb.cache.clone_repo(
                repo_url=repo_url,
                repo_name=repo,
                base_commit=base_commit
            )
        except Exception as e:
            return ReproductionResult(
                success=False,
                error_log=f"Clone/Checkout failed: {e}",
                failing_tests=[],
                passing_tests=[],
                test_output=None,
                repo_path="",
                repro_steps=repro_steps
            ).__dict__

        # Step 2: Install dependencies
        repro_steps.append("Installing dependencies with pip")
        # Run pip install in the virtualenv if possible, otherwise use global pip
        pip_path = "pip"
        # Check if we are running inside virtualenv (venv bin directory)
        import sys
        if hasattr(sys, "real_prefix") or (sys.base_prefix != sys.prefix):
            # We are in a virtualenv
            import os
            venv_pip = os.path.join(sys.prefix, "bin", "pip")
            if os.path.exists(venv_pip):
                pip_path = venv_pip

        install_proc = await asyncio.create_subprocess_exec(
            pip_path, "install", "-e", ".",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=repo_path
        )
        stdout, stderr = await install_proc.communicate()
        if install_proc.returncode != 0:
            repro_steps.append(f"Installation failed with code {install_proc.returncode}")
            return ReproductionResult(
                success=False,
                error_log=f"Installation failed:\nStdout: {stdout.decode()}\nStderr: {stderr.decode()}",
                failing_tests=[],
                passing_tests=[],
                test_output=None,
                repo_path=repo_path,
                repro_steps=repro_steps
            ).__dict__

        # Step 3: Run pytest
        repro_steps.append(f"Running pytest on failing tests: {fail_tests}")
        pytest_path = "pytest"
        if hasattr(sys, "real_prefix") or (sys.base_prefix != sys.prefix):
            import os
            venv_pytest = os.path.join(sys.prefix, "bin", "pytest")
            if os.path.exists(venv_pytest):
                pytest_path = venv_pytest

        # Build pytest command: pytest -v test1.py test2.py
        cmd = [pytest_path, "-v"] + fail_tests
        
        # Enforce timeout
        timeout = directive.timeout or 300
        try:
            test_proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            # Wait with timeout
            stdout_bytes, stderr_bytes = await asyncio.wait_for(test_proc.communicate(), timeout=timeout)
            stdout_str = stdout_bytes.decode()
            stderr_str = stderr_bytes.decode()
            return_code = test_proc.returncode
        except asyncio.TimeoutError:
            repro_steps.append("Running tests timed out")
            try:
                test_proc.kill()
            except Exception:
                pass
            return ReproductionResult(
                success=False,
                error_log=f"Tests timed out after {timeout} seconds",
                failing_tests=[],
                passing_tests=[],
                test_output=None,
                repo_path=repo_path,
                repro_steps=repro_steps
            ).__dict__

        # Parse test results
        failing_tests = []
        passing_tests = []
        for line in stdout_str.splitlines():
            if " FAILED" in line or line.startswith("FAILED "):
                parts = line.split()
                for p in parts:
                    if "::" in p:
                        failing_tests.append(p.strip())
                        break
                    elif p.endswith(".py") or "/" in p:
                        # Fallback for file level failures
                        failing_tests.append(p.strip())
                        break
            elif " PASSED" in line or line.startswith("PASSED "):
                parts = line.split()
                for p in parts:
                    if "::" in p:
                        passing_tests.append(p.strip())
                        break

        # Bug is successfully reproduced if the expected failing tests actually failed (return_code != 0)
        reproduced = return_code != 0 and len(failing_tests) > 0
        repro_steps.append(f"Pytest exited with code {return_code}. Reproduced: {reproduced}")
        
        return ReproductionResult(
            success=reproduced,
            error_log=stderr_str if return_code != 0 and not stdout_str else stdout_str,
            failing_tests=failing_tests,
            passing_tests=passing_tests,
            test_output=stdout_str,
            repo_path=repo_path,
            repro_steps=repro_steps
        ).__dict__
