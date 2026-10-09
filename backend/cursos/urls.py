from django.urls import path

from .views import (
    AsignarDocenteView, CatalogoCursosView, CatalogoSimpleView,
    CursosDelDocenteView, EstudiantesDelCursoView, IdiomasDocenteView,
    CursoDetalleView, DocentesIdiomaView, EstudiantesDelDocenteView,
    InscripcionesView, MisCursosView, ParalelosView,
)


urlpatterns = [
    path('admin/cursos/catalogo/', CatalogoCursosView.as_view(), name='api-catalogo-cursos'),
    path('admin/cursos/catalogo/<int:curso_id>/', CursoDetalleView.as_view(), name='api-curso-detalle'),
    path('admin/cursos/catalogos/<str:catalogo>/', CatalogoSimpleView.as_view(), name='api-catalogo-simple'),
    path('admin/cursos/idiomas/<int:idioma_id>/docentes/', DocentesIdiomaView.as_view(), name='api-docentes-idioma'),
    path('admin/docentes/<int:docente_id>/idiomas/', IdiomasDocenteView.as_view(), name='api-docente-idiomas'),
    path('admin/cursos/paralelos/', ParalelosView.as_view(), name='api-paralelos'),
    path('admin/cursos/paralelos/<int:paralelo_id>/asignar-docente/', AsignarDocenteView.as_view(), name='api-asignar-docente'),
    path('admin/cursos/inscripciones/', InscripcionesView.as_view(), name='api-inscripciones'),
    path('admin/cursos/inscripciones/<int:inscripcion_id>/', InscripcionesView.as_view(), name='api-inscripcion-detalle'),
    path('docente/paralelos/<int:paralelo_id>/estudiantes/', EstudiantesDelDocenteView.as_view(), name='api-docente-estudiantes-paralelo'),
    path('docente/cursos/', CursosDelDocenteView.as_view(), name='api-docente-cursos'),
    path('docente/cursos/<int:curso_id>/estudiantes/', EstudiantesDelCursoView.as_view(), name='api-docente-estudiantes-curso'),
    path('estudiante/mis-cursos/', MisCursosView.as_view(), name='api-estudiante-mis-cursos'),
]
