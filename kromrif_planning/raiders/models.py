from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


class Rank(models.Model):
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Rank name (e.g., Guild Leader, Officer, Raider)"
    )
    
    level = models.IntegerField(
        unique=True,
        help_text="Hierarchy level (lower number = higher rank)"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of rank permissions and responsibilities"
    )
    
    permissions = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON field for storing rank-specific permissions"
    )
    
    color = models.CharField(
        max_length=7,
        default="#000000",
        help_text="Hex color code for rank display"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['level']
        indexes = [
            models.Index(fields=['level']),
        ]
    
    def __str__(self):
        return f"{self.name} (Level {self.level})"
    
    def clean(self):
        # Ensure rank names are properly formatted
        if self.name:
            self.name = self.name.strip().title()


class Character(models.Model):
    name = models.CharField(
        max_length=64,
        unique=True,
        validators=[MinLengthValidator(2)],
        help_text="Character name (must be unique)"
    )
    
    character_class = models.CharField(
        max_length=32,
        help_text="Character class (e.g., Warrior, Cleric, etc.)"
    )
    
    level = models.IntegerField(
        default=1,
        help_text="Character level"
    )
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('retired', 'Retired'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Character status"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='characters',
        help_text="The user who owns this character"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Optional character description or notes"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this character is currently active"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this character was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this character was last updated"
    )
    
    # Main/Alt character relationships
    main_character = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alt_characters',
        help_text="Main character if this is an alt (null if this is a main character)"
    )
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['character_class']),
        ]
        permissions = [
            ("can_use_discord_api", "Can use Discord bot API"),
            ("can_manage_discord_links", "Can manage Discord user links"),
            ("can_view_member_data", "Can view detailed member data"),
            ("can_modify_member_status", "Can modify member status"),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.character_class} L{self.level})"
    
    def save(self, *args, **kwargs):
        # Ensure character name is properly capitalized
        if self.name:
            self.name = self.name.strip().title()
        super().save(*args, **kwargs)
    
    # Main/Alt character helper methods
    @property
    def is_main(self):
        """True if this is a main character (no main_character set)."""
        return self.main_character is None
    
    @property
    def is_alt(self):
        """True if this is an alt character (has main_character set)."""
        return self.main_character is not None
    
    def get_main_character(self):
        """Get the main character for this character (returns self if already main)."""
        return self.main_character if self.main_character else self
    
    def get_all_alts(self):
        """Get all alt characters for this character (only works if this is a main character)."""
        if self.is_alt:
            # If this is an alt, delegate to the main character
            return self.main_character.get_all_alts()
        return self.alt_characters.all()
    
    def get_character_family(self):
        """Get all characters in this character's family (main + all alts)."""
        main_char = self.get_main_character()
        # Use a queryset union to combine main character and all alts
        main_qs = Character.objects.filter(id=main_char.id)
        alts_qs = main_char.get_all_alts()
        return main_qs.union(alts_qs)
    
    def clean(self):
        """Validate the character data."""
        super().clean()
        
        # Ensure character can't be its own main character
        if self.main_character and self.main_character.id == self.id:
            raise ValidationError("Character cannot be its own main character")
        
        # Ensure alt characters can't have their own alts (no nested alt relationships)
        if self.main_character and self.main_character.main_character:
            raise ValidationError("Alt characters cannot have their own alt characters")
    


class CharacterOwnership(models.Model):
    """Track character ownership changes over time"""
    
    character = models.ForeignKey(
        Character,
        on_delete=models.CASCADE,
        related_name='ownership_history',
        help_text="The character being transferred"
    )
    
    previous_owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='characters_transferred_from',
        help_text="Previous owner (null for initial creation)"
    )
    
    new_owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='characters_transferred_to',
        help_text="New owner of the character"
    )
    
    transfer_date = models.DateTimeField(
        auto_now_add=True,
        help_text="When the transfer occurred"
    )
    
    TRANSFER_REASONS = [
        ('created', 'Character Created'),
        ('manual', 'Manual Transfer'),
        ('inactive', 'Inactive User Transfer'),
        ('left_guild', 'User Left Guild'),
        ('returned', 'Returned to Original Owner'),
        ('other', 'Other'),
    ]
    
    reason = models.CharField(
        max_length=20,
        choices=TRANSFER_REASONS,
        default='manual',
        help_text="Reason for the transfer"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the transfer"
    )
    
    transferred_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='character_transfers_initiated',
        help_text="Admin/officer who initiated the transfer"
    )
    
    class Meta:
        ordering = ['-transfer_date']
        indexes = [
            models.Index(fields=['character', '-transfer_date']),
            models.Index(fields=['new_owner', '-transfer_date']),
            models.Index(fields=['previous_owner', '-transfer_date']),
        ]
        verbose_name_plural = "Character ownership history"
    
    def __str__(self):
        if self.previous_owner:
            return f"{self.character.name}: {self.previous_owner.username} → {self.new_owner.username} ({self.transfer_date.date()})"
        return f"{self.character.name}: Created for {self.new_owner.username} ({self.transfer_date.date()})"
    
    def clean(self):
        # Validate that previous_owner and new_owner are different
        if self.previous_owner and self.previous_owner == self.new_owner:
            raise ValidationError("Previous owner and new owner cannot be the same.")
    
    @classmethod
    def record_transfer(cls, character, new_owner, reason='manual', notes='', transferred_by=None):
        """Helper method to record a character transfer"""
        previous_owner = character.user
        
        # Create the ownership record
        ownership_record = cls.objects.create(
            character=character,
            previous_owner=previous_owner,
            new_owner=new_owner,
            reason=reason,
            notes=notes,
            transferred_by=transferred_by
        )
        
        # Update the character's current owner
        character.user = new_owner
        character.save()
        
        return ownership_record


class Event(models.Model):
    """
    Represents different types of raid events that can award DKP points.
    Examples: Main Raid, Off-Night Raid, Special Event, etc.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of the event type (e.g., 'Main Raid', 'Off Night')"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of the event type"
    )
    
    base_points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        help_text="Base DKP points awarded for attendance"
    )
    
    on_time_bonus = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        help_text="Additional points for being on time"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this event type is currently active"
    )
    
    color = models.CharField(
        max_length=7,
        default="#007bff",
        help_text="Hex color code for event display"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.base_points} DKP)"
    
    def clean(self):
        # Ensure event name is properly formatted
        if self.name:
            self.name = self.name.strip().title()


class Raid(models.Model):
    """
    Represents a specific raid instance with attendance tracking.
    """
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='raids',
        help_text="Type of event this raid represents"
    )
    
    title = models.CharField(
        max_length=200,
        help_text="Specific title for this raid instance"
    )
    
    date = models.DateField(
        help_text="Date of the raid"
    )
    
    start_time = models.TimeField(
        help_text="Scheduled start time"
    )
    
    end_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Actual end time (optional)"
    )
    
    leader = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='led_raids',
        help_text="Raid leader"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the raid"
    )
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled',
        help_text="Current status of the raid"
    )
    
    # Attendance parsing settings
    parse_attendance = models.BooleanField(
        default=True,
        help_text="Automatically parse character names to award points"
    )
    
    points_awarded = models.BooleanField(
        default=False,
        help_text="Whether DKP points have been awarded for this raid"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-start_time']
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['event', 'date']),
        ]
        unique_together = ['event', 'date', 'start_time']
    
    def __str__(self):
        return f"{self.title} - {self.date}"
    
    @property
    def formatted_datetime(self):
        """Return formatted date and time string"""
        return f"{self.date.strftime('%Y-%m-%d')} at {self.start_time.strftime('%H:%M')}"
    
    def get_attendance_count(self):
        """Get total number of attendees"""
        return self.attendance_records.count()
    
    def get_on_time_count(self):
        """Get number of on-time attendees"""
        return self.attendance_records.filter(on_time=True).count()
    
    def award_points(self, created_by=None):
        """
        Award DKP points to all attendees of this raid.
        Returns list of created PointAdjustment objects.
        """
        if self.points_awarded:
            raise ValidationError("Points have already been awarded for this raid.")
        
        from ..dkp.models import DKPManager
        
        adjustments = []
        
        for attendance in self.attendance_records.all():
            # Award base points
            base_adjustment = DKPManager.award_points(
                user=attendance.user,
                points=self.event.base_points,
                adjustment_type='raid_attendance',
                description=f"Raid attendance: {self.title}",
                character_name=attendance.character_name,
                created_by=created_by
            )
            adjustments.append(base_adjustment)
            
            # Award on-time bonus if applicable
            if attendance.on_time and self.event.on_time_bonus > 0:
                bonus_adjustment = DKPManager.award_points(
                    user=attendance.user,
                    points=self.event.on_time_bonus,
                    adjustment_type='raid_bonus',
                    description=f"On-time bonus: {self.title}",
                    character_name=attendance.character_name,
                    created_by=created_by
                )
                adjustments.append(bonus_adjustment)
        
        # Mark points as awarded
        self.points_awarded = True
        self.save()
        
        return adjustments


class RaidAttendance(models.Model):
    """
    Tracks attendance for specific raids with character information.
    Links users to raids through character name snapshots.
    """
    raid = models.ForeignKey(
        Raid,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        help_text="The raid this attendance record is for"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='raid_attendance',
        help_text="The user who attended"
    )
    
    character_name = models.CharField(
        max_length=64,
        help_text="Name of character used for this raid"
    )
    
    on_time = models.BooleanField(
        default=True,
        help_text="Whether the user arrived on time"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about attendance"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this attendance was recorded"
    )
    
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attendance_records_created',
        help_text="Who recorded this attendance"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['raid', 'user']),
            models.Index(fields=['character_name']),
            models.Index(fields=['created_at']),
        ]
        unique_together = ['raid', 'user']
        verbose_name = "Raid Attendance"
        verbose_name_plural = "Raid Attendance Records"
    
    def __str__(self):
        status = "On Time" if self.on_time else "Late"
        return f"{self.character_name} ({self.user.username}) - {self.raid.title} [{status}]"
    
    def clean(self):
        # Validate that character belongs to user
        if self.character_name and self.user:
            user_characters = self.user.characters.filter(name__iexact=self.character_name)
            if not user_characters.exists():
                raise ValidationError(
                    f"Character '{self.character_name}' does not belong to user '{self.user.username}'"
                )
    
    def save(self, *args, **kwargs):
        # Set character name from user's main character if not provided
        if not self.character_name and self.user:
            main_char = self.user.characters.filter(is_active=True).first()
            if main_char:
                self.character_name = main_char.name
        
        self.clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def parse_character_list(cls, raid, character_names, recorded_by=None, all_on_time=True):
        """
        Parse a list of character names and create attendance records.
        
        Args:
            raid: Raid instance
            character_names: List of character names (strings)
            recorded_by: User who is recording attendance
            all_on_time: Whether to mark all as on-time (default True)
            
        Returns:
            dict with 'created', 'errors', and 'warnings' lists
        """
        results = {
            'created': [],
            'errors': [],
            'warnings': []
        }
        
        for char_name in character_names:
            char_name = char_name.strip()
            if not char_name:
                continue
                
            try:
                # Find character in database
                character = Character.objects.filter(name__iexact=char_name).first()
                
                if not character:
                    results['errors'].append(f"Character '{char_name}' not found in database")
                    continue
                
                # Check if attendance already exists
                existing = cls.objects.filter(raid=raid, user=character.user).first()
                if existing:
                    results['warnings'].append(f"Attendance already recorded for {character.user.username}")
                    continue
                
                # Create attendance record
                attendance = cls.objects.create(
                    raid=raid,
                    user=character.user,
                    character_name=character.name,
                    on_time=all_on_time,
                    recorded_by=recorded_by
                )
                
                results['created'].append(attendance)
                
            except Exception as e:
                results['errors'].append(f"Error processing '{char_name}': {str(e)}")
        
        return results


class Item(models.Model):
    """
    Represents an item that can be distributed during raids.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of the item"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of the item"
    )
    
    suggested_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Suggested DKP cost for this item"
    )
    
    RARITY_CHOICES = [
        ('common', 'Common'),
        ('uncommon', 'Uncommon'),
        ('rare', 'Rare'),
        ('epic', 'Epic'),
        ('legendary', 'Legendary'),
    ]
    
    rarity = models.CharField(
        max_length=20,
        choices=RARITY_CHOICES,
        default='common',
        help_text="Rarity of the item"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this item is currently active for distribution"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['rarity', 'is_active']),
            models.Index(fields=['suggested_cost']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_rarity_display()})"
    
    def clean(self):
        if self.name:
            self.name = self.name.strip()
    
    def get_recent_distributions(self, limit=10):
        """Get recent distributions of this item"""
        return self.distributions.select_related('user', 'character', 'raid').order_by('-distributed_at')[:limit]
    
    def get_average_cost(self):
        """Get the average cost this item was distributed for"""
        from django.db.models import Avg
        result = self.distributions.aggregate(avg_cost=Avg('point_cost'))
        return result['avg_cost'] or Decimal('0.00')


class LootDistribution(models.Model):
    """
    Tracks the distribution of items to players with DKP costs.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='loot_received',
        help_text="The user who received the item"
    )
    
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='distributions',
        help_text="The item that was distributed"
    )
    
    raid = models.ForeignKey(
        Raid,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loot_distributions',
        help_text="The raid where this item was distributed"
    )
    
    character_name = models.CharField(
        max_length=64,
        help_text="Character name at time of distribution"
    )
    
    point_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="DKP points spent on this item"
    )
    
    quantity = models.PositiveIntegerField(
        default=1,
        help_text="Quantity of items distributed"
    )
    
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the distribution"
    )
    
    distributed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the item was distributed"
    )
    
    distributed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loot_distributed',
        help_text="Who distributed this item"
    )
    
    # Discord integration fields
    discord_message_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Discord message ID for reference"
    )
    
    discord_channel_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Discord channel ID where distribution was announced"
    )
    
    class Meta:
        ordering = ['-distributed_at']
        indexes = [
            models.Index(fields=['user', '-distributed_at']),
            models.Index(fields=['item', '-distributed_at']),
            models.Index(fields=['raid', '-distributed_at']),
            models.Index(fields=['character_name']),
        ]
        verbose_name = "Loot Distribution"
        verbose_name_plural = "Loot Distributions"
    
    def __str__(self):
        return f"{self.item.name} → {self.character_name} ({self.point_cost} DKP)"
    
    def clean(self):
        # Validate character belongs to user
        if self.character_name and self.user:
            user_characters = self.user.characters.filter(name__iexact=self.character_name)
            if not user_characters.exists():
                raise ValidationError(
                    f"Character '{self.character_name}' does not belong to user '{self.user.username}'"
                )
        
        # Validate point cost is not negative
        if self.point_cost < 0:
            raise ValidationError("Point cost cannot be negative")
    
    def save(self, *args, **kwargs):
        # Set character name from user's main character if not provided
        if not self.character_name and self.user:
            main_char = self.user.characters.filter(is_active=True).first()
            if main_char:
                self.character_name = main_char.name
        
        self.clean()
        
        # Check if user can afford the item (only for new distributions)
        # Point deduction is handled automatically by signals
        from ..dkp.models import DKPManager
        if self.pk is None:  # New distribution
            current_balance = DKPManager.get_user_balance(self.user)
            total_cost = self.point_cost * self.quantity
            if current_balance < total_cost:
                raise ValidationError(
                    f"Insufficient DKP. Current balance: {current_balance}, "
                    f"Total cost: {total_cost}"
                )
        
        super().save(*args, **kwargs)
    
    def process_point_deduction(self, created_by=None):
        """
        Process the DKP point deduction for this loot distribution.
        Returns the created PointAdjustment record.
        """
        from ..dkp.models import DKPManager
        
        total_cost = self.point_cost * self.quantity
        description = f"Loot: {self.item.name}"
        if self.quantity > 1:
            description += f" (x{self.quantity})"
        
        return DKPManager.deduct_points(
            user=self.user,
            points=total_cost,
            adjustment_type='item_purchase',
            description=description,
            character_name=self.character_name,
            created_by=created_by
        )
    
    @classmethod
    def distribute_item(cls, user, item, point_cost, character_name=None, raid=None, 
                       quantity=1, notes='', distributed_by=None, discord_context=None):
        """
        Distribute an item to a user and automatically deduct DKP points via signals.
        
        Args:
            user: User receiving the item
            item: Item being distributed
            point_cost: DKP cost per item
            character_name: Character name (optional, will use main char if not provided)
            raid: Raid where item was distributed (optional)
            quantity: Number of items (default 1)
            notes: Additional notes
            distributed_by: User distributing the item
            discord_context: Dict with discord_message_id and discord_channel_id
            
        Returns:
            LootDistribution: The created distribution record
        """
        # Create the distribution record
        # Point deduction is handled automatically by post_save signal
        distribution = cls.objects.create(
            user=user,
            item=item,
            raid=raid,
            character_name=character_name,
            point_cost=point_cost,
            quantity=quantity,
            notes=notes,
            distributed_by=distributed_by,
            discord_message_id=discord_context.get('message_id', '') if discord_context else '',
            discord_channel_id=discord_context.get('channel_id', '') if discord_context else ''
        )
        
        return distribution


class LootAuditLog(models.Model):
    """
    Comprehensive audit trail for all loot-related actions.
    Tracks creation, modification, and deletion of items and distributions.
    """
    
    ACTION_TYPES = [
        ('item_created', 'Item Created'),
        ('item_updated', 'Item Updated'),
        ('item_deleted', 'Item Deleted'),
        ('item_activated', 'Item Activated'),
        ('item_deactivated', 'Item Deactivated'),
        ('distribution_created', 'Loot Distribution Created'),
        ('distribution_updated', 'Loot Distribution Updated'),
        ('distribution_deleted', 'Loot Distribution Deleted'),
        ('distribution_refunded', 'Loot Distribution Refunded'),
        ('points_deducted', 'DKP Points Deducted'),
        ('points_refunded', 'DKP Points Refunded'),
        ('admin_action', 'Administrative Action'),
        ('system_action', 'System Action'),
    ]
    
    # Core audit fields
    action_type = models.CharField(
        max_length=25,
        choices=ACTION_TYPES,
        help_text="Type of action performed"
    )
    
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When the action occurred"
    )
    
    # User information
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loot_audit_actions',
        help_text="User who performed the action"
    )
    
    affected_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loot_audit_affected',
        help_text="User affected by the action (recipient of loot, etc.)"
    )
    
    # Related objects (optional, for linking to specific records)
    item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text="Related item (if applicable)"
    )
    
    distribution = models.ForeignKey(
        LootDistribution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text="Related loot distribution (if applicable)"
    )
    
    raid = models.ForeignKey(
        Raid,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loot_audit_logs',
        help_text="Related raid (if applicable)"
    )
    
    # Detailed information
    description = models.TextField(
        help_text="Detailed description of the action"
    )
    
    # Snapshot data for historical accuracy
    character_name = models.CharField(
        max_length=64,
        blank=True,
        help_text="Character name at time of action"
    )
    
    point_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="DKP cost involved in the action (if applicable)"
    )
    
    quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Quantity of items involved (if applicable)"
    )
    
    # Before/after state for changes
    old_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="Previous values before the change (JSON format)"
    )
    
    new_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="New values after the change (JSON format)"
    )
    
    # Additional context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address from which the action was performed"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string for web-based actions"
    )
    
    # Discord integration tracking
    discord_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Discord-related context (message ID, channel, etc.)"
    )
    
    # System metadata
    request_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Request ID for tracking related actions"
    )
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['action_type', '-timestamp']),
            models.Index(fields=['performed_by', '-timestamp']),
            models.Index(fields=['affected_user', '-timestamp']),
            models.Index(fields=['item', '-timestamp']),
            models.Index(fields=['distribution', '-timestamp']),
            models.Index(fields=['raid', '-timestamp']),
            models.Index(fields=['character_name', '-timestamp']),
            models.Index(fields=['-timestamp']),
        ]
        verbose_name = "Loot Audit Log"
        verbose_name_plural = "Loot Audit Logs"
    
    def __str__(self):
        action_display = self.get_action_type_display()
        user_info = f"by {self.performed_by.username}" if self.performed_by else "by System"
        if self.affected_user and self.affected_user != self.performed_by:
            user_info += f" (affecting {self.affected_user.username})"
        return f"{action_display} {user_info} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    def get_summary(self):
        """Get a concise summary of the audit log entry"""
        summary_parts = []
        
        if self.item:
            summary_parts.append(f"Item: {self.item.name}")
        
        if self.character_name:
            summary_parts.append(f"Character: {self.character_name}")
        
        if self.point_cost:
            cost_text = f"{self.point_cost} DKP"
            if self.quantity and self.quantity > 1:
                cost_text += f" (x{self.quantity})"
            summary_parts.append(f"Cost: {cost_text}")
        
        if self.raid:
            summary_parts.append(f"Raid: {self.raid.title}")
        
        return " | ".join(summary_parts) if summary_parts else "N/A"
    
    @classmethod
    def log_item_action(cls, action_type, item, performed_by=None, description="", old_values=None, new_values=None, **kwargs):
        """Helper method to log item-related actions"""
        return cls.objects.create(
            action_type=action_type,
            item=item,
            performed_by=performed_by,
            description=description,
            old_values=old_values or {},
            new_values=new_values or {},
            **kwargs
        )
    
    @classmethod
    def log_distribution_action(cls, action_type, distribution, performed_by=None, description="", **kwargs):
        """Helper method to log distribution-related actions"""
        return cls.objects.create(
            action_type=action_type,
            distribution=distribution,
            item=distribution.item,
            affected_user=distribution.user,
            character_name=distribution.character_name,
            point_cost=distribution.point_cost,
            quantity=distribution.quantity,
            raid=distribution.raid,
            performed_by=performed_by,
            description=description,
            **kwargs
        )
    
    @classmethod
    def log_admin_action(cls, description, performed_by, affected_user=None, **kwargs):
        """Helper method to log administrative actions"""
        return cls.objects.create(
            action_type='admin_action',
            performed_by=performed_by,
            affected_user=affected_user,
            description=description,
            **kwargs
        )