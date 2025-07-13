from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import Character, Rank, CharacterOwnership, Event, Raid, RaidAttendance, Item, LootDistribution, LootAuditLog

User = get_user_model()


class RankSerializer(serializers.ModelSerializer):
    character_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Rank
        fields = [
            'id', 'name', 'level', 'description', 'permissions',
            'color', 'character_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Character count is not available since rank-character relationship was removed
        data['character_count'] = 0
        return data


class CharacterListSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    
    class Meta:
        model = Character
        fields = [
            'id', 'name', 'character_class', 'level', 'status',
            'user', 'is_active', 'created_at'
        ]


class CharacterDetailSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        default=serializers.CurrentUserDefault()
    )
    ownership_history = serializers.SerializerMethodField()
    
    class Meta:
        model = Character
        fields = [
            'id', 'name', 'character_class', 'level', 'status',
            'user', 'description', 'is_active', 'ownership_history',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_ownership_history(self, obj):
        history = obj.ownership_history.all()[:5]  # Last 5 transfers
        return CharacterOwnershipSerializer(history, many=True).data
    
    def create(self, validated_data):
        character = super().create(validated_data)
        # Create initial ownership record
        CharacterOwnership.objects.create(
            character=character,
            new_owner=character.user,
            reason='created',
            transferred_by=self.context['request'].user
        )
        return character


class CharacterOwnershipSerializer(serializers.ModelSerializer):
    character = serializers.StringRelatedField()
    previous_owner = serializers.StringRelatedField()
    new_owner = serializers.StringRelatedField()
    transferred_by = serializers.StringRelatedField()
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    
    class Meta:
        model = CharacterOwnership
        fields = [
            'id', 'character', 'previous_owner', 'new_owner',
            'transfer_date', 'reason', 'reason_display', 'notes',
            'transferred_by'
        ]
        read_only_fields = ['transfer_date']


class CharacterTransferSerializer(serializers.Serializer):
    character_id = serializers.IntegerField()
    new_owner_id = serializers.IntegerField()
    reason = serializers.ChoiceField(
        choices=CharacterOwnership.TRANSFER_REASONS,
        default='manual'
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_character_id(self, value):
        try:
            self.character = Character.objects.get(id=value)
        except Character.DoesNotExist:
            raise serializers.ValidationError("Character not found.")
        return value
    
    def validate_new_owner_id(self, value):
        try:
            self.new_owner = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        return value
    
    def validate(self, data):
        if hasattr(self, 'character') and hasattr(self, 'new_owner'):
            if self.character.user == self.new_owner:
                raise serializers.ValidationError("Character already belongs to this user.")
        return data
    
    def save(self):
        return CharacterOwnership.record_transfer(
            character=self.character,
            new_owner=self.new_owner,
            reason=self.validated_data['reason'],
            notes=self.validated_data.get('notes', ''),
            transferred_by=self.context['request'].user
        )


class EventSerializer(serializers.ModelSerializer):
    raid_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Event
        fields = [
            'id', 'name', 'description', 'base_points', 'on_time_bonus',
            'is_active', 'color', 'raid_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['raid_count'] = instance.raids.count()
        return data


class RaidListSerializer(serializers.ModelSerializer):
    event = serializers.StringRelatedField()
    leader = serializers.StringRelatedField()
    attendance_count = serializers.SerializerMethodField()
    formatted_datetime = serializers.CharField(read_only=True)
    
    class Meta:
        model = Raid
        fields = [
            'id', 'title', 'event', 'date', 'start_time', 'leader',
            'status', 'attendance_count', 'points_awarded', 'formatted_datetime'
        ]
    
    def get_attendance_count(self, obj):
        return {
            'total': obj.get_attendance_count(),
            'on_time': obj.get_on_time_count()
        }


class RaidDetailSerializer(serializers.ModelSerializer):
    event = EventSerializer(read_only=True)
    event_id = serializers.PrimaryKeyRelatedField(
        source='event',
        queryset=Event.objects.filter(is_active=True),
        write_only=True
    )
    leader = serializers.StringRelatedField(read_only=True)
    leader_id = serializers.PrimaryKeyRelatedField(
        source='leader',
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    attendance_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Raid
        fields = [
            'id', 'event', 'event_id', 'title', 'date', 'start_time', 'end_time',
            'leader', 'leader_id', 'notes', 'status', 'parse_attendance',
            'points_awarded', 'attendance_summary', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'points_awarded']
    
    def get_attendance_summary(self, obj):
        return {
            'total_count': obj.get_attendance_count(),
            'on_time_count': obj.get_on_time_count(),
            'attendance_list': RaidAttendanceSerializer(
                obj.attendance_records.all()[:20], many=True
            ).data
        }


class RaidAttendanceSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        source='user',
        queryset=User.objects.all(),
        write_only=True
    )
    raid = serializers.StringRelatedField(read_only=True)
    recorded_by = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = RaidAttendance
        fields = [
            'id', 'raid', 'user', 'user_id', 'character_name', 'on_time',
            'notes', 'recorded_by', 'created_at'
        ]
        read_only_fields = ['created_at', 'recorded_by']
    
    def create(self, validated_data):
        validated_data['recorded_by'] = self.context['request'].user
        return super().create(validated_data)


class BulkAttendanceSerializer(serializers.Serializer):
    """Serializer for bulk attendance creation from character name list"""
    
    character_names = serializers.ListField(
        child=serializers.CharField(max_length=64),
        help_text="List of character names to record attendance for"
    )
    all_on_time = serializers.BooleanField(
        default=True,
        help_text="Mark all attendees as on-time"
    )
    
    def validate_character_names(self, value):
        if not value:
            raise serializers.ValidationError("At least one character name is required")
        
        # Remove duplicates and empty strings
        character_names = list(set(name.strip() for name in value if name.strip()))
        
        if len(character_names) != len(value):
            raise serializers.ValidationError("Duplicate or empty character names found")
        
        return character_names
    
    def create(self, validated_data):
        raid = self.context['raid']
        recorded_by = self.context['request'].user
        
        results = RaidAttendance.parse_character_list(
            raid=raid,
            character_names=validated_data['character_names'],
            recorded_by=recorded_by,
            all_on_time=validated_data['all_on_time']
        )
        
        return results


class AwardPointsSerializer(serializers.Serializer):
    """Serializer for awarding DKP points to raid attendees"""
    
    confirm = serializers.BooleanField(
        help_text="Confirm that you want to award points for this raid"
    )
    
    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError("You must confirm to award points")
        return value
    
    def create(self, validated_data):
        raid = self.context['raid']
        created_by = self.context['request'].user
        
        if raid.points_awarded:
            raise serializers.ValidationError("Points have already been awarded for this raid")
        
        adjustments = raid.award_points(created_by=created_by)
        
        return {
            'raid': raid,
            'adjustments_created': len(adjustments),
            'total_points_awarded': sum(adj.points for adj in adjustments)
        }


class ItemSerializer(serializers.ModelSerializer):
    distribution_count = serializers.IntegerField(read_only=True)
    average_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    recent_distributions = serializers.SerializerMethodField()
    
    class Meta:
        model = Item
        fields = [
            'id', 'name', 'description', 'suggested_cost', 'rarity', 'is_active',
            'distribution_count', 'average_cost', 'recent_distributions',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_recent_distributions(self, obj):
        recent = obj.get_recent_distributions(limit=5)
        return LootDistributionListSerializer(recent, many=True).data
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['distribution_count'] = instance.distributions.count()
        data['average_cost'] = instance.get_average_cost()
        return data


class LootDistributionListSerializer(serializers.ModelSerializer):
    item = serializers.StringRelatedField()
    user = serializers.StringRelatedField()
    raid = serializers.StringRelatedField()
    distributed_by = serializers.StringRelatedField()
    total_cost = serializers.SerializerMethodField()
    
    class Meta:
        model = LootDistribution
        fields = [
            'id', 'item', 'user', 'character_name', 'point_cost', 'quantity',
            'total_cost', 'raid', 'distributed_by', 'distributed_at'
        ]
    
    def get_total_cost(self, obj):
        return obj.point_cost * obj.quantity


class LootDistributionDetailSerializer(serializers.ModelSerializer):
    item = ItemSerializer(read_only=True)
    item_id = serializers.PrimaryKeyRelatedField(
        source='item',
        queryset=Item.objects.filter(is_active=True),
        write_only=True
    )
    user = serializers.StringRelatedField(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        source='user',
        queryset=User.objects.all(),
        write_only=True
    )
    raid = serializers.StringRelatedField(read_only=True)
    raid_id = serializers.PrimaryKeyRelatedField(
        source='raid',
        queryset=Raid.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    distributed_by = serializers.StringRelatedField(read_only=True)
    total_cost = serializers.SerializerMethodField()
    
    class Meta:
        model = LootDistribution
        fields = [
            'id', 'item', 'item_id', 'user', 'user_id', 'character_name',
            'point_cost', 'quantity', 'total_cost', 'raid', 'raid_id',
            'notes', 'distributed_by', 'discord_message_id', 'discord_channel_id',
            'distributed_at'
        ]
        read_only_fields = ['distributed_at', 'distributed_by']
    
    def get_total_cost(self, obj):
        return obj.point_cost * obj.quantity
    
    def create(self, validated_data):
        validated_data['distributed_by'] = self.context['request'].user
        return super().create(validated_data)


class DiscordLootAwardSerializer(serializers.Serializer):
    """
    Serializer for Discord bot to award loot to players.
    Accepts character name or user ID for flexibility.
    """
    
    # Item identification
    item_name = serializers.CharField(
        max_length=100,
        help_text="Name of the item to award"
    )
    
    # Player identification (either character_name OR user_id required)
    character_name = serializers.CharField(
        max_length=64,
        required=False,
        help_text="Character name receiving the item"
    )
    user_id = serializers.IntegerField(
        required=False,
        help_text="User ID receiving the item (alternative to character_name)"
    )
    
    # Award details
    point_cost = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="DKP cost for this item"
    )
    quantity = serializers.IntegerField(
        default=1,
        min_value=1,
        help_text="Quantity of items to award"
    )
    
    # Optional context
    raid_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID of the raid where item was obtained"
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Additional notes"
    )
    
    # Discord context
    discord_message_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Discord message ID for reference"
    )
    discord_channel_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Discord channel ID where award was announced"
    )
    
    def validate(self, data):
        # Either character_name or user_id must be provided
        if not data.get('character_name') and not data.get('user_id'):
            raise serializers.ValidationError(
                "Either character_name or user_id must be provided"
            )
        
        if data.get('character_name') and data.get('user_id'):
            raise serializers.ValidationError(
                "Provide either character_name or user_id, not both"
            )
        
        return data
    
    def validate_item_name(self, value):
        try:
            self.item = Item.objects.get(name__iexact=value.strip(), is_active=True)
        except Item.DoesNotExist:
            raise serializers.ValidationError(f"Item '{value}' not found or inactive")
        return value
    
    def validate_character_name(self, value):
        if value:
            value = value.strip()
            try:
                character = Character.objects.get(name__iexact=value)
                self.user = character.user
                self.character_name = character.name
            except Character.DoesNotExist:
                raise serializers.ValidationError(f"Character '{value}' not found")
        return value
    
    def validate_user_id(self, value):
        if value:
            try:
                self.user = User.objects.get(id=value)
                # Get main character name for user
                main_char = self.user.characters.filter(is_active=True).first()
                self.character_name = main_char.name if main_char else self.user.username
            except User.DoesNotExist:
                raise serializers.ValidationError(f"User with ID {value} not found")
        return value
    
    def validate_raid_id(self, value):
        if value:
            try:
                self.raid = Raid.objects.get(id=value)
            except Raid.DoesNotExist:
                raise serializers.ValidationError(f"Raid with ID {value} not found")
        else:
            self.raid = None
        return value
    
    def validate_point_cost(self, value):
        if value < 0:
            raise serializers.ValidationError("Point cost cannot be negative")
        return value
    
    def create(self, validated_data):
        """Create the loot distribution using the class method"""
        discord_context = {
            'message_id': validated_data.get('discord_message_id', ''),
            'channel_id': validated_data.get('discord_channel_id', '')
        }
        
        distribution = LootDistribution.distribute_item(
            user=self.user,
            item=self.item,
            point_cost=validated_data['point_cost'],
            character_name=self.character_name,
            raid=getattr(self, 'raid', None),
            quantity=validated_data['quantity'],
            notes=validated_data.get('notes', ''),
            distributed_by=self.context['request'].user,
            discord_context=discord_context
        )
        
        return distribution


class UserBalanceSerializer(serializers.Serializer):
    """
    Serializer for Discord bot to check user DKP balance.
    """
    user_id = serializers.IntegerField(
        required=False,
        help_text="User ID to check balance for"
    )
    character_name = serializers.CharField(
        max_length=64,
        required=False,
        help_text="Character name to check balance for"
    )
    
    def validate(self, data):
        if not data.get('user_id') and not data.get('character_name'):
            raise serializers.ValidationError(
                "Either user_id or character_name must be provided"
            )
        return data
    
    def validate_user_id(self, value):
        if value:
            try:
                User.objects.get(id=value)
            except User.DoesNotExist:
                raise serializers.ValidationError(f"User with ID {value} not found")
        return value
    
    def validate_character_name(self, value):
        if value:
            try:
                Character.objects.get(name__iexact=value.strip())
            except Character.DoesNotExist:
                raise serializers.ValidationError(f"Character '{value}' not found")
        return value
    
    def get_user_info(self):
        """Get user and balance information"""
        from ...dkp.models import DKPManager
        
        if self.validated_data.get('user_id'):
            user = User.objects.get(id=self.validated_data['user_id'])
        else:
            character = Character.objects.get(name__iexact=self.validated_data['character_name'])
            user = character.user
        
        balance = DKPManager.get_user_balance(user)
        main_char = user.characters.filter(is_active=True).first()
        
        return {
            'user_id': user.id,
            'username': user.username,
            'main_character': main_char.name if main_char else None,
            'dkp_balance': balance,
            'character_count': user.characters.count()
        }


class LootAuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for audit log entries.
    Read-only for reviewing historical data.
    """
    performed_by = serializers.StringRelatedField()
    affected_user = serializers.StringRelatedField()
    item = serializers.StringRelatedField()
    distribution = serializers.StringRelatedField()
    raid = serializers.StringRelatedField()
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)
    summary = serializers.CharField(source='get_summary', read_only=True)
    
    class Meta:
        model = LootAuditLog
        fields = [
            'id', 'action_type', 'action_type_display', 'timestamp',
            'performed_by', 'affected_user', 'character_name',
            'item', 'distribution', 'raid', 'description', 'summary',
            'point_cost', 'quantity', 'old_values', 'new_values',
            'ip_address', 'discord_context'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields read-only
        for field in self.fields.values():
            field.read_only = True


class LootAuditLogListSerializer(serializers.ModelSerializer):
    """
    Compact serializer for audit log listings.
    """
    performed_by = serializers.StringRelatedField()
    affected_user = serializers.StringRelatedField()
    item_name = serializers.CharField(source='item.name', read_only=True)
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)
    summary = serializers.CharField(source='get_summary', read_only=True)
    
    class Meta:
        model = LootAuditLog
        fields = [
            'id', 'action_type', 'action_type_display', 'timestamp',
            'performed_by', 'affected_user', 'character_name',
            'item_name', 'description', 'summary', 'point_cost', 'quantity'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields read-only
        for field in self.fields.values():
            field.read_only = True


class AuditLogFilterSerializer(serializers.Serializer):
    """
    Serializer for audit log filtering parameters.
    """
    action_type = serializers.ChoiceField(
        choices=LootAuditLog.ACTION_TYPES,
        required=False,
        help_text="Filter by action type"
    )
    performed_by = serializers.CharField(
        required=False,
        help_text="Filter by username who performed the action"
    )
    affected_user = serializers.CharField(
        required=False,
        help_text="Filter by username affected by the action"
    )
    character_name = serializers.CharField(
        required=False,
        help_text="Filter by character name"
    )
    item_name = serializers.CharField(
        required=False,
        help_text="Filter by item name"
    )
    date_from = serializers.DateTimeField(
        required=False,
        help_text="Filter logs from this date (YYYY-MM-DD HH:MM:SS)"
    )
    date_to = serializers.DateTimeField(
        required=False,
        help_text="Filter logs to this date (YYYY-MM-DD HH:MM:SS)"
    )
    limit = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=1000,
        default=100,
        help_text="Maximum number of results to return"
    )