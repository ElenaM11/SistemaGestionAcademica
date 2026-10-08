from django.urls import path
from . import views

urlpatterns = [
    path('panel/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('docente/cursos/', views.docente_dashboard, name='docente_dashboard'),
    path('estudiante/cursos/', views.estudiante_dashboard, name='estudiante_dashboard'),
]