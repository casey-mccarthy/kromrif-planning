#!/bin/bash

# Install git hooks for Task Master GitHub sync

echo "🔧 Installing git hooks for automatic Task Master sync..."

# Create hooks directory if it doesn't exist
mkdir -p .git/hooks

# Create pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash

# Task Master GitHub sync pre-commit hook

echo "🔄 Running Task Master GitHub sync..."

# Check if sync script exists
if [ -f ".taskmaster/scripts/sync-github.py" ]; then
    # Run bidirectional sync
    python3 .taskmaster/scripts/sync-github.py --direction both
    
    # Stage any updated Task Master files
    if git diff --cached --name-only | grep -q "\.taskmaster/"; then
        git add .taskmaster/tasks/tasks.json .taskmaster/github-sync-map.json
        echo "✅ Task Master files synced and staged"
    fi
else
    echo "⚠️  Task Master sync script not found, skipping sync"
fi

exit 0
EOF

# Make the hook executable
chmod +x .git/hooks/pre-commit

echo "✅ Git hooks installed successfully!"
echo ""
echo "The pre-commit hook will automatically:"
echo "  - Sync Task Master tasks with GitHub issues"
echo "  - Update task statuses from GitHub"
echo "  - Stage any sync-related changes"
echo ""
echo "To bypass the hook, use: git commit --no-verify"