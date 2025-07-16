from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Sum, F
from decimal import Decimal

User = get_user_model()


class UserPointsSummary(models.Model):
    """
    Stores the current DKP balance for each user.
    This is a denormalized table for performance optimization.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='dkp_summary',
        help_text="The user whose DKP balance this represents"
    )
    
    total_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Current total DKP balance"
    )
    
    earned_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total points earned (raids, bonuses, etc.)"
    )
    
    spent_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Total points spent on items"
    )
    
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="When this summary was last updated"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this summary was created"
    )
    
    class Meta:
        ordering = ['-total_points', 'user__username']
        indexes = [
            models.Index(fields=['total_points']),
            models.Index(fields=['user', 'total_points']),
        ]
        verbose_name = "User Points Summary"
        verbose_name_plural = "User Points Summaries"
    
    def __str__(self):
        return f"{self.user.username}: {self.total_points} DKP"
    
    def clean(self):
        # Ensure total_points equals earned_points - spent_points
        calculated_total = self.earned_points - self.spent_points
        if self.total_points != calculated_total:
            self.total_points = calculated_total
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def recalculate_from_adjustments(self):
        """Recalculate totals from PointAdjustment records"""
        adjustments = self.user.point_adjustments.all()
        
        earned = adjustments.filter(points__gt=0).aggregate(
            total=Sum('points')
        )['total'] or Decimal('0.00')
        
        spent = adjustments.filter(points__lt=0).aggregate(
            total=Sum('points')
        )['total'] or Decimal('0.00')
        
        self.earned_points = earned
        self.spent_points = abs(spent)
        self.total_points = earned + spent  # spent is negative
        self.save()


class PointAdjustment(models.Model):
    """
    Records all DKP point changes (positive or negative).
    This serves as an audit trail and source of truth for point calculations.
    """
    
    ADJUSTMENT_TYPES = [
        ('raid_attendance', 'Raid Attendance'),
        ('raid_bonus', 'Raid Bonus'),
        ('item_purchase', 'Item Purchase'),
        ('manual_adjustment', 'Manual Adjustment'),
        ('decay', 'Point Decay'),
        ('bonus', 'Other Bonus'),
        ('penalty', 'Penalty'),
        ('transfer', 'Point Transfer'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='point_adjustments',
        help_text="The user receiving the point adjustment"
    )
    
    points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Point value (positive for gains, negative for expenses)"
    )
    
    adjustment_type = models.CharField(
        max_length=20,
        choices=ADJUSTMENT_TYPES,
        help_text="Type of point adjustment"
    )
    
    description = models.TextField(
        help_text="Detailed description of the adjustment"
    )
    
    # Character snapshot at time of adjustment
    character_name = models.CharField(
        max_length=64,
        blank=True,
        help_text="Character name at time of adjustment (for history)"
    )
    
    # Tracking fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this adjustment was created"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='adjustments_created',
        help_text="Admin/officer who created this adjustment"
    )
    
    # Prevent accidental changes
    is_locked = models.BooleanField(
        default=False,
        help_text="Lock this adjustment to prevent modifications"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['adjustment_type', '-created_at']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = "Point Adjustment"
        verbose_name_plural = "Point Adjustments"
        permissions = [
            ("can_lock_adjustments", "Can lock point adjustments"),
            ("can_modify_locked", "Can modify locked adjustments"),
        ]
    
    def __str__(self):
        return f"{self.user.username}: {self.points:+.2f} DKP ({self.get_adjustment_type_display()})"
    
    def clean(self):
        # Validate item purchases are negative
        if self.adjustment_type == 'item_purchase' and self.points > 0:
            raise ValidationError("Item purchases must have negative point values.")
        
        # Validate attendance/bonuses are positive
        if self.adjustment_type in ['raid_attendance', 'raid_bonus', 'bonus'] and self.points < 0:
            raise ValidationError(f"{self.get_adjustment_type_display()} must have positive point values.")
    
    def save(self, *args, **kwargs):
        # Set character name snapshot if not provided
        if not self.character_name and hasattr(self.user, 'characters'):
            # Get user's main character or first character
            main_char = self.user.characters.filter(is_active=True).first()
            if main_char:
                self.character_name = main_char.name
        
        # Validate before saving
        self.clean()
        
        # Check if this would result in negative balance
        if self.pk is None:  # New adjustment
            current_summary = getattr(self.user, 'dkp_summary', None)
            current_balance = current_summary.total_points if current_summary else Decimal('0.00')
            if current_balance + self.points < 0:
                raise ValidationError(
                    f"This adjustment would result in a negative balance. "
                    f"Current balance: {current_balance}, Adjustment: {self.points}"
                )
        
        super().save(*args, **kwargs)


class DKPManager:
    """
    Utility class for DKP-related calculations and operations.
    """
    
    @staticmethod
    def get_user_balance(user):
        """Get current DKP balance for a user"""
        try:
            return user.dkp_summary.total_points
        except UserPointsSummary.DoesNotExist:
            # Create summary if it doesn't exist
            UserPointsSummary.objects.create(user=user)
            return Decimal('0.00')
    
    @staticmethod
    def award_points(user, points, adjustment_type, description, character_name=None, created_by=None):
        """
        Award points to a user with automatic summary update.
        
        Args:
            user: User to award points to
            points: Amount of points (should be positive)
            adjustment_type: Type of adjustment from PointAdjustment.ADJUSTMENT_TYPES
            description: Description of the award
            character_name: Optional character name for history
            created_by: User who created this adjustment
            
        Returns:
            PointAdjustment: The created adjustment record
        """
        if points <= 0:
            raise ValidationError("Points awarded must be positive")
        
        return PointAdjustment.objects.create(
            user=user,
            points=points,
            adjustment_type=adjustment_type,
            description=description,
            character_name=character_name,
            created_by=created_by
        )
    
    @staticmethod
    def deduct_points(user, points, adjustment_type, description, character_name=None, created_by=None):
        """
        Deduct points from a user with automatic summary update.
        
        Args:
            user: User to deduct points from
            points: Amount of points to deduct (should be positive, will be made negative)
            adjustment_type: Type of adjustment from PointAdjustment.ADJUSTMENT_TYPES
            description: Description of the deduction
            character_name: Optional character name for history
            created_by: User who created this adjustment
            
        Returns:
            PointAdjustment: The created adjustment record
        """
        if points <= 0:
            raise ValidationError("Points to deduct must be positive")
        
        # Make points negative for deduction
        negative_points = -abs(points)
        
        return PointAdjustment.objects.create(
            user=user,
            points=negative_points,
            adjustment_type=adjustment_type,
            description=description,
            character_name=character_name,
            created_by=created_by
        )
    
    @staticmethod
    def get_top_dkp_users(limit=10):
        """Get top DKP users ordered by total points"""
        return UserPointsSummary.objects.select_related('user').order_by('-total_points')[:limit]
    
    @staticmethod
    def get_user_adjustment_history(user, limit=50):
        """Get adjustment history for a user"""
        return user.point_adjustments.select_related('created_by').order_by('-created_at')[:limit]
    
    @staticmethod
    def can_afford(user, cost):
        """Check if a user can afford a purchase"""
        current_balance = DKPManager.get_user_balance(user)
        return current_balance >= cost
    
    @staticmethod
    def process_item_purchase(user, item_cost, item_name, created_by=None):
        """
        Process an item purchase, deducting DKP from user.
        
        Args:
            user: User making the purchase
            item_cost: Cost of the item (positive number)
            item_name: Name of the item being purchased
            created_by: User processing the purchase
            
        Returns:
            PointAdjustment: The created purchase record
            
        Raises:
            ValidationError: If user cannot afford the item
        """
        if not DKPManager.can_afford(user, item_cost):
            current_balance = DKPManager.get_user_balance(user)
            raise ValidationError(
                f"Insufficient DKP. Current balance: {current_balance}, "
                f"Item cost: {item_cost}"
            )
        
        return DKPManager.deduct_points(
            user=user,
            points=item_cost,
            adjustment_type='item_purchase',
            description=f"Purchase: {item_name}",
            created_by=created_by
        )
    
    @staticmethod
    def bulk_award_raid_attendance(users, points_per_user, raid_name, created_by=None):
        """
        Award raid attendance points to multiple users.
        
        Args:
            users: List of User objects
            points_per_user: Points to award each user
            raid_name: Name of the raid
            created_by: User awarding the points
            
        Returns:
            List of PointAdjustment objects
        """
        adjustments = []
        for user in users:
            adjustment = DKPManager.award_points(
                user=user,
                points=points_per_user,
                adjustment_type='raid_attendance',
                description=f"Raid attendance: {raid_name}",
                created_by=created_by
            )
            adjustments.append(adjustment)
        return adjustments
    
    @staticmethod
    def recalculate_all_summaries():
        """
        Recalculate all user point summaries from adjustment records.
        This is useful for data fixes or migrations.
        """
        for summary in UserPointsSummary.objects.all():
            summary.recalculate_from_adjustments()
