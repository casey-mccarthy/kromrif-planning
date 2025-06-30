from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Default custom user model for kromrif_planning.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForm accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name = models.CharField("Name of User", blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]

    # Discord-specific fields
    discord_id = models.CharField(
        "Discord ID", max_length=20, unique=True, null=True, blank=True
    )
    discord_username = models.CharField(
        "Discord Username", max_length=32, null=True, blank=True
    )
    discord_discriminator = models.CharField(
        "Discord Discriminator", max_length=4, null=True, blank=True
    )
    discord_avatar = models.CharField(
        "Discord Avatar Hash", max_length=100, null=True, blank=True
    )

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.
        """
        return f"/users/{self.pk}/"

    def get_discord_avatar_url(self) -> str | None:
        """Get Discord avatar URL.

        Returns:
            str | None: Discord avatar URL or None if no avatar.
        """
        if self.discord_avatar and self.discord_id:
            return f"https://cdn.discordapp.com/avatars/{self.discord_id}/{self.discord_avatar}.png"
        return None

    @property
    def discord_tag(self) -> str | None:
        """Get Discord tag (username#discriminator).

        Returns:
            str | None: Discord tag or None if no Discord data.
        """
        if self.discord_username and self.discord_discriminator:
            return f"{self.discord_username}#{self.discord_discriminator}"
        return None