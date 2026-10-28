from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Notification, NotificationRead

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'type_badge', 'target_display', 'reads_status', 'created_at')
    list_filter = ('type', 'target_type', 'created_at')
    search_fields = ('title', 'message', 'recipient__username')
    ordering = ('-created_at',)
    fields = ('title', 'type', 'target_type', 'recipient', 'message')

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def type_badge(self, obj):
        colors = {
            'info': '#388BFD',
            'success': '#3FB950',
            'warning': '#D29922',
            'danger': '#F85149',
        }
        color = colors.get(obj.type, '#388BFD')
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 11px;">{}</span>',
            color,
            obj.get_type_display()
        )
    type_badge.short_description = "Turi"

    def target_display(self, obj):
        if obj.target_type == 'all':
            return mark_safe('<span style="color: #388BFD; font-weight: 600;">📢 Barcha foydalanuvchilar</span>')
        elif obj.recipient:
            return format_html('<span style="color: #A371F7; font-weight: 600;">👤 {}</span>', obj.recipient.username)
        return "—"
    target_display.short_description = "Qabul qiluvchi"

    def reads_status(self, obj):
        count = obj.reads.count()
        return format_html('<b>{}</b> kishi o\'qidi', count)
    reads_status.short_description = "O'qilganlar"

@admin.register(NotificationRead)
class NotificationReadAdmin(admin.ModelAdmin):
    list_display = ('notification', 'user', 'read_at')
    list_filter = ('read_at',)
    search_fields = ('notification__title', 'user__username')
    ordering = ('-read_at',)
    readonly_fields = ('notification', 'user', 'read_at')

    def has_add_permission(self, request):
        return False
