from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Notification, NotificationRead
from .serializers import NotificationSerializer

class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = Notification.objects.filter(
            Q(target_type='all') | Q(recipient=user)
        ).order_by('-created_at')

        reads = NotificationRead.objects.filter(
            user=user,
            notification__in=qs
        ).values('notification_id', 'read_at')
        read_ids = {r['notification_id'] for r in reads}
        read_times = {r['notification_id']: r['read_at'].isoformat() for r in reads}

        filter_param = request.query_params.get('filter', 'all')
        if filter_param == 'unread':
            qs = [n for n in qs if n.id not in read_ids]
        elif filter_param == 'broadcast':
            qs = qs.filter(target_type='all')

        serializer = NotificationSerializer(
            qs,
            many=True,
            context={
                'request': request,
                'read_ids': read_ids,
                'read_times': read_times
            }
        )
        unread_count = sum(1 for item in serializer.data if not item['is_read'])

        return Response({
            'notifications': serializer.data,
            'unread_count': unread_count,
            'total_count': len(serializer.data)
        })

class NotificationUnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        eligible_qs = Notification.objects.filter(
            Q(target_type='all') | Q(recipient=user)
        )
        total_eligible = eligible_qs.count()
        read_count = NotificationRead.objects.filter(
            user=user,
            notification__in=eligible_qs
        ).count()
        unread = max(0, total_eligible - read_count)
        return Response({'unread_count': unread})

class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        notif = get_object_or_404(
            Notification.objects.filter(Q(target_type='all') | Q(recipient=user)),
            id=pk
        )
        NotificationRead.objects.get_or_create(notification=notif, user=user)
        return Response({
            'status': 'success',
            'message': "Bildirishnoma o'qilgan deb belgilandi."
        })

class NotificationMarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        eligible_qs = Notification.objects.filter(
            Q(target_type='all') | Q(recipient=user)
        )
        already_read_ids = set(NotificationRead.objects.filter(
            user=user,
            notification__in=eligible_qs
        ).values_list('notification_id', flat=True))

        unread_notifications = eligible_qs.exclude(id__in=already_read_ids)
        new_reads = [
            NotificationRead(notification=n, user=user)
            for n in unread_notifications
        ]
        if new_reads:
            NotificationRead.objects.bulk_create(new_reads, ignore_conflicts=True)

        return Response({
            'status': 'success',
            'marked_count': len(new_reads),
            'message': f"{len(new_reads)} ta bildirishnoma o'qilgan deb belgilandi."
        })
