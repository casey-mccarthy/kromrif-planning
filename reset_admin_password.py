#!/usr/bin/env python
"""Standalone script to reset admin password"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Get or create admin user
username = 'admin'
password = 'admin123'
email = 'admin@localhost.local'

try:
    user = User.objects.get(username=username)
    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()
    print(f"Password reset for existing user: {username}")
except User.DoesNotExist:
    user = User.objects.create_superuser(username, email, password)
    print(f"Created new superuser: {username}")

# Verify the password works
if user.check_password(password):
    print("✓ Password verification successful")
else:
    print("✗ Password verification failed")

print(f"\nYou can now login with:")
print(f"Username: {username}")
print(f"Password: {password}")
print(f"URL: http://localhost:8000/admin/")