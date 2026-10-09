"""Publico las rutas del módulo académico solicitadas para la aplicación web."""

from django.urls import path

from rol.views import admin_dashboard
from usuarios.views import admin_register_user

from .page_views import (
    asignar_docente_pagina, catalogo_cursos_pagina, catalogos_pagina,
    estudiantes_curso_pagina, inscripciones_pagina, paralelos_pagina,
)


urlpatterns = [
    path('admin/dashboard/', admin_dashboard, name='admin_dashboard_alias'),
    path('admin/registro/', admin_register_user, name='admin_register_user'),
    path('admin/cursos/catalogo/', catalogo_cursos_pagina, name='admin_catalogo_cursos'),
    path('admin/cursos/catalogos/', catalogos_pagina, name='admin_catalogos'),
    path('admin/cursos/paralelos/', paralelos_pagina, name='admin_paralelos'),
    path('admin/cursos/asignar-docente/', asignar_docente_pagina, name='admin_asignar_docente'),
    path('admin/cursos/inscripciones/', inscripciones_pagina, name='admin_inscripciones'),
    path('docente/cursos/<int:curso_id>/estudiantes/', estudiantes_curso_pagina, name='docente_estudiantes_curso'),
]
