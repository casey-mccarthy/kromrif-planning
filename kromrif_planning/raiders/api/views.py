from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from django.http import HttpResponse
import csv
from ..models import Character, Rank, CharacterOwnership, Event, Raid, RaidAttendance, Item, LootDistribution, LootAuditLog
from .serializers import (
    CharacterListSerializer,
    CharacterDetailSerializer,
    RankSerializer,
    CharacterOwnershipSerializer,
    CharacterTransferSerializer,
    EventSerializer,
    RaidListSerializer,
    RaidDetailSerializer,
    RaidAttendanceSerializer,
    BulkAttendanceSerializer,
    AwardPointsSerializer,
    ItemSerializer,
    LootDistributionListSerializer,
    LootDistributionDetailSerializer,
    DiscordLootAwardSerializer,
    UserBalanceSerializer,
    LootAuditLogSerializer,
    LootAuditLogListSerializer,
    AuditLogFilterSerializer
)


class RankViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing guild ranks.
    Only staff users can create/update/delete ranks.
    """
    queryset = Rank.objects.all()
    serializer_class = RankSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['level', 'name', 'created_at']
    ordering = ['level']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return super().get_permissions()


class CharacterViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing characters.
    Users can only edit their own characters unless they are staff.
    """
    queryset = Character.objects.select_related('user')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'user__username']
    ordering_fields = ['name', 'level', 'created_at', 'updated_at']
    ordering = ['name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CharacterListSerializer
        return CharacterDetailSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by user if specified
        if self.action == 'list':
            user_id = self.request.query_params.get('user', None)
            if user_id == 'me':
                queryset = queryset.filter(user=self.request.user)
            elif user_id:
                queryset = queryset.filter(user_id=user_id)
        
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    def perform_update(self, serializer):
        # Check if user is changing
        if 'user' in serializer.validated_data:
            old_user = serializer.instance.user
            new_user = serializer.validated_data['user']
            if old_user != new_user and not self.request.user.is_staff:
                raise permissions.PermissionDenied("Only staff can transfer characters.")
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def my_characters(self, request):
        """Get all characters belonging to the current user."""
        characters = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(characters, many=True)
        return Response(serializer.data)
    
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def transfer(self, request):
        """Transfer a character to another user (admin only)."""
        serializer = CharacterTransferSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        ownership_record = serializer.save()
        return Response(
            CharacterOwnershipSerializer(ownership_record).data,
            status=status.HTTP_201_CREATED
        )


class CharacterOwnershipViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing character ownership history.
    Read-only access for all authenticated users.
    """
    queryset = CharacterOwnership.objects.select_related(
        'character', 'previous_owner', 'new_owner', 'transferred_by'
    )
    serializer_class = CharacterOwnershipSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['transfer_date']
    ordering = ['-transfer_date']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by character if specified
        character_id = self.request.query_params.get('character', None)
        if character_id:
            queryset = queryset.filter(character_id=character_id)
        
        # Filter by user (as either previous or new owner)
        user_id = self.request.query_params.get('user', None)
        if user_id == 'me':
            user_id = self.request.user.id
        if user_id:
            queryset = queryset.filter(
                Q(previous_owner_id=user_id) |
                Q(new_owner_id=user_id)
            )
        
        return queryset


class EventViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing raid events.
    Staff users can create/update/delete events.
    """
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'base_points', 'created_at']
    ordering = ['name']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return super().get_permissions()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by active status if specified
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset


class RaidViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing raids.
    Leaders can manage their own raids, admins can manage all raids.
    """
    queryset = Raid.objects.select_related('event', 'leader')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'notes', 'leader__username']
    ordering_fields = ['date', 'start_time', 'created_at']
    ordering = ['-date', '-start_time']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RaidListSerializer
        return RaidDetailSerializer
    
    def get_permissions(self):
        if self.action in ['create']:
            return [permissions.IsAdminUser()]
        return super().get_permissions()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by event if specified
        event_id = self.request.query_params.get('event', None)
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        
        # Filter by status if specified
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        # Filter by leader for non-admin users
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(leader=self.request.user) | Q(status__in=['scheduled', 'completed'])
            )
        
        return queryset
    
    def perform_create(self, serializer):
        # Set creator as leader if no leader specified
        if not serializer.validated_data.get('leader'):
            serializer.save(leader=self.request.user)
        else:
            serializer.save()
    
    @action(detail=True, methods=['get'])
    def attendance(self, request, pk=None):
        """Get attendance records for this raid."""
        raid = self.get_object()
        attendance_records = raid.attendance_records.select_related('user', 'recorded_by')
        serializer = RaidAttendanceSerializer(attendance_records, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def bulk_attendance(self, request, pk=None):
        """Add bulk attendance from character name list."""
        raid = self.get_object()
        serializer = BulkAttendanceSerializer(
            data=request.data,
            context={'raid': raid, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        results = serializer.save()
        
        return Response({
            'created': len(results['created']),
            'warnings': results['warnings'],
            'errors': results['errors'],
            'attendance_records': RaidAttendanceSerializer(
                results['created'], many=True
            ).data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def award_points(self, request, pk=None):
        """Award DKP points to all raid attendees."""
        raid = self.get_object()
        serializer = AwardPointsSerializer(
            data=request.data,
            context={'raid': raid, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        
        return Response({
            'message': f'Successfully awarded points for {raid.title}',
            'adjustments_created': result['adjustments_created'],
            'total_points_awarded': result['total_points_awarded']
        }, status=status.HTTP_201_CREATED)


class RaidAttendanceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing raid attendance records.
    """
    queryset = RaidAttendance.objects.select_related('user', 'raid', 'raid__event', 'recorded_by')
    serializer_class = RaidAttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'raid__date']
    ordering = ['-created_at']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return super().get_permissions()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by raid if specified
        raid_id = self.request.query_params.get('raid', None)
        if raid_id:
            queryset = queryset.filter(raid_id=raid_id)
        
        # Filter by user if specified
        user_id = self.request.query_params.get('user', None)
        if user_id == 'me':
            user_id = self.request.user.id
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by character name if specified
        character_name = self.request.query_params.get('character', None)
        if character_name:
            queryset = queryset.filter(character_name__icontains=character_name)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


class ItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing items.
    Staff users can create/update/delete items.
    """
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'suggested_cost', 'rarity', 'created_at']
    ordering = ['name']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return super().get_permissions()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by active status if specified
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by rarity if specified
        rarity = self.request.query_params.get('rarity', None)
        if rarity:
            queryset = queryset.filter(rarity=rarity)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def by_rarity(self, request):
        """Get items grouped by rarity."""
        from django.db.models import Count
        
        rarities = Item.objects.values('rarity').annotate(
            count=Count('id')
        ).order_by('rarity')
        
        result = {}
        for rarity_data in rarities:
            rarity = rarity_data['rarity']
            items = self.get_queryset().filter(rarity=rarity)
            serializer = self.get_serializer(items, many=True)
            result[rarity] = {
                'count': rarity_data['count'],
                'items': serializer.data
            }
        
        return Response(result)


class LootDistributionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing loot distributions.
    Staff users can create/update/delete distributions.
    """
    queryset = LootDistribution.objects.select_related(
        'user', 'item', 'raid', 'distributed_by'
    )
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['character_name', 'user__username', 'item__name', 'notes']
    ordering_fields = ['distributed_at', 'point_cost', 'character_name']
    ordering = ['-distributed_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return LootDistributionListSerializer
        elif self.action == 'discord_award':
            return DiscordLootAwardSerializer
        elif self.action == 'user_balance':
            return UserBalanceSerializer
        return LootDistributionDetailSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        elif self.action in ['discord_award']:
            return [permissions.IsAdminUser()]
        return super().get_permissions()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by user if specified
        user_id = self.request.query_params.get('user', None)
        if user_id == 'me':
            user_id = self.request.user.id
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by item if specified
        item_id = self.request.query_params.get('item', None)
        if item_id:
            queryset = queryset.filter(item_id=item_id)
        
        # Filter by raid if specified
        raid_id = self.request.query_params.get('raid', None)
        if raid_id:
            queryset = queryset.filter(raid_id=raid_id)
        
        # Filter by character name if specified
        character_name = self.request.query_params.get('character', None)
        if character_name:
            queryset = queryset.filter(character_name__icontains=character_name)
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        if date_from:
            queryset = queryset.filter(distributed_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(distributed_at__date__lte=date_to)
        
        return queryset
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def discord_award(self, request):
        """Award loot to a player via Discord bot interface."""
        serializer = DiscordLootAwardSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        distribution = serializer.save()
        
        return Response(
            LootDistributionDetailSerializer(distribution).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['post'])
    def user_balance(self, request):
        """Check user DKP balance via Discord bot interface."""
        serializer = UserBalanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_info = serializer.get_user_info()
        return Response(user_info)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent loot distributions."""
        limit = int(request.query_params.get('limit', 20))
        recent_distributions = self.get_queryset()[:limit]
        serializer = self.get_serializer(recent_distributions, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_character(self, request):
        """Get loot distributions grouped by character."""
        character_name = request.query_params.get('character', None)
        if not character_name:
            return Response(
                {'error': 'character parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        distributions = self.get_queryset().filter(
            character_name__icontains=character_name
        )
        serializer = self.get_serializer(distributions, many=True)
        
        # Calculate totals
        total_cost = sum(d.point_cost * d.quantity for d in distributions)
        total_items = sum(d.quantity for d in distributions)
        
        return Response({
            'character_name': character_name,
            'total_distributions': len(distributions),
            'total_items': total_items,
            'total_cost': total_cost,
            'distributions': serializer.data
        })


class LootAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing loot audit logs.
    Read-only access for reviewing historical data.
    Staff users get full access, regular users see limited data.
    """
    queryset = LootAuditLog.objects.select_related(
        'performed_by', 'affected_user', 'item', 'distribution', 'raid'
    )
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'character_name', 'item__name', 'raid__title']
    ordering_fields = ['timestamp', 'action_type']
    ordering = ['-timestamp']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return LootAuditLogListSerializer
        return LootAuditLogSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Non-staff users can only see logs that affect them
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(performed_by=self.request.user) |
                Q(affected_user=self.request.user)
            )
        
        # Apply filters from query parameters
        action_type = self.request.query_params.get('action_type', None)
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        
        performed_by = self.request.query_params.get('performed_by', None)
        if performed_by:
            queryset = queryset.filter(performed_by__username__icontains=performed_by)
        
        affected_user = self.request.query_params.get('affected_user', None)
        if affected_user:
            if affected_user == 'me':
                queryset = queryset.filter(affected_user=self.request.user)
            else:
                queryset = queryset.filter(affected_user__username__icontains=affected_user)
        
        character_name = self.request.query_params.get('character_name', None)
        if character_name:
            queryset = queryset.filter(character_name__icontains=character_name)
        
        item_name = self.request.query_params.get('item_name', None)
        if item_name:
            queryset = queryset.filter(item__name__icontains=item_name)
        
        # Date range filtering
        date_from = self.request.query_params.get('date_from', None)
        date_to = self.request.query_params.get('date_to', None)
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        # Limit results for performance
        limit = int(self.request.query_params.get('limit', 100))
        limit = min(limit, 1000)  # Cap at 1000
        
        return queryset[:limit]
    
    @action(detail=False, methods=['get'])
    def action_types(self, request):
        """Get list of available action types for filtering."""
        return Response([
            {'value': choice[0], 'display': choice[1]}
            for choice in LootAuditLog.ACTION_TYPES
        ])
    
    @action(detail=False, methods=['get'])
    def summary_stats(self, request):
        """Get summary statistics for audit logs."""
        queryset = self.get_queryset()
        
        # Count by action type
        action_counts = {}
        for action_type, display_name in LootAuditLog.ACTION_TYPES:
            count = queryset.filter(action_type=action_type).count()
            if count > 0:
                action_counts[action_type] = {
                    'display': display_name,
                    'count': count
                }
        
        # Recent activity (last 24 hours)
        from django.utils import timezone
        from datetime import timedelta
        
        recent_cutoff = timezone.now() - timedelta(days=1)
        recent_count = queryset.filter(timestamp__gte=recent_cutoff).count()
        
        return Response({
            'total_logs': queryset.count(),
            'recent_activity_24h': recent_count,
            'action_type_counts': action_counts
        })
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAdminUser])
    def export_csv(self, request):
        """Export audit logs to CSV (admin only)."""
        queryset = self.filter_queryset(self.get_queryset())
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="loot_audit_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Timestamp', 'Action Type', 'Performed By', 'Affected User',
            'Character Name', 'Item', 'Point Cost', 'Quantity', 'Description',
            'Raid', 'IP Address'
        ])
        
        for log in queryset:
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.get_action_type_display(),
                log.performed_by.username if log.performed_by else 'System',
                log.affected_user.username if log.affected_user else '',
                log.character_name,
                log.item.name if log.item else '',
                log.point_cost or '',
                log.quantity or '',
                log.description,
                log.raid.title if log.raid else '',
                log.ip_address or ''
            ])
        
        return response
    
    @action(detail=False, methods=['get'])
    def user_activity(self, request):
        """Get audit logs for the current user."""
        user_logs = self.get_queryset().filter(
            Q(performed_by=request.user) | Q(affected_user=request.user)
        )[:50]  # Last 50 activities
        
        serializer = self.get_serializer(user_logs, many=True)
        return Response({
            'user': request.user.username,
            'recent_activity': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def character_history(self, request):
        """Get audit logs for a specific character."""
        character_name = request.query_params.get('character', None)
        if not character_name:
            return Response(
                {'error': 'character parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        character_logs = self.get_queryset().filter(
            character_name__iexact=character_name
        )
        
        serializer = self.get_serializer(character_logs, many=True)
        return Response({
            'character_name': character_name,
            'activity_history': serializer.data
        })