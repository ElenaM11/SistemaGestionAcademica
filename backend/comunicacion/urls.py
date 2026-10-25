from django.urls import path
from . import views

urlpatterns = [
    path("clase/<int:sesion_pk>/token/", views.token_livekit, name="comunicacion_token"),
]
