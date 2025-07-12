# Environment Setup Guide

This document explains how to configure environment variables for the Kromrif Planning application.

## Overview

The application uses environment variables to manage configuration and secrets. There are two different setups:

1. **Local Development** (without Docker): Uses `.env` file
2. **Docker Development**: Uses `.envs/.local/` directory

## Local Development Setup

### 1. Create Environment File

Copy the example file and customize it:

```bash
cp .env.example .env
```

### 2. Configure Discord OAuth

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application or select an existing one
3. Go to OAuth2 settings
4. Add redirect URI: `http://localhost:8000/accounts/discord/login/callback/`
5. Copy your Client ID and Client Secret
6. Update your `.env` file:

```env
DISCORD_CLIENT_ID=your_actual_client_id
DISCORD_CLIENT_SECRET=your_actual_client_secret
```

### 3. Generate Secret Key

Generate a secure Django secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Update your `.env` file:

```env
DJANGO_SECRET_KEY=your_generated_secret_key
```

## Docker Development Setup

### 1. Create Environment Files

Create the environment directory and copy example files:

```bash
mkdir -p .envs/.local
cp envs-examples/local/django .envs/.local/.django
cp envs-examples/local/postgres .envs/.local/.postgres
```

### 2. Configure Discord OAuth

Follow the same Discord setup steps as above, but update:
- `.envs/.local/.django` with your Discord credentials

### 3. Environment File Structure

```
.envs/                          # Actual environment files (ignored by git)
├── .local/
│   ├── .django                 # Django settings, Discord OAuth, etc.
│   └── .postgres               # PostgreSQL database settings
└── .production/                # Production environment files (if needed)

envs-examples/                  # Example files (committed to git)
└── local/
    ├── django                  # Example Django environment file
    └── postgres                # Example PostgreSQL environment file
```

## Required Environment Variables

### Django Settings
- `DJANGO_DEBUG`: Enable/disable debug mode
- `DJANGO_SECRET_KEY`: Secret key for cryptographic signing
- `DJANGO_ACCOUNT_ALLOW_REGISTRATION`: Disable regular signup (keep False)

### Discord OAuth
- `DISCORD_CLIENT_ID`: Your Discord application's client ID
- `DISCORD_CLIENT_SECRET`: Your Discord application's client secret

### Database
- `DATABASE_URL`: Database connection string
  - Local: `sqlite:///db.sqlite3`
  - Docker: `postgres://debug:debug@postgres:5432/kromrif_planning`

### Optional Settings
- `REDIS_URL`: Redis connection for caching and sessions
- `DJANGO_EMAIL_BACKEND`: Email backend for notifications

## Security Notes

⚠️ **IMPORTANT**: Never commit actual environment files to version control!

- `.env` files contain sensitive credentials
- Always use example files for documentation
- The `.gitignore` file excludes all `.env*` and `.envs/` files
- Only `.env.example` and `.envs/.local.example/` should be committed

## Discord OAuth Setup Details

### Redirect URI Configuration

In your Discord application settings, add this exact redirect URI:

```
http://localhost:8000/accounts/discord/login/callback/
```

### OAuth Scopes

The application requests these Discord scopes:
- `identify`: Get user's Discord ID and username
- `email`: Get user's email address (if available)

### User Data Mapping

The application maps Discord data to user fields:
- `discord_id` → Discord user ID
- `discord_username` → Discord username
- `discord_discriminator` → Discord discriminator (legacy)
- `discord_avatar` → Discord avatar hash
- `email` → Discord email (if provided)
- `name` → Discord username (if no display name set)

## Troubleshooting

### Common Issues

1. **OAuth fails with "invalid redirect_uri"**
   - Check that your Discord app has the correct redirect URI
   - Ensure you're using `http://localhost:8000` (not `127.0.0.1`)

2. **"Site matching query does not exist" error**
   - The Django site configuration is incorrect
   - Run: `python manage.py shell` and create the site with domain `localhost:8000`

3. **"MultipleObjectsReturned" error**
   - Duplicate Discord OAuth apps in database
   - Clean up duplicate SocialApp entries in Django admin

4. **Environment variables not loading**
   - Check file permissions on environment files
   - Ensure `DJANGO_READ_DOT_ENV_FILE=True` for local development
   - Verify file names exactly match (no extra extensions)

### Getting Help

If you encounter issues:
1. Check the Docker logs: `docker-compose -f docker-compose.local.yml logs django`
2. Verify environment file contents
3. Test Discord app configuration in Discord Developer Portal
4. Ensure all required environment variables are set