from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('panel/registro/', views.admin_register_user, name='admin_register_user'),
    path('panel/api/codigo-estudiante/', views.api_codigo_estudiante, name='api_codigo_estudiante'),
    path('panel/credenciales/', views.admin_credenciales, name='admin_credenciales'),
    path('panel/credenciales/limpiar/', views.admin_credenciales_limpiar, name='admin_credenciales_limpiar'),
    path('panel/usuarios/<int:id_usuario>/editar/', views.admin_edit_user, name='admin_edit_user'),
    path('panel/usuarios/<int:id_usuario>/estado/', views.admin_toggle_estado, name='admin_toggle_estado'),
    path('panel/usuarios/<int:id_usuario>/reset-password/', views.admin_reset_password, name='admin_reset_password'),
    path('perfil/', views.perfil, name='perfil'),
    path('cambiar-password/', views.cambiar_password, name='cambiar_password'),
]