from django.urls import path

from .views import (
    asignar_docente, catalogo_cursos, catalogo_simple, cursos_del_docente,
    curso_detalle, docentes_por_idioma, estudiantes_del_curso,
    estudiantes_del_paralelo, idiomas_docente, inscripciones, mis_cursos,
    paralelo_detalle, paralelos,
)


urlpatterns = [
    path('admin/cursos/catalogo/', catalogo_cursos, name='api-catalogo-cursos'),
    path('admin/cursos/catalogo/<int:curso_id>/', curso_detalle, name='api-curso-detalle'),
    path('admin/cursos/catalogos/<str:catalogo>/', catalogo_simple, name='api-catalogo-simple'),
    path('admin/cursos/idiomas/<int:idioma_id>/docentes/', docentes_por_idioma, name='api-docentes-idioma'),
    path('admin/docentes/<int:docente_id>/idiomas/', idiomas_docente, name='api-docente-idiomas'),
    path('admin/cursos/paralelos/', paralelos, name='api-paralelos'),
    path('admin/cursos/paralelos/<int:paralelo_id>/', paralelo_detalle, name='api-paralelo-detalle'),
    path('admin/cursos/paralelos/<int:paralelo_id>/asignar-docente/', asignar_docente, name='api-asignar-docente'),
    path('admin/cursos/inscripciones/', inscripciones, name='api-inscripciones'),
    path('admin/cursos/inscripciones/<int:inscripcion_id>/', inscripciones, name='api-inscripcion-detalle'),
    path('docente/paralelos/<int:paralelo_id>/estudiantes/', estudiantes_del_paralelo, name='api-docente-estudiantes-paralelo'),
    path('docente/cursos/', cursos_del_docente, name='api-docente-cursos'),
    path('docente/cursos/<int:curso_id>/estudiantes/', estudiantes_del_curso, name='api-docente-estudiantes-curso'),
    path('estudiante/mis-cursos/', mis_cursos, name='api-estudiante-mis-cursos'),
]
