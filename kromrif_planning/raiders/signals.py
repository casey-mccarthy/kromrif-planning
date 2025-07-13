from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import LootDistribution, Item, LootAuditLog
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


@receiver(post_save, sender=LootDistribution)
def create_loot_distribution_audit_log(sender, instance, created, **kwargs):
    """
    Create audit log entry for loot distribution creation/updates.
    """
    if created:
        # Log the distribution creation
        LootAuditLog.log_distribution_action(
            action_type='distribution_created',
            distribution=instance,
            performed_by=instance.distributed_by,
            description=f"Loot distributed: {instance.item.name} (x{instance.quantity}) to {instance.character_name} for {instance.point_cost * instance.quantity} DKP"
        )
        
        # Log the point deduction
        LootAuditLog.log_distribution_action(
            action_type='points_deducted',
            distribution=instance,
            performed_by=instance.distributed_by,
            description=f"DKP points deducted: {instance.point_cost * instance.quantity} from {instance.user.username} ({instance.character_name})"
        )


@receiver(post_delete, sender=LootDistribution)
def handle_loot_distribution_deletion(sender, instance, **kwargs):
    """
    Handle DKP refund and audit logging when a loot distribution is deleted.
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
        
        # Create audit log for the deletion and refund
        LootAuditLog.log_distribution_action(
            action_type='distribution_deleted',
            distribution=instance,
            performed_by=None,  # Unknown who deleted it in this context
            description=f"Loot distribution deleted: {instance.item.name} (x{instance.quantity}) from {instance.character_name}"
        )
        
        LootAuditLog.log_distribution_action(
            action_type='points_refunded',
            distribution=instance,
            performed_by=None,
            description=f"DKP points refunded: {total_cost} to {instance.user.username} ({instance.character_name}) due to distribution deletion"
        )
        
    except Exception as e:
        # If refund fails, still log the deletion attempt
        LootAuditLog.log_distribution_action(
            action_type='distribution_deleted',
            distribution=instance,
            performed_by=None,
            description=f"Loot distribution deleted: {instance.item.name} (x{instance.quantity}) from {instance.character_name}. Refund failed: {str(e)}"
        )


# Item audit logging
@receiver(post_save, sender=Item)
def create_item_audit_log(sender, instance, created, **kwargs):
    """
    Create audit log entry for item creation/updates.
    """
    if created:
        LootAuditLog.log_item_action(
            action_type='item_created',
            item=instance,
            performed_by=None,  # Unknown in this context
            description=f"Item created: {instance.name} ({instance.get_rarity_display()}) with suggested cost {instance.suggested_cost} DKP"
        )


@receiver(pre_save, sender=Item)
def capture_item_changes(sender, instance, **kwargs):
    """
    Capture changes to item for audit logging.
    """
    if instance.pk:  # Only for updates, not creation
        try:
            old_instance = Item.objects.get(pk=instance.pk)
            instance._audit_old_values = {
                'name': old_instance.name,
                'description': old_instance.description,
                'suggested_cost': old_instance.suggested_cost,
                'rarity': old_instance.rarity,
                'is_active': old_instance.is_active,
            }
            instance._audit_new_values = {
                'name': instance.name,
                'description': instance.description,
                'suggested_cost': instance.suggested_cost,
                'rarity': instance.rarity,
                'is_active': instance.is_active,
            }
        except Item.DoesNotExist:
            pass


@receiver(post_save, sender=Item)
def log_item_changes(sender, instance, created, **kwargs):
    """
    Log changes to items for audit trail.
    """
    if not created and hasattr(instance, '_audit_old_values'):
        old_values = instance._audit_old_values
        new_values = instance._audit_new_values
        
        # Check for specific meaningful changes
        changes = []
        if old_values['name'] != new_values['name']:
            changes.append(f"name: '{old_values['name']}' → '{new_values['name']}'")
        if old_values['suggested_cost'] != new_values['suggested_cost']:
            changes.append(f"suggested cost: {old_values['suggested_cost']} → {new_values['suggested_cost']} DKP")
        if old_values['rarity'] != new_values['rarity']:
            changes.append(f"rarity: {old_values['rarity']} → {new_values['rarity']}")
        if old_values['is_active'] != new_values['is_active']:
            action_type = 'item_activated' if new_values['is_active'] else 'item_deactivated'
            LootAuditLog.log_item_action(
                action_type=action_type,
                item=instance,
                performed_by=None,
                description=f"Item {action_type.split('_')[1]}: {instance.name}",
                old_values=old_values,
                new_values=new_values
            )
        
        if changes:
            LootAuditLog.log_item_action(
                action_type='item_updated',
                item=instance,
                performed_by=None,
                description=f"Item updated: {instance.name}. Changes: {', '.join(changes)}",
                old_values=old_values,
                new_values=new_values
            )


@receiver(post_delete, sender=Item)
def log_item_deletion(sender, instance, **kwargs):
    """
    Log item deletion for audit trail.
    """
    LootAuditLog.log_item_action(
        action_type='item_deleted',
        item=None,  # Item is being deleted
        performed_by=None,
        description=f"Item deleted: {instance.name} ({instance.get_rarity_display()}) - suggested cost was {instance.suggested_cost} DKP",
        old_values={
            'name': instance.name,
            'description': instance.description,
            'suggested_cost': instance.suggested_cost,
            'rarity': instance.rarity,
            'is_active': instance.is_active,
        }
    )