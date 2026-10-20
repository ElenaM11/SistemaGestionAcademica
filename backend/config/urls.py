from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('usuarios.urls')),
    path('', include('rol.urls')),
    path('', include('cursos.web_urls')),
    path('admin/', admin.site.urls),

    path("api/", include("cursos.urls")),

    # Rutas del rol docente
    path("panel/docente/cursos/<int:curso_id>/materiales/",include("materiales.urls")),
    path("panel/docente/cursos/<int:curso_id>/actividades/",include("actividades.urls")),
    path("panel/docente/cursos/<int:curso_id>/asistencia/",include("asistencia.urls")),
    path("panel/docente/cursos/<int:curso_id>/progreso/",include("actividades.urls_progreso")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
