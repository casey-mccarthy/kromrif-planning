Sync Task Master tasks with GitHub issues bidirectionally: $ARGUMENTS

Steps:
1. First, check current git status to ensure we're in a clean state
2. Run the Task Master GitHub sync script
3. If any Task Master tasks were updated from GitHub, regenerate task files
4. Show a summary of what was synced
5. If this is pre-commit, add any changed Task Master files to the commit

```bash
# Check git status
git status --porcelain

# Run the sync
python3 .taskmaster/scripts/sync-github.py --direction both

# Check if Task Master files changed
if git diff --name-only | grep -q "\.taskmaster/"; then
    echo "Task Master files were updated from GitHub sync"
    git add .taskmaster/tasks/tasks.json .taskmaster/github-sync-map.json
fi

# Show current task status
task-master list
```