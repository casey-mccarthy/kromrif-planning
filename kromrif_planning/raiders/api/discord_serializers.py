"""
Serializers specifically designed for Discord bot API responses.
These serializers optimize data format for Discord bot consumption.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import Character, Rank, Event, Raid, RaidAttendance, Item, LootDistribution

User = get_user_model()


class DiscordUserSerializer(serializers.ModelSerializer):
    """
    Serializer for User data optimized for Discord bot consumption.
    """
    discord_tag = serializers.ReadOnlyField()
    discord_avatar_url = serializers.ReadOnlyField(source='get_discord_avatar_url')
    role_display = serializers.ReadOnlyField(source='get_role_display_name')
    role_color = serializers.ReadOnlyField(source='get_role_color')
    dkp_balance = serializers.SerializerMethodField()
    main_character = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'is_active', 'date_joined',
            'discord_id', 'discord_username', 'discord_tag', 'discord_avatar_url',
            'role_group', 'role_display', 'role_color',
            'dkp_balance', 'main_character'
        ]
    
    def get_dkp_balance(self, obj):
        """Get user's DKP balance."""
        try:
            summary = getattr(obj, 'dkp_summary', None)
            if summary:
                return {
                    'total': float(summary.total_points),
                    'earned': float(summary.earned_points),
                    'spent': float(summary.spent_points),
                    'last_updated': summary.last_updated.isoformat() if summary.last_updated else None
                }
        except Exception:
            pass
        return {'total': 0, 'earned': 0, 'spent': 0, 'last_updated': None}
    
    def get_main_character(self, obj):
        """Get user's main character name."""
        main_char = obj.characters.filter(is_active=True).first()
        return main_char.name if main_char else None


class DiscordCharacterSerializer(serializers.ModelSerializer):
    """
    Serializer for Character data optimized for Discord bot consumption.
    """
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    discord_id = serializers.CharField(source='user.discord_id', read_only=True)
    discord_tag = serializers.CharField(source='user.discord_tag', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Character
        fields = [
            'id', 'name', 'character_class', 'level', 'status', 'status_display',
            'is_active', 'description', 'created_at', 'updated_at',
            'user_id', 'username', 'discord_id', 'discord_tag'
        ]


class DiscordRosterMemberSerializer(serializers.Serializer):
    """
    Combined serializer for roster members including user and character data.
    """
    user = DiscordUserSerializer(read_only=True)
    characters = DiscordCharacterSerializer(many=True, read_only=True)
    total_characters = serializers.IntegerField(read_only=True)
    last_raid_attendance = serializers.DateTimeField(read_only=True, allow_null=True)
    
    class Meta:
        fields = ['user', 'characters', 'total_characters', 'last_raid_attendance']


class DiscordMemberLookupSerializer(serializers.Serializer):
    """
    Serializer for member lookup responses.
    """
    found = serializers.BooleanField(default=True)
    user = DiscordUserSerializer(read_only=True)
    characters = DiscordCharacterSerializer(many=True, read_only=True)
    dkp_info = serializers.DictField(read_only=True)
    recent_activity = serializers.DictField(read_only=True)
    
    class Meta:
        fields = ['found', 'user', 'characters', 'dkp_info', 'recent_activity']


class DiscordEventSerializer(serializers.ModelSerializer):
    """
    Serializer for Event data for Discord bot consumption.
    """
    recent_raids_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'name', 'description', 'base_points', 'on_time_bonus',
            'is_active', 'color', 'recent_raids_count', 'created_at'
        ]
    
    def get_recent_raids_count(self, obj):
        """Get count of raids in the last 30 days."""
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.now() - timedelta(days=30)
        return obj.raids.filter(date__gte=thirty_days_ago).count()


class DiscordRaidSerializer(serializers.ModelSerializer):
    """
    Serializer for Raid data for Discord bot consumption.
    """
    event_name = serializers.CharField(source='event.name', read_only=True)
    leader_name = serializers.CharField(source='leader.username', read_only=True)
    attendance_count = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Raid
        fields = [
            'id', 'title', 'event_name', 'date', 'start_time', 'end_time',
            'leader_name', 'status', 'status_display', 'attendance_count',
            'points_awarded', 'notes'
        ]
    
    def get_attendance_count(self, obj):
        """Get attendance statistics for this raid."""
        return {
            'total': obj.get_attendance_count(),
            'on_time': obj.get_on_time_count()
        }


class DiscordGuildStatsSerializer(serializers.Serializer):
    """
    Serializer for guild statistics summary.
    """
    member_counts = serializers.DictField()
    recent_activity = serializers.DictField()
    top_dkp_holders = serializers.ListField()
    rank_distribution = serializers.DictField()
    last_updated = serializers.DateTimeField()
    
    class Meta:
        fields = [
            'member_counts', 'recent_activity', 'top_dkp_holders',
            'rank_distribution', 'last_updated'
        ]


class DiscordMemberStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for member status update requests.
    """
    user_identifier = serializers.CharField(
        help_text="Username, character name, or Discord ID"
    )
    status = serializers.ChoiceField(
        choices=['active', 'inactive'],
        help_text="New status for the member"
    )
    reason = serializers.CharField(
        required=False,
        default="Updated via Discord bot",
        help_text="Reason for the status change"
    )
    
    def validate_user_identifier(self, value):
        """Validate that the user identifier is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("User identifier cannot be empty")
        return value.strip()


class DiscordLinkUserSerializer(serializers.Serializer):
    """
    Serializer for linking Discord users to application accounts.
    """
    discord_id = serializers.CharField(
        max_length=20,
        help_text="Discord user ID"
    )
    discord_username = serializers.CharField(
        max_length=32,
        required=False,
        help_text="Discord username (optional)"
    )
    app_username = serializers.CharField(
        max_length=150,
        help_text="Application username to link to"
    )
    
    def validate_discord_id(self, value):
        """Validate Discord ID format."""
        if not value.isdigit():
            raise serializers.ValidationError("Discord ID must be numeric")
        if len(value) < 10 or len(value) > 20:
            raise serializers.ValidationError("Discord ID must be 10-20 digits")
        return value
    
    def validate_app_username(self, value):
        """Validate that the application username exists."""
        try:
            User.objects.get(username__iexact=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(f"Application user '{value}' not found")
        return value


class DiscordUnlinkUserSerializer(serializers.Serializer):
    """
    Serializer for unlinking Discord users from application accounts.
    """
    identifier = serializers.CharField(
        help_text="Discord ID or application username"
    )
    
    def validate_identifier(self, value):
        """Validate that the identifier is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Identifier cannot be empty")
        return value.strip()


class DiscordOperationResponseSerializer(serializers.Serializer):
    """
    Serializer for Discord operation responses.
    """
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = serializers.DictField(required=False)
    errors = serializers.ListField(required=False)
    
    class Meta:
        fields = ['success', 'message', 'data', 'errors']