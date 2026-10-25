from django.urls import path
from . import views

urlpatterns = [
    path("clases-en-vivo/", views.estudiante_clases_vivo, name="estudiante_clases_vivo"),
    path("clase/<int:sesion_pk>/", views.estudiante_clase_sala, name="estudiante_clase_sala"),
    path("clase/<int:sesion_pk>/salir/", views.estudiante_clase_salir, name="estudiante_clase_salir"),
    path("avisos/", views.estudiante_avisos, name="estudiante_avisos"),
    path("mensajes/", views.estudiante_mensajes, name="estudiante_mensajes"),
]
