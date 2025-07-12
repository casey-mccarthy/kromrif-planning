from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from ..models import Character, Rank, CharacterOwnership
from .serializers import (
    CharacterListSerializer,
    CharacterDetailSerializer,
    RankSerializer,
    CharacterOwnershipSerializer,
    CharacterTransferSerializer
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
    queryset = Character.objects.select_related('user', 'main_character')
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
        
        # Filter by main/alt status
        character_type = self.request.query_params.get('type', None)
        if character_type == 'main':
            queryset = queryset.filter(main_character__isnull=True)
        elif character_type == 'alt':
            queryset = queryset.filter(main_character__isnull=False)
        
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
        """Get the character family (main + all alts)."""
        character = self.get_object()
        family = character.get_character_family()
        serializer = CharacterListSerializer(family, many=True)
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