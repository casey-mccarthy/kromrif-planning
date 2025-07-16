#!/bin/bash

# Setup GitHub labels for Task Master integration

echo "🏷️  Setting up GitHub labels for Task Master sync..."

# Priority labels
gh label create high-priority --color d73a4a --description "High priority tasks" 2>/dev/null || echo "Label high-priority already exists"
gh label create medium-priority --color fbca04 --description "Medium priority tasks" 2>/dev/null || echo "Label medium-priority already exists"
gh label create low-priority --color 0e8a16 --description "Low priority tasks" 2>/dev/null || echo "Label low-priority already exists"

# Task type labels
gh label create main-task --color 1d76db --description "Main task items" 2>/dev/null || echo "Label main-task already exists"
gh label create subtask --color 0075ca --description "Subtask items" 2>/dev/null || echo "Label subtask already exists"

# Sync label
gh label create task-master-sync --color 5319e7 --description "Synced with Task Master" 2>/dev/null || echo "Label task-master-sync already exists"

# Status labels
gh label create in-progress --color ffd93d --description "Currently being worked on" 2>/dev/null || echo "Label in-progress already exists"
gh label create blocked --color e11d21 --description "Blocked by external factors" 2>/dev/null || echo "Label blocked already exists"
gh label create deferred --color c5def5 --description "Postponed for later" 2>/dev/null || echo "Label deferred already exists"

# Domain labels
gh label create django --color 092e20 --description "Django framework related tasks" 2>/dev/null || echo "Label django already exists"
gh label create discord --color 5865F2 --description "Discord integration tasks" 2>/dev/null || echo "Label discord already exists"
gh label create dkp --color ff6b6b --description "DKP system related" 2>/dev/null || echo "Label dkp already exists"
gh label create api --color 4dabf7 --description "API development" 2>/dev/null || echo "Label api already exists"

echo "✅ GitHub labels setup complete!"