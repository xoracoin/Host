from rest_framework import serializers
from .models import Notification, NotificationRead

class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()
    read_at = serializers.SerializerMethodField()
    formatted_type = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'type', 'formatted_type',
            'target_type', 'created_at', 'is_read', 'read_at'
        ]

    def get_is_read(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if not user or not user.is_authenticated:
            return False
        read_ids = self.context.get('read_ids')
        if read_ids is not None:
            return obj.id in read_ids
        return obj.is_read_by(user)

    def get_read_at(self, obj):
        user = self.context.get('request').user if self.context.get('request') else None
        if not user or not user.is_authenticated:
            return None
        read_times = self.context.get('read_times')
        if read_times is not None:
            return read_times.get(obj.id)
        record = obj.reads.filter(user=user).first()
        return record.read_at.isoformat() if record else None
