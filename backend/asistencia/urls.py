from django.urls import path
from . import views, views_historial

urlpatterns = [
    path("", views.docente_asistencia, name="docente_asistencia"),
    path("historial/", views_historial.docente_asistencia_historial, name="docente_asistencia_historial"),
]
