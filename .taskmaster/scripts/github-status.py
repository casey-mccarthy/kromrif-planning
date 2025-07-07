#!/usr/bin/env python3
"""
Show status of Task Master GitHub integration
"""

import json
import subprocess
from pathlib import Path
from collections import defaultdict

def main():
    sync_map_file = Path(".taskmaster/github-sync-map.json")
    
    if not sync_map_file.exists():
        print("❌ No sync map found. Run sync first.")
        return
    
    with open(sync_map_file, 'r') as f:
        sync_map = json.load(f)
    
    print("📊 Task Master GitHub Integration Status\n")
    print(f"Total synced tasks: {len(sync_map)}")
    
    # Count by task level
    main_tasks = [k for k in sync_map.keys() if '.' not in k]
    subtasks = [k for k in sync_map.keys() if '.' in k]
    
    print(f"Main tasks: {len(main_tasks)}")
    print(f"Subtasks: {len(subtasks)}")
    
    # Get issue states
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "--limit", "1000", "--state", "all", "--json", "number,state"],
            capture_output=True,
            text=True,
            check=True
        )
        issues = json.loads(result.stdout)
        issue_states = {issue["number"]: issue["state"] for issue in issues}
        
        # Count states
        states = defaultdict(int)
        for task_id, issue_num in sync_map.items():
            state = issue_states.get(issue_num, "UNKNOWN")
            states[state] += 1
        
        print("\nIssue states:")
        for state, count in sorted(states.items()):
            print(f"  {state}: {count}")
    except subprocess.CalledProcessError:
        print("\n⚠️  Could not fetch issue states")
    
    print("\n✅ Sync is configured and working!")
    print("\nUseful commands:")
    print("  /taskmaster-sync          - Quick sync")
    print("  /taskmaster-commit-sync   - Pre-commit sync with status")
    print("  task-master next          - Get next task to work on")

if __name__ == "__main__":
    main()