"""
Management command for processing Discord notification queue.
Sends queued notifications to Discord channels via webhooks.
"""

import time
from django.core.management.base import BaseCommand
from django.conf import settings
from kromrif_planning.raiders.notification_service import DiscordNotificationService


class Command(BaseCommand):
    help = 'Process queued Discord notifications and send them to Discord channels'

    def add_arguments(self, parser):
        parser.add_argument(
            '--continuous',
            action='store_true',
            help='Run continuously and process notifications every N seconds'
        )
        
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Interval in seconds for continuous processing (default: 30)'
        )
        
        parser.add_argument(
            '--max-iterations',
            type=int,
            help='Maximum number of iterations for continuous mode (default: unlimited)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without actually sending notifications'
        )

    def handle(self, *args, **options):
        service = DiscordNotificationService()
        
        if options['continuous']:
            self.run_continuous(service, options)
        else:
            self.run_once(service, options)

    def run_once(self, service, options):
        """Process notifications once and exit."""
        self.stdout.write("Processing Discord notification queue...")
        
        if options['dry_run']:
            self.stdout.write("DRY RUN: No notifications will be sent")
            # In a real implementation, you'd need to add dry-run support to the service
            return
        
        stats = service.process_notification_queue()
        
        self.stdout.write(
            f"Processing complete: {stats['processed']} processed, "
            f"{stats['successful']} successful, {stats['failed']} failed"
        )
        
        if stats['failed'] > 0:
            self.stdout.write(
                self.style.WARNING(f"⚠ {stats['failed']} notifications failed to send")
            )
        
        if stats['successful'] > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✓ {stats['successful']} notifications sent successfully")
            )

    def run_continuous(self, service, options):
        """Run continuously, processing notifications at regular intervals."""
        interval = options['interval']
        max_iterations = options['max_iterations']
        iterations = 0
        
        self.stdout.write(
            f"Starting continuous Discord notification processing "
            f"(interval: {interval}s, max iterations: {max_iterations or 'unlimited'})"
        )
        
        try:
            while True:
                if max_iterations and iterations >= max_iterations:
                    self.stdout.write(f"Reached maximum iterations ({max_iterations}), stopping")
                    break
                
                iterations += 1
                self.stdout.write(f"\nIteration {iterations}:")
                
                if options['dry_run']:
                    self.stdout.write("DRY RUN: No notifications will be sent")
                    time.sleep(interval)
                    continue
                
                stats = service.process_notification_queue()
                
                if stats['processed'] > 0:
                    self.stdout.write(
                        f"Processed {stats['processed']} notifications: "
                        f"{stats['successful']} successful, {stats['failed']} failed"
                    )
                else:
                    self.stdout.write("No notifications in queue")
                
                # Wait for next iteration
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.stdout.write("\nReceived interrupt signal, stopping...")
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error in continuous processing: {str(e)}")
            )
            raise