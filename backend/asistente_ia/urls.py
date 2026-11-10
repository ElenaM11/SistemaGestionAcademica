from django.urls import path
from . import views

urlpatterns = [
    path(
        "estudiante/cuestionario/<int:actividad_id>/verificar/",
        views.verificar_respuesta,
        name="estudiante_cuestionario_verificar",
    ),
    path(
        "estudiante/cuestionario/revisar-texto/",
        views.revisar_texto,
        name="estudiante_cuestionario_revisar_texto",
    ),
]