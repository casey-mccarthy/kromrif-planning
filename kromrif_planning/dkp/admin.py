from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import UserPointsSummary, PointAdjustment, DKPManager


@admin.register(UserPointsSummary)
class UserPointsSummaryAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'total_points_display', 'earned_points', 'spent_points', 
        'last_updated', 'adjustment_count'
    ]
    list_filter = ['last_updated', 'created_at']
    search_fields = ['user__username', 'user__email']
    ordering = ['-total_points']
    readonly_fields = ['created_at', 'last_updated', 'adjustment_count']
    
    fieldsets = (
        (None, {
            'fields': ('user', 'total_points', 'earned_points', 'spent_points')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_updated', 'adjustment_count'),
            'classes': ('collapse',)
        }),
    )
    
    def total_points_display(self, obj):
        if obj.total_points >= 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{:.2f} DKP</span>',
                obj.total_points
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">{:.2f} DKP</span>',
                obj.total_points
            )
    total_points_display.short_description = 'Total Points'
    total_points_display.admin_order_field = 'total_points'
    
    def adjustment_count(self, obj):
        return obj.user.point_adjustments.count()
    adjustment_count.short_description = 'Adjustments'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user')
    
    actions = ['recalculate_summaries']
    
    def recalculate_summaries(self, request, queryset):
        """Action to recalculate selected summaries"""
        count = 0
        for summary in queryset:
            summary.recalculate_from_adjustments()
            count += 1
        
        self.message_user(
            request,
            f'Successfully recalculated {count} user point summaries.'
        )
    recalculate_summaries.short_description = 'Recalculate selected summaries'


@admin.register(PointAdjustment)
class PointAdjustmentAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'points_display', 'adjustment_type_display', 'character_name',
        'description_short', 'created_at', 'created_by', 'is_locked'
    ]
    list_filter = [
        'adjustment_type', 'is_locked', 'created_at', 'created_by'
    ]
    search_fields = [
        'user__username', 'user__email', 'description', 'character_name'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Adjustment Details', {
            'fields': ('user', 'points', 'adjustment_type', 'description')
        }),
        ('Character Information', {
            'fields': ('character_name',),
            'classes': ('collapse',)
        }),
        ('Administrative', {
            'fields': ('created_by', 'is_locked'),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at']
    autocomplete_fields = ['user', 'created_by']
    
    def points_display(self, obj):
        if obj.points > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">+{:.2f}</span>',
                obj.points
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">{:.2f}</span>',
                obj.points
            )
    points_display.short_description = 'Points'
    points_display.admin_order_field = 'points'
    
    def adjustment_type_display(self, obj):
        colors = {
            'raid_attendance': '#28a745',  # green
            'raid_bonus': '#17a2b8',      # blue
            'item_purchase': '#dc3545',   # red
            'manual_adjustment': '#6c757d', # gray
            'decay': '#fd7e14',           # orange
            'bonus': '#20c997',           # teal
            'penalty': '#e83e8c',         # pink
            'transfer': '#6f42c1',        # purple
        }
        color = colors.get(obj.adjustment_type, '#000000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_adjustment_type_display()
        )
    adjustment_type_display.short_description = 'Type'
    adjustment_type_display.admin_order_field = 'adjustment_type'
    
    def description_short(self, obj):
        if len(obj.description) > 50:
            return obj.description[:50] + '...'
        return obj.description
    description_short.short_description = 'Description'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'created_by')
    
    def has_change_permission(self, request, obj=None):
        # Prevent changes to locked adjustments unless user has special permission
        if obj and obj.is_locked:
            return request.user.has_perm('dkp.can_modify_locked')
        return super().has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of locked adjustments unless user has special permission
        if obj and obj.is_locked:
            return request.user.has_perm('dkp.can_modify_locked')
        return super().has_delete_permission(request, obj)
    
    actions = ['lock_adjustments', 'unlock_adjustments']
    
    def lock_adjustments(self, request, queryset):
        """Action to lock selected adjustments"""
        if not request.user.has_perm('dkp.can_lock_adjustments'):
            self.message_user(
                request,
                'You do not have permission to lock adjustments.',
                level='ERROR'
            )
            return
        
        count = queryset.update(is_locked=True)
        self.message_user(
            request,
            f'Successfully locked {count} adjustments.'
        )
    lock_adjustments.short_description = 'Lock selected adjustments'
    
    def unlock_adjustments(self, request, queryset):
        """Action to unlock selected adjustments"""
        if not request.user.has_perm('dkp.can_modify_locked'):
            self.message_user(
                request,
                'You do not have permission to unlock adjustments.',
                level='ERROR'
            )
            return
        
        count = queryset.update(is_locked=False)
        self.message_user(
            request,
            f'Successfully unlocked {count} adjustments.'
        )
    unlock_adjustments.short_description = 'Unlock selected adjustments'
