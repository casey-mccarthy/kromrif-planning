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
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['character_class']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.character_class} L{self.level})"
    
    def save(self, *args, **kwargs):
        # Ensure character name is properly capitalized
        if self.name:
            self.name = self.name.strip().title()
        super().save(*args, **kwargs)
    


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