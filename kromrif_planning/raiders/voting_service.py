"""
Voting Period Management Service for Recruitment Applications.

Handles automated voting period operations including:
- Opening and closing voting periods
- Deadline enforcement and notifications
- Vote tallying and decision making
- Status transitions and workflow management
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Sum, Q, Avg
from django.contrib.auth import get_user_model

from .models import Application, ApplicationVote, MemberAttendanceSummary

User = get_user_model()
logger = logging.getLogger(__name__)


class VotingPeriodManager:
    """
    Service class for managing voting periods and automated operations.
    Handles the complete voting lifecycle from opening to closure.
    """
    
    # Configuration constants
    DEFAULT_VOTING_DURATION_HOURS = 48
    APPROVAL_THRESHOLD_PERCENTAGE = 60  # Minimum approval percentage for acceptance
    MINIMUM_VOTES_REQUIRED = 3  # Minimum number of votes to make a decision
    NOTIFICATION_HOURS_BEFORE_DEADLINE = [24, 6, 1]  # Hours before deadline to send notifications
    
    def __init__(self):
        """Initialize the voting period manager with default settings."""
        self.voting_duration_hours = getattr(
            settings, 
            'RECRUITMENT_VOTING_DURATION_HOURS', 
            self.DEFAULT_VOTING_DURATION_HOURS
        )
        self.approval_threshold = getattr(
            settings, 
            'RECRUITMENT_APPROVAL_THRESHOLD', 
            self.APPROVAL_THRESHOLD_PERCENTAGE
        )
        self.minimum_votes = getattr(
            settings, 
            'RECRUITMENT_MINIMUM_VOTES', 
            self.MINIMUM_VOTES_REQUIRED
        )
    
    def open_voting_period(self, application: Application, opened_by: User = None) -> bool:
        """
        Open voting period for an application.
        
        Args:
            application: Application instance to open voting for
            opened_by: User who opened the voting (optional)
            
        Returns:
            bool: True if successfully opened, False otherwise
        """
        try:
            with transaction.atomic():
                # Validate application can have voting opened
                if application.status != 'officer_approved':
                    logger.warning(f"Cannot open voting for application {application.id} - invalid status: {application.status}")
                    return False
                
                # Set voting period
                now = timezone.now()
                deadline = now + timedelta(hours=self.voting_duration_hours)
                
                # Update application status
                application.status = 'voting_open'
                application.voting_opened_at = now
                application.voting_deadline = deadline
                
                if opened_by:
                    application.reviewed_by = opened_by
                
                application.save()
                
                logger.info(f"Opened voting period for application {application.id} (deadline: {deadline})")
                
                # Send notifications about voting opening (would integrate with Discord webhook)
                self._notify_voting_opened(application)
                
                return True
                
        except Exception as e:
            logger.error(f"Error opening voting period for application {application.id}: {str(e)}")
            return False
    
    def close_voting_period(self, application: Application, closed_by: User = None) -> Dict:
        """
        Close voting period and tally results.
        
        Args:
            application: Application instance to close voting for
            closed_by: User who closed the voting (optional)
            
        Returns:
            Dict: Results of vote tallying and decision
        """
        try:
            with transaction.atomic():
                # Validate application is in voting state
                if application.status != 'voting_open':
                    logger.warning(f"Cannot close voting for application {application.id} - invalid status: {application.status}")
                    return {'success': False, 'error': 'Invalid application status'}
                
                # Tally votes
                vote_results = self._tally_votes(application)
                
                # Make decision
                decision_result = self._make_voting_decision(application, vote_results)
                
                # Update application status
                application.status = 'voting_closed' if not decision_result['final_decision'] else decision_result['final_status']
                application.decision_made_at = timezone.now()
                
                if closed_by:
                    application.decision_made_by = closed_by
                
                application.save()
                
                # Combine results
                results = {
                    'success': True,
                    'application_id': application.id,
                    'vote_summary': vote_results,
                    'decision': decision_result,
                    'closed_at': timezone.now(),
                    'closed_by': closed_by.username if closed_by else 'System'
                }
                
                logger.info(f"Closed voting period for application {application.id} - Decision: {decision_result['final_status']}")
                
                # Send notifications about voting closure
                self._notify_voting_closed(application, results)
                
                return results
                
        except Exception as e:
            logger.error(f"Error closing voting period for application {application.id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def process_expired_voting_periods(self) -> Dict:
        """
        Process all voting periods that have expired.
        Called by management command or scheduled task.
        
        Returns:
            Dict: Summary of processed applications
        """
        now = timezone.now()
        
        # Find expired voting periods
        expired_applications = Application.objects.filter(
            status='voting_open',
            voting_deadline__lt=now
        )
        
        processed_count = 0
        results = []
        
        for application in expired_applications:
            logger.info(f"Processing expired voting period for application {application.id}")
            result = self.close_voting_period(application)
            
            if result.get('success'):
                processed_count += 1
                results.append({
                    'application_id': application.id,
                    'character_name': application.character_name,
                    'decision': result['decision']['final_status']
                })
            else:
                logger.error(f"Failed to process expired application {application.id}: {result.get('error')}")
        
        summary = {
            'processed_count': processed_count,
            'total_expired': expired_applications.count(),
            'processed_applications': results,
            'processed_at': now
        }
        
        logger.info(f"Processed {processed_count} expired voting periods")
        return summary
    
    def send_deadline_notifications(self) -> Dict:
        """
        Send notifications for upcoming voting deadlines.
        
        Returns:
            Dict: Summary of notifications sent
        """
        now = timezone.now()
        notifications_sent = 0
        
        for hours_before in self.NOTIFICATION_HOURS_BEFORE_DEADLINE:
            # Calculate deadline range for this notification window
            notification_time = now + timedelta(hours=hours_before)
            window_start = notification_time - timedelta(minutes=30)  # 30-minute window
            window_end = notification_time + timedelta(minutes=30)
            
            # Find applications with deadlines in this window
            applications = Application.objects.filter(
                status='voting_open',
                voting_deadline__gte=window_start,
                voting_deadline__lte=window_end
            )
            
            for application in applications:
                try:
                    self._notify_voting_deadline_reminder(application, hours_before)
                    notifications_sent += 1
                    logger.info(f"Sent {hours_before}h deadline reminder for application {application.id}")
                except Exception as e:
                    logger.error(f"Failed to send deadline reminder for application {application.id}: {str(e)}")
        
        return {
            'notifications_sent': notifications_sent,
            'processed_at': now
        }
    
    def get_voting_statistics(self, application: Application) -> Dict:
        """
        Get detailed voting statistics for an application.
        
        Args:
            application: Application instance to get statistics for
            
        Returns:
            Dict: Comprehensive voting statistics
        """
        votes = ApplicationVote.objects.filter(application=application)
        
        # Basic vote counts
        vote_counts = votes.aggregate(
            total_votes=Count('id'),
            yes_votes=Count('id', filter=Q(vote='yes')),
            no_votes=Count('id', filter=Q(vote='no')),
            abstain_votes=Count('id', filter=Q(vote='abstain')),
            total_weight=Sum('vote_weight'),
            yes_weight=Sum('vote_weight', filter=Q(vote='yes')),
            no_weight=Sum('vote_weight', filter=Q(vote='no')),
            abstain_weight=Sum('vote_weight', filter=Q(vote='abstain')),
            avg_attendance=Avg('attendance_rate_30d')
        )
        
        # Calculate percentages
        total_weight = vote_counts['total_weight'] or Decimal('0')
        yes_weight = vote_counts['yes_weight'] or Decimal('0')
        no_weight = vote_counts['no_weight'] or Decimal('0')
        
        if total_weight > 0:
            approval_percentage = (yes_weight / total_weight) * 100
            rejection_percentage = (no_weight / total_weight) * 100
        else:
            approval_percentage = Decimal('0')
            rejection_percentage = Decimal('0')
        
        # Eligible voters count
        eligible_voters = MemberAttendanceSummary.objects.filter(
            is_voting_eligible=True
        ).count()
        
        # Participation rate
        participation_rate = (vote_counts['total_votes'] / eligible_voters * 100) if eligible_voters > 0 else 0
        
        return {
            'vote_counts': vote_counts,
            'approval_percentage': float(approval_percentage),
            'rejection_percentage': float(rejection_percentage),
            'eligible_voters': eligible_voters,
            'participation_rate': float(participation_rate),
            'meets_minimum_votes': vote_counts['total_votes'] >= self.minimum_votes,
            'meets_approval_threshold': approval_percentage >= self.approval_threshold,
            'time_remaining': application.voting_time_remaining,
            'is_active': application.is_voting_active
        }
    
    def _tally_votes(self, application: Application) -> Dict:
        """Tally votes for an application with detailed breakdown."""
        return self.get_voting_statistics(application)
    
    def _make_voting_decision(self, application: Application, vote_results: Dict) -> Dict:
        """
        Make final decision based on vote results.
        
        Args:
            application: Application instance
            vote_results: Results from vote tallying
            
        Returns:
            Dict: Decision information
        """
        # Check if minimum vote threshold is met
        meets_minimum = vote_results['meets_minimum_votes']
        meets_threshold = vote_results['meets_approval_threshold']
        approval_percentage = vote_results['approval_percentage']
        total_votes = vote_results['vote_counts']['total_votes']
        
        # Decision logic
        if not meets_minimum:
            decision = 'insufficient_votes'
            final_status = 'rejected'
            reason = f"Insufficient votes ({total_votes} received, {self.minimum_votes} required)"
        elif meets_threshold:
            decision = 'approved'
            final_status = 'approved'
            reason = f"Approved with {approval_percentage:.1f}% approval (≥{self.approval_threshold}% required)"
        else:
            decision = 'rejected'
            final_status = 'rejected'
            reason = f"Rejected with {approval_percentage:.1f}% approval (<{self.approval_threshold}% required)"
        
        return {
            'final_decision': decision,
            'final_status': final_status,
            'reason': reason,
            'approval_percentage': approval_percentage,
            'total_votes': total_votes,
            'meets_minimum_votes': meets_minimum,
            'meets_approval_threshold': meets_threshold
        }
    
    def _notify_voting_opened(self, application: Application):
        """Send notification when voting period opens."""
        # This would integrate with Discord webhook system
        # For now, just log the notification
        logger.info(f"NOTIFICATION: Voting opened for {application.character_name} - Deadline: {application.voting_deadline}")
    
    def _notify_voting_closed(self, application: Application, results: Dict):
        """Send notification when voting period closes."""
        decision = results['decision']
        logger.info(f"NOTIFICATION: Voting closed for {application.character_name} - Decision: {decision['final_status']} ({decision['reason']})")
    
    def _notify_voting_deadline_reminder(self, application: Application, hours_remaining: int):
        """Send deadline reminder notification."""
        logger.info(f"NOTIFICATION: {hours_remaining}h remaining for {application.character_name} voting deadline")
    
    @classmethod
    def get_active_voting_applications(cls) -> List[Application]:
        """Get all applications currently in voting period."""
        return list(Application.objects.filter(
            status='voting_open',
            voting_deadline__gt=timezone.now()
        ).order_by('voting_deadline'))
    
    @classmethod
    def get_applications_needing_review(cls) -> List[Application]:
        """Get applications that need officer review before voting."""
        return list(Application.objects.filter(
            status='submitted'
        ).order_by('submitted_at'))
    
    @classmethod
    def get_officer_approved_applications(cls) -> List[Application]:
        """Get applications approved by officers and ready for voting."""
        return list(Application.objects.filter(
            status='officer_approved'
        ).order_by('reviewed_at'))


# Convenience function to get the voting manager instance
def get_voting_manager() -> VotingPeriodManager:
    """Get a VotingPeriodManager instance."""
    return VotingPeriodManager() 