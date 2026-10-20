from django.urls import path
from . import views, views_entregas

urlpatterns = [
    path("", views.docente_actividades, name="docente_actividades"),
    path("<int:pk>/editar/", views.docente_actividad_editar, name="docente_actividad_editar"),
    path("<int:pk>/eliminar/", views.docente_actividad_eliminar, name="docente_actividad_eliminar"),
    # Ruta para ver la lista de entregas y calificar 
    path("<int:pk>/entregas/", views_entregas.docente_entregas, name="docente_entregas"),
    # Ruta para descargar el archivo
    path("<int:pk>/entregas/<int:entrega_id>/archivo/", views_entregas.docente_entrega_archivo, name="docente_entrega_archivo"),
]