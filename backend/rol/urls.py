from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('panel/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('panel/registro/', views.admin_register_user, name='admin_register_user'),
    path('docente/cursos/', views.docente_dashboard, name='docente_dashboard'),
    path('estudiante/cursos/', views.estudiante_dashboard, name='estudiante_dashboard'),
]