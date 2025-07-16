"""
Management command to open voting periods for officer-approved recruitment applications.
Automatically starts voting for applications that have been approved by officers.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from kromrif_planning.raiders.voting_service import get_voting_manager
from kromrif_planning.raiders.models import Application

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Open voting periods for officer-approved recruitment applications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--application-id',
            type=int,
            help='Open voting for a specific application ID',
        )
        parser.add_argument(
            '--max-applications',
            type=int,
            default=10,
            help='Maximum number of applications to process at once (default: 10)',
        )
        parser.add_argument(
            '--auto-open',
            action='store_true',
            help='Automatically open voting for all officer-approved applications',
        )
        parser.add_argument(
            '--opened-by',
            type=str,
            help='Username of the user opening the voting periods (defaults to system)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be opened without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        """Main command handler."""
        dry_run = options['dry_run']
        verbose = options['verbose']
        application_id = options['application_id']
        max_applications = options['max_applications']
        auto_open = options['auto_open']
        opened_by_username = options['opened_by']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        if verbose:
            self.stdout.write(f"Opening voting periods at {timezone.now()}")
        
        try:
            voting_manager = get_voting_manager()
            
            # Get the user who is opening voting periods
            opened_by = None
            if opened_by_username:
                try:
                    opened_by = User.objects.get(username=opened_by_username)
                    if verbose:
                        self.stdout.write(f"Opening voting periods as user: {opened_by.username}")
                except User.DoesNotExist:
                    raise CommandError(f"User '{opened_by_username}' does not exist")
            
            # Handle specific application
            if application_id:
                result = self._open_specific_application(voting_manager, application_id, opened_by, dry_run, verbose)
                if result['success']:
                    action_word = "would open" if dry_run else "opened"
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully {action_word} voting for application {application_id}')
                    )
                else:
                    raise CommandError(f"Failed to open voting for application {application_id}: {result['error']}")
            
            # Handle auto-opening for officer-approved applications
            elif auto_open:
                result = self._auto_open_approved_applications(voting_manager, max_applications, opened_by, dry_run, verbose)
                if result['opened_count'] > 0:
                    action_word = "would open" if dry_run else "opened"
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully {action_word} voting for {result["opened_count"]} applications')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS('No applications ready for voting at this time')
                    )
            
            # Default: show status of applications ready for voting
            else:
                self._show_applications_ready_for_voting(voting_manager)
                
        except Exception as e:
            raise CommandError(f'Error opening voting periods: {str(e)}')

    def _open_specific_application(self, voting_manager, application_id, opened_by, dry_run, verbose):
        """Open voting for a specific application."""
        try:
            application = Application.objects.get(id=application_id)
        except Application.DoesNotExist:
            return {'success': False, 'error': f'Application {application_id} does not exist'}
        
        if verbose:
            self.stdout.write(f"Processing application: {application.character_name} (ID: {application_id})")
            self.stdout.write(f"  Current status: {application.get_status_display()}")
        
        # Validate application is ready for voting
        if application.status != 'officer_approved':
            return {
                'success': False, 
                'error': f'Application is not ready for voting (status: {application.get_status_display()})'
            }
        
        if not dry_run:
            success = voting_manager.open_voting_period(application, opened_by)
            if not success:
                return {'success': False, 'error': 'Failed to open voting period'}
        
        if verbose:
            if dry_run:
                self.stdout.write(f"  Would open voting period (48h deadline)")
            else:
                deadline_str = application.voting_deadline.strftime('%Y-%m-%d %H:%M:%S') if application.voting_deadline else 'Unknown'
                self.stdout.write(f"  Opened voting period (deadline: {deadline_str})")
        
        return {'success': True}

    def _auto_open_approved_applications(self, voting_manager, max_applications, opened_by, dry_run, verbose):
        """Automatically open voting for officer-approved applications."""
        # Get applications ready for voting
        ready_applications = voting_manager.get_officer_approved_applications()
        
        if not ready_applications:
            if verbose:
                self.stdout.write("No applications ready for voting")
            return {'opened_count': 0, 'applications': []}
        
        # Limit the number to process
        applications_to_process = ready_applications[:max_applications]
        
        if verbose:
            self.stdout.write(f"Found {len(ready_applications)} applications ready for voting")
            self.stdout.write(f"Processing {len(applications_to_process)} applications (max: {max_applications})")
        
        opened_count = 0
        opened_applications = []
        
        for application in applications_to_process:
            if verbose:
                reviewed_date = application.reviewed_at.strftime('%Y-%m-%d') if application.reviewed_at else 'Unknown'
                self.stdout.write(f"  Processing: {application.character_name} (reviewed: {reviewed_date})")
            
            if not dry_run:
                try:
                    success = voting_manager.open_voting_period(application, opened_by)
                    
                    if success:
                        opened_count += 1
                        opened_applications.append({
                            'id': application.id,
                            'character_name': application.character_name,
                            'deadline': application.voting_deadline.isoformat() if application.voting_deadline else None
                        })
                        
                        if verbose:
                            deadline_str = application.voting_deadline.strftime('%Y-%m-%d %H:%M:%S')
                            self.stdout.write(f"    Opened voting (deadline: {deadline_str})")
                    else:
                        if verbose:
                            self.stdout.write(
                                self.style.ERROR(f"    Failed to open voting for {application.character_name}")
                            )
                            
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"    Error opening voting for {application.character_name}: {str(e)}")
                    )
            else:
                opened_count += 1
                if verbose:
                    self.stdout.write(f"    Would open voting period (48h deadline)")
        
        return {
            'opened_count': opened_count,
            'applications': opened_applications
        }

    def _show_applications_ready_for_voting(self, voting_manager):
        """Show applications that are ready to have voting opened."""
        self.stdout.write("=== Applications Ready for Voting ===")
        
        ready_applications = voting_manager.get_officer_approved_applications()
        
        if not ready_applications:
            self.stdout.write("No applications are currently ready for voting.")
            self.stdout.write("\nTo open voting periods automatically, use: --auto-open")
            return
        
        self.stdout.write(f"Found {len(ready_applications)} applications ready for voting:")
        
        for application in ready_applications:
            reviewed_date = application.reviewed_at.strftime('%Y-%m-%d %H:%M') if application.reviewed_at else 'Unknown'
            reviewed_by = application.reviewed_by.username if application.reviewed_by else 'Unknown'
            
            self.stdout.write(
                f"  ID {application.id}: {application.character_name} "
                f"(reviewed: {reviewed_date} by {reviewed_by})"
            )
        
        self.stdout.write(f"\nTo open voting for all applications: --auto-open")
        self.stdout.write(f"To open voting for specific application: --application-id <ID>")
        
        # Show current active voting periods for context
        active_applications = voting_manager.get_active_voting_applications()
        if active_applications:
            self.stdout.write(f"\n=== Currently Active Voting Periods ===")
            self.stdout.write(f"{len(active_applications)} applications currently in voting:")
            
            for application in active_applications:
                time_remaining = application.voting_time_remaining
                if time_remaining:
                    hours_remaining = time_remaining.total_seconds() / 3600
                    deadline_str = application.voting_deadline.strftime('%Y-%m-%d %H:%M')
                    
                    # Get basic vote count
                    vote_count = application.votes.count()
                    
                    self.stdout.write(
                        f"  {application.character_name}: "
                        f"{vote_count} votes, {hours_remaining:.1f}h remaining (deadline: {deadline_str})"
                    )
        
        # Show applications needing officer review
        needing_review = voting_manager.get_applications_needing_review()
        if needing_review:
            self.stdout.write(f"\n=== Applications Awaiting Officer Review ===")
            self.stdout.write(f"{len(needing_review)} applications need officer review:")
            
            for app in needing_review[:10]:  # Show first 10
                submitted_date = app.submitted_at.strftime('%Y-%m-%d')
                self.stdout.write(f"  ID {app.id}: {app.character_name} (submitted: {submitted_date})")
            
            if len(needing_review) > 10:
                self.stdout.write(f"  ... and {len(needing_review) - 10} more") 