from django.contrib import admin
from django.utils.html import format_html
from .models import Character, Rank, CharacterOwnership


@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ['name', 'level', 'color_display', 'character_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'description']
    ordering = ['level']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'level', 'color')
        }),
        ('Details', {
            'fields': ('description', 'permissions'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'character_count']
    
    def color_display(self, obj):
        return format_html(
            '<span style="background-color: {}; padding: 2px 10px; color: white; border-radius: 3px;">{}</span>',
            obj.color,
            obj.color
        )
    color_display.short_description = 'Color'
    
    def character_count(self, obj):
        # Character count not available since rank-character relationship was removed
        return 0
    character_count.short_description = 'Characters'


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ['name', 'character_class', 'level', 'status', 'user', 'is_active', 'created_at']
    list_filter = ['character_class', 'status', 'is_active', 'level', 'created_at']
    search_fields = ['name', 'user__username', 'user__email', 'description']
    ordering = ['name']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'character_class', 'level', 'status', 'user')
        }),
        ('Details', {
            'fields': ('description', 'is_active'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user')
    


@admin.register(CharacterOwnership)
class CharacterOwnershipAdmin(admin.ModelAdmin):
    list_display = ['character', 'transfer_display', 'reason', 'transfer_date', 'transferred_by']
    list_filter = ['reason', 'transfer_date']
    search_fields = ['character__name', 'previous_owner__username', 'new_owner__username', 'notes']
    date_hierarchy = 'transfer_date'
    ordering = ['-transfer_date']
    
    fieldsets = (
        ('Transfer Details', {
            'fields': ('character', 'previous_owner', 'new_owner', 'reason')
        }),
        ('Additional Information', {
            'fields': ('notes', 'transferred_by'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('transfer_date',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['transfer_date']
    autocomplete_fields = ['character', 'previous_owner', 'new_owner', 'transferred_by']
    
    def transfer_display(self, obj):
        if obj.previous_owner:
            return format_html(
                '<span style="color: #666;">{}</span> → <span style="color: #333;">{}</span>',
                obj.previous_owner.username,
                obj.new_owner.username
            )
        return format_html(
            '<span style="color: green;">Created for {}</span>',
            obj.new_owner.username
        )
    transfer_display.short_description = 'Transfer'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('character', 'previous_owner', 'new_owner', 'transferred_by')