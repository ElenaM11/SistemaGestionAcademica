
from django.shortcuts import redirect, render
from cursos.permissions import usuario_de_sesion
from .models import Notificacion

def lista(request):
    usuario = usuario_de_sesion(request)
    if not usuario:
        return redirect("login")
    notificaciones = Notificacion.objects.filter(usuario=usuario)[:50]
    return render(request, "notificaciones/lista.html", {
        "usuario": usuario, "notificaciones": notificaciones, "rol": usuario.rol.nombre,
    })

def marcar_todas(request):
    usuario = usuario_de_sesion(request)
    if not usuario:
        return redirect("login")
    if request.method == "POST":
        Notificacion.objects.filter(usuario=usuario, leida=False).update(leida=True)
    return redirect("notificaciones")