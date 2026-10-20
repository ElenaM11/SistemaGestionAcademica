from django.shortcuts import render
from usuarios.contexto import contexto_curso
from usuarios.decorators import docente_requerido
from .services_progreso import progreso_paralelo

@docente_requerido
def docente_progreso(request, curso_id):
    ctx = contexto_curso(request, curso_id)
    ctx["progreso"] = progreso_paralelo(ctx["paralelo"])
    return render(request, "docente/progreso.html", ctx)