"""
Management command for Discord user linking operations.
Provides CLI interface for bulk linking and management operations.
"""

import csv
import json
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from kromrif_planning.raiders.services import DiscordMemberService

User = get_user_model()


class Command(BaseCommand):
    help = 'Manage Discord user linking operations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['link', 'unlink', 'list', 'bulk-link', 'validate'],
            required=True,
            help='Action to perform'
        )
        
        parser.add_argument(
            '--discord-id',
            type=str,
            help='Discord user ID'
        )
        
        parser.add_argument(
            '--username',
            type=str,
            help='Application username'
        )
        
        parser.add_argument(
            '--discord-username',
            type=str,
            help='Discord username (optional)'
        )
        
        parser.add_argument(
            '--csv-file',
            type=str,
            help='CSV file for bulk operations (columns: discord_id,username,discord_username)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'link':
            self.handle_link(options)
        elif action == 'unlink':
            self.handle_unlink(options)
        elif action == 'list':
            self.handle_list(options)
        elif action == 'bulk-link':
            self.handle_bulk_link(options)
        elif action == 'validate':
            self.handle_validate(options)

    def handle_link(self, options):
        """Link a single Discord user to an application account."""
        discord_id = options.get('discord_id')
        username = options.get('username')
        discord_username = options.get('discord_username')
        
        if not discord_id or not username:
            raise CommandError('Both --discord-id and --username are required for linking')
        
        if options.get('dry_run'):
            self.stdout.write(
                f"DRY RUN: Would link Discord ID {discord_id} to user {username}"
            )
            return
        
        success, message, user = DiscordMemberService.link_discord_user(
            discord_id=discord_id,
            app_username=username,
            discord_username=discord_username
        )
        
        if success:
            self.stdout.write(
                self.style.SUCCESS(f"✓ {message}")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"✗ {message}")
            )

    def handle_unlink(self, options):
        """Unlink a Discord user from an application account."""
        identifier = options.get('discord_id') or options.get('username')
        
        if not identifier:
            raise CommandError('Either --discord-id or --username is required for unlinking')
        
        if options.get('dry_run'):
            self.stdout.write(
                f"DRY RUN: Would unlink {identifier}"
            )
            return
        
        success, message, user = DiscordMemberService.unlink_discord_user(identifier)
        
        if success:
            self.stdout.write(
                self.style.SUCCESS(f"✓ {message}")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"✗ {message}")
            )

    def handle_list(self, options):
        """List all Discord-linked users."""
        linked_users = DiscordMemberService.get_discord_linked_users()
        
        if not linked_users:
            self.stdout.write("No Discord-linked users found.")
            return
        
        self.stdout.write(f"\nFound {len(linked_users)} Discord-linked users:\n")
        self.stdout.write(f"{'Username':<20} {'Discord ID':<20} {'Discord Name':<20} {'Main Character':<20} {'Status'}")
        self.stdout.write("-" * 100)
        
        for user_data in linked_users:
            status = "Active" if user_data['is_active'] else "Inactive"
            self.stdout.write(
                f"{user_data['username']:<20} "
                f"{user_data['discord_id']:<20} "
                f"{user_data['discord_username'] or 'N/A':<20} "
                f"{user_data['main_character'] or 'N/A':<20} "
                f"{status}"
            )

    def handle_bulk_link(self, options):
        """Bulk link users from CSV file."""
        csv_file = options.get('csv_file')
        
        if not csv_file:
            raise CommandError('--csv-file is required for bulk linking')
        
        try:
            with open(csv_file, 'r', newline='') as file:
                reader = csv.DictReader(file)
                
                if not all(col in reader.fieldnames for col in ['discord_id', 'username']):
                    raise CommandError('CSV file must have columns: discord_id, username (discord_username is optional)')
                
                results = {
                    'successful': 0,
                    'failed': 0,
                    'errors': []
                }
                
                for row in reader:
                    discord_id = row['discord_id'].strip()
                    username = row['username'].strip()
                    discord_username = row.get('discord_username', '').strip() or None
                    
                    if not discord_id or not username:
                        results['failed'] += 1
                        results['errors'].append(f"Skipped row with missing data: {row}")
                        continue
                    
                    if options.get('dry_run'):
                        self.stdout.write(
                            f"DRY RUN: Would link Discord ID {discord_id} to user {username}"
                        )
                        continue
                    
                    success, message, user = DiscordMemberService.link_discord_user(
                        discord_id=discord_id,
                        app_username=username,
                        discord_username=discord_username
                    )
                    
                    if success:
                        results['successful'] += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"✓ Linked {discord_id} to {username}")
                        )
                    else:
                        results['failed'] += 1
                        results['errors'].append(f"Failed to link {discord_id} to {username}: {message}")
                        self.stdout.write(
                            self.style.ERROR(f"✗ Failed to link {discord_id} to {username}: {message}")
                        )
                
                # Summary
                if not options.get('dry_run'):
                    self.stdout.write(f"\nBulk link summary:")
                    self.stdout.write(f"  Successful: {results['successful']}")
                    self.stdout.write(f"  Failed: {results['failed']}")
                    
                    if results['errors']:
                        self.stdout.write(f"\nErrors:")
                        for error in results['errors']:
                            self.stdout.write(f"  - {error}")
                            
        except FileNotFoundError:
            raise CommandError(f"CSV file not found: {csv_file}")
        except Exception as e:
            raise CommandError(f"Error processing CSV file: {str(e)}")

    def handle_validate(self, options):
        """Validate Discord links and report any issues."""
        linked_users = DiscordMemberService.get_discord_linked_users()
        issues = []
        
        self.stdout.write(f"Validating {len(linked_users)} Discord-linked users...\n")
        
        for user_data in linked_users:
            user_issues = []
            
            # Check for missing Discord username
            if not user_data.get('discord_username'):
                user_issues.append("Missing Discord username")
            
            # Check for inactive users
            if not user_data.get('is_active'):
                user_issues.append("User is inactive")
            
            # Check for missing main character
            if not user_data.get('main_character'):
                user_issues.append("No main character found")
            
            # Check Discord ID format
            discord_id = user_data.get('discord_id', '')
            if not discord_id.isdigit() or len(discord_id) < 10:
                user_issues.append("Invalid Discord ID format")
            
            if user_issues:
                issues.append({
                    'username': user_data['username'],
                    'discord_id': user_data['discord_id'],
                    'issues': user_issues
                })
        
        if issues:
            self.stdout.write(self.style.WARNING(f"Found {len(issues)} users with issues:\n"))
            for issue_data in issues:
                self.stdout.write(f"User: {issue_data['username']} (Discord ID: {issue_data['discord_id']})")
                for issue in issue_data['issues']:
                    self.stdout.write(f"  - {issue}")
                self.stdout.write("")
        else:
            self.stdout.write(self.style.SUCCESS("✓ All Discord links validated successfully!"))