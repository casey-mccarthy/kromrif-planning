"""
Discord Webhook Notification Service for Recruitment System.

Handles Discord notifications for all recruitment events including:
- New application submissions
- Voting period management (open/close/reminders)
- Application approvals and rejections  
- Character creation and promotion workflows
- Officer review notifications
"""

import logging
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Application, ApplicationVote

User = get_user_model()
logger = logging.getLogger(__name__)


class DiscordNotificationService:
    """
    Service class for sending Discord webhook notifications.
    Handles formatting and delivery of recruitment-related notifications.
    """
    
    def __init__(self):
        """Initialize the Discord notification service."""
        self.webhook_url = getattr(settings, 'DISCORD_RECRUITMENT_WEBHOOK_URL', None)
        self.notification_enabled = getattr(settings, 'DISCORD_NOTIFICATIONS_ENABLED', False)
        
        # Color scheme for different event types
        self.colors = {
            'new_application': 0x3498db,      # Blue
            'voting_open': 0x9b59b6,          # Purple  
            'voting_reminder': 0xf39c12,      # Orange
            'voting_closed': 0x95a5a6,        # Gray
            'approved': 0x27ae60,             # Green
            'rejected': 0xe74c3c,             # Red
            'character_created': 0x2ecc71,    # Bright Green
            'error': 0xe67e22,                # Dark Orange
            'info': 0x3498db,                 # Blue
        }
    
    def _send_webhook(self, payload: Dict) -> bool:
        """
        Send a webhook payload to Discord.
        
        Args:
            payload: Discord webhook payload
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.notification_enabled or not self.webhook_url:
            logger.debug("Discord notifications disabled or webhook URL not configured")
            return False
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 204:
                logger.debug("Discord notification sent successfully")
                return True
            else:
                logger.warning(f"Discord webhook returned status {response.status_code}: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Discord notification: {str(e)}")
            return False
    
    def notify_new_application(self, application: Application) -> bool:
        """
        Send notification for new application submission.
        
        Args:
            application: The submitted Application instance
            
        Returns:
            bool: True if notification sent successfully
        """
        embed = {
            "title": "🆕 New Guild Application",
            "description": f"**{application.character_name}** has submitted an application",
            "color": self.colors['new_application'],
            "fields": [
                {
                    "name": "Character",
                    "value": f"Level {application.character_level} {application.character_class}",
                    "inline": True
                },
                {
                    "name": "Applicant",
                    "value": application.applicant_name,
                    "inline": True
                },
                {
                    "name": "Discord",
                    "value": application.discord_username,
                    "inline": True
                },
                {
                    "name": "Status",
                    "value": "⏳ Awaiting Officer Review",
                    "inline": False
                }
            ],
            "footer": {
                "text": f"Application ID: {application.id}"
            },
            "timestamp": application.submitted_at.isoformat()
        }
        
        # Add preview of guild experience if available
        if application.guild_experience:
            experience_preview = application.guild_experience[:200]
            if len(application.guild_experience) > 200:
                experience_preview += "..."
            
            embed["fields"].append({
                "name": "Guild Experience",
                "value": f"```{experience_preview}```",
                "inline": False
            })
        
        payload = {
            "embeds": [embed],
            "content": f"📋 **Officers**: New application requires review!"
        }
        
        return self._send_webhook(payload)
    
    def notify_voting_opened(self, application: Application, deadline: datetime) -> bool:
        """
        Send notification when voting period opens.
        
        Args:
            application: Application with voting opened
            deadline: Voting deadline
            
        Returns:
            bool: True if notification sent successfully
        """
        # Calculate relative deadline
        hours_remaining = (deadline - timezone.now()).total_seconds() / 3600
        deadline_str = deadline.strftime('%Y-%m-%d %H:%M:%S UTC')
        
        embed = {
            "title": "🗳️ Voting Period Opened",
            "description": f"Voting is now open for **{application.character_name}**",
            "color": self.colors['voting_open'],
            "fields": [
                {
                    "name": "Character",
                    "value": f"Level {application.character_level} {application.character_class}",
                    "inline": True
                },
                {
                    "name": "Applicant",
                    "value": application.applicant_name,
                    "inline": True
                },
                {
                    "name": "Voting Deadline",
                    "value": f"{deadline_str}\n({hours_remaining:.1f} hours remaining)",
                    "inline": False
                },
                {
                    "name": "Eligibility",
                    "value": "✅ Members with ≥15% attendance (30 days)",
                    "inline": False
                }
            ],
            "footer": {
                "text": f"Application ID: {application.id} • Vote weights: 15-50%=1.0x, 51-75%=1.5x, 76%+=2.0x"
            },
            "timestamp": timezone.now().isoformat()
        }
        
        payload = {
            "embeds": [embed],
            "content": f"🗳️ **@everyone**: Voting is now open! Eligible members please cast your votes."
        }
        
        return self._send_webhook(payload)
    
    def notify_voting_reminder(self, application: Application, hours_remaining: int) -> bool:
        """
        Send voting deadline reminder notification.
        
        Args:
            application: Application with upcoming deadline
            hours_remaining: Hours until voting deadline
            
        Returns:
            bool: True if notification sent successfully
        """
        deadline_str = application.voting_deadline.strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Get current vote count
        vote_count = application.votes.count()
        
        embed = {
            "title": f"⏰ Voting Reminder - {hours_remaining}h Remaining",
            "description": f"Voting deadline approaching for **{application.character_name}**",
            "color": self.colors['voting_reminder'],
            "fields": [
                {
                    "name": "Deadline",
                    "value": f"{deadline_str}\n**{hours_remaining} hours remaining**",
                    "inline": True
                },
                {
                    "name": "Current Votes",
                    "value": f"{vote_count} votes cast",
                    "inline": True
                },
                {
                    "name": "Action Required",
                    "value": "🗳️ Cast your vote if you haven't already!",
                    "inline": False
                }
            ],
            "footer": {
                "text": f"Application ID: {application.id}"
            },
            "timestamp": timezone.now().isoformat()
        }
        
        payload = {
            "embeds": [embed],
            "content": f"⏰ **Reminder**: {hours_remaining}h remaining to vote on {application.character_name}'s application!"
        }
        
        return self._send_webhook(payload)
    
    def notify_voting_closed(self, application: Application, vote_results: Dict, decision: Dict) -> bool:
        """
        Send notification when voting period closes with results.
        
        Args:
            application: Application with closed voting
            vote_results: Voting statistics 
            decision: Decision information
            
        Returns:
            bool: True if notification sent successfully
        """
        # Determine status and color
        final_status = decision['final_status']
        if final_status == 'approved':
            color = self.colors['approved']
            status_emoji = "✅"
            status_text = "APPROVED"
        else:
            color = self.colors['rejected']
            status_emoji = "❌"  
            status_text = "REJECTED"
        
        # Format vote statistics
        vote_counts = vote_results['vote_counts']
        approval_pct = vote_results['approval_percentage']
        
        embed = {
            "title": f"{status_emoji} Voting Closed - {status_text}",
            "description": f"**{application.character_name}** - {decision['reason']}",
            "color": color,
            "fields": [
                {
                    "name": "Vote Results",
                    "value": (
                        f"**Approval**: {approval_pct:.1f}%\n"
                        f"**Total Votes**: {vote_counts['total_votes']}\n"
                        f"**Vote Weight**: {vote_counts['total_weight']:.1f}"
                    ),
                    "inline": True
                },
                {
                    "name": "Vote Breakdown",
                    "value": (
                        f"✅ Yes: {vote_counts['yes_votes']} ({vote_counts['yes_weight']:.1f})\n"
                        f"❌ No: {vote_counts['no_votes']} ({vote_counts['no_weight']:.1f})\n"
                        f"⚪ Abstain: {vote_counts['abstain_votes']} ({vote_counts['abstain_weight']:.1f})"
                    ),
                    "inline": True
                },
                {
                    "name": "Requirements",
                    "value": (
                        f"Min Votes: {vote_counts['total_votes']}/3 {'✅' if vote_results['meets_minimum_votes'] else '❌'}\n"
                        f"Approval: {approval_pct:.1f}%/60% {'✅' if vote_results['meets_approval_threshold'] else '❌'}"
                    ),
                    "inline": False
                }
            ],
            "footer": {
                "text": f"Application ID: {application.id}"
            },
            "timestamp": timezone.now().isoformat()
        }
        
        content = f"🗳️ **Voting Results**: {application.character_name} - {status_text}"
        
        payload = {
            "embeds": [embed],
            "content": content
        }
        
        return self._send_webhook(payload)
    
    def notify_character_created(self, application: Application, workflow_results: Dict) -> bool:
        """
        Send notification when character is automatically created after approval.
        
        Args:
            application: Approved application
            workflow_results: Results from workflow processing
            
        Returns:
            bool: True if notification sent successfully
        """
        user_info = workflow_results['user']
        character_info = workflow_results['character']
        
        embed = {
            "title": "🎉 Welcome New Guild Member!",
            "description": f"**{character_info['name']}** has been added to the guild",
            "color": self.colors['character_created'],
            "fields": [
                {
                    "name": "Character",
                    "value": f"Level {character_info['level']} {character_info['class']}",
                    "inline": True
                },
                {
                    "name": "User Account",
                    "value": user_info['username'],
                    "inline": True
                },
                {
                    "name": "Setup Complete",
                    "value": (
                        f"✅ User Account Created\n"
                        f"✅ Character Record Added\n"
                        f"{'✅' if workflow_results['dkp_initialized'] else '❌'} DKP Initialized\n"
                        f"{'✅' if workflow_results['groups_assigned'] else '❌'} Groups Assigned"
                    ),
                    "inline": False
                }
            ],
            "footer": {
                "text": f"Application ID: {application.id} • Processed by: {workflow_results['processed_by']}"
            },
            "timestamp": workflow_results['processed_at'].isoformat()
        }
        
        payload = {
            "embeds": [embed],
            "content": f"🎊 **Welcome {character_info['name']}** to the guild! Please check your access and DKP points."
        }
        
        return self._send_webhook(payload)
    
    def notify_officer_review_needed(self, applications_count: int) -> bool:
        """
        Send notification when applications need officer review.
        
        Args:
            applications_count: Number of applications awaiting review
            
        Returns:
            bool: True if notification sent successfully
        """
        if applications_count == 0:
            return True  # No notification needed
        
        embed = {
            "title": "📋 Officer Review Required",
            "description": f"**{applications_count}** application(s) awaiting officer review",
            "color": self.colors['info'],
            "fields": [
                {
                    "name": "Action Required",
                    "value": "Please review pending applications and approve for voting",
                    "inline": False
                }
            ],
            "footer": {
                "text": "Use management commands or admin interface to review applications"
            },
            "timestamp": timezone.now().isoformat()
        }
        
        payload = {
            "embeds": [embed],
            "content": f"📋 **Officers**: {applications_count} application(s) need review!"
        }
        
        return self._send_webhook(payload)
    
    def notify_error(self, error_message: str, context: Dict = None) -> bool:
        """
        Send error notification for recruitment system issues.
        
        Args:
            error_message: Description of the error
            context: Additional context information
            
        Returns:
            bool: True if notification sent successfully
        """
        embed = {
            "title": "⚠️ Recruitment System Error",
            "description": error_message,
            "color": self.colors['error'],
            "timestamp": timezone.now().isoformat()
        }
        
        if context:
            embed["fields"] = []
            for key, value in context.items():
                embed["fields"].append({
                    "name": key.replace('_', ' ').title(),
                    "value": str(value),
                    "inline": True
                })
        
        payload = {
            "embeds": [embed],
            "content": "🚨 **System Alert**: Recruitment system error detected"
        }
        
        return self._send_webhook(payload)
    
    def send_daily_summary(self, summary_data: Dict) -> bool:
        """
        Send daily summary of recruitment activity.
        
        Args:
            summary_data: Dictionary containing daily activity summary
            
        Returns:
            bool: True if notification sent successfully
        """
        embed = {
            "title": "📊 Daily Recruitment Summary",
            "description": f"Recruitment activity for {timezone.now().strftime('%Y-%m-%d')}",
            "color": self.colors['info'],
            "fields": [
                {
                    "name": "New Applications",
                    "value": str(summary_data.get('new_applications', 0)),
                    "inline": True
                },
                {
                    "name": "Voting Periods Opened",
                    "value": str(summary_data.get('voting_opened', 0)),
                    "inline": True
                },
                {
                    "name": "Voting Periods Closed",
                    "value": str(summary_data.get('voting_closed', 0)),
                    "inline": True
                },
                {
                    "name": "Applications Approved",
                    "value": str(summary_data.get('approved', 0)),
                    "inline": True
                },
                {
                    "name": "Applications Rejected",
                    "value": str(summary_data.get('rejected', 0)),
                    "inline": True
                },
                {
                    "name": "Characters Created",
                    "value": str(summary_data.get('characters_created', 0)),
                    "inline": True
                }
            ],
            "footer": {
                "text": "Automated daily summary"
            },
            "timestamp": timezone.now().isoformat()
        }
        
        payload = {
            "embeds": [embed]
        }
        
        return self._send_webhook(payload)


# Convenience function to get the notification service instance
def get_discord_notification_service() -> DiscordNotificationService:
    """Get a DiscordNotificationService instance."""
    return DiscordNotificationService() 