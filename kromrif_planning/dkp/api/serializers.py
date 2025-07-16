"""
DKP API serializers for REST API endpoints.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal
from ..models import UserPointsSummary, PointAdjustment, DKPManager

User = get_user_model()


class UserPointsSummarySerializer(serializers.ModelSerializer):
    """Serializer for user DKP summary information."""
    
    user = serializers.StringRelatedField()
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserPointsSummary
        fields = [
            'id', 'user', 'user_id', 'username', 'total_points', 
            'earned_points', 'spent_points', 'last_updated', 'created_at'
        ]
        read_only_fields = ['last_updated', 'created_at']


class PointAdjustmentSerializer(serializers.ModelSerializer):
    """Serializer for point adjustment records."""
    
    user = serializers.StringRelatedField()
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    created_by = serializers.StringRelatedField()
    adjustment_type_display = serializers.CharField(source='get_adjustment_type_display', read_only=True)
    
    class Meta:
        model = PointAdjustment
        fields = [
            'id', 'user', 'user_id', 'username', 'points', 'adjustment_type',
            'adjustment_type_display', 'description', 'character_name',
            'created_at', 'created_by', 'is_locked'
        ]
        read_only_fields = ['created_at', 'created_by', 'is_locked']


class PointAdjustmentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new point adjustments."""
    
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    
    class Meta:
        model = PointAdjustment
        fields = [
            'user', 'points', 'adjustment_type', 'description', 'character_name'
        ]
    
    def create(self, validated_data):
        # Set created_by to the requesting user
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class BulkPointAwardSerializer(serializers.Serializer):
    """Serializer for bulk point awards (e.g., raid attendance)."""
    
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="List of user IDs to award points to"
    )
    points = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        help_text="Points to award each user"
    )
    adjustment_type = serializers.ChoiceField(
        choices=PointAdjustment.ADJUSTMENT_TYPES,
        help_text="Type of point adjustment"
    )
    description = serializers.CharField(
        max_length=500,
        help_text="Description of the point award"
    )
    
    def validate_user_ids(self, value):
        """Validate that all user IDs exist."""
        existing_users = User.objects.filter(id__in=value).values_list('id', flat=True)
        missing_users = set(value) - set(existing_users)
        if missing_users:
            raise serializers.ValidationError(
                f"The following user IDs do not exist: {list(missing_users)}"
            )
        return value
    
    def create(self, validated_data):
        """Create point adjustments for all specified users."""
        user_ids = validated_data['user_ids']
        points = validated_data['points']
        adjustment_type = validated_data['adjustment_type']
        description = validated_data['description']
        created_by = self.context['request'].user
        
        users = User.objects.filter(id__in=user_ids)
        adjustments = []
        
        for user in users:
            adjustment = PointAdjustment.objects.create(
                user=user,
                points=points,
                adjustment_type=adjustment_type,
                description=description,
                created_by=created_by
            )
            adjustments.append(adjustment)
        
        return adjustments


class ItemPurchaseSerializer(serializers.Serializer):
    """Serializer for processing item purchases with DKP."""
    
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    item_cost = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        help_text="Cost of the item in DKP"
    )
    item_name = serializers.CharField(
        max_length=200,
        help_text="Name of the item being purchased"
    )
    character_name = serializers.CharField(
        max_length=64,
        required=False,
        help_text="Character name for the purchase (optional)"
    )
    
    def validate(self, data):
        """Validate that the user can afford the item."""
        user = data['user']
        item_cost = data['item_cost']
        
        if not DKPManager.can_afford(user, item_cost):
            current_balance = DKPManager.get_user_balance(user)
            raise serializers.ValidationError(
                f"User {user.username} cannot afford this item. "
                f"Current balance: {current_balance}, Item cost: {item_cost}"
            )
        
        return data
    
    def create(self, validated_data):
        """Process the item purchase."""
        user = validated_data['user']
        item_cost = validated_data['item_cost']
        item_name = validated_data['item_name']
        character_name = validated_data.get('character_name', '')
        created_by = self.context['request'].user
        
        # Create the purchase adjustment
        adjustment = DKPManager.process_item_purchase(
            user=user,
            item_cost=item_cost,
            item_name=item_name,
            created_by=created_by
        )
        
        # Set character name if provided
        if character_name:
            adjustment.character_name = character_name
            adjustment.save()
        
        return adjustment


class UserBalanceSerializer(serializers.Serializer):
    """Serializer for checking user DKP balance."""
    
    user_id = serializers.IntegerField()
    username = serializers.CharField(read_only=True)
    current_balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    can_afford = serializers.SerializerMethodField()
    
    def __init__(self, *args, **kwargs):
        self.check_amount = kwargs.pop('check_amount', None)
        super().__init__(*args, **kwargs)
    
    def get_can_afford(self, obj):
        """Check if user can afford a specific amount."""
        if self.check_amount is not None:
            return obj['current_balance'] >= self.check_amount
        return None


class DKPLeaderboardSerializer(serializers.Serializer):
    """Serializer for DKP leaderboard data."""
    
    rank = serializers.IntegerField()
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    total_points = serializers.DecimalField(max_digits=10, decimal_places=2)
    earned_points = serializers.DecimalField(max_digits=10, decimal_places=2)
    spent_points = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    def to_representation(self, instance):
        # Handle both UserPointsSummary instances and dict data
        if hasattr(instance, 'user'):
            # UserPointsSummary instance
            return {
                'rank': getattr(instance, 'rank', 0),
                'user_id': instance.user.id,
                'username': instance.user.username,
                'total_points': instance.total_points,
                'earned_points': instance.earned_points,
                'spent_points': instance.spent_points,
            }
        else:
            # Dict data
            return super().to_representation(instance)


class DKPStatsSerializer(serializers.Serializer):
    """Serializer for DKP system statistics."""
    
    total_users = serializers.IntegerField()
    total_points_in_system = serializers.DecimalField(max_digits=15, decimal_places=2)
    average_points_per_user = serializers.DecimalField(max_digits=10, decimal_places=2)
    recent_adjustments_count = serializers.IntegerField()
    top_earner = serializers.CharField()
    top_spender = serializers.CharField()