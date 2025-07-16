from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import PointAdjustment, UserPointsSummary

User = get_user_model()


@receiver(post_save, sender=PointAdjustment)
def update_user_points_summary_on_adjustment_save(sender, instance, created, **kwargs):
    """
    Update UserPointsSummary when a PointAdjustment is created or modified.
    """
    user = instance.user
    
    # Get or create the user's summary
    summary, created_summary = UserPointsSummary.objects.get_or_create(
        user=user,
        defaults={
            'total_points': Decimal('0.00'),
            'earned_points': Decimal('0.00'),
            'spent_points': Decimal('0.00')
        }
    )
    
    # Recalculate the summary from all adjustments
    summary.recalculate_from_adjustments()


@receiver(post_delete, sender=PointAdjustment)
def update_user_points_summary_on_adjustment_delete(sender, instance, **kwargs):
    """
    Update UserPointsSummary when a PointAdjustment is deleted.
    """
    user = instance.user
    
    # Get the user's summary if it exists
    try:
        summary = UserPointsSummary.objects.get(user=user)
        # Recalculate the summary from remaining adjustments
        summary.recalculate_from_adjustments()
    except UserPointsSummary.DoesNotExist:
        # Summary doesn't exist, nothing to update
        pass


@receiver(post_save, sender=User)
def create_user_points_summary(sender, instance, created, **kwargs):
    """
    Create a UserPointsSummary when a new user is created.
    """
    if created:
        UserPointsSummary.objects.get_or_create(
            user=instance,
            defaults={
                'total_points': Decimal('0.00'),
                'earned_points': Decimal('0.00'),
                'spent_points': Decimal('0.00')
            }
        )