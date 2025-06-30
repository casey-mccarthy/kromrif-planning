"""
Adapters for django-allauth.
"""
import logging
import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.http import HttpRequest

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin

    from .models import User


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        # Always block regular account signup - only Discord OAuth allowed
        return False


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest, sociallogin: "SocialLogin") -> bool:
        # Only allow Discord OAuth registration
        logger.debug(f"is_open_for_signup called for provider: {sociallogin.account.provider}")
        result = sociallogin.account.provider == 'discord'
        logger.debug(f"is_open_for_signup returning: {result}")
        return result

    def populate_user(self, request: HttpRequest, sociallogin: "SocialLogin", data: dict[str, typing.Any]) -> "User":
        """
        Populates user information from social provider info.

        See: https://docs.allauth.org/en/latest/socialaccount/advanced.html#creating-and-populating-user-instances
        """
        logger.debug(f"populate_user called for provider: {sociallogin.account.provider}")
        logger.debug(f"Discord extra_data: {sociallogin.account.extra_data}")
        logger.debug(f"Data parameter: {data}")
        
        user = super().populate_user(request, sociallogin, data)
        logger.debug(f"User after super().populate_user: username={user.username}, email={user.email}")
        
        # Handle Discord-specific data mapping
        if sociallogin.account.provider == 'discord':
            discord_data = sociallogin.account.extra_data
            
            # Set Discord-specific fields
            user.discord_id = discord_data.get('id')
            user.discord_username = discord_data.get('username')
            user.discord_discriminator = discord_data.get('discriminator')
            user.discord_avatar = discord_data.get('avatar')
            
            # Set display name from Discord username if name is not set
            if not user.name and user.discord_username:
                user.name = user.discord_username
            
            # Set email from Discord if available
            if not user.email and discord_data.get('email'):
                user.email = discord_data.get('email')
        
        # Fallback for other providers or generic data
        elif not user.name:
            if name := data.get("name"):
                user.name = name
            elif first_name := data.get("first_name"):
                user.name = first_name
                if last_name := data.get("last_name"):
                    user.name += f" {last_name}"
        
        return user

    def save_user(self, request: HttpRequest, sociallogin: "SocialLogin", form=None) -> "User":
        """
        Saves a newly created user instance together with social account data.
        """
        logger.debug(f"save_user called for provider: {sociallogin.account.provider}")
        try:
            user = super().save_user(request, sociallogin, form)
            logger.debug(f"User saved successfully: {user.username}")
        except Exception as e:
            logger.error(f"Error saving user: {e}")
            raise
        
        # Handle Discord data after user is saved
        if sociallogin.account.provider == 'discord':
            discord_data = sociallogin.account.extra_data
            
            # Update Discord fields if they weren't set during populate_user
            if not user.discord_id:
                user.discord_id = discord_data.get('id')
            if not user.discord_username:
                user.discord_username = discord_data.get('username')
            if not user.discord_discriminator:
                user.discord_discriminator = discord_data.get('discriminator')
            if not user.discord_avatar:
                user.discord_avatar = discord_data.get('avatar')
            
            user.save()
        
        return user