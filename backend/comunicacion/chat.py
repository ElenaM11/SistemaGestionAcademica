
from collections import OrderedDict
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.formats import date_format

from cursos.models import EstudianteParalelo, Paralelo
from notificaciones.models import Notificacion
from usuarios.contexto import texto_error
from usuarios.models import Docente, Estudiante, Usuario

from .models import Mensaje
from .permisos import pueden_conversar
from .servicios import enviar_mensaje


def _iniciales(u):
    return f"{u.nombres[:1]}{u.ap_pat[:1]}".upper()


def _contactos(usuario):
    uid, res = usuario.pk, {}
    for d in Docente.objects.filter(usuario__estado=True).exclude(pk=uid).select_related("usuario"):
        res[d.pk] = {"usuario": d.usuario, "rol": "Docente", "detalles": []}
    for e in Estudiante.objects.filter(usuario__estado=True).exclude(pk=uid).select_related("usuario"):
        res[e.pk] = {"usuario": e.usuario, "rol": "Estudiante", "detalles": []}

    def anotar(persona_id, paralelo):
        c = res.get(persona_id)
        etiqueta = f"{paralelo.curso.idioma.nombre} {paralelo.curso.nivel.codigo}"
        if c and etiqueta not in c["detalles"]:
            c["detalles"].append(etiqueta)

    for ep in (EstudianteParalelo.objects.filter(estado="ACTIVO")
               .select_related("paralelo__curso__idioma", "paralelo__curso__nivel")):
        anotar(ep.estudiante_id, ep.paralelo)
    for p in Paralelo.objects.filter(estado="ACTIVO").select_related("curso__idioma", "curso__nivel"):
        anotar(p.docente_id, p)
    return res


def _grupos_contactos(usuario):
    contactos = list(_contactos(usuario).values())
    grupos = []
    for rol, titulo in (("Docente", "Docentes"), ("Estudiante", "Estudiantes")):
        personas = sorted((c for c in contactos if c["rol"] == rol),
                          key=lambda c: (c["usuario"].ap_pat.lower(), c["usuario"].nombres.lower()))
        if personas:
            grupos.append({"titulo": titulo, "personas": [
                {"usuario": c["usuario"], "iniciales": _iniciales(c["usuario"]), "detalle": " · ".join(c["detalles"][:3])}
                for c in personas]})
    return grupos


def _conversaciones(usuario):
    yo = usuario.pk
    recientes = (Mensaje.objects.filter(Q(emisor_id=yo) | Q(receptor_id=yo))
                 .order_by("-fecha_envio").values("emisor_id", "receptor_id", "contenido")[:1000])
    ultimos = OrderedDict()
    for m in recientes:
        otro = m["receptor_id"] if m["emisor_id"] == yo else m["emisor_id"]
        if otro != yo and otro not in ultimos:
            ultimos[otro] = ("Tú: " if m["emisor_id"] == yo else "") + m["contenido"]
    sin_leer = {f["emisor_id"]: f["n"] for f in
                Mensaje.objects.filter(receptor_id=yo, leido=False).values("emisor_id").annotate(n=Count("pk"))}
    usuarios = Usuario.objects.in_bulk(list(ultimos))
    docentes = set(Docente.objects.filter(pk__in=list(ultimos)).values_list("pk", flat=True))
    return [{"usuario": usuarios[i], "iniciales": _iniciales(usuarios[i]),
             "rol": "Docente" if i in docentes else "Estudiante",
             "ultimo": ultimos[i], "no_leidos": sin_leer.get(i, 0)} for i in ultimos if i in usuarios]


def _historial(yo, otro):
    recientes = list(Mensaje.conversacion(yo, otro).order_by("-fecha_envio")[:200])[::-1]
    hoy, items, previo = timezone.localdate(), [], None
    for m in recientes:
        dia = timezone.localtime(m.fecha_envio).date()
        if dia != previo:
            etiqueta = "Hoy" if dia == hoy else "Ayer" if dia == hoy - timedelta(days=1) else date_format(dia, "j \\d\\e F")
            items.append({"separador": etiqueta})
            previo = dia
        items.append({"texto": m.contenido, "es_mio": m.emisor_id == yo.pk, "fecha_envio": m.fecha_envio})
    return items, (previo.isoformat() if previo else "")


def construir_chat(request, usuario):
    """Devuelve (redirección, None) tras un POST o (None, contexto) para mostrar la bandeja."""
    if request.method == "POST":
        try:
            receptor_id = int(request.POST.get("con", ""))
        except ValueError:
            return redirect(request.path), None
        try:
            enviar_mensaje(usuario, receptor_id, request.POST.get("texto", ""))
        except ValidationError as e:
            messages.error(request, texto_error(e))
        return redirect(f"{request.path}?con={receptor_id}"), None

    try:
        con = int(request.GET.get("con", ""))
    except ValueError:
        con = None
    abierta = None
    if con and pueden_conversar(usuario.pk, con):
        otro = Usuario.objects.filter(pk=con).first()
        if otro:
            Mensaje.objects.filter(emisor=otro, receptor=usuario, leido=False).update(leido=True)
            Notificacion.objects.filter(usuario=usuario, tipo="MENSAJE", leida=False,
                                        mensaje=f"Nuevo mensaje de {otro.nombres} {otro.ap_pat}").update(leida=True)
            items, ultimo_dia = _historial(usuario, otro)
            abierta = {"usuario": otro, "iniciales": _iniciales(otro), "mensajes": items, "ultimo_dia": ultimo_dia,
                       "rol": "Docente" if Docente.objects.filter(pk=otro.pk).exists() else "Estudiante"}
    return None, {
        "conversaciones": _conversaciones(usuario), "abierta": abierta, "grupos": _grupos_contactos(usuario),
        "mi_id": usuario.pk, "ws_ruta": f"/ws/chat/{con}/" if abierta else "",
    }