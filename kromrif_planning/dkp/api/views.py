"""
DKP API views for REST API endpoints.
"""

from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from ..models import UserPointsSummary, PointAdjustment, DKPManager
from .serializers import (
    UserPointsSummarySerializer, PointAdjustmentSerializer, 
    PointAdjustmentCreateSerializer, BulkPointAwardSerializer,
    ItemPurchaseSerializer, UserBalanceSerializer, DKPLeaderboardSerializer,
    DKPStatsSerializer
)
from ...raiders.permissions import IsBotOrStaff, IsOfficerOrHigher, IsMemberOrHigher

User = get_user_model()


class UserPointsSummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing user DKP summaries.
    Provides read-only access to current DKP balances.
    """
    queryset = UserPointsSummary.objects.select_related('user').order_by('-total_points')
    serializer_class = UserPointsSummarySerializer
    permission_classes = [IsMemberOrHigher]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__username', 'user__email']
    ordering_fields = ['total_points', 'earned_points', 'spent_points', 'last_updated']
    ordering = ['-total_points']
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """Get DKP leaderboard with rankings."""
        limit = min(int(request.query_params.get('limit', 50)), 100)
        summaries = self.get_queryset()[:limit]
        
        leaderboard_data = []
        for rank, summary in enumerate(summaries, 1):
            data = {
                'rank': rank,
                'user_id': summary.user.id,
                'username': summary.user.username,
                'total_points': summary.total_points,
                'earned_points': summary.earned_points,
                'spent_points': summary.spent_points,
            }
            leaderboard_data.append(data)
        
        serializer = DKPLeaderboardSerializer(leaderboard_data, many=True)
        return Response({
            'leaderboard': serializer.data,
            'total_entries': len(leaderboard_data)
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get overall DKP system statistics."""
        summaries = UserPointsSummary.objects.all()
        
        stats = summaries.aggregate(
            total_users=Count('id'),
            total_points=Sum('total_points'),
            avg_points=Avg('total_points')
        )
        
        # Get recent activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_adjustments = PointAdjustment.objects.filter(
            created_at__gte=thirty_days_ago
        ).count()
        
        # Get top earner and spender
        top_earner = summaries.order_by('-earned_points').first()
        top_spender = summaries.order_by('-spent_points').first()
        
        stats_data = {
            'total_users': stats['total_users'] or 0,
            'total_points_in_system': stats['total_points'] or Decimal('0.00'),
            'average_points_per_user': stats['avg_points'] or Decimal('0.00'),
            'recent_adjustments_count': recent_adjustments,
            'top_earner': top_earner.user.username if top_earner else 'N/A',
            'top_spender': top_spender.user.username if top_spender else 'N/A',
        }
        
        serializer = DKPStatsSerializer(stats_data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """Get current balance for a specific user."""
        summary = self.get_object()
        check_amount = request.query_params.get('check_amount')
        
        balance_data = {
            'user_id': summary.user.id,
            'username': summary.user.username,
            'current_balance': summary.total_points
        }
        
        kwargs = {}
        if check_amount:
            try:
                kwargs['check_amount'] = Decimal(check_amount)
            except (ValueError, TypeError):
                return Response(
                    {'error': 'Invalid check_amount value'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = UserBalanceSerializer(balance_data, **kwargs)
        return Response(serializer.data)


class PointAdjustmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing DKP point adjustments.
    Provides CRUD operations with proper permissions.
    """
    queryset = PointAdjustment.objects.select_related('user', 'created_by').order_by('-created_at')
    permission_classes = [IsBotOrStaff]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__username', 'description', 'character_name']
    ordering_fields = ['created_at', 'points', 'adjustment_type']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PointAdjustmentCreateSerializer
        return PointAdjustmentSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by user if specified
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by adjustment type
        adjustment_type = self.request.query_params.get('adjustment_type')
        if adjustment_type:
            queryset = queryset.filter(adjustment_type=adjustment_type)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset
    
    def has_change_permission(self, obj=None):
        """Check if user can modify this adjustment."""
        if obj and obj.is_locked:
            return self.request.user.has_perm('dkp.can_modify_locked')
        return True
    
    def update(self, request, *args, **kwargs):
        """Override update to check locked status."""
        instance = self.get_object()
        if not self.has_change_permission(instance):
            return Response(
                {'error': 'This adjustment is locked and cannot be modified'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to check locked status."""
        instance = self.get_object()
        if not self.has_change_permission(instance):
            return Response(
                {'error': 'This adjustment is locked and cannot be deleted'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=False, methods=['post'])
    def bulk_award(self, request):
        """Bulk award points to multiple users."""
        serializer = BulkPointAwardSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            adjustments = serializer.save()
            response_data = PointAdjustmentSerializer(adjustments, many=True).data
            return Response({
                'message': f'Successfully awarded points to {len(adjustments)} users',
                'adjustments': response_data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def process_purchase(self, request):
        """Process an item purchase with DKP deduction."""
        serializer = ItemPurchaseSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            adjustment = serializer.save()
            response_data = PointAdjustmentSerializer(adjustment).data
            return Response({
                'message': 'Item purchase processed successfully',
                'adjustment': response_data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def user_history(self, request):
        """Get adjustment history for a specific user."""
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        limit = min(int(request.query_params.get('limit', 50)), 100)
        adjustments = DKPManager.get_user_adjustment_history(user, limit)
        
        serializer = PointAdjustmentSerializer(adjustments, many=True)
        return Response({
            'user': user.username,
            'current_balance': DKPManager.get_user_balance(user),
            'history': serializer.data
        })


class DKPManagementViewSet(viewsets.ViewSet):
    """
    ViewSet for DKP management operations.
    Provides administrative and utility endpoints.
    """
    permission_classes = [IsOfficerOrHigher]
    
    @action(detail=False, methods=['post'])
    def recalculate_summaries(self, request):
        """Recalculate all user point summaries."""
        try:
            DKPManager.recalculate_all_summaries()
            return Response({
                'message': 'Successfully recalculated all user point summaries'
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to recalculate summaries: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def check_balance(self, request):
        """Check if a user can afford a specific amount."""
        user_id = request.query_params.get('user_id')
        amount = request.query_params.get('amount')
        
        if not user_id or not amount:
            return Response(
                {'error': 'user_id and amount parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
            check_amount = Decimal(amount)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid amount value'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        current_balance = DKPManager.get_user_balance(user)
        can_afford = DKPManager.can_afford(user, check_amount)
        
        return Response({
            'user_id': user.id,
            'username': user.username,
            'current_balance': current_balance,
            'check_amount': check_amount,
            'can_afford': can_afford,
            'shortfall': max(check_amount - current_balance, Decimal('0.00'))
        })
    
    @action(detail=False, methods=['get'])
    def top_users(self, request):
        """Get top DKP users."""
        limit = min(int(request.query_params.get('limit', 10)), 50)
        top_users = DKPManager.get_top_dkp_users(limit)
        
        serializer = UserPointsSummarySerializer(top_users, many=True)
        return Response({
            'top_users': serializer.data,
            'total_shown': len(serializer.data)
        })
    
    @action(detail=False, methods=['post'])
    def award_raid_attendance(self, request):
        """Award raid attendance points to multiple users."""
        user_ids = request.data.get('user_ids', [])
        points = request.data.get('points')
        raid_name = request.data.get('raid_name', 'Unknown Raid')
        
        if not user_ids or not points:
            return Response(
                {'error': 'user_ids and points are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            points = Decimal(str(points))
            if points <= 0:
                raise ValueError("Points must be positive")
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid points value'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        users = User.objects.filter(id__in=user_ids)
        if len(users) != len(user_ids):
            found_ids = set(users.values_list('id', flat=True))
            missing_ids = set(user_ids) - found_ids
            return Response(
                {'error': f'Users not found: {list(missing_ids)}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            adjustments = DKPManager.bulk_award_raid_attendance(
                users=users,
                points_per_user=points,
                raid_name=raid_name,
                created_by=request.user
            )
            
            serializer = PointAdjustmentSerializer(adjustments, many=True)
            return Response({
                'message': f'Successfully awarded {points} DKP to {len(users)} users for {raid_name}',
                'adjustments': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to award points: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )