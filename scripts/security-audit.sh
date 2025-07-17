#!/bin/bash

# Security Audit Script
# Runs comprehensive dependency vulnerability scanning

set -e

echo "🔍 Running Security Audit..."
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}Warning: Not in a virtual environment${NC}"
    echo "It's recommended to run this in your project's virtual environment"
    echo ""
fi

# Run pip-audit
echo "🛡️  Running pip-audit..."
if pip-audit --format=json --output=security-audit-report.json --timeout=30; then
    echo -e "${GREEN}✅ pip-audit: No vulnerabilities found${NC}"
else
    exit_code=$?
    if [ $exit_code -eq 1 ]; then
        echo -e "${RED}❌ pip-audit: Vulnerabilities detected!${NC}"
        echo "📄 Detailed report saved to: security-audit-report.json"
        echo "🔍 Showing vulnerability details:"
        pip-audit --timeout=30 || echo "⚠️  Network timeout - check security-audit-report.json for cached results"
    else
        echo -e "${YELLOW}⚠️  pip-audit: Network timeout or other error${NC}"
        echo "📄 You can still check security-audit-report.json if it was generated"
    fi
    echo ""
fi

echo ""

# Run safety scan (using new scan command)
echo "🛡️  Running safety scan..."
if timeout 60 safety scan --continue-on-error 2>/dev/null; then
    echo -e "${GREEN}✅ safety: No vulnerabilities found${NC}"
else
    exit_code=$?
    if [ $exit_code -eq 1 ]; then
        echo -e "${RED}❌ safety: Vulnerabilities detected!${NC}"
    elif [ $exit_code -eq 124 ]; then
        echo -e "${YELLOW}⚠️  safety: Timeout - skipping safety scan${NC}"
        echo "💡 You can run 'safety scan' manually later"
    else
        echo -e "${YELLOW}⚠️  safety: Skipped (requires authentication or network issue)${NC}"
        echo "💡 You can run 'safety scan' manually later"
    fi
    echo ""
fi

echo ""
echo "🔒 Security audit complete!"
echo "📄 Full pip-audit report: security-audit-report.json"
echo ""
echo "💡 To fix vulnerabilities:"
echo "   1. Review the output above"
echo "   2. Update vulnerable packages: pip install --upgrade package-name"
echo "   3. Update requirements files with new versions"
echo "   4. Re-run this script to verify fixes" 