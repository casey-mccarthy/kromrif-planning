from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

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