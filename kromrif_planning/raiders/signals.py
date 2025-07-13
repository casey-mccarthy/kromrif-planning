from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import LootDistribution
from ..dkp.models import DKPManager, PointAdjustment, UserPointsSummary


@receiver(post_save, sender=LootDistribution)
def handle_loot_distribution_points(sender, instance, created, **kwargs):
    """
    Automatically deduct DKP points when loot is distributed.
    Only processes new distributions (created=True).
    """
    if created:
        # Calculate total cost for this distribution
        total_cost = instance.point_cost * instance.quantity
        
        try:
            # Create the point adjustment 
            adjustment = PointAdjustment.objects.create(
                user=instance.user,
                points=-total_cost,  # Negative for deduction
                adjustment_type='item_purchase',
                description=f"Loot: {instance.item.name} (x{instance.quantity})",
                character_name=instance.character_name,
                created_by=instance.distributed_by
            )
            
            # Manually trigger summary update since the signal chain might not work
            summary, created_summary = UserPointsSummary.objects.get_or_create(
                user=instance.user
            )
            summary.recalculate_from_adjustments()
            
        except Exception as e:
            # If the deduction fails, raise the error
            # This will prevent the LootDistribution from being saved
            raise ValidationError(f"Cannot distribute loot: {str(e)}")


@receiver(post_delete, sender=LootDistribution)
def handle_loot_distribution_deletion(sender, instance, **kwargs):
    """
    Optionally refund DKP points when a loot distribution is deleted.
    This creates a refund adjustment for audit trail purposes.
    """
    # Calculate total cost that was originally deducted
    total_cost = instance.point_cost * instance.quantity
    
    # Create a refund adjustment
    try:
        DKPManager.award_points(
            user=instance.user,
            points=total_cost,
            adjustment_type='manual_adjustment',
            description=f"Refund for deleted distribution: {instance.item.name} (x{instance.quantity})",
            character_name=instance.character_name,
            created_by=None  # System-generated refund
        )
    except Exception:
        # If refund fails, log it but don't prevent deletion
        # In a production system, you might want to log this
        pass