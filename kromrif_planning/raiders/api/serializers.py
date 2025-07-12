from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import Character, Rank, CharacterOwnership

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
    character_type = serializers.SerializerMethodField()
    
    class Meta:
        model = Character
        fields = [
            'id', 'name', 'character_class', 'level', 'status',
            'user', 'character_type', 'is_active', 'created_at'
        ]
    
    def get_character_type(self, obj):
        if obj.is_main:
            alt_count = obj.alt_characters.count()
            return f"Main ({alt_count} alts)" if alt_count > 0 else "Main"
        return f"Alt of {obj.main_character.name}"


class CharacterDetailSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        default=serializers.CurrentUserDefault()
    )
    main_character = serializers.PrimaryKeyRelatedField(
        queryset=Character.objects.all(),
        required=False,
        allow_null=True
    )
    alt_characters = CharacterListSerializer(many=True, read_only=True)
    ownership_history = serializers.SerializerMethodField()
    
    class Meta:
        model = Character
        fields = [
            'id', 'name', 'character_class', 'level', 'status',
            'user', 'main_character', 'alt_characters',
            'description', 'is_active', 'ownership_history',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_ownership_history(self, obj):
        history = obj.ownership_history.all()[:5]  # Last 5 transfers
        return CharacterOwnershipSerializer(history, many=True).data
    
    def validate_main_character(self, value):
        if value and value == self.instance:
            raise serializers.ValidationError("A character cannot be its own main character.")
        return value
    
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