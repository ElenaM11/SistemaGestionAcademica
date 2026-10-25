from django.urls import path
from . import views

urlpatterns = [
    path("curso/<int:curso_id>/avisos/", views.docente_avisos, name="docente_avisos"),
    path("curso/<int:curso_id>/mensajes/", views.docente_mensajes, name="docente_mensajes"),
    path("curso/<int:curso_id>/clase/", views.docente_clase_iniciar, name="docente_clase_iniciar"),
    path("curso/<int:curso_id>/clase/<int:sesion_pk>/", views.docente_clase_sala, name="docente_clase_sala"),
    path("curso/<int:curso_id>/clase/<int:sesion_pk>/finalizar/", views.docente_clase_finalizar, name="docente_clase_finalizar"),
]
