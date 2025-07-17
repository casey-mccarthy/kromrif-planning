# Dependency Security Management

This document outlines our approach to managing security vulnerabilities in Python dependencies.

## 🛡️ Security Tools

### Primary Tools

- **pip-audit**: Official PyPA tool for scanning Python packages for known vulnerabilities
- **safety**: Additional vulnerability scanner with different data sources

### Installation

Security tools are defined in `requirements/security.txt`:

```bash
pip install -r requirements/security.txt
```

## 🔍 Running Security Audits

### Manual Scanning

```bash
# Run the comprehensive security audit script
./scripts/security-audit.sh

# Or run tools individually:
pip-audit                          # Human-readable output
pip-audit --format=json --output=report.json  # JSON report
safety scan                        # Safety scanner
```

### Automated Scanning

- **GitHub Actions**: Runs on every push, PR, and daily at 2 AM UTC
- **CI/CD Integration**: Workflow fails if vulnerabilities are detected
- **Dependency Review**: Automatic review of new dependencies in PRs

## 📊 Vulnerability Response Process

### 1. Detection
- Automated scans run daily and on all code changes
- Manual scans before releases
- Security alerts from GitHub Dependabot

### 2. Assessment
- Review vulnerability details and severity
- Determine impact on our application
- Check if vulnerable code paths are used

### 3. Resolution
- Update to secure versions: `pip install --upgrade package-name`
- Update requirements files with new pinned versions
- Test application functionality after updates
- Re-run security scans to verify fixes

### 4. Documentation
- Update this document if new procedures are needed
- Document any security incidents in appropriate channels

## 📋 Current Security Status

### Last Audit: 2025-07-17
- **pip-audit**: ✅ No vulnerabilities found
- **safety**: ✅ No vulnerabilities found

### Recent Fixes
- **2025-07-17**: Updated Pillow from 11.2.1 to 11.3.0 (fixed PYSEC-2025-61)

## 🔄 Maintenance Schedule

### Daily
- Automated security scans via GitHub Actions

### Weekly
- Review Dependabot security alerts
- Check for new versions of critical dependencies

### Monthly
- Manual review of all dependencies for updates
- Update dependency documentation
- Review and update security procedures

### Before Releases
- Full security audit
- Update all dependencies to latest secure versions
- Review security documentation

## 🚨 Emergency Response

### Critical Vulnerabilities
1. **Immediate**: Stop deployments if affected
2. **Within 2 hours**: Assess impact and create fix plan
3. **Within 4 hours**: Implement and test fixes
4. **Within 6 hours**: Deploy fixes to production
5. **Within 24 hours**: Document incident and update procedures

### High Severity Vulnerabilities
1. **Within 24 hours**: Assess impact and create fix plan
2. **Within 48 hours**: Implement and test fixes
3. **Within 72 hours**: Deploy fixes to production

## 📝 Security Configuration

### pip-audit Configuration
- Default configuration (no custom config needed)
- JSON reports saved to `security-audit-report.json`
- Exit codes used in CI/CD to fail builds on vulnerabilities

### safety Configuration
- Uses latest open-source vulnerability database
- Scans full Python environment
- Integrated with GitHub Actions

## 🔗 Useful Resources

- [pip-audit Documentation](https://github.com/pypa/pip-audit)
- [Safety Documentation](https://github.com/pyupio/safety)
- [Python Security Best Practices](https://python.org/dev/security/)
- [OWASP Dependency Check](https://owasp.org/www-project-dependency-check/)

## 📞 Contact

For security vulnerabilities or questions:
- Create a GitHub issue (for non-sensitive issues)
- Follow responsible disclosure practices
- Review this document for standard procedures 