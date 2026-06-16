from swebench_lite_source import SWEBenchLiteSource
from pprint import pp

def main():
    print("Initializing SWEBenchLiteSource...")
    source = SWEBenchLiteSource(db_path="swebench_lite.db")

    # Get a random unsolved issue
    print("\nRetrieving a random unsolved issue:")
    issue = source.get_issue()
    if issue:
        print(f"Retrieved issue ID: {issue['instance_id']}")
        print(f"Repo: {issue['repo']}")
        print(f"Base commit: {issue['base_commit']}")
        print(f"Solved status in DB: {issue['solved']}")
        
        # Mark the issue as solved
        print(f"\nMarking {issue['instance_id']} as solved...")
        source.mark_as_solved(issue['instance_id'])
        
        # Retrieve another random issue
        next_issue = source.get_issue()
        print(f"Next retrieved issue ID: {next_issue['instance_id']}")
        
        # Verify the previous issue is not selected again if we check its status directly in SQLite
        # Let's mark it as unresolved (back to unsolved)
        print(f"\nMarking {issue['instance_id']} as unresolved...")
        source.mark_as_unresolved(issue['instance_id'])
        
    else:
        print("No unsolved issues found!")

    # Test the hardcoded test issue
    print("\nRetrieving the hardcoded test issue:")
    test_issue = source.get_test_issue()
    pp(test_issue)

if __name__ == "__main__":
    main()
