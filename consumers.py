import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs

User = get_user_model()

class BotLogsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.file_id = self.scope['url_route']['kwargs']['file_id']
        self.room_group_name = f"bot_logs_{self.file_id}"

        user = await self.get_user_from_scope()
        if not user or user.is_anonymous:
            await self.close(code=4401)
            return

        self.user = user

        has_access = await self.check_file_access(user, self.file_id)
        if not has_access:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        await self.send(text_data=json.dumps({
            'type': 'system',
            'message': f"Log oqimiga ulandi (Bot #{self.file_id})"
        }))

        recent_logs = await self.get_recent_logs(self.file_id)
        for log in recent_logs:
            await self.send(text_data=json.dumps({
                'type': 'log',
                'line': log['log_line'],
                'level': log['level'],
                'timestamp': log['timestamp']
            }))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')
            if action == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            elif action == 'get_stats':
                stats = await self.get_stats(self.file_id)
                await self.send(text_data=json.dumps({'type': 'stats', 'data': stats}))
        except Exception:
            pass

    async def bot_log_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'log',
            'line': event['line'],
            'level': event.get('level', 'INFO'),
            'timestamp': event.get('timestamp')
        }))

    async def bot_status_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status',
            'status': event['status'],
            'message': event.get('message', '')
        }))

    async def bot_stats_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'stats',
            'data': event['data']
        }))

    @database_sync_to_async
    def get_stats(self, file_id):
        from .models import BotProcess
        from .telemetry import get_bot_telemetry
        proc = BotProcess.objects.filter(file_id=file_id).first()
        if proc:
            return get_bot_telemetry(proc)
        return {
            'status': 'stopped',
            'cpu_percent': 0.0,
            'memory_mb': 0.0,
            'max_memory_mb': 128.0,
            'cpu_limit': 0.25,
            'uptime_seconds': 0,
            'restart_count': 0,
            'auto_restart': True
        }

    @database_sync_to_async
    def get_user_from_scope(self):
        user = self.scope.get('user')
        if user and user.is_authenticated:
            return user

        query_string = self.scope.get('query_string', b'').decode('utf-8')
        params = parse_qs(query_string)
        token_str = params.get('token', [None])[0]
        if token_str:
            try:
                access_token = AccessToken(token_str)
                user_id = access_token['user_id']
                return User.objects.get(id=user_id)
            except Exception:
                return AnonymousUser()
        return AnonymousUser()

    @database_sync_to_async
    def check_file_access(self, user, file_id):
        from apps.filemanager.models import File
        return File.objects.filter(id=file_id, owner=user).exists()

    @database_sync_to_async
    def get_recent_logs(self, file_id):
        from apps.botengine.models import BotProcess, BotLog
        process = BotProcess.objects.filter(file_id=file_id).first()
        if not process:
            return []
        logs = BotLog.objects.filter(bot_process=process).order_by('-timestamp')[:60]
        result = []
        for l in reversed(list(logs)):
            result.append({
                'log_line': l.log_line,
                'level': l.level,
                'timestamp': l.timestamp.strftime('%H:%M:%S')
            })
        return result
