"""
Discord Bot API endpoints for roster and member management.
These endpoints are specifically designed for Discord bot integration.
"""

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Sum
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.serializers import ValidationError

from .error_handling import DiscordAPIErrorMixin, discord_api_error_handler, HealthCheckMixin

from ..models import Character, Rank, CharacterOwnership, Event, Raid, RaidAttendance, Item, LootDistribution
from .serializers import (
    CharacterListSerializer, CharacterDetailSerializer, 
    RankSerializer, EventSerializer, RaidListSerializer,
    ItemSerializer, LootDistributionListSerializer
)
from .discord_serializers import (
    DiscordUserSerializer, DiscordCharacterSerializer, DiscordRosterMemberSerializer,
    DiscordMemberLookupSerializer, DiscordEventSerializer, DiscordRaidSerializer,
    DiscordGuildStatsSerializer, DiscordMemberStatusUpdateSerializer,
    DiscordLinkUserSerializer, DiscordUnlinkUserSerializer, DiscordOperationResponseSerializer
)
from .permissions import IsMemberOrHigher, IsOfficerOrHigher, IsDiscordBot
from ..services import DiscordMemberService, DiscordSyncService

User = get_user_model()


class DiscordRosterViewSet(DiscordAPIErrorMixin, HealthCheckMixin, viewsets.ReadOnlyModelViewSet):
    """
    Discord bot API for roster queries and member information.
    Provides read-only access to guild roster data optimized for Discord bot operations.
    """
    permission_classes = [IsDiscordBot]
    
    @action(detail=False, methods=['get'])
    @discord_api_error_handler("guild_roster")
    def guild_roster(self, request):
        """Get complete guild roster with character and user information."""
        # Get all active characters with user info
        characters = Character.objects.filter(is_active=True).select_related(
            'user'
        ).prefetch_related('user__dkp_summary')
        
        # Serialize character data
        serializer = DiscordCharacterSerializer(characters, many=True)
        
        # Get summary statistics
        total_members = User.objects.filter(characters__is_active=True).distinct().count()
        total_characters = characters.count()
        
        # Get rank distribution
        rank_distribution = {}
        if characters.exists():
            ranks = Rank.objects.all()
            for rank in ranks:
                # Count characters by rank if rank system is implemented
                rank_distribution[rank.name] = characters.filter(
                    # Add rank filter when rank field exists on Character
                ).count() if hasattr(Character, 'rank') else 0
        
        return Response({
            'total_members': total_members,
            'total_characters': total_characters,
            'rank_distribution': rank_distribution,
            'characters': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def member_lookup(self, request):
        """Look up a member by various identifiers (username, character name, Discord ID)."""
        # Get search parameters
        username = request.query_params.get('username')
        character_name = request.query_params.get('character_name')
        discord_id = request.query_params.get('discord_id')
        
        if not any([username, character_name, discord_id]):
            return Response(
                {'error': 'Must provide username, character_name, or discord_id parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = None
        character = None
        
        try:
            # Look up by Discord ID (stored in User model)
            if discord_id:
                user = User.objects.get(discord_id=discord_id)
            
            # Look up by username
            elif username:
                user = User.objects.get(username__iexact=username)
            
            # Look up by character name
            elif character_name:
                character = Character.objects.get(name__iexact=character_name)
                user = character.user
            
            # Get user's characters
            characters = user.characters.filter(is_active=True)
            character_data = DiscordCharacterSerializer(characters, many=True).data
            
            # Get DKP information
            dkp_balance = getattr(user, 'dkp_summary', None)
            dkp_info = {
                'total_points': dkp_balance.total_points if dkp_balance else 0,
                'earned_points': dkp_balance.earned_points if dkp_balance else 0,
                'spent_points': dkp_balance.spent_points if dkp_balance else 0
            }
            
            return Response({
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'discord_id': getattr(user, 'discord_id', None),
                    'discord_username': getattr(user, 'discord_username', None),
                    'email': user.email,
                    'is_active': user.is_active,
                    'date_joined': user.date_joined,
                },
                'characters': character_data,
                'dkp': dkp_info,
                'main_character': characters.first().name if characters.exists() else None
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Character.DoesNotExist:
            return Response(
                {'error': 'Character not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def online_members(self, request):
        """Get list of members who are currently online (placeholder for future Discord presence integration)."""
        # This endpoint is a placeholder for future Discord presence API integration
        # For now, return all active members
        characters = Character.objects.filter(is_active=True).select_related('user')
        serializer = DiscordCharacterSerializer(characters, many=True)
        
        return Response({
            'message': 'Online status tracking not yet implemented',
            'all_active_members': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def member_stats(self, request):
        """Get overall member statistics for the guild."""
        # Get member counts
        total_users = User.objects.filter(is_active=True).count()
        total_characters = Character.objects.filter(is_active=True).count()
        
        # Get recent activity (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        recent_raids = Raid.objects.filter(date__gte=thirty_days_ago).count()
        recent_attendance = RaidAttendance.objects.filter(
            raid__date__gte=thirty_days_ago
        ).count()
        recent_loot = LootDistribution.objects.filter(
            distributed_at__gte=thirty_days_ago
        ).count()
        
        # Get top DKP holders
        top_dkp = []
        try:
            from ...dkp.models import DKPManager
            top_dkp_users = DKPManager.get_top_dkp_users(limit=5)
            for summary in top_dkp_users:
                main_char = summary.user.characters.filter(is_active=True).first()
                top_dkp.append({
                    'username': summary.user.username,
                    'character_name': main_char.name if main_char else summary.user.username,
                    'dkp': summary.total_points
                })
        except Exception:
            # DKP system not available
            pass
        
        return Response({
            'member_counts': {
                'total_users': total_users,
                'total_characters': total_characters,
            },
            'recent_activity': {
                'raids_last_30_days': recent_raids,
                'attendance_records_last_30_days': recent_attendance,
                'loot_distributions_last_30_days': recent_loot,
            },
            'top_dkp_holders': top_dkp
        })
    
    @action(detail=False, methods=['get'])
    @discord_api_error_handler("health_check")
    def health_check(self, request):
        """Health check endpoint for Discord bot integration."""
        health_status = self.check_discord_health()
        
        # Add some additional API-specific health info
        try:
            character_count = Character.objects.filter(is_active=True).count()
            health_status['api_metrics'] = {
                'active_characters': character_count,
                'total_users': User.objects.count()
            }
        except Exception as e:
            health_status['api_metrics'] = {'error': str(e)}
        
        response_status = status.HTTP_200_OK
        if health_status['status'] == 'unhealthy':
            response_status = status.HTTP_503_SERVICE_UNAVAILABLE
        elif health_status['status'] == 'degraded':
            response_status = status.HTTP_206_PARTIAL_CONTENT
        
        return Response(health_status, status=response_status)


class DiscordMemberManagementViewSet(DiscordAPIErrorMixin, viewsets.ViewSet):
    """
    Discord bot API for member management operations.
    Provides endpoints for updating member status, linking/unlinking, and notifications.
    """
    permission_classes = [IsDiscordBot]
    
    @action(detail=False, methods=['post'])
    def update_member_status(self, request):
        """Update a member's status (active/inactive) via Discord command."""
        serializer = DiscordMemberStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use service layer for business logic
        success, message, user = DiscordMemberService.update_member_status(
            user_identifier=serializer.validated_data['user_identifier'],
            new_status=serializer.validated_data['status'],
            reason=serializer.validated_data['reason'],
            requester=request.user
        )
        
        if success:
            return Response({
                'success': True,
                'message': message,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'status': serializer.validated_data['status'],
                    'discord_id': getattr(user, 'discord_id', None)
                }
            })
        else:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST if user else status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    @discord_api_error_handler("link_discord_user")
    def link_discord_user(self, request):
        """Link a Discord user to an application user account."""
        serializer = DiscordLinkUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use service layer for business logic
        success, message, user = DiscordMemberService.link_discord_user(
            discord_id=serializer.validated_data['discord_id'],
            app_username=serializer.validated_data['app_username'],
            discord_username=serializer.validated_data.get('discord_username'),
            requester=request.user
        )
        
        if success:
            return Response({
                'success': True,
                'message': message,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'discord_id': user.discord_id,
                    'discord_username': getattr(user, 'discord_username', None)
                }
            })
        else:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST if user else status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def unlink_discord_user(self, request):
        """Unlink a Discord user from an application user account."""
        serializer = DiscordUnlinkUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid data', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use service layer for business logic
        success, message, user = DiscordMemberService.unlink_discord_user(
            identifier=serializer.validated_data['identifier'],
            requester=request.user
        )
        
        if success:
            return Response({
                'success': True,
                'message': message,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'discord_id': None,
                    'discord_username': None
                }
            })
        else:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST if user else status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def discord_linked_users(self, request):
        """Get list of all users linked to Discord."""
        # Use service layer for business logic
        user_data = DiscordMemberService.get_discord_linked_users()
        
        return Response({
            'total_linked': len(user_data),
            'linked_users': user_data
        })
    
    @action(detail=False, methods=['post'])
    def bulk_link_users(self, request):
        """Bulk link multiple Discord users to application accounts."""
        link_data = request.data.get('links', [])
        
        if not link_data or not isinstance(link_data, list):
            return Response(
                {'error': 'links parameter must be a non-empty list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        results = {
            'successful': [],
            'failed': [],
            'total_processed': 0
        }
        
        for link_info in link_data:
            results['total_processed'] += 1
            
            try:
                success, message, user = DiscordMemberService.link_discord_user(
                    discord_id=link_info.get('discord_id'),
                    app_username=link_info.get('app_username'),
                    discord_username=link_info.get('discord_username'),
                    requester=request.user
                )
                
                if success:
                    results['successful'].append({
                        'discord_id': link_info.get('discord_id'),
                        'app_username': link_info.get('app_username'),
                        'message': message
                    })
                else:
                    results['failed'].append({
                        'discord_id': link_info.get('discord_id'),
                        'app_username': link_info.get('app_username'),
                        'error': message
                    })
                    
            except Exception as e:
                results['failed'].append({
                    'discord_id': link_info.get('discord_id'),
                    'app_username': link_info.get('app_username'),
                    'error': str(e)
                })
        
        return Response({
            'success': True,
            'message': f'Processed {results["total_processed"]} link requests',
            'results': results
        })
    
    @action(detail=False, methods=['post'])
    def sync_discord_members(self, request):
        """Sync Discord guild members with application users."""
        guild_members = request.data.get('guild_members', [])
        
        if not guild_members or not isinstance(guild_members, list):
            return Response(
                {'error': 'guild_members parameter must be a non-empty list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use service layer for synchronization
        stats = DiscordSyncService.sync_guild_members(guild_members)
        
        return Response({
            'success': True,
            'message': f'Synced {stats["processed"]} guild members',
            'stats': stats
        })