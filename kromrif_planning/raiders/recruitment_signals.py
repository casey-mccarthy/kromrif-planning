"""
Django signals for automatic recruitment workflow triggers.

Handles automatic workflow execution when:
- Applications are manually approved by officers
- Voting periods close with approval decisions
- Applications transition to 'approved' status
"""

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Application
from .recruitment_workflows import get_recruitment_workflow_manager

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Application)
def handle_application_approval(sender, instance, created, **kwargs):
    """
    Signal handler for when an Application is saved.
    Triggers automatic workflow when status changes to 'approved'.
    """
    # Only process approved applications that haven't been processed yet
    if instance.status == 'approved' and not instance.approved_user:
        logger.info(f"Application {instance.id} approved - triggering automatic workflow")
        
        try:
            workflow_manager = get_recruitment_workflow_manager()
            
            # Process the approved application
            result = workflow_manager.process_approved_application(
                application=instance,
                approved_by=instance.decision_made_by
            )
            
            if result['success']:
                logger.info(
                    f"Successfully processed approved application {instance.id} for {instance.character_name}"
                )
            else:
                logger.error(
                    f"Failed to process approved application {instance.id}: {result['error']}"
                )
                
        except Exception as e:
            logger.error(
                f"Exception during automatic workflow processing for application {instance.id}: {str(e)}"
            )


@receiver(pre_save, sender=Application)
def track_application_status_changes(sender, instance, **kwargs):
    """
    Signal handler to track status changes and log workflow triggers.
    Runs before the Application is saved.
    """
    # Skip for new applications
    if not instance.pk:
        return
    
    try:
        # Get the previous state
        previous_instance = Application.objects.get(pk=instance.pk)
        previous_status = previous_instance.status
        new_status = instance.status
        
        # Log status transitions
        if previous_status != new_status:
            logger.info(
                f"Application {instance.id} ({instance.character_name}) "
                f"status changed: {previous_status} → {new_status}"
            )
            
            # Special handling for transitions to approved
            if new_status == 'approved' and previous_status != 'approved':
                logger.info(
                    f"Application {instance.id} transitioning to approved - "
                    f"automatic workflow will be triggered"
                )
                
                # Set decision timestamp if not already set
                if not instance.decision_made_at:
                    instance.decision_made_at = timezone.now()
            
            # Log other important transitions
            elif new_status == 'voting_open' and previous_status != 'voting_open':
                logger.info(f"Voting opened for application {instance.id}")
                
            elif new_status == 'rejected' and previous_status != 'rejected':
                logger.info(f"Application {instance.id} rejected")
                
            elif new_status == 'voting_closed' and previous_status != 'voting_closed':
                logger.info(f"Voting closed for application {instance.id}")
                
    except Application.DoesNotExist:
        # This shouldn't happen, but handle gracefully
        logger.warning(f"Could not find previous state for application {instance.pk}")


# Additional signal for handling bulk approvals or manual workflow triggers
def trigger_workflow_for_application(application_id, approved_by_user=None):
    """
    Manual trigger function for processing approved applications.
    Can be called from management commands or admin actions.
    
    Args:
        application_id: ID of the application to process
        approved_by_user: User who approved (optional)
        
    Returns:
        Dict: Results of workflow processing
    """
    try:
        application = Application.objects.get(id=application_id, status='approved')
        
        if application.approved_user:
            return {
                'success': False,
                'error': 'Application has already been processed'
            }
        
        workflow_manager = get_recruitment_workflow_manager()
        result = workflow_manager.process_approved_application(
            application=application,
            approved_by=approved_by_user
        )
        
        logger.info(f"Manual workflow trigger for application {application_id}: {result['success']}")
        return result
        
    except Application.DoesNotExist:
        error_msg = f"Application {application_id} not found or not approved"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f"Error processing application {application_id}: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }


def trigger_workflows_for_multiple_applications(application_ids, approved_by_user=None):
    """
    Manual trigger function for processing multiple approved applications.
    
    Args:
        application_ids: List of application IDs to process
        approved_by_user: User who approved (optional)
        
    Returns:
        Dict: Summary of batch processing
    """
    workflow_manager = get_recruitment_workflow_manager()
    result = workflow_manager.process_multiple_applications(
        application_ids=application_ids,
        approved_by=approved_by_user
    )
    
    logger.info(
        f"Batch workflow processing: {result['total_processed']} successful, "
        f"{len(result['failed'])} failed"
    )
    
    return result 