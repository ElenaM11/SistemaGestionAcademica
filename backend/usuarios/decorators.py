from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from cursos.permissions import usuario_de_sesion
from usuarios.models import Docente

def docente_requerido(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        usuario = usuario_de_sesion(request)
        if not usuario:
            return redirect("login")
        if usuario.rol.nombre != "Docente":
            return HttpResponseForbidden("No tienes permisos para acceder a esta página.")
        request.docente = Docente.objects.get(pk=usuario.pk)
        return vista(request, *args, **kwargs)
    return envoltura