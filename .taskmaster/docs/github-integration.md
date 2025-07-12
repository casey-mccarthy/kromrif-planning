# Task Master GitHub Integration Guide

This guide explains how to use the Task Master GitHub integration for synchronized project management.

## Overview

The integration provides bidirectional synchronization between Task Master tasks and GitHub issues, allowing you to:

- Automatically create GitHub issues from Task Master tasks
- Update task statuses based on GitHub issue states
- Organize tasks into sprints using GitHub milestones
- Track task hierarchy and dependencies
- Maintain consistent project state across both systems

## Quick Start

### 1. Initial Setup

Run the setup script to configure GitHub labels, milestones, and perform initial sync:

```bash
python3 .taskmaster/scripts/setup-github-integration.py
```

This will:
- Create all necessary GitHub labels
- Set up sprint milestones
- Create a GitHub Project (if you have permissions)
- Perform initial sync of all tasks to GitHub issues

### 2. Install Git Hooks (Optional)

For automatic syncing on every commit:

```bash
.taskmaster/scripts/install-git-hooks.sh
```

### 3. Manual Sync

To manually sync at any time:

```bash
python3 .taskmaster/scripts/sync-github.py
```

Options:
- `--direction both` (default): Bidirectional sync
- `--direction to-github`: Only push Task Master changes to GitHub
- `--direction from-github`: Only pull GitHub changes to Task Master

## Claude Commands

Two custom commands are available for use within Claude Code:

### `/taskmaster-sync`

Basic sync command for quick synchronization:
- Runs bidirectional sync
- Shows summary of changes
- Stages any modified Task Master files

### `/taskmaster-commit-sync`

Comprehensive pre-commit sync workflow:
- Shows current task status
- Performs full bidirectional sync
- Stages all sync-related changes
- Regenerates task files if needed
- Provides commit-ready status

## How It Works

### Task to Issue Mapping

1. Each Task Master task creates a corresponding GitHub issue
2. Task IDs are preserved in issue metadata: `<!-- task-master-id: X.Y -->`
3. Mappings are stored in `.taskmaster/github-sync-map.json`

### Status Synchronization

Task Master Status → GitHub Issue State:
- `pending`, `in-progress`, `blocked`, `deferred` → Open issue
- `done`, `cancelled` → Closed issue

GitHub Issue State → Task Master Status:
- Open issue → Maintains current status (or `pending` if was `done`)
- Closed issue → `done`

### Labels

Issues are automatically labeled based on:
- **Priority**: `high-priority`, `medium-priority`, `low-priority`
- **Type**: `main-task`, `subtask`
- **Sync**: `task-master-sync` (all synced issues)
- **Domain**: `django`, `discord`, `dkp`, `api` (manually added)

### Sprint Organization

Tasks are organized into 5 sprints:

1. **Sprint 1: Foundation** (Tasks 1-3) - ✅ Completed
2. **Sprint 2: Character & DKP Core** (Tasks 4-5)
3. **Sprint 3: Events & Attendance** (Tasks 6-7)
4. **Sprint 4: Loot & Discord** (Tasks 8-9)
5. **Sprint 5: Recruitment** (Task 10)

## Workflow Examples

### Daily Development

1. Start your day with a sync:
   ```bash
   /taskmaster-sync
   ```

2. Check next available task:
   ```bash
   task-master next
   ```

3. Work on the task and update status:
   ```bash
   task-master set-status --id=4.1 --status=in-progress
   ```

4. Before committing, run comprehensive sync:
   ```bash
   /taskmaster-commit-sync
   ```

### Creating New Tasks

1. Add task in Task Master:
   ```bash
   task-master add-task --prompt="Add caching layer for API endpoints" --research
   ```

2. Sync to create GitHub issue:
   ```bash
   python3 .taskmaster/scripts/sync-github.py --direction to-github
   ```

### Closing Issues

1. Complete work and close GitHub issue:
   ```bash
   gh issue close 42
   ```

2. Sync back to Task Master:
   ```bash
   python3 .taskmaster/scripts/sync-github.py --direction from-github
   ```

## File Structure

```
.taskmaster/
├── github-sync-map.json     # Task ID to Issue number mappings
├── scripts/
│   ├── sync-github.py       # Main sync script
│   ├── setup-github-integration.py  # Initial setup
│   └── install-git-hooks.sh # Git hooks installer
└── docs/
    └── github-integration.md # This file

.claude/commands/
├── taskmaster-sync.md       # Basic sync command
└── taskmaster-commit-sync.md # Pre-commit sync command
```

## Troubleshooting

### Authentication Issues

Ensure GitHub CLI is authenticated:
```bash
gh auth status
```

If needed, refresh with required scopes:
```bash
gh auth refresh -s repo,project,write:org
```

### Sync Conflicts

If tasks and issues get out of sync:

1. Check sync map: `cat .taskmaster/github-sync-map.json`
2. Verify issue exists: `gh issue view <number>`
3. Force resync: Delete the sync map and run setup again

### Missing Labels

Rerun label setup:
```bash
.taskmaster/scripts/setup-github-labels.sh
```

## Best Practices

1. **Always sync before major work sessions** to ensure you have the latest status
2. **Use the git hook** for automatic sync on commits
3. **Close issues in GitHub** rather than marking tasks done in Task Master
4. **Add domain labels** to issues for better organization
5. **Update task details** in Task Master, not issue descriptions
6. **Use milestones** to track sprint progress

## Advanced Usage

### Custom Sync Filters

Modify `sync-github.py` to add filters:
- Skip certain task IDs
- Only sync specific priority levels
- Exclude completed tasks from initial sync

### Webhook Integration

For real-time sync, set up GitHub webhooks to trigger sync on issue changes.

### CI/CD Integration

Add sync to your CI/CD pipeline:
```yaml
- name: Sync Task Master
  run: python3 .taskmaster/scripts/sync-github.py --direction from-github
```

## Support

For issues or questions:
1. Check Task Master documentation: `task-master --help`
2. Review GitHub CLI docs: `gh --help`
3. Examine sync script logs for detailed error messages