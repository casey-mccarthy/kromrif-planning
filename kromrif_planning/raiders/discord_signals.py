"""
Django signals for Discord integration and webhook notifications.
Handles Discord events and triggers appropriate actions in the application.
"""

import logging
import json
from typing import Dict, Optional
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver, Signal
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone

from .models import Character, Rank, LootDistribution, RaidAttendance, CharacterOwnership

User = get_user_model()
logger = logging.getLogger(__name__)

# Custom signals for Discord events
discord_member_joined = Signal()  # Sent when a Discord member joins the guild
discord_member_left = Signal()    # Sent when a Discord member leaves the guild
discord_member_updated = Signal() # Sent when a Discord member's data is updated
discord_role_changed = Signal()   # Sent when a Discord member's roles change
discord_status_changed = Signal() # Sent when a member's online status changes
discord_webhook_received = Signal() # Generic signal for incoming webhooks

# Signal for notification events
notification_required = Signal()  # Sent when a notification should be sent to Discord


@receiver(post_save, sender=User)
def handle_user_discord_link_change(sender, instance, created, **kwargs):
    """
    Handle changes to Discord linking on User model.
    Triggers notifications when users are linked/unlinked from Discord.
    """
    if created:
        return  # Skip for new users
    
    # Check if Discord ID changed
    if hasattr(instance, '_discord_id_changed'):
        old_discord_id = getattr(instance, '_old_discord_id', None)
        new_discord_id = instance.discord_id
        
        if old_discord_id and not new_discord_id:
            # User was unlinked from Discord
            notification_required.send(
                sender=sender,
                notification_type='discord_unlinked',
                user=instance,
                data={
                    'username': instance.username,
                    'old_discord_id': old_discord_id,
                    'timestamp': timezone.now().isoformat()
                }
            )
            logger.info(f"Discord unlink notification triggered for {instance.username}")
            
        elif not old_discord_id and new_discord_id:
            # User was linked to Discord
            notification_required.send(
                sender=sender,
                notification_type='discord_linked',
                user=instance,
                data={
                    'username': instance.username,
                    'discord_id': new_discord_id,
                    'discord_username': getattr(instance, 'discord_username', None),
                    'timestamp': timezone.now().isoformat()
                }
            )
            logger.info(f"Discord link notification triggered for {instance.username}")


@receiver(pre_save, sender=User)
def track_discord_id_changes(sender, instance, **kwargs):
    """
    Track Discord ID changes for notification purposes.
    """
    if instance.pk:
        try:
            old_instance = User.objects.get(pk=instance.pk)
            if old_instance.discord_id != instance.discord_id:
                instance._discord_id_changed = True
                instance._old_discord_id = old_instance.discord_id
        except User.DoesNotExist:
            pass


@receiver(post_save, sender=Character)
def handle_character_status_change(sender, instance, created, **kwargs):
    """
    Handle character status changes and notify Discord.
    """
    if created:
        # New character created
        notification_required.send(
            sender=sender,
            notification_type='character_created',
            user=instance.user,
            data={
                'character_name': instance.name,
                'character_class': instance.character_class,
                'level': instance.level,
                'username': instance.user.username,
                'timestamp': timezone.now().isoformat()
            }
        )
        return
    
    # Check for status changes
    if hasattr(instance, '_status_changed'):
        old_status = getattr(instance, '_old_status', None)
        new_status = instance.status
        
        notification_required.send(
            sender=sender,
            notification_type='character_status_changed',
            user=instance.user,
            data={
                'character_name': instance.name,
                'old_status': old_status,
                'new_status': new_status,
                'username': instance.user.username,
                'timestamp': timezone.now().isoformat()
            }
        )


@receiver(pre_save, sender=Character)
def track_character_status_changes(sender, instance, **kwargs):
    """
    Track character status changes for notification purposes.
    """
    if instance.pk:
        try:
            old_instance = Character.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                instance._status_changed = True
                instance._old_status = old_instance.status
        except Character.DoesNotExist:
            pass


@receiver(post_save, sender=LootDistribution)
def handle_loot_distribution_notification(sender, instance, created, **kwargs):
    """
    Send Discord notification when loot is distributed.
    """
    if created:
        notification_required.send(
            sender=sender,
            notification_type='loot_awarded',
            user=instance.user,
            data={
                'item_name': instance.item.name,
                'character_name': instance.character_name,
                'point_cost': float(instance.point_cost),
                'quantity': instance.quantity,
                'total_cost': float(instance.point_cost * instance.quantity),
                'raid_title': instance.raid.title if instance.raid else None,
                'distributed_by': instance.distributed_by.username if instance.distributed_by else 'System',
                'timestamp': instance.distributed_at.isoformat()
            }
        )


@receiver(post_save, sender=RaidAttendance)
def handle_raid_attendance_notification(sender, instance, created, **kwargs):
    """
    Send Discord notification for raid attendance tracking.
    """
    if created:
        # Batch notifications to avoid spam
        cache_key = f"raid_attendance_notification_{instance.raid.id}"
        attendees = cache.get(cache_key, [])
        attendees.append({
            'username': instance.user.username,
            'character_name': instance.character_name,
            'on_time': instance.on_time
        })
        cache.set(cache_key, attendees, 60)  # Cache for 1 minute
        
        # Check if this is the last expected attendee (optional logic)
        # For now, we'll send individual notifications
        if len(attendees) == 1:  # First attendee triggers the notification
            notification_required.send(
                sender=sender,
                notification_type='raid_attendance_started',
                user=instance.raid.leader,
                data={
                    'raid_title': instance.raid.title,
                    'event_name': instance.raid.event.name,
                    'date': instance.raid.date.isoformat(),
                    'leader': instance.raid.leader.username if instance.raid.leader else 'Unknown',
                    'timestamp': timezone.now().isoformat()
                }
            )


@receiver(post_save, sender=CharacterOwnership)
def handle_character_transfer_notification(sender, instance, created, **kwargs):
    """
    Send Discord notification when a character is transferred.
    """
    if created:
        notification_required.send(
            sender=sender,
            notification_type='character_transferred',
            user=instance.new_owner,
            data={
                'character_name': instance.character.name,
                'previous_owner': instance.previous_owner.username if instance.previous_owner else 'None',
                'new_owner': instance.new_owner.username,
                'reason': instance.get_reason_display(),
                'notes': instance.notes,
                'transferred_by': instance.transferred_by.username if instance.transferred_by else 'System',
                'timestamp': instance.transfer_date.isoformat()
            }
        )


# Discord webhook event handlers
@receiver(discord_member_joined)
def handle_discord_member_joined(sender, member_data, **kwargs):
    """
    Handle when a Discord member joins the guild.
    
    Args:
        member_data: Discord member data from webhook
    """
    discord_id = member_data.get('user', {}).get('id')
    discord_username = member_data.get('user', {}).get('username')
    
    logger.info(f"Discord member joined: {discord_username} ({discord_id})")
    
    # Check if this Discord user is already linked
    from .services import DiscordMemberService
    user = DiscordMemberService.find_member_by_discord_id(discord_id)
    
    if user:
        # Update user's active status if they were inactive
        if not user.is_active:
            user.is_active = True
            user.save()
            logger.info(f"Reactivated user {user.username} after Discord rejoin")
        
        notification_required.send(
            sender=None,
            notification_type='linked_member_joined',
            user=user,
            data={
                'username': user.username,
                'discord_username': discord_username,
                'discord_id': discord_id,
                'timestamp': timezone.now().isoformat()
            }
        )
    else:
        # New Discord member not linked to any user
        notification_required.send(
            sender=None,
            notification_type='unlinked_member_joined',
            user=None,
            data={
                'discord_username': discord_username,
                'discord_id': discord_id,
                'timestamp': timezone.now().isoformat()
            }
        )


@receiver(discord_member_left)
def handle_discord_member_left(sender, member_data, **kwargs):
    """
    Handle when a Discord member leaves the guild.
    
    Args:
        member_data: Discord member data from webhook
    """
    discord_id = member_data.get('user', {}).get('id')
    discord_username = member_data.get('user', {}).get('username')
    
    logger.info(f"Discord member left: {discord_username} ({discord_id})")
    
    # Check if this Discord user is linked
    from .services import DiscordMemberService
    user = DiscordMemberService.find_member_by_discord_id(discord_id)
    
    if user:
        # Optionally deactivate the user
        # user.is_active = False
        # user.save()
        
        notification_required.send(
            sender=None,
            notification_type='member_left_guild',
            user=user,
            data={
                'username': user.username,
                'discord_username': discord_username,
                'discord_id': discord_id,
                'timestamp': timezone.now().isoformat()
            }
        )


@receiver(discord_role_changed)
def handle_discord_role_change(sender, member_data, old_roles, new_roles, **kwargs):
    """
    Handle Discord role changes for a member.
    
    Args:
        member_data: Discord member data
        old_roles: Previous role IDs
        new_roles: New role IDs
    """
    discord_id = member_data.get('user', {}).get('id')
    
    # Check if this Discord user is linked
    from .services import DiscordMemberService
    user = DiscordMemberService.find_member_by_discord_id(discord_id)
    
    if user:
        added_roles = set(new_roles) - set(old_roles)
        removed_roles = set(old_roles) - set(new_roles)
        
        if added_roles or removed_roles:
            notification_required.send(
                sender=None,
                notification_type='member_roles_changed',
                user=user,
                data={
                    'username': user.username,
                    'discord_id': discord_id,
                    'added_roles': list(added_roles),
                    'removed_roles': list(removed_roles),
                    'timestamp': timezone.now().isoformat()
                }
            )


@receiver(discord_webhook_received)
def handle_generic_discord_webhook(sender, event_type, data, **kwargs):
    """
    Handle generic Discord webhook events.
    
    Args:
        event_type: Type of Discord event
        data: Event data from webhook
    """
    logger.debug(f"Received Discord webhook event: {event_type}")
    
    # Route to specific handlers based on event type
    event_handlers = {
        'GUILD_MEMBER_ADD': lambda d: discord_member_joined.send(sender=None, member_data=d),
        'GUILD_MEMBER_REMOVE': lambda d: discord_member_left.send(sender=None, member_data=d),
        'GUILD_MEMBER_UPDATE': lambda d: discord_member_updated.send(sender=None, member_data=d),
    }
    
    handler = event_handlers.get(event_type)
    if handler:
        handler(data)
    else:
        logger.warning(f"Unhandled Discord webhook event type: {event_type}")


# Notification processor
@receiver(notification_required)
def process_notification_request(sender, notification_type, user, data, **kwargs):
    """
    Process notification requests and queue them for sending.
    
    Args:
        notification_type: Type of notification
        user: User associated with the notification
        data: Notification data
    """
    logger.info(f"Processing notification: {notification_type}")
    
    # Here you would typically queue the notification for sending
    # This could involve:
    # 1. Saving to a notification queue table
    # 2. Sending to a message queue (Redis, RabbitMQ, etc.)
    # 3. Calling a webhook sender service
    
    # For now, we'll just log it
    notification_data = {
        'type': notification_type,
        'user_id': user.id if user else None,
        'username': user.username if user else 'System',
        'data': data,
        'created_at': timezone.now().isoformat()
    }
    
    # Cache the notification for batch processing
    cache_key = f"discord_notifications_queue"
    notifications = cache.get(cache_key, [])
    notifications.append(notification_data)
    cache.set(cache_key, notifications, 300)  # Cache for 5 minutes
    
    logger.debug(f"Queued notification: {notification_data}")