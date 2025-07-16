from django.contrib.auth.models import AbstractUser, BaseUserManager, Group, UserManager as DjangoUserManager
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from typing import Optional


class UserManager(DjangoUserManager):
    """Custom manager for User model with Discord-specific methods."""
    
    def get_by_discord_id(self, discord_id: str) -> Optional['User']:
        """Get user by Discord ID.
        
        Args:
            discord_id (str): Discord user ID
            
        Returns:
            Optional[User]: User instance or None if not found
        """
        try:
            return self.get(discord_id=discord_id)
        except self.model.DoesNotExist:
            return None
    
    def get_by_discord_username(self, discord_username: str) -> Optional['User']:
        """Get user by Discord username.
        
        Args:
            discord_username (str): Discord username
            
        Returns:
            Optional[User]: User instance or None if not found
        """
        try:
            return self.get(discord_username=discord_username)
        except self.model.DoesNotExist:
            return None
    
    def create_from_discord(self, discord_data: dict, **extra_fields) -> 'User':
        """Create user from Discord OAuth data.
        
        Args:
            discord_data (dict): Discord user data from OAuth
            **extra_fields: Additional fields for user creation
            
        Returns:
            User: Created user instance
        """
        # Extract Discord data
        discord_id = discord_data.get('id')
        discord_username = discord_data.get('username')
        discord_discriminator = discord_data.get('discriminator')
        discord_avatar = discord_data.get('avatar')
        
        # Set username if not provided
        if 'username' not in extra_fields:
            extra_fields['username'] = discord_username or f'discord_{discord_id}'
        
        # Create user with Discord data
        user = self.create(
            discord_id=discord_id,
            discord_username=discord_username,
            discord_discriminator=discord_discriminator,
            discord_avatar=discord_avatar,
            **extra_fields
        )
        
        return user
    
    def update_discord_data(self, user_id: int, discord_data: dict) -> 'User':
        """Update user's Discord data.
        
        Args:
            user_id (int): User ID
            discord_data (dict): Updated Discord data
            
        Returns:
            User: Updated user instance
        """
        user = self.get(id=user_id)
        
        # Update Discord fields
        user.discord_id = discord_data.get('id', user.discord_id)
        user.discord_username = discord_data.get('username', user.discord_username)
        user.discord_discriminator = discord_data.get('discriminator', user.discord_discriminator)
        user.discord_avatar = discord_data.get('avatar', user.discord_avatar)
        
        user.save(update_fields=[
            'discord_id', 
            'discord_username', 
            'discord_discriminator', 
            'discord_avatar'
        ])
        
        return user


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

    # Role and permission system
    ROLE_CHOICES = [
        ('developer', 'Developer'),
        ('officer', 'Officer'),
        ('recruiter', 'Recruiter'),
        ('member', 'Member'),
        ('applicant', 'Applicant'),
        ('guest', 'Guest'),
    ]
    
    role_group = models.CharField(
        "Role Group",
        max_length=20,
        choices=ROLE_CHOICES,
        default='guest',
        help_text="User's role within the guild hierarchy"
    )

    # Custom manager
    objects = UserManager()

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['discord_id']),
            models.Index(fields=['discord_username']),
            models.Index(fields=['role_group']),
        ]

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

    def assign_role_group(self, role: str) -> None:
        """Assign user to role group and corresponding Django Group.
        
        Args:
            role (str): Role name from ROLE_CHOICES
        """
        if role not in [choice[0] for choice in self.ROLE_CHOICES]:
            raise ValueError(f"Invalid role: {role}")
        
        # Remove user from all role groups
        role_groups = Group.objects.filter(name__in=[choice[1] for choice in self.ROLE_CHOICES])
        self.groups.remove(*role_groups)
        
        # Set new role
        self.role_group = role
        self.save(update_fields=['role_group'])
        
        # Add user to corresponding Django Group
        group_name = dict(self.ROLE_CHOICES)[role]
        group, created = Group.objects.get_or_create(name=group_name)
        self.groups.add(group)

    def get_role_display_name(self) -> str:
        """Get display name for user's role.
        
        Returns:
            str: Role display name
        """
        return dict(self.ROLE_CHOICES).get(self.role_group, 'Unknown')
    
    def get_role_color(self) -> str:
        """Get Tailwind color class for user's role.
        
        Returns:
            str: Tailwind color class (without bg- or text- prefix)
        """
        role_colors = {
            'developer': 'purple',
            'officer': 'blue',
            'recruiter': 'green',
            'member': 'gray',
            'applicant': 'yellow',
            'guest': 'gray',
        }
        return role_colors.get(self.role_group, 'gray')

    def has_role_permission(self, required_role: str) -> bool:
        """Check if user has required role or higher.
        
        Args:
            required_role (str): Minimum required role
            
        Returns:
            bool: True if user has required role or higher
        """
        role_hierarchy = [choice[0] for choice in self.ROLE_CHOICES]
        try:
            user_role_index = role_hierarchy.index(self.role_group)
            required_role_index = role_hierarchy.index(required_role)
            return user_role_index <= required_role_index
        except ValueError:
            return False


@receiver(post_save, sender=User)
def assign_user_to_role_group(sender, instance: User, created: bool, **kwargs):
    """Automatically assign user to Django Group based on role_group field.
    
    Args:
        sender: The model class (User)
        instance: The User instance being saved
        created: Whether this is a new user
        **kwargs: Additional keyword arguments
    """
    if instance.role_group:
        # Get or create the Django Group for this role
        group_name = dict(User.ROLE_CHOICES)[instance.role_group]
        group, group_created = Group.objects.get_or_create(name=group_name)
        
        # Remove user from all other role groups
        role_groups = Group.objects.filter(name__in=[choice[1] for choice in User.ROLE_CHOICES])
        instance.groups.remove(*role_groups)
        
        # Add user to the correct group
        instance.groups.add(group)