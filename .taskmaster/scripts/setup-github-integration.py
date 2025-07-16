#!/usr/bin/env python3
"""
Setup GitHub integration for Task Master

This script initializes the GitHub project, creates labels, milestones,
and performs the initial sync of all tasks to GitHub issues.
"""

import subprocess
import json
import sys
from pathlib import Path

def run_command(cmd, check=True):
    """Run a shell command and return the result."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def setup_labels():
    """Create all necessary GitHub labels."""
    print("🏷️  Setting up GitHub labels...")
    
    labels = [
        # Priority labels
        {"name": "high-priority", "color": "d73a4a", "description": "High priority tasks"},
        {"name": "medium-priority", "color": "fbca04", "description": "Medium priority tasks"},
        {"name": "low-priority", "color": "0e8a16", "description": "Low priority tasks"},
        
        # Task type labels
        {"name": "main-task", "color": "1d76db", "description": "Main task items"},
        {"name": "subtask", "color": "0075ca", "description": "Subtask items"},
        
        # Sync label
        {"name": "task-master-sync", "color": "5319e7", "description": "Synced with Task Master"},
        
        # Status labels
        {"name": "in-progress", "color": "ffd93d", "description": "Currently being worked on"},
        {"name": "blocked", "color": "e11d21", "description": "Blocked by external factors"},
        {"name": "deferred", "color": "c5def5", "description": "Postponed for later"},
        
        # Domain labels
        {"name": "django", "color": "092e20", "description": "Django framework related tasks"},
        {"name": "discord", "color": "5865F2", "description": "Discord integration tasks"},
        {"name": "dkp", "color": "ff6b6b", "description": "DKP system related"},
        {"name": "api", "color": "4dabf7", "description": "API development"},
    ]
    
    for label in labels:
        cmd = f'gh label create "{label["name"]}" --color {label["color"]} --description "{label["description"]}"'
        stdout, stderr, code = run_command(cmd, check=False)
        if code == 0:
            print(f"  ✅ Created label: {label['name']}")
        else:
            if "already exists" in stderr:
                print(f"  ℹ️  Label already exists: {label['name']}")
            else:
                print(f"  ❌ Error creating label {label['name']}: {stderr}")

def setup_milestones():
    """Create sprint milestones."""
    print("\n🎯 Setting up sprint milestones...")
    
    milestones = [
        {
            "title": "Sprint 1: Foundation",
            "description": "Django setup, Discord OAuth, and User model (Tasks 1-3)",
            "state": "closed"  # Already completed
        },
        {
            "title": "Sprint 2: Character & DKP Core",
            "description": "Character management and DKP system (Tasks 4-5)",
            "state": "open"
        },
        {
            "title": "Sprint 3: Events & Attendance",
            "description": "Event management and attendance tracking (Tasks 6-7)",
            "state": "open"
        },
        {
            "title": "Sprint 4: Loot & Discord",
            "description": "Loot distribution and Discord integration (Tasks 8-9)",
            "state": "open"
        },
        {
            "title": "Sprint 5: Recruitment",
            "description": "Recruitment and voting system (Task 10)",
            "state": "open"
        }
    ]
    
    # Get existing milestones
    stdout, _, _ = run_command("gh api repos/{owner}/{repo}/milestones --jq '.[].title'", check=False)
    existing_milestones = stdout.split('\n') if stdout else []
    
    for i, milestone in enumerate(milestones, 1):
        if milestone["title"] in existing_milestones:
            print(f"  ℹ️  Milestone already exists: {milestone['title']}")
        else:
            cmd = f'''gh api repos/{{owner}}/{{repo}}/milestones -X POST \
                -f title="{milestone['title']}" \
                -f description="{milestone['description']}" \
                -f state="{milestone['state']}"'''
            stdout, stderr, code = run_command(cmd, check=False)
            if code == 0:
                print(f"  ✅ Created milestone: {milestone['title']}")
            else:
                print(f"  ❌ Error creating milestone: {stderr}")

def create_project():
    """Create GitHub Project v2."""
    print("\n📊 Setting up GitHub Project...")
    
    # Check if project already exists
    stdout, _, _ = run_command('gh project list --owner @me --format json', check=False)
    if stdout:
        projects = json.loads(stdout)
        if any(p.get('title') == 'Kromrif DKP System' for p in projects):
            print("  ℹ️  Project 'Kromrif DKP System' already exists")
            return
    
    # Create new project
    cmd = '''gh project create --owner @me --title "Kromrif DKP System" \
        --body "Task management for Kromrif DKP system development"'''
    stdout, stderr, code = run_command(cmd, check=False)
    if code == 0:
        print("  ✅ Created project: Kromrif DKP System")
    else:
        print(f"  ❌ Error creating project: {stderr}")

def assign_issues_to_milestones():
    """Assign existing issues to appropriate milestones."""
    print("\n🔗 Assigning issues to milestones...")
    
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
    
    # Get milestones
    stdout, _, _ = run_command("gh api repos/{owner}/{repo}/milestones --jq '.[] | {number, title}'", check=False)
    milestones = {}
    if stdout:
        for line in stdout.strip().split('\n'):
            if line.strip():
                milestone_data = json.loads(line)
                milestones[milestone_data['title']] = milestone_data['number']
    
    # Get issues with task IDs
    stdout, _, _ = run_command('gh issue list --limit 1000 --json number,title,body', check=False)
    if stdout:
        issues = json.loads(stdout)
        for issue in issues:
            # Extract task ID from title or body
            task_id = None
            if issue['title'].startswith('Task '):
                task_id = issue['title'].split(':')[0].replace('Task ', '').split('.')[0]
            elif '<!-- task-master-id:' in issue.get('body', ''):
                task_id = issue['body'].split('<!-- task-master-id:')[1].split('-->')[0].strip().split('.')[0]
            
            if task_id and task_id in task_sprint_map:
                sprint = task_sprint_map[task_id]
                if sprint in milestones:
                    cmd = f"gh issue edit {issue['number']} --milestone {milestones[sprint]}"
                    run_command(cmd, check=False)
                    print(f"  ✅ Assigned issue #{issue['number']} to {sprint}")

def main():
    """Run the complete GitHub integration setup."""
    print("🚀 Setting up GitHub integration for Task Master\n")
    
    # Check if we're in a git repository
    _, _, code = run_command("git rev-parse --is-inside-work-tree", check=False)
    if code != 0:
        print("❌ Error: Not in a git repository")
        sys.exit(1)
    
    # Run setup steps
    setup_labels()
    setup_milestones()
    create_project()
    
    # Initial sync
    print("\n🔄 Running initial sync...")
    sync_script = Path(".taskmaster/scripts/sync-github.py")
    if sync_script.exists():
        run_command(f"python3 {sync_script} --direction to-github")
        assign_issues_to_milestones()
    else:
        print("❌ Sync script not found. Please ensure sync-github.py exists.")
    
    print("\n✅ GitHub integration setup complete!")
    print("\n📝 Next steps:")
    print("  1. Use '/taskmaster-sync' command to sync before commits")
    print("  2. Use '/taskmaster-commit-sync' for comprehensive pre-commit sync")
    print("  3. Run 'python3 .taskmaster/scripts/sync-github.py' for manual sync")

if __name__ == "__main__":
    main()