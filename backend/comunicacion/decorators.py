from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect

from cursos.permissions import usuario_de_sesion
from usuarios.models import Estudiante


def estudiante_requerido(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        usuario = usuario_de_sesion(request)
        if not usuario:
            return redirect("login")
        if usuario.rol.nombre.lower() != "estudiante":
            return HttpResponseForbidden("No tienes permisos para acceder a esta página.")
        request.estudiante = get_object_or_404(Estudiante, pk=usuario.pk)
        return vista(request, *args, **kwargs)
    return envoltura
