"""Management command to create default admin user for development."""

import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.conf import settings

User = get_user_model()


class Command(BaseCommand):
    """Create default admin user for development ONLY."""
    
    help = 'Create default admin user with credentials from environment variables (DEVELOPMENT ONLY)'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--username',
            type=str,
            help='Admin username (default: from DJANGO_ADMIN_USERNAME env var)'
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Admin password (default: from DJANGO_ADMIN_PASSWORD env var)'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Admin email (default: from DJANGO_ADMIN_EMAIL env var)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing user'
        )
        parser.add_argument(
            '--allow-production',
            action='store_true',
            help='Allow running in production (NOT RECOMMENDED)'
        )

    def handle(self, *args, **options):
        """Create or update the default admin user."""
        # Safety check: prevent running in production unless explicitly allowed
        if not settings.DEBUG and not options.get('allow_production'):
            raise CommandError(
                "❌ This command is intended for DEVELOPMENT only. "
                "Use --allow-production flag to override (NOT RECOMMENDED)."
            )
        
        # Get credentials from environment or command line
        username = options.get('username') or os.getenv('DJANGO_ADMIN_USERNAME')
        password = options.get('password') or os.getenv('DJANGO_ADMIN_PASSWORD')
        email = options.get('email') or os.getenv('DJANGO_ADMIN_EMAIL')
        force = options.get('force', False)

        # Validate required credentials
        if not username:
            raise CommandError(
                "❌ Admin username required. Set DJANGO_ADMIN_USERNAME environment variable "
                "or use --username argument."
            )
        
        if not password:
            raise CommandError(
                "❌ Admin password required. Set DJANGO_ADMIN_PASSWORD environment variable "
                "or use --password argument."
            )
        
        if not email:
            raise CommandError(
                "❌ Admin email required. Set DJANGO_ADMIN_EMAIL environment variable "
                "or use --email argument."
            )

        # Validate password strength (basic check)
        if len(password) < 8:
            raise CommandError(
                "❌ Password must be at least 8 characters long for security."
            )

        try:
            # Check if user already exists
            user = User.objects.get(username=username)
            
            if force:
                # Update existing user
                user.set_password(password)
                user.email = email
                user.is_staff = True
                user.is_superuser = True
                user.is_active = True
                user.role_group = 'developer'  # Highest role
                user.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Updated existing admin user: {username}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  Admin user "{username}" already exists. Use --force to update.'
                    )
                )
                
        except User.DoesNotExist:
            # Create new user
            try:
                user = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password
                )
                # Set additional fields
                user.role_group = 'developer'  # Highest role
                user.name = f'Admin User ({username})'
                user.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Created default admin user: {username}'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'📧 Email: {email}'
                    )
                )
                self.stdout.write(
                    self.style.WARNING(
                        '🔒 Password set from environment variable (not displayed for security)'
                    )
                )
                
            except IntegrityError as e:
                raise CommandError(f'❌ Error creating admin user: {e}')
        
        except Exception as e:
            raise CommandError(f'❌ Unexpected error: {e}') 