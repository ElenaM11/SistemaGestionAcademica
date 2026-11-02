from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/chat/<int:otro_id>/", consumers.ChatConsumer.as_asgi()),
    path("ws/bandeja/", consumers.BandejaConsumer.as_asgi()),
]