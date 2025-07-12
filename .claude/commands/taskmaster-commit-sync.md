Perform a complete Task Master to GitHub sync before committing changes.

This command ensures Task Master and GitHub issues are fully synchronized before making a commit.

Steps:
1. Save current work state
2. Sync Task Master with GitHub bidirectionally
3. Stage any sync-related changes
4. Show sync summary
5. Prepare for commit

```bash
echo "🔄 Starting Task Master GitHub sync..."

# Ensure sync script exists
if [ ! -f ".taskmaster/scripts/sync-github.py" ]; then
    echo "❌ Sync script not found. Please run the setup first."
    exit 1
fi

# Show current task status before sync
echo "\n📊 Current Task Status:"
task-master list --status pending --limit 3
task-master list --status in-progress

# Run bidirectional sync
echo "\n🔄 Syncing with GitHub..."
python3 .taskmaster/scripts/sync-github.py --direction both

# Check if any Task Master files were modified
TASKMASTER_CHANGES=$(git diff --name-only | grep "\.taskmaster/" || true)

if [ -n "$TASKMASTER_CHANGES" ]; then
    echo "\n📝 Task Master files updated from GitHub:"
    echo "$TASKMASTER_CHANGES"
    
    # Stage the sync-related files
    git add .taskmaster/tasks/tasks.json .taskmaster/github-sync-map.json
    
    # Regenerate task markdown files if needed
    task-master generate
fi

# Show final status
echo "\n✅ Sync completed! Current status:"
task-master list --status pending --limit 3

echo "\n💡 Ready to commit. Task Master and GitHub are now in sync."
```