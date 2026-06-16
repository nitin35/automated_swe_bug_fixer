import sqlite3
import random
from datasets import load_dataset

class SWEBenchLiteSource:
    def __init__(self, db_path="swebench_lite.db"):
        """
        Initializes the SWEBenchLiteSource.
        Loads the dataset and populates the SQLite database if it doesn't already exist.
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                instance_id TEXT PRIMARY KEY,
                repo TEXT,
                base_commit TEXT,
                patch TEXT,
                test_patch TEXT,
                problem_statement TEXT,
                hints_text TEXT,
                created_at TEXT,
                version TEXT,
                fail_to_pass TEXT,
                pass_to_pass TEXT,
                environment_setup_commit TEXT,
                solved INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        
        # Check if table is empty
        cursor.execute("SELECT COUNT(*) FROM issues")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("Database is empty. Loading SWE-bench_Lite dataset from Hugging Face...")
            dataset = load_dataset('princeton-nlp/SWE-bench_Lite', split='test')
            
            # Insert all issues
            for item in dataset:
                cursor.execute("""
                    INSERT INTO issues (
                        instance_id, repo, base_commit, patch, test_patch,
                        problem_statement, hints_text, created_at, version,
                        fail_to_pass, pass_to_pass, environment_setup_commit, solved
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    item.get('instance_id'),
                    item.get('repo'),
                    item.get('base_commit'),
                    item.get('patch'),
                    item.get('test_patch'),
                    item.get('problem_statement'),
                    item.get('hints_text'),
                    item.get('created_at'),
                    item.get('version'),
                    item.get('FAIL_TO_PASS'),
                    item.get('PASS_TO_PASS'),
                    item.get('environment_setup_commit')
                ))
            conn.commit()
            print(f"Loaded {len(dataset)} issues into the database.")
        conn.close()

    def get_issue(self):
        """
        Returns a random unsolved issue from the database.
        Returns None if all issues are solved.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM issues WHERE solved = 0")
        unsolved_issues = cursor.fetchall()
        conn.close()
        
        if not unsolved_issues:
            return None
        
        selected = random.choice(unsolved_issues)
        return dict(selected)

    def mark_as_solved(self, instance_id):
        """
        Marks an issue as solved.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE issues SET solved = 1 WHERE instance_id = ?", (instance_id,))
        conn.commit()
        conn.close()

    def mark_as_unresolved(self, instance_id):
        """
        Marks an issue as unsolved/unresolved.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE issues SET solved = 0 WHERE instance_id = ?", (instance_id,))
        conn.commit()
        conn.close()

    def get_test_issue(self):
        """
        Returns the hardcoded test issue for testing the bug-fix agent.
        """
        return {
            "instance_id": "test_bug_fix__issue-1",
            "repo": "nitin35/test_bug_fix",
            "base_commit": "9f611af203a546fd9fed83e5d3d8f9a7510325f2",
            "patch": (
                "diff --git a/calculator.py b/calculator.py\n"
                "index 9381144..1dba21d 100644\n"
                "--- a/calculator.py\n"
                "+++ b/calculator.py\n"
                "@@ -10,6 +10,8 @@ def multiply(a, b):\n"
                "     return a * b\n"
                " \n"
                " def divide(a, b):\n"
                "+    if b == 0:\n"
                "+        raise ValueError(\"Cannot divide by zero.\")\n"
                "     return a / b\n"
            ),
            "test_patch": "",
            "problem_statement": (
                "### Description\n"
                "When calling the `divide(a, b)` function with `b = 0`, the function raises a raw `ZeroDivisionError`. "
                "According to our codebase specifications and tests, it is expected to raise a `ValueError` with "
                "the message \"Cannot divide by zero.\".\n\n"
                "### Steps to Reproduce\n"
                "Run the following code:\n"
                "```python\n"
                "from calculator import divide\n"
                "divide(5, 0)\n"
                "```\n\n"
                "### Expected Behavior\n"
                "A `ValueError` is raised with the message \"Cannot divide by zero.\".\n\n"
                "### Actual Behavior\n"
                "A `ZeroDivisionError` is raised, causing the `test_divide` unit test to fail."
            ),
            "hints_text": "",
            "created_at": "2026-06-14T17:11:00Z",
            "version": "1.0",
            "FAIL_TO_PASS": '["test_calculator.py::test_divide"]',
            "PASS_TO_PASS": (
                '["test_calculator.py::test_add", '
                '"test_calculator.py::test_subtract", '
                '"test_calculator.py::test_multiply", '
                '"test_calculator.py::test_square", '
                '"test_calculator.py::test_power", '
                '"test_calculator.py::test_log", '
                '"test_calculator.py::test_evaluate_simple", '
                '"test_calculator.py::test_evaluate_advanced", '
                '"test_calculator.py::test_evaluate_invalid"]'
            ),
            "environment_setup_commit": "9f611af203a546fd9fed83e5d3d8f9a7510325f2",
            "solved": 0
        }
