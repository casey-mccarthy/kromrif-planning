"""
Management command to set up Django groups and permissions for recruitment system.
Creates role-based groups and assigns appropriate permissions.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from kromrif_planning.raiders.models import Application, ApplicationVote

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Set up Django groups and permissions for recruitment system role-based access control'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of groups even if they exist',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        """Main command handler."""
        dry_run = options['dry_run']
        force = options['force']
        verbose = options['verbose']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        try:
            with transaction.atomic():
                # Define group permissions mapping
                group_permissions = self._get_group_permissions()
                
                created_groups = 0
                updated_groups = 0
                
                for group_name, permissions_info in group_permissions.items():
                    if verbose:
                        self.stdout.write(f"\nProcessing group: {group_name}")
                    
                    # Check if group exists
                    group, created = Group.objects.get_or_create(name=group_name)
                    
                    if created:
                        created_groups += 1
                        if verbose:
                            self.stdout.write(f"  Created new group: {group_name}")
                    elif force:
                        # Clear existing permissions if force is enabled
                        group.permissions.clear()
                        updated_groups += 1
                        if verbose:
                            self.stdout.write(f"  Cleared existing permissions for: {group_name}")
                    elif group.permissions.exists():
                        if verbose:
                            self.stdout.write(f"  Group {group_name} already exists with permissions (use --force to reset)")
                        continue
                    else:
                        updated_groups += 1
                        if verbose:
                            self.stdout.write(f"  Adding permissions to existing group: {group_name}")
                    
                    # Add permissions to group
                    permissions_added = 0
                    for app_label, model_name, perm_codename in permissions_info['permissions']:
                        try:
                            content_type = ContentType.objects.get(
                                app_label=app_label,
                                model=model_name
                            )
                            permission = Permission.objects.get(
                                content_type=content_type,
                                codename=perm_codename
                            )
                            
                            if not dry_run:
                                group.permissions.add(permission)
                            
                            permissions_added += 1
                            
                            if verbose:
                                self.stdout.write(f"    Added permission: {perm_codename}")
                                
                        except (ContentType.DoesNotExist, Permission.DoesNotExist) as e:
                            self.stdout.write(
                                self.style.WARNING(f"    Permission not found: {app_label}.{model_name}.{perm_codename}")
                            )
                    
                    if verbose:
                        self.stdout.write(f"  Total permissions added: {permissions_added}")
                
                # Raise exception to rollback transaction in dry-run mode
                if dry_run:
                    raise CommandError("Dry run complete - rolling back changes")
                
                # Success message
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nSuccessfully set up recruitment groups!\n'
                        f'Created: {created_groups} groups\n'
                        f'Updated: {updated_groups} groups'
                    )
                )
                
        except CommandError:
            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS('\nDry run completed - no changes made')
                )
            else:
                raise
        except Exception as e:
            raise CommandError(f'Error setting up groups: {str(e)}')

    def _get_group_permissions(self):
        """
        Define the permissions mapping for each group.
        Returns a dictionary with group names and their associated permissions.
        """
        return {
            'Recruitment Officers': {
                'description': 'Officers who can manage all recruitment activities',
                'permissions': [
                    # Application permissions
                    ('raiders', 'application', 'add_application'),
                    ('raiders', 'application', 'change_application'),
                    ('raiders', 'application', 'delete_application'),
                    ('raiders', 'application', 'view_application'),
                    ('raiders', 'application', 'review_applications'),
                    ('raiders', 'application', 'manage_applications'),
                    ('raiders', 'application', 'vote_on_applications'),
                    ('raiders', 'application', 'view_application_votes'),
                    ('raiders', 'application', 'view_sensitive_application_info'),
                    
                    # ApplicationVote permissions
                    ('raiders', 'applicationvote', 'add_applicationvote'),
                    ('raiders', 'applicationvote', 'change_applicationvote'),
                    ('raiders', 'applicationvote', 'delete_applicationvote'),
                    ('raiders', 'applicationvote', 'view_applicationvote'),
                    ('raiders', 'applicationvote', 'view_application_vote_details'),
                    ('raiders', 'applicationvote', 'manage_application_votes'),
                ]
            },
            'Voting Members': {
                'description': 'Members with sufficient attendance who can vote on applications',
                'permissions': [
                    # Basic application viewing
                    ('raiders', 'application', 'view_application'),
                    ('raiders', 'application', 'vote_on_applications'),
                    ('raiders', 'application', 'view_application_votes'),
                    
                    # Basic vote permissions  
                    ('raiders', 'applicationvote', 'add_applicationvote'),
                    ('raiders', 'applicationvote', 'view_applicationvote'),
                ]
            },
            'Guild Members': {
                'description': 'Regular guild members with read-only access to public application info',
                'permissions': [
                    # Read-only application access
                    ('raiders', 'application', 'view_application'),
                    ('raiders', 'applicationvote', 'view_applicationvote'),
                ]
            },
            'Applicants': {
                'description': 'Users who have submitted applications',
                'permissions': [
                    # Limited application access (own applications only via object-level permissions)
                    ('raiders', 'application', 'view_application'),
                    ('raiders', 'application', 'change_application'),  # For updating own application
                ]
            },
        }

    def _show_group_info(self, group_name, permissions_info, verbose=False):
        """Display information about a group and its permissions."""
        self.stdout.write(f"\n{group_name}:")
        self.stdout.write(f"  Description: {permissions_info['description']}")
        
        if verbose:
            self.stdout.write("  Permissions:")
            for app_label, model_name, perm_codename in permissions_info['permissions']:
                self.stdout.write(f"    - {app_label}.{model_name}.{perm_codename}") 