from django.urls import path
from . import views

urlpatterns = [
    path("", views.docente_materiales, name="docente_materiales"),
    path("<int:pk>/editar/", views.docente_material_editar, name="docente_material_editar"),
    path("<int:pk>/eliminar/", views.docente_material_eliminar, name="docente_material_eliminar"),
]