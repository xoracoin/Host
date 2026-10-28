from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/bots/(?P<file_id>\d+)/logs/?$', consumers.BotLogsConsumer.as_asgi()),
]
