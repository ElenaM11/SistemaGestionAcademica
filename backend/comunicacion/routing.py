from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("ws/chat/<int:paralelo_id>/<int:otro_id>/", consumers.ChatConsumer.as_asgi()),
]
