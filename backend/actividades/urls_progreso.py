from django.urls import path
from . import views_progreso

urlpatterns = [
    path("", views_progreso.docente_progreso, name="docente_progreso"),
]