from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import Character, Rank, CharacterOwnership, Event, Raid, RaidAttendance

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