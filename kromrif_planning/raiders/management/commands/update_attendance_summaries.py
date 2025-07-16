"""
Management command for updating member attendance summaries.
Runs daily calculations for rolling averages and voting eligibility.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from kromrif_planning.raiders.attendance_service import get_attendance_service
from kromrif_planning.raiders.models import MemberAttendanceSummary

User = get_user_model()


class Command(BaseCommand):
    help = 'Update member attendance summaries with rolling averages and voting eligibility'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date for calculations (YYYY-MM-DD format, defaults to today)'
        )
        
        parser.add_argument(
            '--user-id',
            type=int,
            help='Update only specific user by ID'
        )
        
        parser.add_argument(
            '--username',
            type=str,
            help='Update only specific user by username'
        )
        
        parser.add_argument(
            '--active-only',
            action='store_true',
            help='Only update users with recent raid attendance (default: False)'
        )
        
        parser.add_argument(
            '--days-back',
            type=int,
            default=180,
            help='Consider users active if they have attendance within N days (default: 180)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )

    def handle(self, *args, **options):
        """
        Main command handler.
        
        Args:
            *args: Command arguments
            **options: Command options
        """
        # Configure logging
        logging.basicConfig(
            level=logging.INFO if options['verbose'] else logging.WARNING,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger(__name__)
        
        try:
            # Parse calculation date
            calculation_date = self._parse_date(options.get('date'))
            logger.info(f"Starting attendance summary update for {calculation_date}")
            
            # Get users to update
            users_to_update = self._get_users_to_update(options, logger)
            
            if not users_to_update:
                self.stdout.write(
                    self.style.WARNING('No users found matching criteria')
                )
                return
            
            self.stdout.write(
                f"Found {len(users_to_update)} user(s) to update"
            )
            
            if options['dry_run']:
                self.stdout.write(
                    self.style.WARNING('DRY RUN MODE - No changes will be made')
                )
                self._show_dry_run_preview(users_to_update, calculation_date)
                return
            
            # Perform the updates
            self._update_summaries(users_to_update, calculation_date, logger)
            
        except Exception as e:
            logger.error(f"Command failed: {str(e)}")
            raise CommandError(f"Failed to update attendance summaries: {str(e)}")

    def _parse_date(self, date_str: Optional[str]) -> datetime:
        """
        Parse the calculation date from string input.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            Parsed datetime object
            
        Raises:
            CommandError: If date format is invalid
        """
        if not date_str:
            return timezone.now().date()
        
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError(
                f"Invalid date format: {date_str}. Use YYYY-MM-DD format."
            )

    def _get_users_to_update(self, options: dict, logger: logging.Logger):
        """
        Get the list of users to update based on command options.
        
        Args:
            options: Command options
            logger: Logger instance
            
        Returns:
            QuerySet of users to update
        """
        # Handle specific user selection
        if options.get('user_id'):
            try:
                return [User.objects.get(id=options['user_id'])]
            except User.DoesNotExist:
                raise CommandError(f"User with ID {options['user_id']} not found")
        
        if options.get('username'):
            try:
                return [User.objects.get(username=options['username'])]
            except User.DoesNotExist:
                raise CommandError(f"User '{options['username']}' not found")
        
        # Get users based on activity criteria
        if options['active_only']:
            days_back = options['days_back']
            cutoff_date = timezone.now().date() - timedelta(days=days_back)
            
            users = User.objects.filter(
                raid_attendance__raid__date__gte=cutoff_date
            ).distinct().order_by('username')
            
            logger.info(
                f"Filtering to users with attendance since {cutoff_date} "
                f"({days_back} days ago)"
            )
        else:
            # All users with any raid attendance
            users = User.objects.filter(
                raid_attendance__isnull=False
            ).distinct().order_by('username')
            
            logger.info("Processing all users with raid attendance history")
        
        return list(users)

    def _show_dry_run_preview(self, users: list, calculation_date: datetime):
        """
        Show preview of what would be updated in dry run mode.
        
        Args:
            users: List of users to preview
            calculation_date: Date for calculations
        """
        self.stdout.write("\nDRY RUN PREVIEW:")
        self.stdout.write("=" * 50)
        
        for user in users[:10]:  # Show first 10 users
            self.stdout.write(f"Would update: {user.username} (ID: {user.id})")
        
        if len(users) > 10:
            self.stdout.write(f"... and {len(users) - 10} more users")
        
        self.stdout.write(f"\nCalculation date: {calculation_date}")
        self.stdout.write("\nRun without --dry-run to execute updates")

    @transaction.atomic
    def _update_summaries(self, users: list, calculation_date: datetime, logger: logging.Logger):
        """
        Update attendance summaries for the specified users.
        
        Args:
            users: List of users to update
            calculation_date: Date for calculations
            logger: Logger instance
        """
        # Initialize attendance service
        attendance_service = get_attendance_service(base_date=calculation_date)
        
        success_count = 0
        error_count = 0
        
        self.stdout.write(
            f"Updating attendance summaries for {len(users)} users..."
        )
        
        for i, user in enumerate(users, 1):
            try:
                # Update summary for this user
                summary = attendance_service.update_user_summary(
                    user=user, 
                    summary_date=calculation_date
                )
                
                success_count += 1
                logger.info(
                    f"Updated summary for {user.username} - "
                    f"30d: {summary.attendance_rate_30d}%, "
                    f"voting eligible: {summary.is_voting_eligible}"
                )
                
                # Progress indicator
                if i % 10 == 0 or i == len(users):
                    self.stdout.write(
                        f"Processed {i}/{len(users)} users...",
                        ending='\r'
                    )
                
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to update {user.username}: {str(e)}")
                
                # Don't fail the entire command for individual user errors
                continue
        
        # Final results
        self.stdout.write()  # New line after progress indicator
        
        if success_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully updated {success_count} attendance summaries"
                )
            )
        
        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(
                    f"Failed to update {error_count} summaries"
                )
            )
            
        # Summary statistics
        total_summaries = MemberAttendanceSummary.objects.filter(
            summary_date=calculation_date
        ).count()
        
        voting_eligible = MemberAttendanceSummary.objects.filter(
            summary_date=calculation_date,
            is_voting_eligible=True
        ).count()
        
        self.stdout.write(
            f"\nSummary for {calculation_date}:"
        )
        self.stdout.write(f"Total summaries: {total_summaries}")
        self.stdout.write(f"Voting eligible members: {voting_eligible}")
        
        logger.info(
            f"Command completed. Success: {success_count}, Errors: {error_count}"
        ) 