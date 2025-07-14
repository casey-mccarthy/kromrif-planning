"""
Service layer for Discord integration and member management.
Handles business logic for linking/unlinking Discord users and member operations.
"""

import logging
from typing import Optional, Dict, List, Tuple
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta

from .models import Character, LootAuditLog

User = get_user_model()
logger = logging.getLogger(__name__)


class DiscordMemberService:
    """
    Service class for Discord member management operations.
    Handles linking/unlinking Discord users with application accounts.
    """
    
    @staticmethod
    def link_discord_user(
        discord_id: str,
        app_username: str,
        discord_username: Optional[str] = None,
        discord_discriminator: Optional[str] = None,
        requester: Optional[User] = None
    ) -> Tuple[bool, str, Optional[User]]:
        """
        Link a Discord user to an application user account.
        
        Args:
            discord_id: Discord user ID
            app_username: Application username to link to
            discord_username: Discord username (optional)
            discord_discriminator: Discord discriminator (optional)
            requester: User performing the operation
            
        Returns:
            Tuple of (success, message, user_object)
        """
        try:
            with transaction.atomic():
                # Validate Discord ID format
                if not discord_id.isdigit() or len(discord_id) < 10 or len(discord_id) > 20:
                    return False, "Invalid Discord ID format", None
                
                # Find the application user
                try:
                    app_user = User.objects.get(username__iexact=app_username)
                except User.DoesNotExist:
                    return False, f"Application user '{app_username}' not found", None
                
                # Check if Discord ID is already linked
                existing_link = User.objects.filter(discord_id=discord_id).first()
                if existing_link:
                    if existing_link == app_user:
                        return False, f"Discord user {discord_id} is already linked to {app_username}", app_user
                    else:
                        return False, f"Discord ID {discord_id} is already linked to user {existing_link.username}", None
                
                # Check if app user is already linked to another Discord account
                if app_user.discord_id and app_user.discord_id != discord_id:
                    return False, f"User {app_username} is already linked to Discord ID {app_user.discord_id}", None
                
                # Store old values for audit log
                old_discord_id = app_user.discord_id
                old_discord_username = getattr(app_user, 'discord_username', None)
                
                # Update user with Discord information
                app_user.discord_id = discord_id
                if discord_username:
                    app_user.discord_username = discord_username
                if discord_discriminator and hasattr(app_user, 'discord_discriminator'):
                    app_user.discord_discriminator = discord_discriminator
                
                app_user.save()
                
                # Create audit log entry
                DiscordMemberService._create_audit_log(
                    action_type='discord_linked',
                    performed_by=requester,
                    affected_user=app_user,
                    description=f"Discord user {discord_username or discord_id} linked to {app_username}",
                    old_values={
                        'discord_id': old_discord_id,
                        'discord_username': old_discord_username
                    },
                    new_values={
                        'discord_id': discord_id,
                        'discord_username': discord_username
                    }
                )
                
                logger.info(f"Successfully linked Discord user {discord_id} to {app_username}")
                return True, f"Successfully linked Discord user {discord_username or discord_id} to {app_username}", app_user
                
        except Exception as e:
            logger.error(f"Failed to link Discord user {discord_id} to {app_username}: {str(e)}")
            return False, f"Failed to link Discord user: {str(e)}", None
    
    @staticmethod
    def unlink_discord_user(
        identifier: str,
        requester: Optional[User] = None
    ) -> Tuple[bool, str, Optional[User]]:
        """
        Unlink a Discord user from an application user account.
        
        Args:
            identifier: Discord ID or application username
            requester: User performing the operation
            
        Returns:
            Tuple of (success, message, user_object)
        """
        try:
            with transaction.atomic():
                user = None
                
                # Try to find by Discord ID
                if identifier.isdigit():
                    try:
                        user = User.objects.get(discord_id=identifier)
                    except User.DoesNotExist:
                        pass
                
                # Try to find by username
                if not user:
                    try:
                        user = User.objects.get(username__iexact=identifier)
                    except User.DoesNotExist:
                        pass
                
                if not user:
                    return False, f"User not found: {identifier}", None
                
                if not user.discord_id:
                    return False, f"User {user.username} is not linked to Discord", user
                
                # Store old values for audit log
                old_discord_id = user.discord_id
                old_discord_username = getattr(user, 'discord_username', None)
                
                # Clear Discord information
                user.discord_id = None
                if hasattr(user, 'discord_username'):
                    user.discord_username = None
                if hasattr(user, 'discord_discriminator'):
                    user.discord_discriminator = None
                
                user.save()
                
                # Create audit log entry
                DiscordMemberService._create_audit_log(
                    action_type='discord_unlinked',
                    performed_by=requester,
                    affected_user=user,
                    description=f"Discord user {old_discord_username or old_discord_id} unlinked from {user.username}",
                    old_values={
                        'discord_id': old_discord_id,
                        'discord_username': old_discord_username
                    },
                    new_values={
                        'discord_id': None,
                        'discord_username': None
                    }
                )
                
                logger.info(f"Successfully unlinked Discord user {old_discord_id} from {user.username}")
                return True, f"Successfully unlinked Discord user {old_discord_username or old_discord_id} from {user.username}", user
                
        except Exception as e:
            logger.error(f"Failed to unlink Discord user {identifier}: {str(e)}")
            return False, f"Failed to unlink Discord user: {str(e)}", None
    
    @staticmethod
    def update_member_status(
        user_identifier: str,
        new_status: str,
        reason: str = "Updated via Discord bot",
        requester: Optional[User] = None
    ) -> Tuple[bool, str, Optional[User]]:
        """
        Update a member's status (active/inactive).
        
        Args:
            user_identifier: Username, character name, or Discord ID
            new_status: 'active' or 'inactive'
            reason: Reason for the status change
            requester: User performing the operation
            
        Returns:
            Tuple of (success, message, user_object)
        """
        try:
            with transaction.atomic():
                if new_status not in ['active', 'inactive']:
                    return False, "Status must be 'active' or 'inactive'", None
                
                # Find the user
                user = DiscordMemberService._find_user_by_identifier(user_identifier)
                if not user:
                    return False, f"User not found: {user_identifier}", None
                
                # Store old status
                old_status = 'active' if user.is_active else 'inactive'
                
                if old_status == new_status:
                    return False, f"User {user.username} is already {new_status}", user
                
                # Update user status
                user.is_active = (new_status == 'active')
                user.save()
                
                # Update character statuses to match
                if new_status == 'inactive':
                    affected_characters = user.characters.filter(is_active=True)
                    affected_characters.update(is_active=False)
                elif new_status == 'active':
                    # Optionally reactivate main character
                    main_char = user.characters.filter(is_active=False).first()
                    if main_char:
                        main_char.is_active = True
                        main_char.save()
                
                # Create audit log entry
                DiscordMemberService._create_audit_log(
                    action_type='member_status_updated',
                    performed_by=requester,
                    affected_user=user,
                    description=f"Member status changed from {old_status} to {new_status}. Reason: {reason}",
                    old_values={'status': old_status},
                    new_values={'status': new_status}
                )
                
                logger.info(f"Updated {user.username} status from {old_status} to {new_status}")
                return True, f"Updated {user.username} status from {old_status} to {new_status}", user
                
        except Exception as e:
            logger.error(f"Failed to update member status for {user_identifier}: {str(e)}")
            return False, f"Failed to update member status: {str(e)}", None
    
    @staticmethod
    def get_discord_linked_users() -> List[Dict]:
        """
        Get list of all users linked to Discord.
        
        Returns:
            List of user data dictionaries
        """
        try:
            linked_users = User.objects.exclude(
                discord_id__isnull=True
            ).exclude(
                discord_id=''
            ).select_related().prefetch_related('characters')
            
            user_data = []
            for user in linked_users:
                main_char = user.characters.filter(is_active=True).first()
                user_data.append({
                    'id': user.id,
                    'username': user.username,
                    'discord_id': user.discord_id,
                    'discord_username': getattr(user, 'discord_username', None),
                    'discord_tag': getattr(user, 'discord_tag', None),
                    'main_character': main_char.name if main_char else None,
                    'is_active': user.is_active,
                    'character_count': user.characters.count(),
                    'linked_date': user.date_joined
                })
            
            return user_data
            
        except Exception as e:
            logger.error(f"Failed to get Discord linked users: {str(e)}")
            return []
    
    @staticmethod
    def find_member_by_discord_id(discord_id: str) -> Optional[User]:
        """
        Find a member by Discord ID.
        
        Args:
            discord_id: Discord user ID
            
        Returns:
            User object or None if not found
        """
        try:
            return User.objects.get(discord_id=discord_id)
        except User.DoesNotExist:
            return None
    
    @staticmethod
    def validate_discord_permissions(user: User, required_role: str = 'member') -> bool:
        """
        Validate that a user has the required Discord permissions.
        
        Args:
            user: User to check
            required_role: Minimum required role
            
        Returns:
            True if user has required permissions
        """
        if not user.is_authenticated:
            return False
        
        if user.is_superuser:
            return True
        
        if hasattr(user, 'has_role_permission'):
            return user.has_role_permission(required_role)
        
        return user.is_active
    
    @staticmethod
    def _find_user_by_identifier(identifier: str) -> Optional[User]:
        """
        Find a user by various identifiers.
        
        Args:
            identifier: Username, character name, or Discord ID
            
        Returns:
            User object or None if not found
        """
        # Try Discord ID first
        if identifier.isdigit():
            try:
                return User.objects.get(discord_id=identifier)
            except User.DoesNotExist:
                pass
        
        # Try username
        try:
            return User.objects.get(username__iexact=identifier)
        except User.DoesNotExist:
            pass
        
        # Try character name
        try:
            character = Character.objects.get(name__iexact=identifier)
            return character.user
        except Character.DoesNotExist:
            pass
        
        return None
    
    @staticmethod
    def _create_audit_log(
        action_type: str,
        description: str,
        performed_by: Optional[User] = None,
        affected_user: Optional[User] = None,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None
    ):
        """
        Create an audit log entry for Discord operations.
        
        Args:
            action_type: Type of action performed
            description: Description of the action
            performed_by: User who performed the action
            affected_user: User affected by the action
            old_values: Previous values (if any)
            new_values: New values (if any)
        """
        try:
            # Check if we can use the LootAuditLog model for Discord actions
            # or if we need a separate audit log model
            if hasattr(LootAuditLog, '_meta'):
                # Create audit log entry using the existing audit system
                LootAuditLog.objects.create(
                    action_type='admin_action',  # Use existing action type
                    performed_by=performed_by,
                    affected_user=affected_user,
                    description=description,
                    old_values=old_values or {},
                    new_values=new_values or {},
                    discord_context={'action_type': action_type}
                )
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")


class DiscordSyncService:
    """
    Service class for synchronizing Discord server data with application state.
    """
    
    @staticmethod
    def sync_member_roles(discord_member_data: Dict) -> Tuple[bool, str]:
        """
        Sync Discord member roles with application roles.
        
        Args:
            discord_member_data: Discord member data from API
            
        Returns:
            Tuple of (success, message)
        """
        try:
            discord_id = discord_member_data.get('user', {}).get('id')
            discord_roles = discord_member_data.get('roles', [])
            
            if not discord_id:
                return False, "No Discord ID provided"
            
            # Find linked user
            user = DiscordMemberService.find_member_by_discord_id(discord_id)
            if not user:
                return False, f"No linked user found for Discord ID {discord_id}"
            
            # Role mapping logic would go here
            # This is a placeholder for future Discord role synchronization
            logger.info(f"Synced roles for user {user.username} (Discord ID: {discord_id})")
            return True, f"Synced roles for {user.username}"
            
        except Exception as e:
            logger.error(f"Failed to sync member roles: {str(e)}")
            return False, f"Failed to sync roles: {str(e)}"
    
    @staticmethod
    def sync_guild_members(guild_members: List[Dict]) -> Dict[str, int]:
        """
        Sync Discord guild members with application users.
        
        Args:
            guild_members: List of Discord guild member data
            
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'processed': 0,
            'linked': 0,
            'updated': 0,
            'errors': 0
        }
        
        try:
            for member_data in guild_members:
                stats['processed'] += 1
                
                try:
                    discord_id = member_data.get('user', {}).get('id')
                    discord_username = member_data.get('user', {}).get('username')
                    
                    if not discord_id:
                        stats['errors'] += 1
                        continue
                    
                    # Find or update linked user
                    user = DiscordMemberService.find_member_by_discord_id(discord_id)
                    if user:
                        # Update Discord username if changed
                        if discord_username and user.discord_username != discord_username:
                            user.discord_username = discord_username
                            user.save()
                            stats['updated'] += 1
                    else:
                        # Could implement auto-linking logic here if needed
                        pass
                        
                except Exception as e:
                    logger.error(f"Error processing member {member_data}: {str(e)}")
                    stats['errors'] += 1
            
            logger.info(f"Guild member sync completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to sync guild members: {str(e)}")
            stats['errors'] = len(guild_members)
            return stats