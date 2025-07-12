#!/usr/bin/env python3
"""
Task Master to GitHub Issues Sync Script

This script provides bidirectional synchronization between Task Master tasks
and GitHub issues, maintaining task hierarchy and status consistency.
"""

import json
import subprocess
import sys
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import argparse
from pathlib import Path

class TaskMasterGitHubSync:
    def __init__(self, repo_owner: str = None, repo_name: str = None):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.tasks_file = Path(".taskmaster/tasks/tasks.json")
        self.sync_map_file = Path(".taskmaster/github-sync-map.json")
        self.sync_map = self.load_sync_map()
        
        # Determine repo info if not provided
        if not self.repo_owner or not self.repo_name:
            self._detect_repo_info()
    
    def _detect_repo_info(self):
        """Detect repository owner and name from git remote."""
        try:
            result = subprocess.run(
                ["gh", "repo", "view", "--json", "owner,name"],
                capture_output=True,
                text=True,
                check=True
            )
            repo_info = json.loads(result.stdout)
            self.repo_owner = repo_info["owner"]["login"]
            self.repo_name = repo_info["name"]
        except subprocess.CalledProcessError:
            print("Error: Could not detect repository information. Make sure you're in a git repository.")
            sys.exit(1)
    
    def load_sync_map(self) -> Dict[str, int]:
        """Load the mapping between Task Master IDs and GitHub issue numbers."""
        if self.sync_map_file.exists():
            with open(self.sync_map_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_sync_map(self):
        """Save the sync mapping to disk."""
        self.sync_map_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.sync_map_file, 'w') as f:
            json.dump(self.sync_map, f, indent=2)
    
    def load_tasks(self) -> Dict:
        """Load tasks from Task Master."""
        if not self.tasks_file.exists():
            print(f"Error: Tasks file not found at {self.tasks_file}")
            sys.exit(1)
        
        with open(self.tasks_file, 'r') as f:
            return json.load(f)
    
    def save_tasks(self, tasks: Dict):
        """Save tasks back to Task Master."""
        with open(self.tasks_file, 'w') as f:
            json.dump(tasks, f, indent=2)
    
    def get_github_issues(self) -> List[Dict]:
        """Fetch all issues from GitHub."""
        try:
            result = subprocess.run(
                [
                    "gh", "issue", "list",
                    "--repo", f"{self.repo_owner}/{self.repo_name}",
                    "--limit", "1000",
                    "--json", "number,title,body,state,labels,assignees"
                ],
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"Error fetching GitHub issues: {e}")
            return []
    
    def get_milestone_for_task(self, task_id: str) -> Optional[str]:
        """Get the milestone title for a given task ID."""
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
        
        # Get main task ID (before first dot)
        main_task_id = task_id.split('.')[0]
        
        if main_task_id not in task_sprint_map:
            return None
        
        return task_sprint_map[main_task_id]
    
    def create_github_issue(self, task: Dict) -> Optional[int]:
        """Create a new GitHub issue from a Task Master task."""
        # Prepare labels
        labels = ["task-master-sync"]
        
        # Add priority label
        if task.get("priority"):
            labels.append(f"{task['priority']}-priority")
        
        # Add main task or subtask label
        if "." in task["id"]:
            labels.append("subtask")
        else:
            labels.append("main-task")
        
        # Prepare the issue body
        body_parts = []
        
        # Add Task Master ID
        body_parts.append(f"**Task Master ID:** {task['id']}")
        
        # Add description
        if task.get("description"):
            body_parts.append(f"\n**Description:**\n{task['description']}")
        
        # Add details
        if task.get("details"):
            body_parts.append(f"\n**Details:**\n{task['details']}")
        
        # Add test strategy
        if task.get("testStrategy"):
            body_parts.append(f"\n**Test Strategy:**\n{task['testStrategy']}")
        
        # Add parent task reference for subtasks
        if "." in task["id"]:
            parent_id = task["id"].rsplit(".", 1)[0]
            if parent_id in self.sync_map:
                body_parts.append(f"\n**Parent Task:** #{self.sync_map[parent_id]}")
        
        # Add dependencies
        if task.get("dependencies"):
            dep_refs = []
            for dep_id in task["dependencies"]:
                if dep_id in self.sync_map:
                    dep_refs.append(f"#{self.sync_map[dep_id]}")
                else:
                    dep_refs.append(f"Task {dep_id}")
            body_parts.append(f"\n**Dependencies:** {', '.join(dep_refs)}")
        
        # Add sync metadata
        body_parts.append(f"\n\n<!-- task-master-id: {task['id']} -->")
        
        body = "\n".join(body_parts)
        
        # Prepare title
        title = f"Task {task['id']}: {task['title']}"
        
        # Create the issue
        try:
            cmd = [
                "gh", "issue", "create",
                "--repo", f"{self.repo_owner}/{self.repo_name}",
                "--title", title,
                "--body", body
            ]
            
            # Add labels
            for label in labels:
                cmd.extend(["--label", label])
            
            # Add milestone
            milestone_title = self.get_milestone_for_task(task["id"])
            if milestone_title:
                cmd.extend(["--milestone", milestone_title])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Extract issue number from output
            output = result.stdout.strip()
            if output.startswith("https://"):
                issue_number = int(output.split("/")[-1])
                return issue_number
            
        except subprocess.CalledProcessError as e:
            print(f"Error creating issue for task {task['id']}: {e}")
            print(f"Error output: {e.stderr}")
        
        return None
    
    def update_github_issue(self, issue_number: int, task: Dict):
        """Update an existing GitHub issue with task data."""
        # Determine new state based on task status
        issue_state = "open"
        if task["status"] in ["done", "cancelled"]:
            issue_state = "closed"
        
        # Get current issue details
        try:
            result = subprocess.run(
                ["gh", "issue", "view", str(issue_number), "--json", "state,milestone"],
                capture_output=True,
                text=True,
                check=True
            )
            current_issue = json.loads(result.stdout)
            current_state = "closed" if current_issue["state"] == "CLOSED" else "open"
            current_milestone = current_issue.get("milestone", {}).get("number") if current_issue.get("milestone") else None
            
            # Update state if needed
            if current_state != issue_state:
                action = "close" if issue_state == "closed" else "reopen"
                try:
                    subprocess.run(
                        [
                            "gh", "issue", action, str(issue_number),
                            "--repo", f"{self.repo_owner}/{self.repo_name}"
                        ],
                        check=True
                    )
                    print(f"Updated issue #{issue_number} state to {issue_state}")
                except subprocess.CalledProcessError as e:
                    print(f"Error updating issue #{issue_number} state: {e}")
            
            # Update milestone if needed (only for open issues)
            if current_state == "open":
                expected_milestone_title = self.get_milestone_for_task(task["id"])
                if expected_milestone_title:
                    # Check if milestone needs updating
                    current_milestone_title = current_issue.get("milestone", {}).get("title") if current_issue.get("milestone") else None
                    if current_milestone_title != expected_milestone_title:
                        try:
                            subprocess.run(
                                [
                                    "gh", "issue", "edit", str(issue_number),
                                    "--milestone", expected_milestone_title
                                ],
                                check=True
                            )
                            print(f"Updated issue #{issue_number} milestone to {expected_milestone_title}")
                        except subprocess.CalledProcessError as e:
                            print(f"Error updating issue #{issue_number} milestone: {e}")
                    
        except subprocess.CalledProcessError as e:
            print(f"Error getting issue #{issue_number} details: {e}")
    
    def update_task_from_issue(self, task: Dict, issue: Dict) -> bool:
        """Update a Task Master task based on GitHub issue state."""
        changed = False
        
        # Map GitHub state to Task Master status
        if issue["state"] == "CLOSED":
            if task["status"] not in ["done", "cancelled"]:
                task["status"] = "done"
                changed = True
        else:  # OPEN
            if task["status"] in ["done", "cancelled"]:
                task["status"] = "pending"
                changed = True
        
        return changed
    
    def sync_to_github(self, tasks_data: Dict):
        """Sync Task Master tasks to GitHub issues."""
        print("Syncing tasks to GitHub...")
        
        # Get current GitHub issues
        github_issues = self.get_github_issues()
        
        # Create a map of task IDs found in issue bodies
        issue_task_map = {}
        for issue in github_issues:
            body = issue.get("body", "")
            if "<!-- task-master-id:" in body:
                task_id = body.split("<!-- task-master-id:")[1].split("-->")[0].strip()
                issue_task_map[task_id] = issue["number"]
        
        # Update sync map with any issues created outside this script
        for task_id, issue_number in issue_task_map.items():
            if task_id not in self.sync_map:
                self.sync_map[task_id] = issue_number
                print(f"Found existing issue #{issue_number} for task {task_id}")
        
        # Extract tasks from the correct structure
        tasks = tasks_data.get("master", {}).get("tasks", [])
        if not tasks and "tasks" in tasks_data:
            tasks = tasks_data["tasks"]
        
        # Helper function to process tasks recursively
        def process_task(task, parent_id=None):
            # Build full task ID
            if parent_id:
                task_id = f"{parent_id}.{task['id']}"
            else:
                task_id = str(task["id"])
            
            # Create a full task object with the correct ID
            full_task = task.copy()
            full_task["id"] = task_id
            
            if task_id in self.sync_map:
                # Update existing issue
                issue_number = self.sync_map[task_id]
                self.update_github_issue(issue_number, full_task)
            else:
                # Create new issue
                issue_number = self.create_github_issue(full_task)
                if issue_number:
                    self.sync_map[task_id] = issue_number
                    print(f"Created issue #{issue_number} for task {task_id}")
            
            # Process subtasks
            for subtask in task.get("subtasks", []):
                process_task(subtask, task_id)
        
        # Process all main tasks
        for task in tasks:
            process_task(task)
        
        self.save_sync_map()
    
    def sync_from_github(self, tasks_data: Dict) -> bool:
        """Sync GitHub issue states back to Task Master tasks."""
        print("Syncing from GitHub to Task Master...")
        
        github_issues = self.get_github_issues()
        tasks_changed = False
        
        # Create a map of issue numbers to issues
        issue_map = {issue["number"]: issue for issue in github_issues}
        
        # Extract tasks from the correct structure
        tasks = tasks_data.get("master", {}).get("tasks", [])
        if not tasks and "tasks" in tasks_data:
            tasks = tasks_data["tasks"]
        
        # Helper function to process tasks recursively
        def check_task(task, parent_id=None):
            nonlocal tasks_changed
            
            # Build full task ID
            if parent_id:
                task_id = f"{parent_id}.{task['id']}"
            else:
                task_id = str(task["id"])
            
            if task_id in self.sync_map:
                issue_number = self.sync_map[task_id]
                
                if issue_number in issue_map:
                    issue = issue_map[issue_number]
                    if self.update_task_from_issue(task, issue):
                        tasks_changed = True
                        print(f"Updated task {task_id} status from issue #{issue_number}")
            
            # Process subtasks
            for subtask in task.get("subtasks", []):
                check_task(subtask, task_id)
        
        # Update all tasks
        for task in tasks:
            check_task(task)
        
        return tasks_changed
    
    def run_sync(self, direction: str = "both"):
        """Run the synchronization process."""
        tasks_data = self.load_tasks()
        
        if direction in ["both", "from-github"]:
            tasks_changed = self.sync_from_github(tasks_data)
            if tasks_changed:
                self.save_tasks(tasks_data)
                # Regenerate task files
                subprocess.run(["task-master", "generate"], check=True)
        
        if direction in ["both", "to-github"]:
            self.sync_to_github(tasks_data)
        
        print("Sync completed successfully!")
    
    def create_project_and_setup_sprints(self):
        """Create GitHub Project and set up sprint milestones."""
        print("Setting up GitHub Project and sprints...")
        
        # Create milestones for each sprint
        sprints = [
            {
                "title": "Sprint 1: Foundation",
                "description": "Django setup, Discord OAuth, and User model (Tasks 1-3)",
                "due_date": "2024-02-01"
            },
            {
                "title": "Sprint 2: Character & DKP Core",
                "description": "Character management and DKP system (Tasks 4-5)",
                "due_date": "2024-02-15"
            },
            {
                "title": "Sprint 3: Events & Attendance",
                "description": "Event management and attendance tracking (Tasks 6-7)",
                "due_date": "2024-03-01"
            },
            {
                "title": "Sprint 4: Loot & Discord",
                "description": "Loot distribution and Discord integration (Tasks 8-9)",
                "due_date": "2024-03-15"
            },
            {
                "title": "Sprint 5: Recruitment",
                "description": "Recruitment and voting system (Task 10)",
                "due_date": "2024-03-30"
            }
        ]
        
        # Create milestones
        for i, sprint in enumerate(sprints, 1):
            try:
                subprocess.run(
                    [
                        "gh", "api", "repos/{owner}/{repo}/milestones",
                        "-X", "POST",
                        "-f", f"title={sprint['title']}",
                        "-f", f"description={sprint['description']}",
                        "-f", f"due_on={sprint['due_date']}T00:00:00Z",
                        "-f", f"state=open"
                    ],
                    check=True
                )
                print(f"Created milestone: {sprint['title']}")
            except subprocess.CalledProcessError:
                print(f"Milestone might already exist: {sprint['title']}")

def main():
    parser = argparse.ArgumentParser(description="Sync Task Master tasks with GitHub issues")
    parser.add_argument("--direction", choices=["both", "to-github", "from-github"], 
                      default="both", help="Sync direction")
    parser.add_argument("--setup-project", action="store_true", 
                      help="Create GitHub project and set up sprints")
    parser.add_argument("--owner", help="GitHub repository owner")
    parser.add_argument("--repo", help="GitHub repository name")
    
    args = parser.parse_args()
    
    sync = TaskMasterGitHubSync(args.owner, args.repo)
    
    if args.setup_project:
        sync.create_project_and_setup_sprints()
    
    sync.run_sync(args.direction)

if __name__ == "__main__":
    main()