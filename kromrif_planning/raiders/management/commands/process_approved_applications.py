"""
Management command to process approved recruitment applications.
Triggers automatic character creation, user setup, and guild integration workflows.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone

from kromrif_planning.raiders.recruitment_workflows import get_recruitment_workflow_manager
from kromrif_planning.raiders.recruitment_signals import (
    trigger_workflow_for_application,
    trigger_workflows_for_multiple_applications
)
from kromrif_planning.raiders.models import Application

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process approved recruitment applications and trigger automatic workflows'

    def add_arguments(self, parser):
        parser.add_argument(
            '--application-id',
            type=int,
            help='Process a specific application by ID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all approved applications that haven\'t been processed yet',
        )
        parser.add_argument(
            '--max-applications',
            type=int,
            default=50,
            help='Maximum number of applications to process at once (default: 50)',
        )
        parser.add_argument(
            '--approved-by',
            type=str,
            help='Username of the user who approved the applications (for audit trail)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force processing even if applications have already been processed',
        )

    def handle(self, *args, **options):
        """Main command handler."""
        dry_run = options['dry_run']
        verbose = options['verbose']
        application_id = options['application_id']
        process_all = options['all']
        max_applications = options['max_applications']
        approved_by_username = options['approved_by']
        force = options['force']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        if verbose:
            self.stdout.write(f"Processing approved applications at {timezone.now()}")
        
        try:
            # Get the user who approved the applications
            approved_by = None
            if approved_by_username:
                try:
                    approved_by = User.objects.get(username=approved_by_username)
                    if verbose:
                        self.stdout.write(f"Processing as user: {approved_by.username}")
                except User.DoesNotExist:
                    raise CommandError(f"User '{approved_by_username}' does not exist")
            
            # Handle specific application
            if application_id:
                result = self._process_specific_application(
                    application_id, approved_by, force, dry_run, verbose
                )
                if result['success']:
                    action_word = "would process" if dry_run else "processed"
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully {action_word} application {application_id}')
                    )
                else:
                    raise CommandError(f"Failed to process application {application_id}: {result['error']}")
            
            # Handle processing all approved applications
            elif process_all:
                result = self._process_all_applications(
                    max_applications, approved_by, force, dry_run, verbose
                )
                if result['total_processed'] > 0:
                    action_word = "would process" if dry_run else "processed"
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Successfully {action_word} {result["total_processed"]} applications'
                        )
                    )
                    if result['failed']:
                        self.stdout.write(
                            self.style.WARNING(f'{len(result["failed"])} applications failed processing')
                        )
                else:
                    self.stdout.write(
                        self.style.SUCCESS('No approved applications need processing at this time')
                    )
            
            # Default: show status of applications ready for processing
            else:
                self._show_applications_ready_for_processing(force)
                
        except Exception as e:
            raise CommandError(f'Error processing approved applications: {str(e)}')

    def _process_specific_application(self, application_id, approved_by, force, dry_run, verbose):
        """Process a specific application."""
        try:
            application = Application.objects.get(id=application_id, status='approved')
        except Application.DoesNotExist:
            return {
                'success': False, 
                'error': f'Application {application_id} not found or not approved'
            }
        
        if verbose:
            self.stdout.write(f"Processing application: {application.character_name} (ID: {application_id})")
            self.stdout.write(f"  Applicant: {application.applicant_name} ({application.applicant_email})")
            self.stdout.write(f"  Character: Level {application.character_level} {application.character_class}")
        
        # Check if already processed
        if application.approved_user and not force:
            return {
                'success': False,
                'error': 'Application has already been processed (use --force to reprocess)'
            }
        
        if not dry_run:
            if force and application.approved_user:
                # For force processing, we need to clear the existing user link
                if verbose:
                    self.stdout.write(f"  Force mode: Clearing existing user link")
                application.approved_user = None
                application.save()
            
            # Trigger the workflow
            result = trigger_workflow_for_application(application_id, approved_by)
            
            if result['success']:
                if verbose:
                    user_info = result['user']
                    character_info = result['character']
                    self.stdout.write(f"  Created user: {user_info['username']}")
                    self.stdout.write(f"  Created character: {character_info['name']}")
                    self.stdout.write(f"  DKP initialized: {result['dkp_initialized']}")
                    self.stdout.write(f"  Groups assigned: {result['groups_assigned']}")
            else:
                if verbose:
                    self.stdout.write(
                        self.style.ERROR(f"  Processing failed: {result['error']}")
                    )
                return result
        else:
            if verbose:
                self.stdout.write(f"  Would create user account and character record")
                self.stdout.write(f"  Would initialize DKP and assign to groups")
        
        return {'success': True}

    def _process_all_applications(self, max_applications, approved_by, force, dry_run, verbose):
        """Process all approved applications that haven't been processed yet."""
        workflow_manager = get_recruitment_workflow_manager()
        
        # Get applications ready for processing
        if force:
            # Include all approved applications if force is enabled
            ready_applications = list(Application.objects.filter(
                status='approved'
            ).order_by('decision_made_at')[:max_applications])
        else:
            # Only unprocessed applications
            ready_applications = workflow_manager.get_applications_ready_for_processing()[:max_applications]
        
        if not ready_applications:
            if verbose:
                self.stdout.write("No approved applications need processing")
            return {'total_processed': 0, 'successful': [], 'failed': []}
        
        if verbose:
            self.stdout.write(f"Found {len(ready_applications)} approved applications to process")
            if max_applications < len(ready_applications):
                self.stdout.write(f"Processing first {max_applications} applications (use --max-applications to change)")
        
        processed_count = 0
        successful = []
        failed = []
        
        for application in ready_applications:
            if verbose:
                decision_date = application.decision_made_at.strftime('%Y-%m-%d %H:%M') if application.decision_made_at else 'Unknown'
                self.stdout.write(
                    f"  Processing: {application.character_name} "
                    f"(ID: {application.id}, approved: {decision_date})"
                )
            
            if not dry_run:
                try:
                    if force and application.approved_user:
                        # Clear existing user link for force processing
                        application.approved_user = None
                        application.save()
                    
                    result = workflow_manager.process_approved_application(
                        application=application,
                        approved_by=approved_by
                    )
                    
                    if result['success']:
                        processed_count += 1
                        successful.append({
                            'application_id': application.id,
                            'character_name': application.character_name,
                            'username': result['user']['username']
                        })
                        
                        if verbose:
                            self.stdout.write(f"    ✓ Created user: {result['user']['username']}")
                    else:
                        failed.append({
                            'application_id': application.id,
                            'character_name': application.character_name,
                            'error': result['error']
                        })
                        
                        if verbose:
                            self.stdout.write(
                                self.style.ERROR(f"    ✗ Failed: {result['error']}")
                            )
                            
                except Exception as e:
                    failed.append({
                        'application_id': application.id,
                        'character_name': application.character_name,
                        'error': str(e)
                    })
                    
                    if verbose:
                        self.stdout.write(
                            self.style.ERROR(f"    ✗ Exception: {str(e)}")
                        )
            else:
                processed_count += 1
                if verbose:
                    self.stdout.write(f"    Would create user account and character record")
        
        return {
            'total_processed': processed_count,
            'successful': successful,
            'failed': failed
        }

    def _show_applications_ready_for_processing(self, force):
        """Show applications that are ready for processing."""
        self.stdout.write("=== Approved Applications Ready for Processing ===")
        
        workflow_manager = get_recruitment_workflow_manager()
        
        if force:
            ready_applications = list(Application.objects.filter(
                status='approved'
            ).order_by('decision_made_at'))
            self.stdout.write("Showing ALL approved applications (--force mode)")
        else:
            ready_applications = workflow_manager.get_applications_ready_for_processing()
            self.stdout.write("Showing unprocessed approved applications")
        
        if not ready_applications:
            self.stdout.write("No approved applications need processing.")
            self.stdout.write("\nTo process all approved applications: --all")
            return
        
        self.stdout.write(f"Found {len(ready_applications)} applications ready for processing:")
        
        for application in ready_applications:
            decision_date = application.decision_made_at.strftime('%Y-%m-%d %H:%M') if application.decision_made_at else 'Unknown'
            decision_by = application.decision_made_by.username if application.decision_made_by else 'Unknown'
            
            status_indicator = "🔄" if application.approved_user else "✅"
            
            self.stdout.write(
                f"  {status_indicator} ID {application.id}: {application.character_name} "
                f"({application.applicant_name}) - "
                f"Approved: {decision_date} by {decision_by}"
            )
        
        self.stdout.write(f"\nTo process all applications: --all")
        self.stdout.write(f"To process specific application: --application-id <ID>")
        self.stdout.write(f"To include already processed: --force")
        
        # Show summary of what would be created
        if ready_applications:
            total_chars = len(ready_applications)
            classes = {}
            levels = []
            
            for app in ready_applications:
                char_class = app.character_class
                classes[char_class] = classes.get(char_class, 0) + 1
                levels.append(app.character_level)
            
            self.stdout.write(f"\n=== Summary ===")
            self.stdout.write(f"Total characters to create: {total_chars}")
            self.stdout.write(f"Class distribution: {dict(classes)}")
            if levels:
                avg_level = sum(levels) / len(levels)
                self.stdout.write(f"Average level: {avg_level:.1f} (range: {min(levels)}-{max(levels)})") 