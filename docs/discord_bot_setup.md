# Discord Bot API Setup Guide

This guide explains how to configure the Discord bot API endpoints with proper authentication and permissions.

## Settings Configuration

Add the following settings to your Django settings file:

```python
# Discord Bot Configuration
DISCORD_BOT_TOKEN = 'your_discord_bot_token_here'
DISCORD_WEBHOOK_TOKEN = 'your_webhook_token_here'  # Optional alternative auth
DISCORD_WEBHOOK_SECRET = 'your_webhook_secret_here'  # For signature verification

# Discord Webhook URLs for notifications
DISCORD_WEBHOOK_URLS = {
    'default': 'https://discord.com/api/webhooks/your_default_webhook',
    'loot': 'https://discord.com/api/webhooks/your_loot_webhook',
    'attendance': 'https://discord.com/api/webhooks/your_attendance_webhook',
    'moderation': 'https://discord.com/api/webhooks/your_moderation_webhook',
}
```

## API Endpoints

### Discord Bot Endpoints

These endpoints require Discord bot authentication:

**Authentication**: Include `Authorization: Bot YOUR_BOT_TOKEN` header

- `GET /api/raiders/discord/roster/guild_roster/` - Get complete guild roster
- `GET /api/raiders/discord/roster/member_lookup/` - Look up specific member
- `GET /api/raiders/discord/roster/guild_stats/` - Get guild statistics
- `POST /api/raiders/discord/members/update_member_status/` - Update member status
- `POST /api/raiders/discord/members/link_user/` - Link Discord user to account
- `POST /api/raiders/discord/members/unlink_user/` - Unlink Discord user
- `POST /api/raiders/discord/members/sync_status/` - Sync member status

### Webhook Endpoints

These endpoints handle incoming Discord webhooks:

- `POST /api/raiders/webhooks/discord/` - Basic webhook handler
- `POST /api/raiders/webhooks/discord/api/` - DRF-enhanced webhook handler

**Authentication**: Include `X-Webhook-Token: YOUR_WEBHOOK_TOKEN` header or Discord signature verification

## Permission Classes

### IsDiscordBot
Validates Discord bot token authentication.

### IsBotOrStaff  
Allows access to Discord bots or Django staff users.

### IsMemberOrHigher
Restricts access to guild members or higher roles.

### IsOfficerOrHigher
Restricts access to officers or higher roles.

### IsOwnerOrOfficer
Allows access to object owners or officers.

### IsReadOnlyOrOfficer
Read access for all authenticated users, write access for officers.

### HasAttendanceBasedVoting
Checks if user has sufficient attendance for voting privileges.

### DiscordWebhookPermission
Validates Discord webhook signatures and source.

## Usage Examples

### Bot Authentication
```python
import requests

headers = {
    'Authorization': 'Bot YOUR_BOT_TOKEN',
    'Content-Type': 'application/json'
}

response = requests.get(
    'https://yoursite.com/api/raiders/discord/roster/guild_roster/',
    headers=headers
)
```

### Webhook Configuration
```python
# Discord webhook payload
payload = {
    't': 'GUILD_MEMBER_ADD',  # Event type
    'd': {  # Event data
        'user': {
            'id': '123456789',
            'username': 'newmember'
        }
    }
}

headers = {
    'X-Webhook-Token': 'YOUR_WEBHOOK_TOKEN',
    'Content-Type': 'application/json'
}

requests.post(
    'https://yoursite.com/api/raiders/webhooks/discord/',
    json=payload,
    headers=headers
)
```

## Management Commands

### Process Discord Notifications
```bash
# Process notification queue once
python manage.py process_discord_notifications

# Run continuously every 30 seconds
python manage.py process_discord_notifications --continuous --interval=30

# Dry run to see what would be sent
python manage.py process_discord_notifications --dry-run
```

### Discord User Linking
```bash
# Link a Discord user to an application account
python manage.py discord_link_users --action=link --discord-id=123456789 --username=myuser

# Bulk link from CSV file
python manage.py discord_link_users --action=bulk-link --csv-file=links.csv

# List all linked users
python manage.py discord_link_users --action=list

# Validate all Discord links
python manage.py discord_link_users --action=validate
```

## Role Hierarchy

The permission system uses the following role hierarchy:

1. **guest** (0) - No permissions
2. **applicant** (1) - Limited access
3. **member** (2) - Basic member access
4. **recruiter** (3) - Recruitment permissions
5. **officer** (4) - Administrative access
6. **developer** (5) - Full access

## Security Considerations

1. **Bot Token Security**: Store Discord bot tokens securely and never expose them in logs
2. **Webhook Verification**: Always verify webhook signatures in production
3. **Rate Limiting**: Implement rate limiting for Discord API calls
4. **Error Handling**: Log security-related errors for monitoring
5. **Permission Auditing**: Regularly audit user permissions and role assignments

## Troubleshooting

### Common Issues

1. **401 Unauthorized**: Check bot token configuration
2. **403 Forbidden**: Verify user role and permissions
3. **Webhook Failures**: Check webhook token or signature verification
4. **Rate Limits**: Implement exponential backoff for Discord API calls

### Debug Settings
```python
# Enable debug logging for Discord integration
LOGGING = {
    'loggers': {
        'kromrif_planning.raiders.permissions': {
            'level': 'DEBUG',
        },
        'kromrif_planning.raiders.notification_service': {
            'level': 'DEBUG',
        },
    }
}
```