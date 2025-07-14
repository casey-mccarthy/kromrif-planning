"""
Service for sending Discord notifications and managing webhook notifications.
"""

import json
import logging
import requests
from typing import Dict, List, Optional
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
from .utils.retry import (
    make_discord_request, DiscordErrorHandler, exponential_backoff,
    DiscordAPIError, DiscordRateLimitError, discord_webhook_circuit_breaker,
    safe_discord_operation
)

logger = logging.getLogger(__name__)


class DiscordNotificationService:
    """
    Service for sending notifications to Discord channels via webhooks.
    """
    
    def __init__(self):
        self.webhook_urls = getattr(settings, 'DISCORD_WEBHOOK_URLS', {})
        self.default_webhook_url = self.webhook_urls.get('default')
        self.timeout = 10  # Request timeout in seconds
    
    @safe_discord_operation("send_notification", default_return=False)
    def send_notification(
        self,
        notification_type: str,
        data: Dict,
        channel: str = 'default',
        user_id: Optional[int] = None
    ) -> bool:
        """
        Send a notification to Discord.
        
        Args:
            notification_type: Type of notification
            data: Notification data
            channel: Discord channel identifier
            user_id: User ID for user-specific notifications
            
        Returns:
            bool: True if notification was sent successfully
        """
        webhook_url = self.webhook_urls.get(channel, self.default_webhook_url)
        
        if not webhook_url:
            logger.warning(f"No webhook URL configured for channel: {channel}")
            return False
        
        # Build Discord message
        embed = self.build_embed(notification_type, data)
        
        if not embed:
            logger.warning(f"Could not build embed for notification type: {notification_type}")
            return False
        
        # Send to Discord
        return self.send_webhook_message(webhook_url, embeds=[embed])
    
    @discord_webhook_circuit_breaker
    @exponential_backoff(max_retries=3, base_delay=1.0)
    def send_webhook_message(
        self,
        webhook_url: str,
        content: Optional[str] = None,
        embeds: Optional[List[Dict]] = None,
        username: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> bool:
        """
        Send a message to Discord via webhook with error handling and retries.
        
        Args:
            webhook_url: Discord webhook URL
            content: Text content of the message
            embeds: List of Discord embeds
            username: Override webhook username
            avatar_url: Override webhook avatar
            
        Returns:
            bool: True if message was sent successfully
        """
        payload = {}
        
        if content:
            payload['content'] = content
        
        if embeds:
            payload['embeds'] = embeds
        
        if username:
            payload['username'] = username
        
        if avatar_url:
            payload['avatar_url'] = avatar_url
        
        with DiscordErrorHandler("send_webhook_message"):
            try:
                # Use the enhanced Discord request function
                make_discord_request(
                    method='POST',
                    url=webhook_url,
                    json_data=payload,
                    timeout=self.timeout
                )
                
                logger.debug("Discord notification sent successfully")
                return True
                
            except DiscordRateLimitError as e:
                logger.warning(f"Discord rate limited, retry after {e.retry_after}s")
                # Re-raise to trigger retry mechanism
                raise
                
            except DiscordAPIError as e:
                logger.error(f"Discord webhook error: {e.message} (Status: {e.status_code})")
                return False
                
            except Exception as e:
                logger.error(f"Unexpected error sending Discord webhook: {str(e)}")
                return False
    
    def build_embed(self, notification_type: str, data: Dict) -> Optional[Dict]:
        """
        Build Discord embed for notification.
        
        Args:
            notification_type: Type of notification
            data: Notification data
            
        Returns:
            Discord embed dictionary or None
        """
        embed_builders = {
            'discord_linked': self.build_discord_linked_embed,
            'discord_unlinked': self.build_discord_unlinked_embed,
            'character_created': self.build_character_created_embed,
            'character_status_changed': self.build_character_status_embed,
            'character_transferred': self.build_character_transfer_embed,
            'loot_awarded': self.build_loot_awarded_embed,
            'raid_attendance_started': self.build_raid_attendance_embed,
            'member_left_guild': self.build_member_left_embed,
            'linked_member_joined': self.build_member_joined_embed,
            'unlinked_member_joined': self.build_unlinked_member_embed,
            'member_roles_changed': self.build_roles_changed_embed,
        }
        
        builder = embed_builders.get(notification_type)
        if builder:
            return builder(data)
        
        # Default embed for unknown types
        return {
            'title': f'Notification: {notification_type}',
            'description': f'Event data: {json.dumps(data, indent=2)}',
            'color': 0x7289DA,  # Discord blurple
            'timestamp': datetime.now().isoformat()
        }
    
    def build_discord_linked_embed(self, data: Dict) -> Dict:
        """Build embed for Discord account linking."""
        return {
            'title': '🔗 Discord Account Linked',
            'description': f"**{data['username']}** has linked their Discord account",
            'fields': [
                {
                    'name': 'Discord User',
                    'value': f"{data.get('discord_username', 'Unknown')} (`{data['discord_id']}`)",
                    'inline': True
                },
                {
                    'name': 'Application User',
                    'value': data['username'],
                    'inline': True
                }
            ],
            'color': 0x00FF00,  # Green
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
    
    def build_discord_unlinked_embed(self, data: Dict) -> Dict:
        """Build embed for Discord account unlinking."""
        return {
            'title': '🔓 Discord Account Unlinked',
            'description': f"**{data['username']}** has unlinked their Discord account",
            'fields': [
                {
                    'name': 'Previous Discord ID',
                    'value': f"`{data['old_discord_id']}`",
                    'inline': True
                },
                {
                    'name': 'Application User',
                    'value': data['username'],
                    'inline': True
                }
            ],
            'color': 0xFF0000,  # Red
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
    
    def build_character_created_embed(self, data: Dict) -> Dict:
        """Build embed for character creation."""
        return {
            'title': '⭐ New Character Created',
            'description': f"**{data['character_name']}** has been created",
            'fields': [
                {
                    'name': 'Class',
                    'value': data['character_class'],
                    'inline': True
                },
                {
                    'name': 'Level',
                    'value': str(data['level']),
                    'inline': True
                },
                {
                    'name': 'Owner',
                    'value': data['username'],
                    'inline': True
                }
            ],
            'color': 0x00FFFF,  # Cyan
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
    
    def build_loot_awarded_embed(self, data: Dict) -> Dict:
        """Build embed for loot distribution."""
        return {
            'title': '🎁 Loot Awarded',
            'description': f"**{data['item_name']}** awarded to **{data['character_name']}**",
            'fields': [
                {
                    'name': 'Cost',
                    'value': f"{data['point_cost']} DKP",
                    'inline': True
                },
                {
                    'name': 'Quantity',
                    'value': str(data['quantity']),
                    'inline': True
                },
                {
                    'name': 'Total Cost',
                    'value': f"{data['total_cost']} DKP",
                    'inline': True
                },
                {
                    'name': 'Raid',
                    'value': data.get('raid_title', 'Unknown'),
                    'inline': True
                },
                {
                    'name': 'Distributed By',
                    'value': data['distributed_by'],
                    'inline': True
                }
            ],
            'color': 0xFFD700,  # Gold
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
    
    def build_raid_attendance_embed(self, data: Dict) -> Dict:
        """Build embed for raid attendance."""
        return {
            'title': '⚔️ Raid Started',
            'description': f"**{data['raid_title']}** attendance tracking has begun",
            'fields': [
                {
                    'name': 'Event',
                    'value': data['event_name'],
                    'inline': True
                },
                {
                    'name': 'Date',
                    'value': data['date'],
                    'inline': True
                },
                {
                    'name': 'Leader',
                    'value': data['leader'],
                    'inline': True
                }
            ],
            'color': 0xFF4500,  # Orange Red
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
    
    def build_member_joined_embed(self, data: Dict) -> Dict:
        """Build embed for linked member joining Discord."""
        return {
            'title': '👋 Member Joined Discord',
            'description': f"**{data['username']}** has joined the Discord server",
            'fields': [
                {
                    'name': 'Discord User',
                    'value': f"{data.get('discord_username', 'Unknown')} (`{data['discord_id']}`)",
                    'inline': True
                }
            ],
            'color': 0x00FF00,  # Green
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
    
    def build_unlinked_member_embed(self, data: Dict) -> Dict:
        """Build embed for unlinked member joining Discord."""
        return {
            'title': '❓ New Discord Member',
            'description': f"A new Discord user has joined but is not linked to any application account",
            'fields': [
                {
                    'name': 'Discord User',
                    'value': f"{data.get('discord_username', 'Unknown')} (`{data['discord_id']}`)",
                    'inline': True
                },
                {
                    'name': 'Action Required',
                    'value': 'Consider linking this user to an application account',
                    'inline': False
                }
            ],
            'color': 0xFFFF00,  # Yellow
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
    
    def build_member_left_embed(self, data: Dict) -> Dict:
        """Build embed for member leaving Discord."""
        return {
            'title': '👋 Member Left Discord',
            'description': f"**{data['username']}** has left the Discord server",
            'fields': [
                {
                    'name': 'Discord User',
                    'value': f"{data.get('discord_username', 'Unknown')} (`{data['discord_id']}`)",
                    'inline': True
                }
            ],
            'color': 0xFF0000,  # Red
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
    
    def build_character_status_embed(self, data: Dict) -> Dict:
        """Build embed for character status changes."""
        return {
            'title': '🔄 Character Status Changed',
            'description': f"**{data['character_name']}** status changed",
            'fields': [
                {
                    'name': 'Previous Status',
                    'value': data['old_status'],
                    'inline': True
                },
                {
                    'name': 'New Status',
                    'value': data['new_status'],
                    'inline': True
                },
                {
                    'name': 'Owner',
                    'value': data['username'],
                    'inline': True
                }
            ],
            'color': 0x9932CC,  # Dark Orchid
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
    
    def build_character_transfer_embed(self, data: Dict) -> Dict:
        """Build embed for character transfers."""
        return {
            'title': '↔️ Character Transferred',
            'description': f"**{data['character_name']}** has been transferred",
            'fields': [
                {
                    'name': 'Previous Owner',
                    'value': data['previous_owner'],
                    'inline': True
                },
                {
                    'name': 'New Owner',
                    'value': data['new_owner'],
                    'inline': True
                },
                {
                    'name': 'Reason',
                    'value': data['reason'],
                    'inline': True
                },
                {
                    'name': 'Transferred By',
                    'value': data['transferred_by'],
                    'inline': True
                }
            ],
            'color': 0x8A2BE2,  # Blue Violet
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
    
    def build_roles_changed_embed(self, data: Dict) -> Dict:
        """Build embed for Discord role changes."""
        added_roles = data.get('added_roles', [])
        removed_roles = data.get('removed_roles', [])
        
        fields = []
        if added_roles:
            fields.append({
                'name': 'Added Roles',
                'value': ', '.join(added_roles),
                'inline': False
            })
        if removed_roles:
            fields.append({
                'name': 'Removed Roles',
                'value': ', '.join(removed_roles),
                'inline': False
            })
        
        return {
            'title': '🎭 Member Roles Changed',
            'description': f"Roles updated for **{data['username']}**",
            'fields': fields,
            'color': 0x1E90FF,  # Dodger Blue
            'timestamp': data.get('timestamp', datetime.now().isoformat())
        }
    
    def process_notification_queue(self) -> Dict[str, int]:
        """
        Process queued notifications and send them to Discord with error handling.
        
        Returns:
            Dictionary with processing statistics
        """
        cache_key = "discord_notifications_queue"
        notifications = cache.get(cache_key, [])
        
        if not notifications:
            return {'processed': 0, 'successful': 0, 'failed': 0, 'rate_limited': 0}
        
        stats = {'processed': 0, 'successful': 0, 'failed': 0, 'rate_limited': 0}
        failed_notifications = []  # Store failed notifications for retry
        
        for notification in notifications:
            stats['processed'] += 1
            
            with DiscordErrorHandler("process_notification", log_errors=False) as error_handler:
                try:
                    success = self.send_notification(
                        notification_type=notification['type'],
                        data=notification['data'],
                        user_id=notification.get('user_id')
                    )
                    
                    if success:
                        stats['successful'] += 1
                    else:
                        stats['failed'] += 1
                        # Add to failed notifications for potential retry
                        notification['retry_count'] = notification.get('retry_count', 0) + 1
                        if notification['retry_count'] <= 3:  # Max 3 retries
                            failed_notifications.append(notification)
                            
                except DiscordRateLimitError:
                    stats['rate_limited'] += 1
                    # Add back to queue for later processing
                    notification['retry_count'] = notification.get('retry_count', 0) + 1
                    failed_notifications.append(notification)
                    
                except DiscordAPIError as e:
                    stats['failed'] += 1
                    logger.error(f"Failed to process notification: {e.message}")
                    
                except Exception as e:
                    stats['failed'] += 1
                    logger.error(f"Unexpected error processing notification: {str(e)}")
        
        # Update cache with failed notifications for retry
        if failed_notifications:
            cache.set(f"{cache_key}_retry", failed_notifications, 300)  # 5 minute retry window
            logger.info(f"Queued {len(failed_notifications)} notifications for retry")
        
        # Clear the original queue
        cache.delete(cache_key)
        
        logger.info(
            f"Processed {stats['processed']} notifications: "
            f"{stats['successful']} successful, {stats['failed']} failed, "
            f"{stats['rate_limited']} rate limited"
        )
        return stats