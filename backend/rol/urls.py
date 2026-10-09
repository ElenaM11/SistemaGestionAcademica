from django.urls import path
from . import views
from cursos.page_views import docente_cursos_pagina, mis_cursos_pagina

urlpatterns = [
    path('panel/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('docente/cursos/', docente_cursos_pagina, name='docente_dashboard'),
    path('estudiante/cursos/', mis_cursos_pagina, name='estudiante_dashboard'),
]
