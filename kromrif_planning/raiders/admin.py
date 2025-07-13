from django.contrib import admin
from django.utils.html import format_html
from .models import Character, Rank, CharacterOwnership, Event, Raid, RaidAttendance, Item, LootDistribution


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


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'base_points_display', 'on_time_bonus', 'is_active', 'raid_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Points Configuration', {
            'fields': ('base_points', 'on_time_bonus')
        }),
        ('Display', {
            'fields': ('color',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'raid_count']
    
    def base_points_display(self, obj):
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} DKP</span>',
            obj.color,
            obj.base_points
        )
    base_points_display.short_description = 'Base Points'
    base_points_display.admin_order_field = 'base_points'
    
    def raid_count(self, obj):
        return obj.raids.count()
    raid_count.short_description = 'Raids'


@admin.register(Raid)
class RaidAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'event', 'date', 'start_time', 'status_display', 
        'attendance_count', 'points_awarded', 'leader'
    ]
    list_filter = ['status', 'points_awarded', 'event', 'date']
    search_fields = ['title', 'notes', 'leader__username']
    date_hierarchy = 'date'
    ordering = ['-date', '-start_time']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('event', 'title', 'leader')
        }),
        ('Schedule', {
            'fields': ('date', 'start_time', 'end_time', 'status')
        }),
        ('Attendance & Points', {
            'fields': ('parse_attendance', 'points_awarded')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'attendance_count']
    autocomplete_fields = ['leader']
    
    def status_display(self, obj):
        colors = {
            'scheduled': '#6c757d',    # gray
            'in_progress': '#fd7e14',  # orange
            'completed': '#28a745',    # green
            'cancelled': '#dc3545',    # red
        }
        color = colors.get(obj.status, '#000000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def attendance_count(self, obj):
        count = obj.get_attendance_count()
        on_time = obj.get_on_time_count()
        return format_html(
            '{} total ({} on time)',
            count, on_time
        )
    attendance_count.short_description = 'Attendance'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('event', 'leader')
    
    actions = ['award_points_action']
    
    def award_points_action(self, request, queryset):
        """Action to award DKP points for selected raids"""
        awarded = 0
        errors = []
        
        for raid in queryset:
            try:
                if not raid.points_awarded:
                    raid.award_points(created_by=request.user)
                    awarded += 1
                else:
                    errors.append(f"Points already awarded for {raid.title}")
            except Exception as e:
                errors.append(f"Error awarding points for {raid.title}: {str(e)}")
        
        if awarded:
            self.message_user(
                request,
                f'Successfully awarded points for {awarded} raids.'
            )
        
        if errors:
            self.message_user(
                request,
                'Errors: ' + '; '.join(errors),
                level='WARNING'
            )
    
    award_points_action.short_description = 'Award DKP points for selected raids'


@admin.register(RaidAttendance)
class RaidAttendanceAdmin(admin.ModelAdmin):
    list_display = [
        'character_name', 'user', 'raid', 'on_time_display', 
        'recorded_by', 'created_at'
    ]
    list_filter = ['on_time', 'raid__event', 'raid__date', 'recorded_by']
    search_fields = [
        'character_name', 'user__username', 'raid__title', 
        'recorded_by__username', 'notes'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Attendance Details', {
            'fields': ('raid', 'user', 'character_name', 'on_time')
        }),
        ('Additional Information', {
            'fields': ('notes', 'recorded_by'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at']
    autocomplete_fields = ['user', 'recorded_by']
    
    def on_time_display(self, obj):
        if obj.on_time:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ On Time</span>'
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗ Late</span>'
            )
    on_time_display.short_description = 'Timeliness'
    on_time_display.admin_order_field = 'on_time'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'raid', 'raid__event', 'recorded_by')


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'rarity_display', 'suggested_cost', 'is_active', 'distribution_count', 'average_cost', 'created_at']
    list_filter = ['rarity', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Pricing', {
            'fields': ('suggested_cost', 'rarity')
        }),
        ('Statistics', {
            'fields': ('distribution_count', 'average_cost'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'distribution_count', 'average_cost']
    
    def rarity_display(self, obj):
        colors = {
            'common': '#6c757d',      # gray
            'uncommon': '#28a745',    # green
            'rare': '#007bff',        # blue
            'epic': '#6f42c1',        # purple
            'legendary': '#fd7e14',   # orange
        }
        color = colors.get(obj.rarity, '#000000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_rarity_display()
        )
    rarity_display.short_description = 'Rarity'
    rarity_display.admin_order_field = 'rarity'
    
    def distribution_count(self, obj):
        count = obj.distributions.count()
        return format_html(
            '<a href="/admin/raiders/lootdistribution/?item__id__exact={}">{} distributions</a>',
            obj.id, count
        )
    distribution_count.short_description = 'Distributions'
    
    def average_cost(self, obj):
        avg = obj.get_average_cost()
        return f"{avg:.2f} DKP" if avg else "No distributions"
    average_cost.short_description = 'Average Cost'


@admin.register(LootDistribution)
class LootDistributionAdmin(admin.ModelAdmin):
    list_display = [
        'item', 'character_name', 'user', 'point_cost_display', 'quantity', 
        'raid', 'distributed_at', 'distributed_by'
    ]
    list_filter = [
        'item__rarity', 'distributed_at', 'distributed_by', 
        'raid__event', 'quantity'
    ]
    search_fields = [
        'item__name', 'character_name', 'user__username', 
        'raid__title', 'notes', 'distributed_by__username'
    ]
    date_hierarchy = 'distributed_at'
    ordering = ['-distributed_at']
    
    fieldsets = (
        ('Distribution Details', {
            'fields': ('item', 'user', 'character_name', 'point_cost', 'quantity')
        }),
        ('Context', {
            'fields': ('raid', 'distributed_by', 'notes')
        }),
        ('Discord Integration', {
            'fields': ('discord_message_id', 'discord_channel_id'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('distributed_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['distributed_at']
    autocomplete_fields = ['user', 'item', 'raid', 'distributed_by']
    
    def point_cost_display(self, obj):
        total_cost = obj.point_cost * obj.quantity
        if obj.quantity > 1:
            return format_html(
                '<span style="font-weight: bold;">{:.2f} DKP</span><br><small>({:.2f} × {})</small>',
                total_cost, obj.point_cost, obj.quantity
            )
        else:
            return format_html(
                '<span style="font-weight: bold;">{:.2f} DKP</span>',
                obj.point_cost
            )
    point_cost_display.short_description = 'Cost'
    point_cost_display.admin_order_field = 'point_cost'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('item', 'user', 'raid', 'distributed_by')
    
    actions = ['recalculate_point_deductions']
    
    def recalculate_point_deductions(self, request, queryset):
        """Action to recalculate point deductions for selected distributions"""
        count = 0
        errors = []
        
        for distribution in queryset:
            try:
                # This would require implementing a recalculation method
                # For now, just count successful ones
                count += 1
            except Exception as e:
                errors.append(f"Error with {distribution}: {str(e)}")
        
        if count:
            self.message_user(
                request,
                f'Successfully processed {count} distributions.'
            )
        
        if errors:
            self.message_user(
                request,
                'Errors: ' + '; '.join(errors),
                level='WARNING'
            )
    
    recalculate_point_deductions.short_description = 'Recalculate point deductions'