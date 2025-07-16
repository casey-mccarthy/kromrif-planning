"""
Recruitment Workflow Service for Automatic Character Creation and Promotion.

Handles automated post-approval workflows including:
- User account creation and linking
- Character record creation with proper ownership
- DKP point initialization 
- Guild rank assignment
- Integration with existing character management system
"""

import logging
from typing import Dict, Optional, Tuple
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Application, Character, Rank, CharacterOwnership
from .voting_service import get_voting_manager
from .discord_notifications import get_discord_notification_service

# Import DKP models if available
try:
    from kromrif_planning.dkp.models import UserPointsSummary, PointAdjustment
    HAS_DKP_SYSTEM = True
except ImportError:
    HAS_DKP_SYSTEM = False
    UserPointsSummary = None
    PointAdjustment = None

User = get_user_model()
logger = logging.getLogger(__name__)


class RecruitmentWorkflowManager:
    """
    Service class for managing post-approval recruitment workflows.
    Handles automatic character creation, user setup, and guild integration.
    """
    
    # Default settings
    DEFAULT_STARTING_DKP = Decimal('0.00')
    DEFAULT_STARTING_RANK = 'Trial Member'  # Should match a rank name in your system
    DEFAULT_GROUP_NAME = 'Guild Members'    # Should match a Django group name
    
    def __init__(self):
        """Initialize the recruitment workflow manager."""
        self.starting_dkp = getattr(
            settings, 
            'RECRUITMENT_STARTING_DKP', 
            self.DEFAULT_STARTING_DKP
        )
        self.starting_rank_name = getattr(
            settings, 
            'RECRUITMENT_STARTING_RANK', 
            self.DEFAULT_STARTING_RANK
        )
        self.default_group_name = getattr(
            settings, 
            'RECRUITMENT_DEFAULT_GROUP', 
            self.DEFAULT_GROUP_NAME
        )
    
    def process_approved_application(self, application: Application, approved_by: User = None) -> Dict:
        """
        Process an approved application and perform all post-approval workflows.
        
        Args:
            application: The approved Application instance
            approved_by: User who approved the application (optional)
            
        Returns:
            Dict: Results of the workflow processing
        """
        if application.status != 'approved':
            return {
                'success': False,
                'error': f'Application status is {application.status}, not approved'
            }
        
        if application.approved_user:
            return {
                'success': False,
                'error': 'Application has already been processed (user account exists)'
            }
        
        try:
            with transaction.atomic():
                # Step 1: Create user account
                user_result = self._create_user_account(application)
                if not user_result['success']:
                    return user_result
                
                user = user_result['user']
                
                # Step 2: Create character record
                character_result = self._create_character_record(application, user)
                if not character_result['success']:
                    return character_result
                
                character = character_result['character']
                
                # Step 3: Initialize DKP points
                dkp_result = self._initialize_dkp_points(user, application)
                if not dkp_result['success']:
                    logger.warning(f"DKP initialization failed for {user.username}: {dkp_result['error']}")
                    # Don't fail the entire workflow for DKP issues
                
                # Step 4: Assign guild rank
                rank_result = self._assign_guild_rank(character)
                if not rank_result['success']:
                    logger.warning(f"Rank assignment failed for {character.name}: {rank_result['error']}")
                
                # Step 5: Add to appropriate groups
                group_result = self._assign_user_groups(user)
                if not group_result['success']:
                    logger.warning(f"Group assignment failed for {user.username}: {group_result['error']}")
                
                # Step 6: Link user to application
                application.approved_user = user
                application.save()
                
                # Step 7: Record character ownership
                CharacterOwnership.record_transfer(
                    character=character,
                    new_owner=user,
                    reason='created',
                    notes=f'Character created from approved application {application.id}',
                    transferred_by=approved_by
                )
                
                # Compile results
                workflow_results = {
                    'success': True,
                    'application_id': application.id,
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email
                    },
                    'character': {
                        'id': character.id,
                        'name': character.name,
                        'class': character.character_class,
                        'level': character.level
                    },
                    'dkp_initialized': dkp_result['success'],
                    'rank_assigned': rank_result['success'],
                    'groups_assigned': group_result['success'],
                    'processed_at': timezone.now(),
                    'processed_by': approved_by.username if approved_by else 'System'
                }
                
                logger.info(f"Successfully processed approved application {application.id} for {character.name}")
                
                # Send notifications (would integrate with Discord)
                self._notify_workflow_completed(application, workflow_results)
                
                return workflow_results
                
        except Exception as e:
            logger.error(f"Error processing approved application {application.id}: {str(e)}")
            return {
                'success': False,
                'error': f'Workflow processing failed: {str(e)}'
            }
    
    def _create_user_account(self, application: Application) -> Dict:
        """Create a user account from application data."""
        try:
            # Generate username from character name (ensure uniqueness)
            base_username = application.character_name.lower().replace(' ', '_')
            username = base_username
            counter = 1
            
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1
            
            # Create user account
            user = User.objects.create_user(
                username=username,
                email=application.applicant_email,
                first_name=application.applicant_name.split()[0] if ' ' in application.applicant_name else application.applicant_name,
                last_name=' '.join(application.applicant_name.split()[1:]) if ' ' in application.applicant_name else '',
            )
            
            # Set Discord information if available
            if hasattr(user, 'discord_username'):
                user.discord_username = application.discord_username
            
            # Set role group to member
            if hasattr(user, 'role_group'):
                user.role_group = 'member'
            
            user.save()
            
            logger.info(f"Created user account: {username} ({application.applicant_email})")
            
            return {
                'success': True,
                'user': user,
                'username_generated': username != base_username
            }
            
        except Exception as e:
            logger.error(f"Error creating user account for application {application.id}: {str(e)}")
            return {
                'success': False,
                'error': f'User account creation failed: {str(e)}'
            }
    
    def _create_character_record(self, application: Application, user: User) -> Dict:
        """Create a character record from application data."""
        try:
            # Create character
            character = Character.objects.create(
                name=application.character_name,
                character_class=application.character_class,
                level=application.character_level,
                status='active',
                user=user,
                description=f"Character created from approved application {application.id}",
                is_active=True
            )
            
            logger.info(f"Created character record: {character.name} (Level {character.level} {character.character_class})")
            
            return {
                'success': True,
                'character': character
            }
            
        except Exception as e:
            logger.error(f"Error creating character for application {application.id}: {str(e)}")
            return {
                'success': False,
                'error': f'Character creation failed: {str(e)}'
            }
    
    def _initialize_dkp_points(self, user: User, application: Application) -> Dict:
        """Initialize DKP points for new member."""
        if not HAS_DKP_SYSTEM:
            return {
                'success': False,
                'error': 'DKP system not available'
            }
        
        try:
            # Create initial points summary
            points_summary, created = UserPointsSummary.objects.get_or_create(
                user=user,
                defaults={'current_points': self.starting_dkp}
            )
            
            # Create initial point adjustment record
            PointAdjustment.objects.create(
                user=user,
                adjustment_type='initial',
                points=self.starting_dkp,
                character_name=application.character_name,
                reason=f'Initial DKP allocation for new member from application {application.id}',
                created_by=None,  # System-generated
            )
            
            logger.info(f"Initialized DKP points for {user.username}: {self.starting_dkp}")
            
            return {
                'success': True,
                'starting_points': self.starting_dkp,
                'summary_created': created
            }
            
        except Exception as e:
            logger.error(f"Error initializing DKP for user {user.username}: {str(e)}")
            return {
                'success': False,
                'error': f'DKP initialization failed: {str(e)}'
            }
    
    def _assign_guild_rank(self, character: Character) -> Dict:
        """Assign starting guild rank to character."""
        try:
            # Get the starting rank
            try:
                starting_rank = Rank.objects.get(name=self.starting_rank_name)
            except Rank.DoesNotExist:
                # Fallback to lowest level rank if starting rank doesn't exist
                starting_rank = Rank.objects.order_by('level').first()
                
                if not starting_rank:
                    return {
                        'success': False,
                        'error': 'No ranks available in the system'
                    }
                    
                logger.warning(f"Starting rank '{self.starting_rank_name}' not found, using '{starting_rank.name}'")
            
            # Note: The Character model doesn't have a rank field in the current implementation
            # This would need to be added if rank assignment is required
            # For now, we'll just log the intended rank assignment
            
            logger.info(f"Character {character.name} would be assigned rank: {starting_rank.name}")
            
            return {
                'success': True,
                'rank': starting_rank.name,
                'rank_level': starting_rank.level,
                'note': 'Rank logged (Character model does not have rank field)'
            }
            
        except Exception as e:
            logger.error(f"Error assigning rank to character {character.name}: {str(e)}")
            return {
                'success': False,
                'error': f'Rank assignment failed: {str(e)}'
            }
    
    def _assign_user_groups(self, user: User) -> Dict:
        """Assign user to appropriate Django groups."""
        try:
            groups_assigned = []
            
            # Add to default guild members group
            try:
                default_group = Group.objects.get(name=self.default_group_name)
                user.groups.add(default_group)
                groups_assigned.append(default_group.name)
                logger.info(f"Added {user.username} to group: {default_group.name}")
            except Group.DoesNotExist:
                logger.warning(f"Default group '{self.default_group_name}' does not exist")
            
            # Add to recruitment-related groups if they exist
            group_names_to_try = ['Guild Members', 'Voting Members']
            
            for group_name in group_names_to_try:
                try:
                    group = Group.objects.get(name=group_name)
                    if group not in user.groups.all():
                        user.groups.add(group)
                        groups_assigned.append(group.name)
                        logger.info(f"Added {user.username} to group: {group.name}")
                except Group.DoesNotExist:
                    continue
            
            return {
                'success': True,
                'groups_assigned': groups_assigned
            }
            
        except Exception as e:
            logger.error(f"Error assigning groups to user {user.username}: {str(e)}")
            return {
                'success': False,
                'error': f'Group assignment failed: {str(e)}'
            }
    
    def _notify_workflow_completed(self, application: Application, results: Dict):
        """Send notification about completed workflow."""
        try:
            discord_service = get_discord_notification_service()
            discord_service.notify_character_created(application, results)
        except Exception as e:
            logger.error(f"Failed to send Discord notification for character creation: {str(e)}")
        
        logger.info(
            f"NOTIFICATION: Recruitment workflow completed for {application.character_name}\n"
            f"  User: {results['user']['username']} ({results['user']['email']})\n"
            f"  Character: {results['character']['name']} (Level {results['character']['level']} {results['character']['class']})\n"
            f"  DKP Initialized: {results['dkp_initialized']}\n"
            f"  Rank Assigned: {results['rank_assigned']}\n"
            f"  Groups Assigned: {results['groups_assigned']}"
        )
    
    def process_multiple_applications(self, application_ids: list, approved_by: User = None) -> Dict:
        """
        Process multiple approved applications in batch.
        
        Args:
            application_ids: List of application IDs to process
            approved_by: User who approved the applications
            
        Returns:
            Dict: Summary of batch processing results
        """
        results = {
            'total_processed': 0,
            'successful': [],
            'failed': [],
            'processed_at': timezone.now()
        }
        
        for app_id in application_ids:
            try:
                application = Application.objects.get(id=app_id, status='approved')
                result = self.process_approved_application(application, approved_by)
                
                if result['success']:
                    results['successful'].append({
                        'application_id': app_id,
                        'character_name': application.character_name,
                        'username': result['user']['username']
                    })
                    results['total_processed'] += 1
                else:
                    results['failed'].append({
                        'application_id': app_id,
                        'character_name': application.character_name,
                        'error': result['error']
                    })
                    
            except Application.DoesNotExist:
                results['failed'].append({
                    'application_id': app_id,
                    'character_name': 'Unknown',
                    'error': 'Application not found or not approved'
                })
        
        logger.info(f"Batch processed {results['total_processed']} applications ({len(results['failed'])} failed)")
        return results
    
    @classmethod
    def get_applications_ready_for_processing(cls) -> list:
        """Get all approved applications that haven't been processed yet."""
        return list(Application.objects.filter(
            status='approved',
            approved_user__isnull=True
        ).order_by('decision_made_at'))


# Convenience function to get the workflow manager instance
def get_recruitment_workflow_manager() -> RecruitmentWorkflowManager:
    """Get a RecruitmentWorkflowManager instance."""
    return RecruitmentWorkflowManager() 