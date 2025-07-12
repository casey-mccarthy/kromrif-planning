# 🛡️ Security Setup Guide

This document provides essential security configuration for the Kromrif Planning application. **Follow this guide completely before any production deployment.**

## 🚨 Critical Security Requirements

### 1. Environment Variables Configuration

#### Development Setup
1. **Copy environment template:**
   ```bash
   cp envs-examples/local/django .envs/.local/.django
   ```

2. **Configure required variables in `.envs/.local/.django`:**
   ```bash
   # Generate a secure secret key
   python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
   
   # Update the file with:
   DJANGO_SECRET_KEY=your_generated_secret_key_here
   DJANGO_ADMIN_USERNAME=your_admin_username
   DJANGO_ADMIN_PASSWORD=your_secure_password_8_chars_min
   DJANGO_ADMIN_EMAIL=your_admin_email@domain.com
   ```

3. **Configure Discord OAuth:**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create new application
   - Go to OAuth2 section
   - Add redirect URI: `http://localhost:8000/accounts/discord/login/callback/`
   - Copy Client ID and Secret to your `.envs/.local/.django` file

#### Production Setup
1. **Use production environment template:**
   ```bash
   cp envs-examples/production/django your_production_env_file
   ```

2. **Configure ALL required variables (see production template for complete list)**

3. **NEVER set development admin variables in production:**
   - Do NOT set `DJANGO_ADMIN_USERNAME`
   - Do NOT set `DJANGO_ADMIN_PASSWORD`
   - Do NOT set `DJANGO_ADMIN_EMAIL`

### 2. Admin User Management

#### Development (Automatic)
- Admin user is created automatically via environment variables
- Only runs when `DEBUG=True`
- Requires all three environment variables to be set

#### Production (Manual)
```bash
# Create admin user manually in production
python manage.py createsuperuser

# Or for Docker:
docker-compose -f docker-compose.production.yml exec django python manage.py createsuperuser
```

### 3. Discord OAuth Security

#### Development vs Production Applications
- **Use separate Discord applications for dev and prod**
- **Different redirect URIs:**
  - Dev: `http://localhost:8000/accounts/discord/login/callback/`
  - Prod: `https://yourdomain.com/accounts/discord/login/callback/`

#### OAuth Configuration
```bash
# Development
DISCORD_CLIENT_ID=your_dev_client_id
DISCORD_CLIENT_SECRET=your_dev_client_secret

# Production  
DISCORD_CLIENT_ID=your_prod_client_id
DISCORD_CLIENT_SECRET=your_prod_client_secret
```

## 🔐 Role-Based Access Control

### Admin Permission Hierarchy
```
developer    > officer > recruiter > member > applicant > guest
(superuser)    (staff)   (staff)     (user)   (user)     (user)
```

### Bulk Role Assignment Permissions
- **Developers:** Can assign member, applicant, guest roles
- **Officers:** Can assign applicant, guest roles  
- **Recruiters:** Can assign guest role only
- **Lower roles:** Cannot assign any roles

### Protection Features
- Cannot downgrade higher-privileged users
- Permission validation on all bulk actions
- Audit logging of role changes

## 🔍 Security Validation Checklist

### Before Development
- [ ] Environment variables configured from template
- [ ] Secure secret key generated and set
- [ ] Discord OAuth app created and configured
- [ ] Admin credentials set in environment
- [ ] `.envs/` directory in `.gitignore` (should already be)

### Before Production Deployment
- [ ] Production environment variables configured
- [ ] NO development admin variables set in production
- [ ] Separate Discord OAuth app for production
- [ ] SSL/HTTPS configured
- [ ] Secure admin URL configured (`DJANGO_ADMIN_URL`)
- [ ] Database credentials secured
- [ ] Email service configured
- [ ] Admin user created manually via `createsuperuser`

### Security Monitoring
- [ ] Monitor failed login attempts
- [ ] Review user role changes in logs
- [ ] Monitor Discord OAuth errors
- [ ] Regular security updates

## 🚫 Common Security Mistakes

### ❌ DO NOT:
1. **Commit real secrets to git**
2. **Use hardcoded passwords**
3. **Use development Discord app in production**
4. **Set development admin variables in production**
5. **Use default/weak secret keys**
6. **Allow 0.0.0.0 in ALLOWED_HOSTS**
7. **Run with DEBUG=True in production**

### ✅ DO:
1. **Use environment variables for all secrets**
2. **Generate secure, unique passwords**
3. **Use separate Discord apps for dev/prod**
4. **Create admin users manually in production**
5. **Use cryptographically secure secret keys**
6. **Restrict ALLOWED_HOSTS to your domains**
7. **Set DEBUG=False in production**

## 🆘 Security Incident Response

### If Credentials are Compromised:
1. **Immediately rotate all affected credentials**
2. **Check access logs for suspicious activity**
3. **Force password reset for all admin users**
4. **Regenerate Django secret key**
5. **Update Discord OAuth app credentials**

### If Admin Account is Compromised:
1. **Disable the compromised account**
2. **Check audit logs for unauthorized changes**
3. **Review all user role modifications**
4. **Create new admin account**
5. **Force logout all sessions**

## 🔧 Quick Setup Commands

### Development Environment
```bash
# 1. Copy environment template
cp envs-examples/local/django .envs/.local/.django

# 2. Generate secret key
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# 3. Edit .envs/.local/.django with your values
nano .envs/.local/.django

# 4. Start Docker environment
docker-compose -f docker-compose.local.yml up --build
```

### Production Environment
```bash
# 1. Configure production environment file
cp envs-examples/production/django .env.production

# 2. Edit with production values (all variables required)
nano .env.production

# 3. Deploy and create admin user
docker-compose -f docker-compose.production.yml up -d
docker-compose -f docker-compose.production.yml exec django python manage.py createsuperuser
```

## 📞 Support

For security questions or incident reporting:
- Review this document thoroughly
- Check environment variable configuration
- Verify Discord OAuth setup
- Ensure production vs development separation

**Remember: Security is not optional. Follow this guide completely.** 