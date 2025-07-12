#!/usr/bin/env python3
"""
Assign GitHub issues to appropriate sprint milestones based on task IDs
"""

import json
import subprocess
from pathlib import Path

def main():
    # Load sync map
    sync_map_file = Path(".taskmaster/github-sync-map.json")
    if not sync_map_file.exists():
        print("❌ Sync map not found. Run sync first.")
        return
    
    with open(sync_map_file, 'r') as f:
        sync_map = json.load(f)
    
    # Get all milestones including closed ones
    result = subprocess.run(
        ["gh", "api", "repos/{owner}/{repo}/milestones?state=all", "--jq", ".[] | {number, title}"],
        capture_output=True,
        text=True,
        check=True
    )
    
    milestones = {}
    for line in result.stdout.strip().split('\n'):
        if line:
            data = json.loads(line)
            milestones[data['title']] = data['number']
    
    print("📋 Found milestones:", milestones)
    
    # Create Sprint 1 if missing
    if "Sprint 1: Foundation" not in milestones:
        print("Creating Sprint 1 milestone...")
        subprocess.run([
            "gh", "api", "repos/{owner}/{repo}/milestones", "-X", "POST",
            "-f", "title=Sprint 1: Foundation",
            "-f", "description=Django setup, Discord OAuth, and User model (Tasks 1-3)",
            "-f", "state=closed"
        ], check=True)
        # Refresh milestones
        result = subprocess.run(
            ["gh", "api", "repos/{owner}/{repo}/milestones?state=all", "--jq", ".[] | {number, title}"],
            capture_output=True,
            text=True,
            check=True
        )
        milestones = {}
        for line in result.stdout.strip().split('\n'):
            if line:
                data = json.loads(line)
                milestones[data['title']] = data['number']
    
    # Task to sprint mapping
    task_sprint_map = {
        "1": "Sprint 1: Foundation",
        "2": "Sprint 1: Foundation",
        "3": "Sprint 1: Foundation",
        "4": "Sprint 2: Character & DKP Core",
        "5": "Sprint 2: Character & DKP Core",
        "6": "Sprint 3: Events & Attendance",
        "7": "Sprint 3: Events & Attendance",
        "8": "Sprint 4: Loot & Discord",
        "9": "Sprint 4: Loot & Discord",
        "10": "Sprint 5: Recruitment"
    }
    
    # Assign issues to milestones
    assigned_count = 0
    for task_id, issue_number in sync_map.items():
        # Get main task ID (before first dot)
        main_task_id = task_id.split('.')[0]
        
        if main_task_id in task_sprint_map:
            sprint = task_sprint_map[main_task_id]
            if sprint in milestones:
                milestone_number = milestones[sprint]
                
                # Check if already assigned
                result = subprocess.run(
                    ["gh", "issue", "view", str(issue_number), "--json", "milestone"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                current_milestone = json.loads(result.stdout).get("milestone")
                
                if not current_milestone:
                    # Assign milestone
                    subprocess.run(
                        ["gh", "issue", "edit", str(issue_number), "--milestone", str(milestone_number)],
                        capture_output=True,
                        check=True
                    )
                    print(f"✅ Assigned issue #{issue_number} (task {task_id}) to {sprint}")
                    assigned_count += 1
                elif current_milestone.get("number") != milestone_number:
                    # Update milestone
                    subprocess.run(
                        ["gh", "issue", "edit", str(issue_number), "--milestone", str(milestone_number)],
                        capture_output=True,
                        check=True
                    )
                    print(f"✅ Updated issue #{issue_number} (task {task_id}) to {sprint}")
                    assigned_count += 1
                else:
                    print(f"ℹ️  Issue #{issue_number} (task {task_id}) already in {sprint}")
    
    print(f"\n🎯 Assigned {assigned_count} issues to milestones")
    
    # Show summary
    print("\n📊 Sprint Summary:")
    for sprint_name, milestone_number in sorted(milestones.items()):
        # Count issues in this milestone
        result = subprocess.run(
            ["gh", "issue", "list", "--milestone", str(milestone_number), "--state", "all", "--json", "state"],
            capture_output=True,
            text=True,
            check=True
        )
        issues = json.loads(result.stdout)
        open_count = sum(1 for i in issues if i["state"] == "OPEN")
        closed_count = sum(1 for i in issues if i["state"] == "CLOSED")
        total = len(issues)
        
        print(f"  {sprint_name}: {total} issues ({closed_count} closed, {open_count} open)")

if __name__ == "__main__":
    main()