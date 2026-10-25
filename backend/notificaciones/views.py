from django.apps import apps
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse

from cursos.permissions import usuario_de_sesion
from .models import Notificacion

POR_PAGINA = 15

ICONOS = {
    "MATERIAL": "bi-folder2-open", "ACTIVIDAD": "bi-clipboard-check", "CALIFICACION": "bi-patch-check",
    "AVISO": "bi-megaphone", "MENSAJE": "bi-chat-square-text", "CLASE": "bi-telephone",
}

DESTINOS = {
    "estudiante": {
        "AVISO": "estudiante_avisos", "MENSAJE": "estudiante_mensajes", "CLASE": "estudiante_clases_vivo",
        "MATERIAL": "estudiante_dashboard", "ACTIVIDAD": "estudiante_academico?vista=tareas",
        "CALIFICACION": "estudiante_academico?vista=tareas",
    },
    "docente": {"MENSAJE": "docente_dashboard", "AVISO": "docente_dashboard", "CLASE": "docente_dashboard"},
}


def _destino(n, rol):
    clave = DESTINOS.get(rol, {}).get(n.tipo)
    if not clave:
        return None
    nombre, _, consulta = clave.partition("?")
    try:
        url = reverse(nombre)
    except NoReverseMatch:
        return None
    return f"{url}?{consulta}" if consulta else url


def _contexto_nav(usuario, rol):
    """Datos que necesita el menú lateral de cada rol (la pantalla no pertenece a un curso)."""
    if rol == "docente":
        Paralelo = apps.get_model("cursos", "Paralelo")
        return {"paralelos": list(
            Paralelo.objects.filter(docente__usuario=usuario, estado="ACTIVO")
            .select_related("curso__idioma", "curso__nivel", "turno"))}
    if rol == "estudiante":
        EstudianteParalelo = apps.get_model("cursos", "EstudianteParalelo")
        return {"inscripciones": list(
            EstudianteParalelo.objects.filter(estudiante__usuario=usuario, estado="ACTIVO")
            .select_related("paralelo__curso__idioma", "paralelo__curso__nivel", "paralelo__turno"))}
    return {}


def lista(request):
    usuario = usuario_de_sesion(request)
    if not usuario:
        return redirect("login")
    rol = usuario.rol.nombre.lower()
    qs = Notificacion.objects.filter(usuario=usuario)
    sin_leer = qs.filter(leida=False).count()
    solo_no_leidas = request.GET.get("solo") == "no_leidas"
    if solo_no_leidas:
        qs = qs.filter(leida=False)

    pagina = Paginator(qs, POR_PAGINA).get_page(request.GET.get("page"))
    pagina.object_list = list(pagina.object_list)
    for n in pagina.object_list:
        n.icono = ICONOS.get(n.tipo, "bi-bell")
        n.tipo_texto = n.get_tipo_display() or "Notificación"
        n.destino = _destino(n, rol)

    ctx = {"usuario": usuario, "rol": rol, "pagina": pagina, "sin_leer": sin_leer,
           "solo_no_leidas": solo_no_leidas}
    ctx.update(_contexto_nav(usuario, rol))
    return render(request, "notificaciones/lista.html", ctx)


def abrir(request, pk):
    """Marca la notificación como leída y lleva a su destino (o vuelve a la lista)."""
    usuario = usuario_de_sesion(request)
    if not usuario:
        return redirect("login")
    n = get_object_or_404(Notificacion, pk=pk, usuario=usuario)
    n.marcar_leida()
    return redirect(_destino(n, usuario.rol.nombre.lower()) or "notificaciones")


def marcar_todas(request):
    usuario = usuario_de_sesion(request)
    if not usuario:
        return redirect("login")
    if request.method == "POST":
        n = Notificacion.objects.filter(usuario=usuario, leida=False).update(leida=True)
        if n:
            messages.success(request, "Todas tus notificaciones quedaron como leídas.")
    return redirect("notificaciones")