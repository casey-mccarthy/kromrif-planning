"""Signal handlers for automatic Discord data synchronization via django-allauth."""

import logging
from typing import Any, Dict

from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.signals import social_account_added, social_account_updated
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(social_account_added)
def populate_user_from_discord_oauth(sender: Any, request, sociallogin, **kwargs) -> None:
    """Populate user data when a new Discord social account is added.
    
    Args:
        sender: The signal sender
        request: The HTTP request object
        sociallogin: The SocialLogin instance containing Discord data
        **kwargs: Additional keyword arguments
    """
    if sociallogin.account.provider == 'discord':
        user = sociallogin.user
        extra_data = sociallogin.account.extra_data
        
        logger.info(f"Populating Discord data for new user: {user.username}")
        
        try:
            # Update Discord-specific fields
            user.discord_id = sociallogin.account.uid
            user.discord_username = extra_data.get('username', '')
            user.discord_discriminator = extra_data.get('discriminator', '')
            user.discord_avatar = extra_data.get('avatar', '')
            
            # Set default role for new users
            if not user.role_group:
                user.role_group = 'guest'
            
            # Update name field if not set
            if not user.name:
                user.name = extra_data.get('global_name', '') or extra_data.get('username', '')
            
            # Update email if not set and available
            if not user.email and extra_data.get('email'):
                user.email = extra_data.get('email')
            
            user.save(update_fields=[
                'discord_id', 
                'discord_username', 
                'discord_discriminator', 
                'discord_avatar',
                'role_group',
                'name',
                'email'
            ])
            
            logger.info(f"Successfully populated Discord data for user: {user.username}")
            
        except Exception as e:
            logger.error(f"Error populating Discord data for user {user.username}: {str(e)}")


@receiver(social_account_updated)
def update_user_from_discord_oauth(sender: Any, request, sociallogin, **kwargs) -> None:
    """Update user data when Discord social account is updated.
    
    Args:
        sender: The signal sender
        request: The HTTP request object
        sociallogin: The SocialLogin instance containing updated Discord data
        **kwargs: Additional keyword arguments
    """
    if sociallogin.account.provider == 'discord':
        user = sociallogin.user
        extra_data = sociallogin.account.extra_data
        
        logger.info(f"Updating Discord data for user: {user.username}")
        
        try:
            # Track what fields are being updated
            updated_fields = []
            
            # Update Discord ID if changed
            new_discord_id = sociallogin.account.uid
            if user.discord_id != new_discord_id:
                logger.warning(f"Discord ID changed for user {user.username}: {user.discord_id} -> {new_discord_id}")
                user.discord_id = new_discord_id
                updated_fields.append('discord_id')
            
            # Update Discord username if changed
            new_username = extra_data.get('username', '')
            if user.discord_username != new_username:
                logger.info(f"Discord username changed for user {user.username}: {user.discord_username} -> {new_username}")
                user.discord_username = new_username
                updated_fields.append('discord_username')
            
            # Update Discord discriminator if changed
            new_discriminator = extra_data.get('discriminator', '')
            if user.discord_discriminator != new_discriminator:
                logger.info(f"Discord discriminator changed for user {user.username}: {user.discord_discriminator} -> {new_discriminator}")
                user.discord_discriminator = new_discriminator
                updated_fields.append('discord_discriminator')
            
            # Update Discord avatar if changed
            new_avatar = extra_data.get('avatar', '')
            if user.discord_avatar != new_avatar:
                logger.info(f"Discord avatar changed for user {user.username}")
                user.discord_avatar = new_avatar
                updated_fields.append('discord_avatar')
            
            # Update display name if available and user's name is empty
            new_global_name = extra_data.get('global_name', '') or extra_data.get('username', '')
            if not user.name and new_global_name:
                user.name = new_global_name
                updated_fields.append('name')
            
            # Update email if available and user's email is empty
            new_email = extra_data.get('email', '')
            if not user.email and new_email:
                user.email = new_email
                updated_fields.append('email')
            
            # Save only if there are changes
            if updated_fields:
                user.save(update_fields=updated_fields)
                logger.info(f"Updated Discord data for user {user.username}. Fields updated: {', '.join(updated_fields)}")
            else:
                logger.info(f"No Discord data changes for user {user.username}")
                
        except Exception as e:
            logger.error(f"Error updating Discord data for user {user.username}: {str(e)}")


def handle_discord_data_conflicts(user: User, discord_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle potential conflicts when updating Discord data.
    
    Args:
        user: The User instance being updated
        discord_data: Dictionary of Discord data from OAuth
        
    Returns:
        Dict containing resolution actions taken
    """
    conflicts = {}
    
    # Check for Discord ID conflicts
    discord_id = discord_data.get('id')
    if discord_id and user.discord_id and user.discord_id != discord_id:
        # This is a serious conflict - Discord IDs should never change
        logger.error(f"Discord ID mismatch for user {user.username}: stored={user.discord_id}, oauth={discord_id}")
        conflicts['discord_id_mismatch'] = {
            'stored': user.discord_id,
            'oauth': discord_id,
            'action': 'kept_stored_value'
        }
    
    # Check for username conflicts with other users
    discord_username = discord_data.get('username')
    if discord_username:
        existing_user = User.objects.filter(
            discord_username=discord_username
        ).exclude(id=user.id).first()
        
        if existing_user:
            logger.warning(f"Discord username {discord_username} already exists for user {existing_user.username}")
            conflicts['username_conflict'] = {
                'username': discord_username,
                'existing_user': existing_user.username,
                'action': 'proceeding_with_update'
            }
    
    return conflicts


@receiver(post_save, sender=SocialAccount)
def log_social_account_changes(sender, instance: SocialAccount, created: bool, **kwargs) -> None:
    """Log social account creation and updates for audit purposes.
    
    Args:
        sender: The model class (SocialAccount)
        instance: The SocialAccount instance being saved
        created: Whether this is a new social account
        **kwargs: Additional keyword arguments
    """
    if instance.provider == 'discord':
        action = 'created' if created else 'updated'
        user = instance.user
        discord_username = instance.extra_data.get('username', 'unknown')
        
        logger.info(f"Discord social account {action} for user {user.username} (Discord: {discord_username})")
        
        # Log important data for debugging
        if created:
            logger.debug(f"New Discord account data: {instance.extra_data}")
        else:
            logger.debug(f"Updated Discord account data: {instance.extra_data}")