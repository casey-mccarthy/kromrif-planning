# Entity Relationship Diagram (ERD)
# EQ DKP Django Database Design

## Database Schema Overview

This ERD defines the database structure for the Django-based EQ DKP system, focusing on the core entities needed for guild roster management, DKP tracking, events, raids, and loot distribution. The design uses Django ORM models and follows Django best practices.

## Core Django Models

### 1. User Model (Extended Django User)
**Purpose**: Extend Django's built-in User model with Discord integration via django-allauth

```python
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinLengthValidator, RegexValidator
from django.utils import timezone

class User(AbstractUser):
    """Extended Django User model with Discord integration via django-allauth"""
    
    # Discord Integration Fields (populated from allauth SocialAccount)
    discord_id = models.CharField(
        max_length=50, 
        unique=True,
        validators=[MinLengthValidator(10)],
        help_text="Discord user ID - primary external identifier"
    )
    discord_username = models.CharField(
        max_length=50,
        validators=[MinLengthValidator(2)]
    )
    discord_discriminator = models.CharField(
        max_length=10, 
        blank=True, 
        null=True,
        help_text="Legacy Discord discriminators"
    )
    discord_global_name = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="New Discord display names"
    )
    discord_avatar = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Discord avatar hash/URL"
    )
    # Note: discord_email comes from User.email field populated by allauth
    
    # Role and Status Fields
    ROLE_CHOICES = [
        ('officer', 'Officer'),
        ('recruiter', 'Recruiter'),
        ('developer', 'Developer'),
        ('member', 'Member'),
        ('applicant', 'Applicant'),
        ('guest', 'Guest'),
    ]
    role_group = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='guest'
    )
    
    MEMBERSHIP_STATUS_CHOICES = [
        ('member', 'Member'),
        ('trial', 'Trial'),
        ('applicant', 'Applicant'),
        ('inactive', 'Inactive'),
    ]
    membership_status = models.CharField(
        max_length=20, 
        choices=MEMBERSHIP_STATUS_CHOICES, 
        default='applicant'
    )
    
    # OAuth Token Storage (handled by django-allauth SocialToken model)
    # No need for manual token fields - allauth manages this automatically
    
    # Timestamps (Django provides created/updated via date_joined/last_login)
    last_login = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['discord_id']),
            models.Index(fields=['discord_username']),
            models.Index(fields=['role_group']),
            models.Index(fields=['membership_status']),
            models.Index(fields=['is_active']),
            models.Index(fields=['last_login']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(discord_id__length__gte=10),
                name='users_discord_id_length'
            ),
            models.CheckConstraint(
                check=models.Q(discord_username__length__gte=2),
                name='users_discord_username_length'
            ),
        ]

    def __str__(self):
        return f"{self.discord_username} ({self.discord_id})"
    
    def save(self, *args, **kwargs):
        """Override save to sync data from allauth SocialAccount"""
        # Sync Discord data from allauth when user is saved
        if self.pk:
            from allauth.socialaccount.models import SocialAccount
            try:
                discord_account = SocialAccount.objects.get(user=self, provider='discord')
                extra_data = discord_account.extra_data
                
                # Update Discord fields from allauth data
                self.discord_id = discord_account.uid
                self.discord_username = extra_data.get('username', self.discord_username)
                self.discord_discriminator = extra_data.get('discriminator')
                self.discord_global_name = extra_data.get('global_name')
                self.discord_avatar = extra_data.get('avatar')
                
                # Update email from allauth if not set
                if not self.email and discord_account.extra_data.get('email'):
                    self.email = discord_account.extra_data.get('email')
                    
            except SocialAccount.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
```

### 2. API Keys Model
**Purpose**: Store API keys for user and bot programmatic access (extends DRF Token)

```python
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinLengthValidator
from rest_framework.authtoken.models import Token
import uuid

class APIKey(models.Model):
    """Extended API keys for programmatic access - works with DRF Token"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='api_keys',
        null=True, 
        blank=True
    )
    # Link to DRF Token for actual authentication
    token = models.OneToOneField(
        Token,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="DRF Token for authentication"
    )
    key_name = models.CharField(
        max_length=100,
        validators=[MinLengthValidator(3)]
    )
    key_prefix = models.CharField(max_length=20)
    
    KEY_TYPE_CHOICES = [
        ('personal', 'Personal'),
        ('bot', 'Bot'),
    ]
    key_type = models.CharField(
        max_length=20, 
        choices=KEY_TYPE_CHOICES, 
        default='personal'
    )
    
    permissions = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True,
        help_text="Array of permission scopes"
    )
    
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    rate_limit_per_hour = models.PositiveIntegerField(default=1000)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_api_keys',
        help_text="For bot keys created by admins"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'api_keys'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['token']),
            models.Index(fields=['key_prefix']),
            models.Index(fields=['key_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_by']),
            models.Index(fields=['last_used_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(key_name__length__gte=3),
                name='api_keys_name_length'
            ),
            models.CheckConstraint(
                check=(
                    models.Q(key_type='personal', user__isnull=False) |
                    models.Q(key_type='bot', created_by__isnull=False)
                ),
                name='api_keys_user_or_bot'
            ),
        ]

    def save(self, *args, **kwargs):
        """Create DRF Token when API key is saved"""
        if not self.token and self.user:
            # Create or get DRF token for the user
            token, created = Token.objects.get_or_create(user=self.user)
            self.token = token
            self.key_prefix = token.key[:8]  # Use first 8 chars as prefix
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.key_name} ({self.key_prefix}...)"
    
    @property
    def key_value(self):
        """Return the actual DRF token key"""
        return self.token.key if self.token else None
```

### 3. Ranks Model
**Purpose**: Define character ranks within the guild

```python
class Rank(models.Model):
    """Guild character ranks"""
    
    name = models.CharField(
        max_length=50, 
        unique=True,
        validators=[MinLengthValidator(2)]
    )
    description = models.TextField(blank=True)
    sort_order = models.IntegerField(default=0)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ranks'
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['sort_order']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_rank'
            ),
        ]

    def __str__(self):
        return self.name
```

### 4. Characters Model  
**Purpose**: Store character information and link to users

```python
class Character(models.Model):
    """Guild characters linked to Discord users"""
    
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='characters'
    )
    name = models.CharField(
        max_length=50, 
        unique=True,
        validators=[MinLengthValidator(2)]
    )
    character_class = models.CharField(max_length=50, blank=True)
    level = models.PositiveIntegerField(
        default=1,
        validators=[
            models.MaxValueValidator(120),
            models.MinValueValidator(1)
        ]
    )
    rank = models.ForeignKey(
        Rank, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='characters'
    )
    is_main = models.BooleanField(default=False)
    main_character = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='alts'
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'characters'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['user']),
            models.Index(fields=['main_character']),
            models.Index(fields=['is_active']),
            models.Index(fields=['rank']),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(main_character=models.F('id')),
                name='characters_main_not_self'
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        # Ensure main character is not self
        if self.main_character_id == self.pk:
            raise ValidationError('Character cannot be its own main character')
```

### 5. DKP Pools Model
**Purpose**: Define different DKP pools (e.g., Main Raid, Alt Raid, etc.)

```python
class DKPPool(models.Model):
    """DKP pools for different raid types"""
    
    name = models.CharField(
        max_length=100, 
        unique=True,
        validators=[MinLengthValidator(2)]
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'dkp_pools'
        indexes = [
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name
```

### 6. Events Model
**Purpose**: Define types of raids/events that award points

```python
class Event(models.Model):
    """Event types that award DKP points"""
    
    name = models.CharField(
        max_length=100, 
        unique=True,
        validators=[MinLengthValidator(2)]
    )
    description = models.TextField(blank=True)
    default_points = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        validators=[models.MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'events'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name
```

### 7. Raids Model
**Purpose**: Store specific instances of events where points are awarded

```python
class Raid(models.Model):
    """Specific raid instances where points are awarded"""
    
    event = models.ForeignKey(
        Event, 
        on_delete=models.RESTRICT,
        related_name='raids'
    )
    name = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(2)]
    )
    raid_date = models.DateTimeField()
    points_awarded = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        validators=[models.MinValueValidator(0)]
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_raids'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'raids'
        ordering = ['-raid_date']
        indexes = [
            models.Index(fields=['event']),
            models.Index(fields=['raid_date']),
            models.Index(fields=['created_by']),
        ]

    def __str__(self):
        return f"{self.name} ({self.raid_date.date()})"
```

### 8. Raid Attendance Model
**Purpose**: Award points to Discord users based on character attendance (no hard character links)

```python
class RaidAttendance(models.Model):
    """Track raid attendance with points awarded to Discord users"""
    
    raid = models.ForeignKey(
        Raid, 
        on_delete=models.CASCADE,
        related_name='attendance'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='raid_attendance',
        help_text="Points awarded to Discord user"
    )
    dkp_pool = models.ForeignKey(
        DKPPool, 
        on_delete=models.RESTRICT,
        related_name='attendance'
    )
    
    # Character reference data (snapshot, no foreign key constraint)
    character_name = models.CharField(
        max_length=50,
        validators=[MinLengthValidator(2)],
        help_text="Character name at time of attendance"
    )
    character_class = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Character class for reference"
    )
    character_level = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Character level at time of raid"
    )
    
    # Attendance details
    points_earned = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        validators=[models.MinValueValidator(0)]
    )
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('late', 'Late'),
        ('early_leave', 'Early Leave'),
        ('absent', 'Absent'),
    ]
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='present'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'raid_attendance'
        indexes = [
            models.Index(fields=['raid']),
            models.Index(fields=['user']),
            models.Index(fields=['dkp_pool']),
            models.Index(fields=['character_name']),
            models.Index(fields=['character_class']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['raid', 'user', 'character_name', 'dkp_pool'],
                name='raid_attendance_unique'
            ),
        ]

    def __str__(self):
        return f"{self.character_name} - {self.raid.name}"
```

### 9. Items Model
**Purpose**: Store information about items (no fixed costs - all awarded via bidding)

```python
class Item(models.Model):
    """Items available for bidding"""
    
    name = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(2)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'items'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.name
```

### 10. Item Bids Model
**Purpose**: Track bidding sessions and bid history for items

```python
class ItemBid(models.Model):
    """Bidding sessions for items"""
    
    raid = models.ForeignKey(
        Raid, 
        on_delete=models.RESTRICT,
        related_name='item_bids'
    )
    item = models.ForeignKey(
        Item, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='bids'
    )
    item_name = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(2)],
        help_text="Snapshot in case item not in database"
    )
    bid_session_id = models.CharField(
        max_length=100, 
        unique=True,
        validators=[MinLengthValidator(10)],
        help_text="Discord bot generated session ID"
    )
    
    # Bidding session info
    started_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Winner information (Discord user focused, no hard character link)
    winning_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='won_bids'
    )
    winning_character_name = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Character name snapshot, no FK constraint"
    )
    winning_character_class = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Character class for reference"
    )
    winning_bid_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        validators=[models.MinValueValidator(0)]
    )
    
    # Session metadata
    created_by_bot = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'item_bids'
        indexes = [
            models.Index(fields=['raid']),
            models.Index(fields=['item']),
            models.Index(fields=['bid_session_id']),
            models.Index(fields=['is_active']),
            models.Index(fields=['winning_user']),
            models.Index(fields=['started_at']),
            models.Index(fields=['closed_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(
                    is_active=True
                ) | models.Q(
                    is_active=False,
                    winning_user__isnull=False,
                    winning_bid_amount__isnull=False
                ),
                name='item_bids_closed_has_winner'
            ),
        ]

    def __str__(self):
        return f"{self.item_name} - {self.bid_session_id}"
```

### 11. Bid History Model
**Purpose**: Track individual bids placed by Discord users (no hard character links)

```python
class BidHistory(models.Model):
    """Individual bids placed by users"""
    
    bid_session = models.ForeignKey(
        ItemBid, 
        on_delete=models.CASCADE,
        to_field='bid_session_id',
        related_name='bid_history'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='bid_history',
        help_text="Discord user placing bid"
    )
    
    # Character reference data (snapshot, no foreign key constraint)
    character_name = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Character name used for bid"
    )
    character_class = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Character class for reference"
    )
    
    # Bid details
    bid_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[models.MinValueValidator(0.01)]
    )
    user_balance_at_bid = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[models.MinValueValidator(0)],
        help_text="User's balance when bid was placed"
    )
    is_valid = models.BooleanField(
        default=True,
        help_text="False if bid exceeded balance"
    )
    placed_at = models.DateTimeField(auto_now_add=True)
    discord_message_id = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Reference to Discord message"
    )
    
    class Meta:
        db_table = 'bid_history'
        indexes = [
            models.Index(fields=['bid_session']),
            models.Index(fields=['user']),
            models.Index(fields=['character_name']),
            models.Index(fields=['bid_amount']),
            models.Index(fields=['placed_at']),
            models.Index(fields=['is_valid']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(is_valid=False) | models.Q(bid_amount__lte=models.F('user_balance_at_bid')),
                name='bid_history_valid_amount'
            ),
        ]

    def __str__(self):
        return f"{self.user.discord_username} - {self.bid_amount}"
```

### 12. Loot Distribution Model
**Purpose**: Track final item awards from bidding results (Discord user focused, no hard character links)

```python
class LootDistribution(models.Model):
    """Final item awards from bidding results"""
    
    raid = models.ForeignKey(
        Raid, 
        on_delete=models.RESTRICT,
        related_name='loot_distribution'
    )
    bid_session = models.ForeignKey(
        ItemBid, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        to_field='bid_session_id',
        related_name='loot_awards'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.RESTRICT,
        related_name='loot_received',
        help_text="Points deducted from Discord user"
    )
    item = models.ForeignKey(
        Item, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='awards'
    )
    dkp_pool = models.ForeignKey(
        DKPPool, 
        on_delete=models.RESTRICT,
        related_name='loot_distribution'
    )
    
    # Item and character reference data (snapshots, no FK constraints)
    item_name = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(2)],
        help_text="Item name from bid results"
    )
    character_name = models.CharField(
        max_length=50,
        validators=[MinLengthValidator(2)],
        help_text="Character who received item (reference only)"
    )
    character_class = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Character class for reference"
    )
    points_spent = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[models.MinValueValidator(0)],
        help_text="Winning bid amount"
    )
    
    # Source tracking
    submitted_by_bot = models.BooleanField(
        default=True,
        help_text="Submitted via Discord bot API"
    )
    discord_message_id = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Reference to Discord announcement"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'loot_distribution'
        indexes = [
            models.Index(fields=['raid']),
            models.Index(fields=['bid_session']),
            models.Index(fields=['user']),
            models.Index(fields=['item']),
            models.Index(fields=['dkp_pool']),
            models.Index(fields=['item_name']),
            models.Index(fields=['character_name']),
            models.Index(fields=['character_class']),
            models.Index(fields=['points_spent']),
            models.Index(fields=['submitted_by_bot']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.item_name} -> {self.character_name}"
```

### 13. Point Adjustments Model
**Purpose**: Track manual point adjustments to Discord user accounts (no hard character links)

```python
class PointAdjustment(models.Model):
    """Manual point adjustments to user accounts"""
    
    user = models.ForeignKey(
        User, 
        on_delete=models.RESTRICT,
        related_name='point_adjustments',
        help_text="Points adjusted for Discord user"
    )
    dkp_pool = models.ForeignKey(
        DKPPool, 
        on_delete=models.RESTRICT,
        related_name='adjustments'
    )
    
    # Optional character reference data (snapshot, no FK constraint)
    character_name = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Character name for context/reference"
    )
    character_class = models.CharField(
        max_length=50, 
        blank=True,
        help_text="Character class for reference"
    )
    
    # Adjustment details
    points_change = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Can be positive or negative"
    )
    reason = models.CharField(
        max_length=500,
        validators=[MinLengthValidator(3)]
    )
    ADJUSTMENT_TYPE_CHOICES = [
        ('manual', 'Manual'),
        ('bonus', 'Bonus'),
        ('penalty', 'Penalty'),
        ('correction', 'Correction'),
    ]
    adjustment_type = models.CharField(
        max_length=50, 
        choices=ADJUSTMENT_TYPE_CHOICES, 
        default='manual'
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_adjustments',
        help_text="Admin who made adjustment"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'point_adjustments'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['dkp_pool']),
            models.Index(fields=['character_name']),
            models.Index(fields=['character_class']),
            models.Index(fields=['adjustment_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['created_by']),
        ]

    def __str__(self):
        return f"{self.user.discord_username}: {self.points_change} ({self.reason})"
```

### 14. User Points Summary Model
**Purpose**: Materialized view/table for efficient user point balance queries

```python
from django.db.models import F

class UserPointsSummary(models.Model):
    """Efficient user point balance tracking"""
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='points_summary'
    )
    dkp_pool = models.ForeignKey(
        DKPPool, 
        on_delete=models.CASCADE,
        related_name='user_summaries'
    )
    total_earned = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        validators=[models.MinValueValidator(0)]
    )
    total_spent = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        validators=[models.MinValueValidator(0)]
    )
    total_adjustments = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00
    )
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_points_summary'
        unique_together = ['user', 'dkp_pool']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['dkp_pool']),
            models.Index(fields=['total_earned', 'total_spent', 'total_adjustments']),
        ]

    @property
    def current_balance(self):
        """Calculate current balance"""
        return self.total_earned - self.total_spent + self.total_adjustments

    def __str__(self):
        return f"{self.user.discord_username} ({self.dkp_pool.name}): {self.current_balance}"

    def update_totals(self):
        """Recalculate totals from transaction tables"""
        from django.db.models import Sum, Q
        
        # Calculate earned points
        earned = self.user.raid_attendance.filter(
            dkp_pool=self.dkp_pool
        ).aggregate(
            total=Sum('points_earned')
        )['total'] or 0
        
        # Calculate spent points
        spent = self.user.loot_received.filter(
            dkp_pool=self.dkp_pool
        ).aggregate(
            total=Sum('points_spent')
        )['total'] or 0
        
        # Calculate adjustments
        adjustments = self.user.point_adjustments.filter(
            dkp_pool=self.dkp_pool
        ).aggregate(
            total=Sum('points_change')
        )['total'] or 0
        
        # Update fields
        self.total_earned = earned
        self.total_spent = spent
        self.total_adjustments = adjustments
        self.save()
```

### 15. Character Ownership History Model
**Purpose**: Track character reassignments between Discord users

```python
class CharacterOwnershipHistory(models.Model):
    """Track character transfers between users"""
    
    character = models.ForeignKey(
        Character, 
        on_delete=models.CASCADE,
        related_name='ownership_history'
    )
    previous_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='previous_character_ownership'
    )
    new_user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='new_character_ownership'
    )
    transfer_reason = models.CharField(max_length=500, blank=True)
    transferred_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='character_transfers_performed',
        help_text="Admin who performed transfer"
    )
    transfer_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'character_ownership_history'
        indexes = [
            models.Index(fields=['character']),
            models.Index(fields=['previous_user']),
            models.Index(fields=['new_user']),
            models.Index(fields=['transfer_date']),
            models.Index(fields=['transferred_by']),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(previous_user=models.F('new_user')),
                name='ownership_different_users'
            ),
        ]

    def __str__(self):
        prev = self.previous_user.discord_username if self.previous_user else "None"
        return f"{self.character.name}: {prev} -> {self.new_user.discord_username}"
```

### 16. Discord Role Mappings Model
**Purpose**: Map guild ranks to Discord roles for automated synchronization

```python
class DiscordRoleMapping(models.Model):
    """Map guild ranks to Discord roles"""
    
    rank = models.ForeignKey(
        Rank, 
        on_delete=models.CASCADE,
        related_name='discord_mappings'
    )
    discord_role_id = models.CharField(max_length=50)
    discord_role_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'discord_role_mappings'
        unique_together = ['rank', 'discord_role_id']
        indexes = [
            models.Index(fields=['rank']),
            models.Index(fields=['discord_role_id']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.rank.name} -> {self.discord_role_name}"
```

### 17. Discord Sync Log Model
**Purpose**: Track Discord role synchronization attempts and results

```python
class DiscordSyncLog(models.Model):
    """Track Discord role sync attempts"""
    
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='discord_sync_logs'
    )
    discord_id = models.CharField(max_length=50, blank=True)
    ACTION_CHOICES = [
        ('role_add', 'Role Add'),
        ('role_remove', 'Role Remove'),
        ('sync_full', 'Full Sync'),
        ('link_user', 'Link User'),
    ]
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    discord_role_id = models.CharField(max_length=50, blank=True)
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'discord_sync_log'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['discord_id']),
            models.Index(fields=['action']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.action} - {self.status} ({self.created_at})"
```

### 18. Guild Applications Model
**Purpose**: Store recruitment applications from prospective members

```python
class GuildApplication(models.Model):
    """Recruitment applications"""
    
    character_name = models.CharField(
        max_length=50,
        validators=[MinLengthValidator(2)]
    )
    character_class = models.CharField(max_length=50)
    character_level = models.PositiveIntegerField(
        validators=[
            models.MinValueValidator(1),
            models.MaxValueValidator(120)
        ]
    )
    character_server = models.CharField(max_length=50, blank=True)
    discord_username = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    previous_guilds = models.TextField(blank=True)
    availability = models.TextField(blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    references = models.TextField(blank=True)
    application_text = models.TextField()
    
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('trial_accepted', 'Trial Accepted'),
        ('rejected', 'Rejected'),
        ('voting_active', 'Voting Active'),
        ('voting_complete', 'Voting Complete'),
        ('approved', 'Approved'),
    ]
    status = models.CharField(
        max_length=25, 
        choices=STATUS_CHOICES, 
        default='submitted'
    )
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='reviewed_applications'
    )
    rejection_reason = models.TextField(blank=True)
    trial_start_date = models.DateTimeField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    voting_start_date = models.DateTimeField(null=True, blank=True)
    voting_end_date = models.DateTimeField(null=True, blank=True)
    discord_webhook_sent = models.BooleanField(default=False)
    created_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_applications'
    )
    
    class Meta:
        db_table = 'guild_applications'
        indexes = [
            models.Index(fields=['character_name']),
            models.Index(fields=['status']),
            models.Index(fields=['submitted_at']),
            models.Index(fields=['reviewed_by']),
            models.Index(fields=['trial_start_date', 'trial_end_date']),
            models.Index(fields=['voting_start_date', 'voting_end_date']),
            models.Index(fields=['discord_webhook_sent']),
        ]

    def __str__(self):
        return f"{self.character_name} ({self.status})"
```

### 19. Application Votes Model
**Purpose**: Track all member votes on guild applications (accept all, count only ≥15% attendance)

```python
class ApplicationVote(models.Model):
    """Member votes on guild applications"""
    
    application = models.ForeignKey(
        GuildApplication, 
        on_delete=models.CASCADE,
        related_name='votes'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='application_votes'
    )
    VOTE_CHOICES = [
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('recycle', 'Recycle'),
    ]
    vote = models.CharField(max_length=10, choices=VOTE_CHOICES)
    attendance_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[models.MinValueValidator(0)],
        help_text="voter's 30-day attendance at time of vote"
    )
    vote_changes = models.PositiveIntegerField(
        default=0,
        help_text="number of times user changed their vote"
    )
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'application_votes'
        unique_together = ['application', 'user']
        indexes = [
            models.Index(fields=['application']),
            models.Index(fields=['user']),
            models.Index(fields=['vote']),
            models.Index(fields=['attendance_percentage']),
            models.Index(fields=['vote_changes']),
            models.Index(fields=['created_at']),
        ]

    @property
    def is_counted(self):
        """Auto-calculated field for counting eligibility"""
        return self.attendance_percentage >= 15.0

    def __str__(self):
        return f"{self.user.discord_username} - {self.vote} ({self.attendance_percentage}%)"
```

### 20. Application Comments Model
**Purpose**: Store review comments and feedback on applications

```python
class ApplicationComment(models.Model):
    """Comments and feedback on applications"""
    
    application = models.ForeignKey(
        GuildApplication, 
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='application_comments'
    )
    comment_text = models.TextField(
        validators=[MinLengthValidator(5)]
    )
    is_internal = models.BooleanField(
        default=True,
        help_text="internal officer comment vs. applicant feedback"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'application_comments'
        indexes = [
            models.Index(fields=['application']),
            models.Index(fields=['user']),
            models.Index(fields=['is_internal']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Comment on {self.application.character_name} by {self.user.discord_username if self.user else 'Anonymous'}"
```

### 21. Member Attendance Summary Model
**Purpose**: Track 30-day rolling attendance percentages for voting eligibility

```python
class MemberAttendanceSummary(models.Model):
    """30-day rolling attendance for voting eligibility"""
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='attendance_summaries'
    )
    character = models.ForeignKey(
        Character, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='attendance_summaries'
    )
    calculation_date = models.DateField()
    total_raids_30_days = models.PositiveIntegerField(
        default=0,
        validators=[models.MinValueValidator(0)]
    )
    attended_raids_30_days = models.PositiveIntegerField(
        default=0,
        validators=[models.MinValueValidator(0)]
    )
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'member_attendance_summary'
        unique_together = ['user', 'calculation_date']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['character']),
            models.Index(fields=['calculation_date']),
            models.Index(fields=['last_updated']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(attended_raids_30_days__lte=models.F('total_raids_30_days')),
                name='attendance_raids_valid'
            ),
        ]

    @property
    def attendance_percentage(self):
        """Calculate attendance percentage"""
        if self.total_raids_30_days == 0:
            return 0.0
        return round((self.attended_raids_30_days / self.total_raids_30_days) * 100, 2)

    @property
    def is_voting_eligible(self):
        """Check voting eligibility (≥15% attendance)"""
        return self.attendance_percentage >= 15.0

    def __str__(self):
        return f"{self.user.discord_username} - {self.attendance_percentage}% ({self.calculation_date})"
```

## Django Custom Managers and QuerySets

### User Manager Extensions
```python
from django.contrib.auth.models import UserManager

class ExtendedUserManager(UserManager):
    """Extended user manager for Discord integration"""
    
    def get_by_discord_id(self, discord_id):
        """Get user by Discord ID"""
        return self.get(discord_id=discord_id)
    
    def active_members(self):
        """Get all active guild members"""
        return self.filter(is_active=True, membership_status='member')
    
    def voting_eligible(self):
        """Get members eligible to vote"""
        from django.utils import timezone
        today = timezone.now().date()
        
        return self.filter(
            is_active=True,
            membership_status='member',
            attendance_summaries__calculation_date=today,
            attendance_summaries__attended_raids_30_days__gte=models.F('attendance_summaries__total_raids_30_days') * 0.15
        )

# Add to User model
User.add_to_class('objects', ExtendedUserManager())
```

### Character QuerySet
```python
class CharacterQuerySet(models.QuerySet):
    """Custom queryset for characters"""
    
    def active(self):
        return self.filter(is_active=True)
    
    def mains(self):
        return self.filter(is_main=True)
    
    def alts(self):
        return self.filter(is_main=False, main_character__isnull=False)
    
    def by_class(self, character_class):
        return self.filter(character_class=character_class)
    
    def by_rank(self, rank):
        return self.filter(rank=rank)

class CharacterManager(models.Manager):
    def get_queryset(self):
        return CharacterQuerySet(self.model, using=self._db)
    
    def active(self):
        return self.get_queryset().active()
    
    def mains(self):
        return self.get_queryset().mains()

Character.add_to_class('objects', CharacterManager())
```

## Django-Allauth Integration

### Discord Provider Configuration
```python
# settings.py configuration for django-allauth Discord provider

INSTALLED_APPS = [
    # ... other apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.discord',
    'rest_framework.authtoken',  # For DRF token authentication
]

# Allauth settings
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SOCIALACCOUNT_PROVIDERS = {
    'discord': {
        'SCOPE': ['identify', 'email'],
        'AUTH_PARAMS': {
            'access_type': 'offline',
        }
    }
}

# Custom adapter to populate User fields from Discord data
SOCIALACCOUNT_ADAPTER = 'myapp.adapters.DiscordSocialAccountAdapter'
```

### Custom Allauth Adapter
```python
# myapp/adapters.py
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount

class DiscordSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter to populate User model from Discord data"""
    
    def save_user(self, request, sociallogin, form=None):
        """Save user with Discord data populated"""
        user = super().save_user(request, sociallogin, form)
        
        if sociallogin.account.provider == 'discord':
            extra_data = sociallogin.account.extra_data
            
            # Populate Discord-specific fields
            user.discord_id = sociallogin.account.uid
            user.discord_username = extra_data.get('username', '')
            user.discord_discriminator = extra_data.get('discriminator')
            user.discord_global_name = extra_data.get('global_name')
            user.discord_avatar = extra_data.get('avatar')
            
            # Set default role for new users
            user.role_group = 'guest'
            user.membership_status = 'applicant'
            
            user.save()
        
        return user
    
    def populate_user(self, request, sociallogin, data):
        """Populate user fields from Discord OAuth data"""
        user = super().populate_user(request, sociallogin, data)
        
        if sociallogin.account.provider == 'discord':
            # Use Discord username as default username
            user.username = data.get('username', '')
            user.email = data.get('email', '')
            user.first_name = data.get('global_name', data.get('username', ''))
        
        return user
```

### Allauth Signal Handlers
```python
# myapp/signals.py
from django.dispatch import receiver
from allauth.socialaccount.signals import social_account_updated
from allauth.socialaccount.models import SocialAccount
from rest_framework.authtoken.models import Token

@receiver(social_account_updated)
def update_user_from_discord(sender, request, sociallogin, **kwargs):
    """Update user data when Discord account is updated"""
    if sociallogin.account.provider == 'discord':
        user = sociallogin.user
        extra_data = sociallogin.account.extra_data
        
        # Update Discord fields
        user.discord_id = sociallogin.account.uid
        user.discord_username = extra_data.get('username', user.discord_username)
        user.discord_discriminator = extra_data.get('discriminator')
        user.discord_global_name = extra_data.get('global_name')
        user.discord_avatar = extra_data.get('avatar')
        
        user.save()

@receiver(social_account_updated)
def ensure_user_has_token(sender, request, sociallogin, **kwargs):
    """Ensure every Discord user has a DRF token for API access"""
    if sociallogin.account.provider == 'discord':
        user = sociallogin.user
        # Create DRF token if it doesn't exist
        token, created = Token.objects.get_or_create(user=user)
        if created:
            # Create default API key record
            from myapp.models import APIKey
            APIKey.objects.create(
                user=user,
                token=token,
                key_name=f"Default API Key - {user.discord_username}",
                key_type='personal',
                permissions=['read_profile', 'view_points']
            )
```

## Django Model Signals

### Point Summary Updates
```python
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=RaidAttendance)
@receiver(post_delete, sender=RaidAttendance)
def update_points_on_attendance_change(sender, instance, **kwargs):
    """Update user points summary when attendance changes"""
    summary, created = UserPointsSummary.objects.get_or_create(
        user=instance.user,
        dkp_pool=instance.dkp_pool
    )
    summary.update_totals()

@receiver(post_save, sender=LootDistribution)
@receiver(post_delete, sender=LootDistribution)
def update_points_on_loot_change(sender, instance, **kwargs):
    """Update user points summary when loot changes"""
    summary, created = UserPointsSummary.objects.get_or_create(
        user=instance.user,
        dkp_pool=instance.dkp_pool
    )
    summary.update_totals()

@receiver(post_save, sender=PointAdjustment)
@receiver(post_delete, sender=PointAdjustment)
def update_points_on_adjustment_change(sender, instance, **kwargs):
    """Update user points summary when adjustments change"""
    summary, created = UserPointsSummary.objects.get_or_create(
        user=instance.user,
        dkp_pool=instance.dkp_pool
    )
    summary.update_totals()
```

### Character Ownership Tracking
```python
@receiver(post_save, sender=Character)
def track_character_ownership_changes(sender, instance, created, **kwargs):
    """Track character ownership changes"""
    if not created and instance.user:
        # Check if user changed
        try:
            old_instance = Character.objects.get(pk=instance.pk)
            if old_instance.user != instance.user:
                CharacterOwnershipHistory.objects.create(
                    character=instance,
                    previous_user=old_instance.user,
                    new_user=instance.user,
                    transfer_reason="Ownership change via admin",
                )
        except Character.DoesNotExist:
            pass
```

## Django Views and ViewSets Examples

### Django REST Framework ViewSets
```python
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

class CharacterViewSet(viewsets.ModelViewSet):
    """Character management ViewSet"""
    queryset = Character.objects.active()
    serializer_class = CharacterSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['character_class', 'rank', 'is_main']
    
    def get_queryset(self):
        """Filter characters based on user permissions"""
        if self.request.user.role_group in ['officer', 'recruiter']:
            return Character.objects.all()
        return Character.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def reassign(self, request, pk=None):
        """Reassign character to different user"""
        character = self.get_object()
        new_user_id = request.data.get('new_user_id')
        
        if request.user.role_group not in ['officer', 'recruiter']:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            new_user = User.objects.get(pk=new_user_id)
            old_user = character.user
            
            character.user = new_user
            character.save()
            
            # Create ownership history entry
            CharacterOwnershipHistory.objects.create(
                character=character,
                previous_user=old_user,
                new_user=new_user,
                transfer_reason=request.data.get('reason', ''),
                transferred_by=request.user
            )
            
            return Response({'status': 'Character reassigned successfully'})
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
```

## Key Business Rules (Django Implementation)

### Data Integrity Rules:
1. Character names must be unique (enforced by unique=True)
2. Each user can have only one main character per DKP pool (business logic)
3. Alt characters must reference a valid main character (foreign key)
4. **Points are always awarded to and deducted from Discord users, never characters**
5. **Character references in transaction tables are snapshots only (no foreign key constraints)**
6. **Character ownership can be transferred without affecting point balances**
7. Points earned/spent must be non-negative (validators)
8. Only active characters can participate in raids (business logic)
9. **Items have no fixed costs** - all distribution via bidding
10. **Bids cannot exceed user's current DKP balance** (validation in views)
11. **Bidding sessions must be associated with active raids**
12. **Only one active bid session per item per raid** (business logic)
13. **Bid amounts must be positive (greater than 0)** (validators)
14. **Loot distribution requires completed bidding session**

### Authentication Rules:
1. **Django social auth for Discord OAuth** - primary authentication method
2. All user accounts must be linked to a valid Discord ID (required field)
3. API keys provide programmatic access with role-based permissions (DRF token auth)
4. Personal API keys inherit permissions from user's role group
5. Bot API keys have extended permissions and can only be created by officers/developers
6. API keys must be rotated regularly for security (expiration dates)
7. OAuth tokens must be refreshed before expiration (Django social auth handles this)
8. Failed authentication attempts are logged and rate-limited (Django middleware)

### Django-Specific Implementation Notes:
1. Use Django's built-in User model extended with Discord fields populated by django-allauth
2. Leverage Django's permission system for role-based access
3. Use django-allauth for Discord OAuth integration with automatic token management
4. Use DRF Token authentication linked to allauth for API access
5. Use Django signals for automatic point summary updates and allauth data synchronization
6. Implement custom managers and querysets for common queries
7. Use Django's validation framework for data integrity
8. Use Django's admin interface for administrative tasks
9. Leverage Django's ORM for complex queries and relationships
10. Custom allauth adapter to populate User model from Discord OAuth data

### Django-Allauth Benefits:
- Automatic OAuth token refresh and management
- Built-in Discord provider with proper scopes
- Social account linking and unlinking
- Automatic user creation from Discord OAuth
- Signal integration for data synchronization
- Admin interface for managing social accounts

This Django implementation maintains the same business logic and data relationships as the FastAPI version while utilizing Django's built-in features, django-allauth for Discord integration, and DRF for API development.