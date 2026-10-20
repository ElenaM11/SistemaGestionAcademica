# notificaciones/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.lista, name="notificaciones"),
    path("leer-todas/", views.marcar_todas, name="notificaciones_leer_todas"),
]