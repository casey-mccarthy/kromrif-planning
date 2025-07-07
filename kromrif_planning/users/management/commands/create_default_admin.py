"""Management command to create default admin user for development."""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


class Command(BaseCommand):
    """Create default admin user for development."""
    
    help = 'Create default admin user with credentials admin/admin123'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Admin username (default: admin)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='admin123',
            help='Admin password (default: admin123)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@kromrif.local',
            help='Admin email (default: admin@kromrif.local)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing user'
        )

    def handle(self, *args, **options):
        """Create or update the default admin user."""
        username = options['username']
        password = options['password']
        email = options['email']
        force = options['force']

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
                user.name = 'Default Admin'
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
                    self.style.SUCCESS(
                        f'🔑 Password: {password}'
                    )
                )
                
            except IntegrityError as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Error creating admin user: {e}'
                    )
                )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'❌ Unexpected error: {e}'
                )
            ) 