"""
Management command to process voting periods for recruitment applications.
Handles automated voting period closure, deadline notifications, and status updates.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction

from kromrif_planning.raiders.voting_service import get_voting_manager
from kromrif_planning.raiders.models import Application

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process voting periods for recruitment applications (close expired, send notifications)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--close-expired',
            action='store_true',
            help='Close expired voting periods and tally votes',
        )
        parser.add_argument(
            '--send-notifications',
            action='store_true',
            help='Send deadline reminder notifications',
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
            '--all',
            action='store_true',
            help='Run all voting period operations (equivalent to --close-expired --send-notifications)',
        )

    def handle(self, *args, **options):
        """Main command handler."""
        dry_run = options['dry_run']
        verbose = options['verbose']
        close_expired = options['close_expired'] or options['all']
        send_notifications = options['send_notifications'] or options['all']
        
        if not any([close_expired, send_notifications]):
            close_expired = send_notifications = True  # Default to all operations
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        if verbose:
            self.stdout.write(f"Processing voting periods at {timezone.now()}")
        
        try:
            voting_manager = get_voting_manager()
            total_processed = 0
            
            # Process expired voting periods
            if close_expired:
                if verbose:
                    self.stdout.write("\n=== Processing Expired Voting Periods ===")
                
                expired_results = self._process_expired_periods(voting_manager, dry_run, verbose)
                total_processed += expired_results['processed_count']
            
            # Send deadline notifications
            if send_notifications:
                if verbose:
                    self.stdout.write("\n=== Sending Deadline Notifications ===")
                
                notification_results = self._send_deadline_notifications(voting_manager, dry_run, verbose)
                total_processed += notification_results['notifications_sent']
            
            # Show active voting periods status
            if verbose:
                self._show_active_voting_status(voting_manager)
            
            # Summary
            if total_processed > 0:
                action_word = "would process" if dry_run else "processed"
                self.stdout.write(
                    self.style.SUCCESS(f'\nSuccessfully {action_word} {total_processed} voting operations')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('\nNo voting operations needed at this time')
                )
                
        except Exception as e:
            raise CommandError(f'Error processing voting periods: {str(e)}')

    def _process_expired_periods(self, voting_manager, dry_run, verbose):
        """Process expired voting periods."""
        # Find expired applications
        now = timezone.now()
        expired_applications = Application.objects.filter(
            status='voting_open',
            voting_deadline__lt=now
        ).order_by('voting_deadline')
        
        if not expired_applications.exists():
            if verbose:
                self.stdout.write("  No expired voting periods found")
            return {'processed_count': 0}
        
        if verbose:
            self.stdout.write(f"  Found {expired_applications.count()} expired voting periods")
        
        processed_count = 0
        results = []
        
        for application in expired_applications:
            if verbose:
                deadline_str = application.voting_deadline.strftime('%Y-%m-%d %H:%M:%S')
                self.stdout.write(f"  Processing: {application.character_name} (deadline: {deadline_str})")
            
            if not dry_run:
                try:
                    result = voting_manager.close_voting_period(application)
                    
                    if result.get('success'):
                        processed_count += 1
                        decision = result['decision']
                        
                        results.append({
                            'application_id': application.id,
                            'character_name': application.character_name,
                            'decision': decision['final_status'],
                            'reason': decision['reason']
                        })
                        
                        if verbose:
                            self.stdout.write(f"    Result: {decision['final_status']} - {decision['reason']}")
                    else:
                        self.stdout.write(
                            self.style.ERROR(f"    Failed: {result.get('error')}")
                        )
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"    Error processing application {application.id}: {str(e)}")
                    )
            else:
                processed_count += 1
                if verbose:
                    self.stdout.write(f"    Would close voting period and tally votes")
        
        return {
            'processed_count': processed_count,
            'results': results
        }

    def _send_deadline_notifications(self, voting_manager, dry_run, verbose):
        """Send deadline reminder notifications."""
        if not dry_run:
            results = voting_manager.send_deadline_notifications()
            notifications_sent = results['notifications_sent']
        else:
            # For dry run, calculate what would be sent
            from datetime import timedelta
            now = timezone.now()
            notifications_sent = 0
            
            for hours_before in voting_manager.NOTIFICATION_HOURS_BEFORE_DEADLINE:
                notification_time = now + timedelta(hours=hours_before)
                window_start = notification_time - timedelta(minutes=30)
                window_end = notification_time + timedelta(minutes=30)
                
                applications = Application.objects.filter(
                    status='voting_open',
                    voting_deadline__gte=window_start,
                    voting_deadline__lte=window_end
                )
                
                for application in applications:
                    notifications_sent += 1
                    if verbose:
                        self.stdout.write(f"  Would send {hours_before}h reminder for: {application.character_name}")
        
        if verbose:
            if notifications_sent > 0:
                action_word = "would send" if dry_run else "sent"
                self.stdout.write(f"  {action_word.title()} {notifications_sent} deadline reminder notifications")
            else:
                self.stdout.write("  No deadline notifications needed")
        
        return {'notifications_sent': notifications_sent}

    def _show_active_voting_status(self, voting_manager):
        """Show status of active voting periods."""
        self.stdout.write("\n=== Active Voting Periods Status ===")
        
        active_applications = voting_manager.get_active_voting_applications()
        
        if not active_applications:
            self.stdout.write("  No active voting periods")
            return
        
        self.stdout.write(f"  {len(active_applications)} active voting periods:")
        
        for application in active_applications:
            time_remaining = application.voting_time_remaining
            if time_remaining:
                hours_remaining = time_remaining.total_seconds() / 3600
                deadline_str = application.voting_deadline.strftime('%Y-%m-%d %H:%M')
                
                # Get vote statistics
                stats = voting_manager.get_voting_statistics(application)
                vote_count = stats['vote_counts']['total_votes']
                approval_pct = stats['approval_percentage']
                
                self.stdout.write(
                    f"    {application.character_name}: "
                    f"{vote_count} votes, {approval_pct:.1f}% approval, "
                    f"{hours_remaining:.1f}h remaining (deadline: {deadline_str})"
                )
        
        # Show applications needing review
        needing_review = voting_manager.get_applications_needing_review()
        if needing_review:
            self.stdout.write(f"\n  {len(needing_review)} applications awaiting officer review:")
            for app in needing_review[:5]:  # Show first 5
                submitted_date = app.submitted_at.strftime('%Y-%m-%d')
                self.stdout.write(f"    {app.character_name} (submitted: {submitted_date})")
            if len(needing_review) > 5:
                self.stdout.write(f"    ... and {len(needing_review) - 5} more")
        
        # Show officer approved applications
        officer_approved = voting_manager.get_officer_approved_applications()
        if officer_approved:
            self.stdout.write(f"\n  {len(officer_approved)} applications approved and ready for voting:")
            for app in officer_approved[:5]:  # Show first 5
                reviewed_date = app.reviewed_at.strftime('%Y-%m-%d') if app.reviewed_at else 'Unknown'
                self.stdout.write(f"    {app.character_name} (reviewed: {reviewed_date})")
            if len(officer_approved) > 5:
                self.stdout.write(f"    ... and {len(officer_approved) - 5} more") 