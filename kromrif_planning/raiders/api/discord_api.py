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

User = get_user_model()


class DiscordRosterViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Discord bot API for roster queries and member information.
    Provides read-only access to guild roster data optimized for Discord bot operations.
    """
    permission_classes = [IsMemberOrHigher]
    
    @action(detail=False, methods=['get'])
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


class DiscordMemberManagementViewSet(viewsets.ViewSet):
    """
    Discord bot API for member management operations.
    Provides endpoints for updating member status, linking/unlinking, and notifications.
    """
    permission_classes = [IsOfficerOrHigher]
    
    @action(detail=False, methods=['post'])
    def update_member_status(self, request):
        """Update a member's status (active/inactive) via Discord command."""
        user_identifier = request.data.get('user_identifier')  # username, character_name, or discord_id
        new_status = request.data.get('status')  # 'active' or 'inactive'
        reason = request.data.get('reason', 'Updated via Discord bot')
        
        if not user_identifier or not new_status:
            return Response(
                {'error': 'user_identifier and status are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if new_status not in ['active', 'inactive']:
            return Response(
                {'error': 'status must be "active" or "inactive"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Find the user
            user = None
            
            # Try Discord ID first
            if user_identifier.isdigit():
                try:
                    user = User.objects.get(discord_id=user_identifier)
                except User.DoesNotExist:
                    pass
            
            # Try username
            if not user:
                try:
                    user = User.objects.get(username__iexact=user_identifier)
                except User.DoesNotExist:
                    pass
            
            # Try character name
            if not user:
                try:
                    character = Character.objects.get(name__iexact=user_identifier)
                    user = character.user
                except Character.DoesNotExist:
                    pass
            
            if not user:
                return Response(
                    {'error': f'User not found: {user_identifier}'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Update user status
            old_status = 'active' if user.is_active else 'inactive'
            user.is_active = (new_status == 'active')
            user.save()
            
            # Update character statuses to match
            if new_status == 'inactive':
                user.characters.filter(is_active=True).update(is_active=False)
            
            # Log the change
            from ...dkp.models import DKPManager, PointAdjustment
            try:
                # Create a log entry for the status change
                # This could be expanded to use a dedicated audit log model
                description = f"Member status changed from {old_status} to {new_status}. Reason: {reason}"
                # You could add this to an audit log model here
            except Exception:
                # Logging failed, but status change succeeded
                pass
            
            return Response({
                'success': True,
                'message': f'Updated {user.username} status from {old_status} to {new_status}',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'status': new_status,
                    'discord_id': getattr(user, 'discord_id', None)
                }
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to update member status: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def link_discord_user(self, request):
        """Link a Discord user to an application user account."""
        discord_id = request.data.get('discord_id')
        discord_username = request.data.get('discord_username')
        app_username = request.data.get('app_username')
        
        if not all([discord_id, app_username]):
            return Response(
                {'error': 'discord_id and app_username are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Find the application user
            app_user = User.objects.get(username__iexact=app_username)
            
            # Check if Discord ID is already linked
            existing_link = User.objects.filter(discord_id=discord_id).first()
            if existing_link and existing_link != app_user:
                return Response(
                    {'error': f'Discord ID {discord_id} is already linked to user {existing_link.username}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update user with Discord information
            app_user.discord_id = discord_id
            if discord_username:
                app_user.discord_username = discord_username
            app_user.save()
            
            return Response({
                'success': True,
                'message': f'Successfully linked Discord user {discord_username or discord_id} to {app_username}',
                'user': {
                    'id': app_user.id,
                    'username': app_user.username,
                    'discord_id': app_user.discord_id,
                    'discord_username': getattr(app_user, 'discord_username', None)
                }
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': f'Application user not found: {app_username}'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to link Discord user: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def unlink_discord_user(self, request):
        """Unlink a Discord user from an application user account."""
        identifier = request.data.get('identifier')  # Can be discord_id or app_username
        
        if not identifier:
            return Response(
                {'error': 'identifier (discord_id or app_username) is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = None
            
            # Try to find by Discord ID
            if identifier.isdigit():
                try:
                    user = User.objects.get(discord_id=identifier)
                except User.DoesNotExist:
                    pass
            
            # Try to find by username
            if not user:
                try:
                    user = User.objects.get(username__iexact=identifier)
                except User.DoesNotExist:
                    pass
            
            if not user:
                return Response(
                    {'error': f'User not found: {identifier}'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if not getattr(user, 'discord_id', None):
                return Response(
                    {'error': f'User {user.username} is not linked to Discord'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Clear Discord information
            old_discord_id = user.discord_id
            old_discord_username = getattr(user, 'discord_username', None)
            
            user.discord_id = None
            if hasattr(user, 'discord_username'):
                user.discord_username = None
            user.save()
            
            return Response({
                'success': True,
                'message': f'Successfully unlinked Discord user {old_discord_username or old_discord_id} from {user.username}',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'discord_id': None,
                    'discord_username': None
                }
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to unlink Discord user: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def discord_linked_users(self, request):
        """Get list of all users linked to Discord."""
        # Find users with Discord IDs
        linked_users = User.objects.exclude(discord_id__isnull=True).exclude(discord_id='')
        
        user_data = []
        for user in linked_users:
            main_char = user.characters.filter(is_active=True).first()
            user_data.append({
                'id': user.id,
                'username': user.username,
                'discord_id': user.discord_id,
                'discord_username': getattr(user, 'discord_username', None),
                'main_character': main_char.name if main_char else None,
                'is_active': user.is_active
            })
        
        return Response({
            'total_linked': len(user_data),
            'linked_users': user_data
        })