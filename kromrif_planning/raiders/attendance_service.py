"""
Attendance calculation service for managing rolling averages and member statistics.
This module provides utilities for calculating attendance rates over various time periods.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import Raid, RaidAttendance, MemberAttendanceSummary

User = get_user_model()


class AttendanceCalculationService:
    """
    Service class for calculating attendance statistics and rolling averages.
    """
    
    def __init__(self, base_date: Optional[datetime] = None):
        """
        Initialize the attendance service.
        
        Args:
            base_date: Base date for calculations (defaults to today)
        """
        self.base_date = base_date or timezone.now().date()
    
    def calculate_period_attendance(
        self, 
        user: User, 
        period_days: int, 
        end_date: Optional[datetime] = None
    ) -> Tuple[int, int, Decimal]:
        """
        Calculate attendance for a specific period.
        
        Args:
            user: User to calculate attendance for
            period_days: Number of days to look back
            end_date: End date for the period (defaults to base_date)
            
        Returns:
            Tuple of (attended_raids, total_raids, attendance_rate)
        """
        if end_date is None:
            end_date = self.base_date
        
        start_date = end_date - timedelta(days=period_days)
        
        # Get all raids in the period
        total_raids = Raid.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
            status='completed'  # Only count completed raids
        ).count()
        
        # Get raids the user attended
        attended_raids = RaidAttendance.objects.filter(
            user=user,
            raid__date__gte=start_date,
            raid__date__lte=end_date,
            raid__status='completed'
        ).count()
        
        # Calculate attendance rate
        if total_raids == 0:
            attendance_rate = Decimal('0.00')
        else:
            attendance_rate = (Decimal(attended_raids) / Decimal(total_raids)) * 100
        
        return attended_raids, total_raids, attendance_rate
    
    def calculate_lifetime_attendance(self, user: User) -> Tuple[int, int, Decimal]:
        """
        Calculate lifetime attendance for a user.
        
        Args:
            user: User to calculate lifetime attendance for
            
        Returns:
            Tuple of (attended_raids, total_raids, attendance_rate)
        """
        # Get user's first raid attendance to determine when they started
        first_attendance = RaidAttendance.objects.filter(user=user).order_by('created_at').first()
        
        if not first_attendance:
            return 0, 0, Decimal('0.00')
        
        start_date = first_attendance.created_at.date()
        
        # Get all raids since user started
        total_raids = Raid.objects.filter(
            date__gte=start_date,
            date__lte=self.base_date,
            status='completed'
        ).count()
        
        # Get all raids user attended
        attended_raids = RaidAttendance.objects.filter(
            user=user,
            raid__date__gte=start_date,
            raid__date__lte=self.base_date,
            raid__status='completed'
        ).count()
        
        # Calculate attendance rate
        if total_raids == 0:
            attendance_rate = Decimal('0.00')
        else:
            attendance_rate = (Decimal(attended_raids) / Decimal(total_raids)) * 100
        
        return attended_raids, total_raids, attendance_rate
    
    def calculate_attendance_streak(self, user: User) -> Tuple[int, int]:
        """
        Calculate current and longest attendance streaks for a user.
        
        Args:
            user: User to calculate streaks for
            
        Returns:
            Tuple of (current_streak, longest_streak)
        """
        # Get all completed raids ordered by date (most recent first)
        raids = Raid.objects.filter(
            date__lte=self.base_date,
            status='completed'
        ).order_by('-date')
        
        # Get user's attendance for these raids
        user_attendance = set(
            RaidAttendance.objects.filter(
                user=user,
                raid__in=raids
            ).values_list('raid_id', flat=True)
        )
        
        current_streak = 0
        longest_streak = 0
        temp_streak = 0
        
        # Calculate streaks
        for raid in raids:
            if raid.id in user_attendance:
                temp_streak += 1
                if current_streak == temp_streak:  # Still in current streak
                    current_streak = temp_streak
                longest_streak = max(longest_streak, temp_streak)
            else:
                if current_streak == temp_streak:  # Current streak broken
                    current_streak = 0
                temp_streak = 0
        
        return current_streak, longest_streak
    
    def is_voting_eligible(self, user: User, minimum_rate: Decimal = Decimal('15.00')) -> bool:
        """
        Check if a user is eligible to vote based on 30-day attendance.
        
        Args:
            user: User to check eligibility for
            minimum_rate: Minimum attendance rate required (default 15%)
            
        Returns:
            True if user is eligible to vote
        """
        _, _, attendance_rate = self.calculate_period_attendance(user, 30)
        return attendance_rate >= minimum_rate
    
    def calculate_all_periods(self, user: User) -> Dict[str, Tuple[int, int, Decimal]]:
        """
        Calculate attendance for all standard periods.
        
        Args:
            user: User to calculate attendance for
            
        Returns:
            Dictionary with period names as keys and (attended, total, rate) tuples as values
        """
        periods = {
            '7d': 7,
            '30d': 30,
            '60d': 60,
            '90d': 90
        }
        
        results = {}
        
        for period_name, days in periods.items():
            results[period_name] = self.calculate_period_attendance(user, days)
        
        # Add lifetime calculation
        results['lifetime'] = self.calculate_lifetime_attendance(user)
        
        return results
    
    def update_user_summary(self, user: User, summary_date: Optional[datetime] = None) -> MemberAttendanceSummary:
        """
        Update or create attendance summary for a user.
        
        Args:
            user: User to update summary for
            summary_date: Date for the summary (defaults to base_date)
            
        Returns:
            Updated MemberAttendanceSummary instance
        """
        if summary_date is None:
            summary_date = self.base_date
        
        # Calculate all periods
        periods = self.calculate_all_periods(user)
        
        # Calculate streaks
        current_streak, longest_streak = self.calculate_attendance_streak(user)
        
        # Get or create summary
        summary, created = MemberAttendanceSummary.objects.get_or_create(
            user=user,
            summary_date=summary_date,
            defaults={}
        )
        
        # Update 7-day period
        summary.attended_raids_7d = periods['7d'][0]
        summary.total_raids_7d = periods['7d'][1]
        summary.attendance_rate_7d = periods['7d'][2]
        
        # Update 30-day period
        summary.attended_raids_30d = periods['30d'][0]
        summary.total_raids_30d = periods['30d'][1]
        summary.attendance_rate_30d = periods['30d'][2]
        
        # Update 60-day period
        summary.attended_raids_60d = periods['60d'][0]
        summary.total_raids_60d = periods['60d'][1]
        summary.attendance_rate_60d = periods['60d'][2]
        
        # Update 90-day period
        summary.attended_raids_90d = periods['90d'][0]
        summary.total_raids_90d = periods['90d'][1]
        summary.attendance_rate_90d = periods['90d'][2]
        
        # Update lifetime period
        summary.attended_raids_lifetime = periods['lifetime'][0]
        summary.total_raids_lifetime = periods['lifetime'][1]
        summary.attendance_rate_lifetime = periods['lifetime'][2]
        
        # Update voting eligibility
        summary.is_voting_eligible = self.is_voting_eligible(user)
        
        # Update streaks
        summary.current_attendance_streak = current_streak
        summary.longest_attendance_streak = longest_streak
        
        summary.save()
        
        return summary
    
    def bulk_update_summaries(
        self, 
        users: Optional[List[User]] = None, 
        summary_date: Optional[datetime] = None
    ) -> int:
        """
        Update attendance summaries for multiple users.
        
        Args:
            users: List of users to update (defaults to all users)
            summary_date: Date for summaries (defaults to base_date)
            
        Returns:
            Number of summaries updated
        """
        if users is None:
            # Get all users who have raid attendance
            users = User.objects.filter(
                raid_attendance__isnull=False
            ).distinct()
        
        if summary_date is None:
            summary_date = self.base_date
        
        updated_count = 0
        
        for user in users:
            self.update_user_summary(user, summary_date)
            updated_count += 1
        
        return updated_count
    
    def get_attendance_trends(self, user: User, periods: int = 7) -> List[Dict]:
        """
        Get attendance trends over the last N periods.
        
        Args:
            user: User to get trends for
            periods: Number of periods to look back
            
        Returns:
            List of dictionaries with date and attendance rate
        """
        trends = []
        
        for i in range(periods):
            date = self.base_date - timedelta(days=i)
            service = AttendanceCalculationService(date)
            _, _, rate = service.calculate_period_attendance(user, 30, date)
            
            trends.append({
                'date': date,
                'attendance_rate': rate
            })
        
        return list(reversed(trends))  # Return chronologically
    
    def get_guild_attendance_stats(self) -> Dict:
        """
        Get overall guild attendance statistics.
        
        Returns:
            Dictionary with guild-wide attendance stats
        """
        # Get all users with attendance
        users_with_attendance = User.objects.filter(
            raid_attendance__isnull=False
        ).distinct()
        
        if not users_with_attendance.exists():
            return {
                'total_members': 0,
                'voting_eligible_members': 0,
                'average_30d_attendance': Decimal('0.00'),
                'average_90d_attendance': Decimal('0.00'),
                'highest_attendance_30d': Decimal('0.00'),
                'lowest_attendance_30d': Decimal('0.00'),
            }
        
        # Calculate stats for all users
        total_30d_rate = Decimal('0.00')
        total_90d_rate = Decimal('0.00')
        voting_eligible_count = 0
        rates_30d = []
        
        for user in users_with_attendance:
            _, _, rate_30d = self.calculate_period_attendance(user, 30)
            _, _, rate_90d = self.calculate_period_attendance(user, 90)
            
            total_30d_rate += rate_30d
            total_90d_rate += rate_90d
            rates_30d.append(rate_30d)
            
            if self.is_voting_eligible(user):
                voting_eligible_count += 1
        
        member_count = users_with_attendance.count()
        
        return {
            'total_members': member_count,
            'voting_eligible_members': voting_eligible_count,
            'voting_eligible_percentage': (Decimal(voting_eligible_count) / Decimal(member_count)) * 100 if member_count > 0 else Decimal('0.00'),
            'average_30d_attendance': total_30d_rate / member_count if member_count > 0 else Decimal('0.00'),
            'average_90d_attendance': total_90d_rate / member_count if member_count > 0 else Decimal('0.00'),
            'highest_attendance_30d': max(rates_30d) if rates_30d else Decimal('0.00'),
            'lowest_attendance_30d': min(rates_30d) if rates_30d else Decimal('0.00'),
        }


def get_attendance_service(base_date: Optional[datetime] = None) -> AttendanceCalculationService:
    """
    Factory function to get an attendance calculation service.
    
    Args:
        base_date: Base date for calculations
        
    Returns:
        AttendanceCalculationService instance
    """
    return AttendanceCalculationService(base_date)