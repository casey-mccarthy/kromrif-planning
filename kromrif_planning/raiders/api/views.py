from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q, Avg, Max
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import csv
from ..permissions import (
    IsOwnerOrOfficer, IsOfficerOrHigher, IsMemberOrHigher, 
    IsReadOnlyOrOfficer, IsBotOrStaff
)
from ..models import Character, Rank, CharacterOwnership, Event, Raid, RaidAttendance, Item, LootDistribution, LootAuditLog, MemberAttendanceSummary
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
    AuditLogFilterSerializer,
    AttendanceSummaryListSerializer,
    AttendanceSummaryDetailSerializer,
    AttendanceStatsSerializer,
    AttendanceLeaderboardSerializer,
    UserAttendanceQuerySerializer
)

User = get_user_model()


class RankViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing guild ranks.
    Only staff users can create/update/delete ranks.
    """
    queryset = Rank.objects.all()
    permission_classes = [IsReadOnlyOrOfficer]
    serializer_class = RankSerializer
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
    permission_classes = [IsOwnerOrOfficer]
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
    
    @action(detail=True, methods=['get'])
    def family(self, request, pk=None):
        """Get all characters in this character's family (main + alts)."""
        character = self.get_object()
        family = character.get_character_family()
        serializer = CharacterListSerializer(family, many=True)
        return Response({
            'main_character': character.get_main_character().name,
            'family_size': family.count(),
            'characters': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def families(self, request):
        """Get all character families grouped together."""
        # Get all main characters with their alts
        main_characters = Character.objects.filter(
            main_character__isnull=True
        ).prefetch_related('alt_characters')
        
        families = []
        for main_char in main_characters:
            alt_chars = main_char.alt_characters.all()
            families.append({
                'main_character': CharacterListSerializer(main_char).data,
                'alt_characters': CharacterListSerializer(alt_chars, many=True).data,
                'family_size': 1 + alt_chars.count(),
                'owner': main_char.user.username if main_char.user else None
            })
        
        return Response({
            'total_families': len(families),
            'families': families
        })
    
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
    permission_classes = [IsBotOrStaff]
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
        """
        Get audit log entries for a specific character.
        """
        character_name = request.query_params.get('character_name')
        
        if not character_name:
            return Response(
                {'error': 'character_name parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logs = self.get_queryset().filter(
            character_name__iexact=character_name
        ).order_by('-timestamp')[:50]
        
        serializer = self.get_serializer(logs, many=True)
        return Response({
            'character_name': character_name,
            'logs': serializer.data,
            'count': len(serializer.data)
        })


class MemberAttendanceSummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for attendance summaries, leaderboards, and statistics.
    Provides read-only access to attendance data with various filtering and aggregation options.
    """
    queryset = MemberAttendanceSummary.objects.select_related('user').all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    ordering_fields = [
        'summary_date', 'attendance_rate_7d', 'attendance_rate_30d', 
        'attendance_rate_60d', 'attendance_rate_90d', 'attendance_rate_lifetime',
        'current_attendance_streak', 'longest_attendance_streak'
    ]
    ordering = ['-summary_date', '-attendance_rate_30d']
    
    def get_serializer_class(self):
        """Select appropriate serializer based on action."""
        if self.action in ['retrieve']:
            return AttendanceSummaryDetailSerializer
        return AttendanceSummaryListSerializer
    
    def get_queryset(self):
        """Filter queryset based on request parameters."""
        queryset = super().get_queryset()
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(summary_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(summary_date__lte=date_to)
        
        # Filter by voting eligibility
        voting_eligible = self.request.query_params.get('voting_eligible')
        if voting_eligible is not None:
            is_eligible = voting_eligible.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(is_voting_eligible=is_eligible)
        
        # Filter by user
        user_id = self.request.query_params.get('user_id')
        username = self.request.query_params.get('username')
        
        if user_id:
            try:
                queryset = queryset.filter(user_id=int(user_id))
            except (ValueError, TypeError):
                pass  # Invalid user_id, ignore filter
        elif username:
            queryset = queryset.filter(user__username__icontains=username)
        
        # Get most recent summaries by default (unless date specified)
        if not date_from and not date_to:
            # Get the most recent summary date and filter to that
            latest_date = queryset.aggregate(
                latest=Max('summary_date')
            )['latest']
            
            if latest_date:
                queryset = queryset.filter(summary_date=latest_date)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def leaderboard(self, request):
        """
        Get attendance leaderboard for specified period.
        
        Query Parameters:
        - period: 7d, 30d, 60d, 90d, lifetime (default: 30d)
        - limit: Number of results (1-100, default: 10)
        - date: Specific date for historical data (YYYY-MM-DD)
        - voting_eligible_only: Only include voting eligible members (default: false)
        """
        # Validate and parse parameters
        serializer = AttendanceLeaderboardSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        period = serializer.validated_data['period']
        limit = serializer.validated_data['limit']
        date = serializer.validated_data.get('date')
        voting_eligible_only = serializer.validated_data['voting_eligible_only']
        
        # Use the model's built-in leaderboard method
        leaderboard_data = MemberAttendanceSummary.get_attendance_leaderboard(
            period=period,
            limit=limit,
            date=date
        )
        
        # Filter by voting eligibility if requested
        if voting_eligible_only:
            leaderboard_data = leaderboard_data.filter(is_voting_eligible=True)
        
        # Serialize the results
        result_serializer = AttendanceSummaryListSerializer(leaderboard_data, many=True)
        
        return Response({
            'period': period,
            'limit': limit,
            'date': date or 'latest',
            'voting_eligible_only': voting_eligible_only,
            'leaderboard': result_serializer.data,
            'count': len(result_serializer.data)
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get overall attendance statistics and aggregated data.
        
        Query Parameters:
        - date: Specific date for historical stats (YYYY-MM-DD, default: latest)
        """
        date = request.query_params.get('date')
        
        # Get base queryset for the specified date
        if date:
            queryset = MemberAttendanceSummary.objects.filter(summary_date=date)
        else:
            # Get most recent summaries
            latest_date = MemberAttendanceSummary.objects.aggregate(
                latest=Max('summary_date')
            )['latest']
            
            if not latest_date:
                return Response({
                    'error': 'No attendance data available'
                }, status=status.HTTP_404_NOT_FOUND)
            
            queryset = MemberAttendanceSummary.objects.filter(summary_date=latest_date)
            date = latest_date
        
        if not queryset.exists():
            return Response({
                'error': f'No attendance data available for {date}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate statistics
        stats = queryset.aggregate(
            total_members=Count('id'),
            voting_eligible_count=Count('id', filter=Q(is_voting_eligible=True)),
            average_attendance_30d=Avg('attendance_rate_30d'),
            average_attendance_90d=Avg('attendance_rate_90d'),
            average_attendance_lifetime=Avg('attendance_rate_lifetime'),
            highest_streak=Max('longest_attendance_streak'),
            active_streaks=Count('id', filter=Q(current_attendance_streak__gt=0))
        )
        
        # Calculate voting eligible percentage
        if stats['total_members'] > 0:
            stats['voting_eligible_percentage'] = round(
                (stats['voting_eligible_count'] / stats['total_members']) * 100, 2
            )
        else:
            stats['voting_eligible_percentage'] = 0
        
        # Get top performers (30-day rate)
        top_performers = queryset.order_by('-attendance_rate_30d')[:5]
        stats['top_performers_30d'] = AttendanceSummaryListSerializer(
            top_performers, many=True
        ).data
        
        # Get recent update timestamp
        stats['recent_updates'] = queryset.order_by('-last_updated').first().last_updated
        
        # Serialize and return
        result_serializer = AttendanceStatsSerializer(data=stats)
        result_serializer.is_valid(raise_exception=True)
        
        return Response({
            'date': date,
            'statistics': result_serializer.validated_data
        })
    
    @action(detail=False, methods=['get'])
    def user_history(self, request):
        """
        Get attendance history for a specific user.
        
        Query Parameters:
        - user_id: User ID to query (required if username not provided)
        - username: Username to query (required if user_id not provided)
        - date_from: Start date for history (YYYY-MM-DD)
        - date_to: End date for history (YYYY-MM-DD)
        """
        # Validate parameters
        serializer = UserAttendanceQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        user_id = serializer.validated_data.get('user_id')
        username = serializer.validated_data.get('username')
        date_from = serializer.validated_data.get('date_from')
        date_to = serializer.validated_data.get('date_to')
        
        # Get user
        try:
            if user_id:
                user = User.objects.get(id=user_id)
            else:
                user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({
                'error': f'User not found: {user_id or username}'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get user's attendance history
        queryset = MemberAttendanceSummary.objects.filter(user=user)
        
        if date_from:
            queryset = queryset.filter(summary_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(summary_date__lte=date_to)
        
        # Order by date (most recent first)
        queryset = queryset.order_by('-summary_date')
        
        # Serialize results
        result_serializer = AttendanceSummaryDetailSerializer(queryset, many=True)
        
        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'display_name': user.get_full_name() or user.username
            },
            'date_range': {
                'from': date_from,
                'to': date_to
            },
            'history': result_serializer.data,
            'count': len(result_serializer.data)
        })
    
    @action(detail=False, methods=['get'])
    def voting_eligible(self, request):
        """
        Get list of voting eligible members.
        
        Query Parameters:
        - date: Specific date for eligibility check (YYYY-MM-DD, default: latest)
        """
        date = request.query_params.get('date')
        
        # Get voting eligible members
        eligible_members = MemberAttendanceSummary.get_voting_eligible_members(date=date)
        
        if not eligible_members.exists():
            return Response({
                'date': date or 'latest',
                'voting_eligible_members': [],
                'count': 0,
                'message': 'No voting eligible members found'
            })
        
        # Serialize results
        serializer = AttendanceSummaryListSerializer(eligible_members, many=True)
        
        return Response({
            'date': date or eligible_members.first().summary_date,
            'voting_eligible_members': serializer.data,
            'count': len(serializer.data)
        })
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAdminUser])
    def export_csv(self, request):
        """
        Export attendance summaries to CSV format.
        Admin only endpoint for data exports.
        
        Query Parameters:
        - date: Specific date for export (YYYY-MM-DD, default: latest)
        - period: Include specific period data (7d, 30d, 60d, 90d, lifetime, all)
        """
        date = request.query_params.get('date')
        period = request.query_params.get('period', 'all')
        
        # Get data for export
        if date:
            queryset = MemberAttendanceSummary.objects.filter(summary_date=date)
        else:
            # Get most recent summaries
            latest_date = MemberAttendanceSummary.objects.aggregate(
                latest=Max('summary_date')
            )['latest']
            
            if not latest_date:
                return Response({
                    'error': 'No attendance data available'
                }, status=status.HTTP_404_NOT_FOUND)
            
            queryset = MemberAttendanceSummary.objects.filter(summary_date=latest_date)
            date = latest_date
        
        # Order by attendance rate (descending)
        queryset = queryset.select_related('user').order_by('-attendance_rate_30d')
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendance_summary_{date}.csv"'
        
        writer = csv.writer(response)
        
        # Write header based on period selection
        if period == 'all':
            header = [
                'Username', 'User ID', 'Summary Date',
                '7d Rate', '7d Attended', '7d Total',
                '30d Rate', '30d Attended', '30d Total',
                '60d Rate', '60d Attended', '60d Total',
                '90d Rate', '90d Attended', '90d Total',
                'Lifetime Rate', 'Lifetime Attended', 'Lifetime Total',
                'Voting Eligible', 'Current Streak', 'Longest Streak',
                'Last Updated'
            ]
        else:
            # Single period export
            period_map = {
                '7d': ('7d', 'attendance_rate_7d', 'attended_raids_7d', 'total_raids_7d'),
                '30d': ('30d', 'attendance_rate_30d', 'attended_raids_30d', 'total_raids_30d'),
                '60d': ('60d', 'attendance_rate_60d', 'attended_raids_60d', 'total_raids_60d'),
                '90d': ('90d', 'attendance_rate_90d', 'attended_raids_90d', 'total_raids_90d'),
                'lifetime': ('Lifetime', 'attendance_rate_lifetime', 'attended_raids_lifetime', 'total_raids_lifetime')
            }
            
            if period not in period_map:
                period = '30d'  # Default fallback
            
            period_name = period_map[period][0]
            header = [
                'Username', 'User ID', 'Summary Date',
                f'{period_name} Rate', f'{period_name} Attended', f'{period_name} Total',
                'Voting Eligible', 'Current Streak', 'Longest Streak'
            ]
        
        writer.writerow(header)
        
        # Write data rows
        for summary in queryset:
            if period == 'all':
                row = [
                    summary.user.username,
                    summary.user.id,
                    summary.summary_date,
                    summary.attendance_rate_7d,
                    summary.attended_raids_7d,
                    summary.total_raids_7d,
                    summary.attendance_rate_30d,
                    summary.attended_raids_30d,
                    summary.total_raids_30d,
                    summary.attendance_rate_60d,
                    summary.attended_raids_60d,
                    summary.total_raids_60d,
                    summary.attendance_rate_90d,
                    summary.attended_raids_90d,
                    summary.total_raids_90d,
                    summary.attendance_rate_lifetime,
                    summary.attended_raids_lifetime,
                    summary.total_raids_lifetime,
                    summary.is_voting_eligible,
                    summary.current_attendance_streak,
                    summary.longest_attendance_streak,
                    summary.last_updated
                ]
            else:
                # Single period row
                _, rate_field, attended_field, total_field = period_map[period]
                row = [
                    summary.user.username,
                    summary.user.id,
                    summary.summary_date,
                    getattr(summary, rate_field),
                    getattr(summary, attended_field),
                    getattr(summary, total_field),
                    summary.is_voting_eligible,
                    summary.current_attendance_streak,
                    summary.longest_attendance_streak
                ]
            
            writer.writerow(row)
        
        return response