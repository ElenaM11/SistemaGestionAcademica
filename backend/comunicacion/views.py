import unicodedata
from datetime import time, timedelta

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from asistencia.models import SesionClase
from cursos.models import EstudianteParalelo
from cursos.permissions import usuario_de_sesion
from notificaciones.models import Notificacion
from notificaciones.services import notificar_paralelo
from usuarios.contexto import contexto_curso, inscripciones_activas, texto_error
from usuarios.decorators import docente_requerido
from usuarios.models import Estudiante

from . import livekit
from .decorators import estudiante_requerido
from .models import Aviso, Mensaje, SesionParticipante
from .permisos import pueden_conversar
from .servicios import enviar_mensaje

EN_CURSO = SesionClase.Estado.EN_CURSO
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
SELECT_SESION = ("paralelo__curso__idioma", "paralelo__curso__nivel", "paralelo__turno")

def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower().strip()


def _marcar_notificaciones(usuario, tipo):
    Notificacion.objects.filter(usuario=usuario, tipo=tipo, leida=False).update(leida=True)


def _plural(n, singular, plural):
    return singular if n == 1 else plural


def _contar_inscritos(paralelos):
    filas = (EstudianteParalelo.objects.filter(paralelo__in=paralelos, estado="ACTIVO")
             .values("paralelo_id").annotate(n=Count("pk")))
    conteo = {f["paralelo_id"]: f["n"] for f in filas}
    for p in paralelos:
        p.n_inscritos = conteo.get(p.pk, 0)
    return paralelos


def _estado_vista(sesion, ahora):
    if sesion.estado == EN_CURSO:
        return "en_vivo"
    if sesion.estado == SesionClase.Estado.FINALIZADA:
        return "finalizada"
    if sesion.hora_inicio is None:
        return "por_iniciar"
    faltan = (sesion.hora_inicio.hour * 60 + sesion.hora_inicio.minute) - (ahora.hour * 60 + ahora.minute)
    return "por_iniciar" if faltan <= 30 else "programada"


def _historial(usuario_a, usuario_b, paralelo, yo_id):
    """Últimos 200 mensajes de la conversación, del más antiguo al más reciente."""
    recientes = list(Mensaje.conversacion(usuario_a, usuario_b, paralelo).order_by("-fecha_envio")[:200])
    return [{"texto": m.contenido, "es_mio": m.emisor_id == yo_id} for m in reversed(recientes)]


#LiveKit
@never_cache
@require_GET
def token_livekit(request, sesion_pk):
    """Entrega el token para entrar a la sala. Solo el docente del paralelo o un estudiante inscrito."""
    usuario = usuario_de_sesion(request)
    if not usuario:
        return JsonResponse({"detalle": "Inicia sesión para entrar a la clase."}, status=401)
    sesion = get_object_or_404(SesionClase.objects.select_related("paralelo"), pk=sesion_pk)
    rol = usuario.rol.nombre.lower()
    if rol == "docente":
        permitido = sesion.paralelo.docente_id == usuario.pk
    elif rol == "estudiante":
        permitido = EstudianteParalelo.objects.filter(
            paralelo_id=sesion.paralelo_id, estudiante_id=usuario.pk, estado="ACTIVO").exists()
    else:
        permitido = False
    if not permitido:
        return JsonResponse({"detalle": "No tienes acceso a esta clase."}, status=403)
    if sesion.estado != EN_CURSO:
        return JsonResponse({"detalle": "La clase no está en curso."}, status=409)
    if not livekit.configurado():
        return JsonResponse({"detalle": "El servicio de llamadas aún no está configurado."}, status=503)
    token = livekit.crear_token(
        sala=sesion.sala_livekit or f"clase-{sesion.pk}", identidad=f"u{usuario.pk}",
        nombre=f"{usuario.nombres} {usuario.ap_pat}", rol="Docente" if rol == "docente" else "Estudiante",
        puede_compartir=(rol == "docente"),
    )
    return JsonResponse({"token": token, "url": settings.LIVEKIT_URL})


#docente: clase en vivo
def _abrir_sesion(paralelo, tema):
    """Reanuda la clase en curso de hoy o inicia una (reutiliza la sesión programada de hoy si existe)."""
    ahora = timezone.localtime()
    hoy = ahora.date()
    with transaction.atomic():
        en_curso = (SesionClase.objects.select_for_update()
                    .filter(paralelo=paralelo, fecha=hoy, estado=EN_CURSO).first())
        if en_curso:
            return en_curso
        sesion = (SesionClase.objects.select_for_update()
                  .filter(paralelo=paralelo, fecha=hoy, estado=SesionClase.Estado.PROGRAMADA)
                  .order_by("hora_inicio").first()
                  or SesionClase(paralelo=paralelo, fecha=hoy, hora_inicio=ahora.time().replace(microsecond=0)))
        sesion.tema = tema
        sesion.estado = EN_CURSO
        sesion.inicio_real = timezone.now()
        sesion.full_clean()
        sesion.save()
        if not sesion.sala_livekit:
            sesion.sala_livekit = f"clase-{sesion.pk}"
            sesion.save(update_fields=["sala_livekit"])
        transaction.on_commit(lambda: notificar_paralelo(
            paralelo, "CLASE", f"Clase en vivo: {paralelo.curso.nombre} · {tema}"))
    return sesion


@docente_requerido
def docente_clase_iniciar(request, curso_id):
    ctx = contexto_curso(request, curso_id)
    paralelos = _contar_inscritos(ctx["paralelos"])
    hoy = timezone.localdate()
    # Limpieza: una clase "en curso" de días anteriores se cerró sin finalizar
    SesionClase.objects.filter(paralelo__in=paralelos, estado=EN_CURSO, fecha__lt=hoy).update(
        estado=SesionClase.Estado.FINALIZADA, fin_real=timezone.now())
    error = None
    if request.method == "POST":
        elegido = next((p for p in paralelos if str(p.pk) == request.POST.get("id_paralelo")), None)
        tema = request.POST.get("tema", "").strip()
        if not elegido:
            error = "Elige uno de tus cursos."
        elif not tema:
            error = "Escribe el tema de la clase."
        else:
            try:
                sesion = _abrir_sesion(elegido, tema)
            except ValidationError as e:
                error = texto_error(e)
            else:
                return redirect("docente_clase_sala", curso_id=elegido.curso_id, sesion_pk=sesion.pk)

    ahora = timezone.localtime()
    sesiones = list(SesionClase.objects.filter(paralelo__in=paralelos, fecha=hoy)
                    .select_related(*SELECT_SESION).order_by("hora_inicio"))
    for s in sesiones:
        s.hora = s.hora_inicio
        s.estado_vista = _estado_vista(s, ahora)
    ctx.update(opciones=paralelos, sesiones_hoy=sesiones, error=error)
    return render(request, "docente/clase_iniciar.html", ctx)


def _sesion_del_docente(request, curso_id, sesion_pk):
    return get_object_or_404(
        SesionClase.objects.select_related(*SELECT_SESION),
        pk=sesion_pk, paralelo__curso_id=curso_id, paralelo__docente=request.docente)


@docente_requerido
def docente_clase_sala(request, curso_id, sesion_pk):
    sesion = _sesion_del_docente(request, curso_id, sesion_pk)
    if sesion.estado != EN_CURSO:
        messages.info(request, "Esa clase ya no está en curso.")
        return redirect("docente_clase_iniciar", curso_id=curso_id)
    ctx = contexto_curso(request, curso_id)
    ctx.update(paralelo=sesion.paralelo, curso=sesion.paralelo.curso, sesion=sesion,
               cantidad_estudiantes=inscripciones_activas(sesion.paralelo).count())
    SesionParticipante.registrar_ingreso(sesion, ctx["usuario"])
    return render(request, "docente/clase_sala.html", ctx)


@docente_requerido
@require_POST
def docente_clase_finalizar(request, curso_id, sesion_pk):
    sesion = _sesion_del_docente(request, curso_id, sesion_pk)
    if sesion.estado == EN_CURSO:
        ahora = timezone.now()
        sesion.estado = SesionClase.Estado.FINALIZADA
        sesion.fin_real = ahora
        campos = ["estado", "fin_real"]
        if not sesion.hora_fin:
            sesion.hora_fin = timezone.localtime(ahora).time().replace(microsecond=0)
            campos.append("hora_fin")
        sesion.save(update_fields=campos)
        sesion.participantes.filter(hora_salida__isnull=True).update(hora_salida=ahora)
        livekit.cerrar_sala(sesion.sala_livekit)
    messages.success(request, "La clase finalizó. Ya puedes registrar la asistencia.")
    destino = reverse("docente_asistencia", args=[curso_id])
    return redirect(f"{destino}?fecha={sesion.fecha:%Y-%m-%d}&paralelo={sesion.paralelo_id}")


#docente: avisos y mensajes
@docente_requerido
def docente_avisos(request, curso_id):
    ctx = contexto_curso(request, curso_id)
    paralelos = _contar_inscritos(ctx["paralelos"])
    error = None
    if request.method == "POST":
        paralelo = next((p for p in paralelos if str(p.pk) == request.POST.get("id_paralelo")), ctx["paralelo"])
        aviso = Aviso(
            paralelo=paralelo, docente=request.docente,
            titulo=request.POST.get("titulo", "").strip(), mensaje=request.POST.get("mensaje", "").strip(),
        )
        try:
            with transaction.atomic():
                aviso.publicar()
                n = notificar_paralelo(paralelo, "AVISO", f"Nuevo aviso: {aviso.titulo}")
        except ValidationError as e:
            error = texto_error(e)
        else:
            messages.success(request, f"Aviso enviado a {n} {_plural(n, 'estudiante', 'estudiantes')}.")
            return redirect("docente_avisos", curso_id=curso_id)

    avisos = Aviso.objects.filter(docente=request.docente, paralelo__curso_id=curso_id)[:30]
    ctx.update(opciones=paralelos, avisos=avisos, error=error)
    return render(request, "docente/avisos.html", ctx)


@docente_requerido
def docente_mensajes(request, curso_id):
    ctx = contexto_curso(request, curso_id)
    paralelo, yo = ctx["paralelo"], ctx["usuario"]

    if request.method == "POST":
        try:
            receptor_id = int(request.POST.get("estudiante", ""))
        except ValueError:
            raise Http404("Conversación no válida.")
        try:
            enviar_mensaje(yo, receptor_id, paralelo, request.POST.get("texto", ""))
        except ValidationError as e:
            messages.error(request, texto_error(e))
        return redirect(f"{request.path}?paralelo={paralelo.pk}&estudiante={receptor_id}")

    seleccionada, ws_ruta = None, ""
    try:
        sel_id = int(request.GET.get("estudiante", ""))
    except ValueError:
        sel_id = None
    if sel_id and pueden_conversar(yo.pk, sel_id, paralelo.pk):
        estudiante = get_object_or_404(Estudiante.objects.select_related("usuario"), pk=sel_id)
        Mensaje.objects.filter(emisor=estudiante.usuario, receptor=yo, paralelo=paralelo, leido=False).update(leido=True)
        _marcar_notificaciones(yo, "MENSAJE")
        seleccionada = {"estudiante": estudiante, "mensajes": _historial(yo, estudiante.usuario, paralelo, yo.pk)}
        ws_ruta = f"/ws/chat/{paralelo.pk}/{sel_id}/"

    recientes = (Mensaje.objects.filter(paralelo=paralelo).filter(Q(emisor=yo) | Q(receptor=yo))
                 .order_by("-fecha_envio").values("emisor_id", "receptor_id", "contenido")[:500])
    ultimos = {}
    for m in recientes:
        otro = m["receptor_id"] if m["emisor_id"] == yo.pk else m["emisor_id"]
        ultimos.setdefault(otro, m["contenido"])
    sin_leer = set(Mensaje.objects.filter(paralelo=paralelo, receptor=yo, leido=False)
                   .values_list("emisor_id", flat=True))
    estudiantes = Estudiante.objects.select_related("usuario").in_bulk(list(ultimos))
    conversaciones = [{"estudiante": estudiantes[i], "ultimo_mensaje": ultimos[i], "nuevo": i in sin_leer}
                      for i in ultimos if i in estudiantes]

    ctx.update(conversaciones=conversaciones, seleccionada=seleccionada, ws_ruta=ws_ruta, mi_id=yo.pk,
               hermanos=[p for p in ctx["paralelos"] if p.curso_id == curso_id])
    return render(request, "docente/mensajes.html", ctx)


#estudiante
def _inscripciones(estudiante):
    return list(
        EstudianteParalelo.objects.filter(estudiante=estudiante, estado="ACTIVO")
        .select_related("paralelo__curso__idioma", "paralelo__curso__nivel", "paralelo__turno",
                        "paralelo__docente__usuario")
        .prefetch_related("paralelo__horarios"))


def _ctx_estudiante(request, elegido=None, por_defecto=False):
    inscripciones = _inscripciones(request.estudiante)
    paralelo = next((i.paralelo for i in inscripciones if str(i.paralelo_id) == str(elegido)), None)
    if paralelo is None and por_defecto and inscripciones:
        paralelo = inscripciones[0].paralelo
    return {"usuario": request.estudiante.usuario, "inscripciones": inscripciones,
            "paralelo": paralelo, "curso": paralelo.curso if paralelo else None}


@estudiante_requerido
def estudiante_clases_vivo(request):
    ctx = _ctx_estudiante(request)
    paralelos = {i.paralelo_id: i.paralelo for i in ctx["inscripciones"]}
    hoy = timezone.localdate()
    en_curso = {s.paralelo_id: s for s in
                SesionClase.objects.filter(paralelo_id__in=paralelos, fecha=hoy, estado=EN_CURSO)}
    clases = []
    for pid, p in paralelos.items():
        s = en_curso.get(pid)
        if s:
            clases.append({"pk": s.pk, "paralelo": p, "tema": s.tema or "", "docente": p.docente,
                           "estado_vista": "en_vivo", "es_hoy": True, "fecha": hoy, "hora_inicio": s.hora_inicio})
            continue
        horas = sorted(h.hora_inicio for h in p.horarios.all() if _sin_tildes(h.dia_semana) == DIAS[hoy.weekday()])
        if horas:  # clase que le toca hoy según el horario, aún sin iniciar
            clases.append({"pk": None, "paralelo": p, "tema": "", "docente": p.docente,
                           "estado_vista": "programada", "es_hoy": True, "fecha": hoy, "hora_inicio": horas[0]})
    clases.sort(key=lambda c: (c["estado_vista"] != "en_vivo", c["hora_inicio"] or time.max))
    ctx["clases"] = clases
    return render(request, "estudiante/clases_vivo.html", ctx)


@estudiante_requerido
def estudiante_clase_sala(request, sesion_pk):
    ctx = _ctx_estudiante(request)
    ids = [i.paralelo_id for i in ctx["inscripciones"]]
    sesion = get_object_or_404(SesionClase.objects.select_related(*SELECT_SESION), pk=sesion_pk, paralelo_id__in=ids)
    if sesion.estado != EN_CURSO:
        messages.info(request, "Esa clase ya terminó.")
        return redirect("estudiante_clases_vivo")
    SesionParticipante.registrar_ingreso(sesion, ctx["usuario"])
    _marcar_notificaciones(ctx["usuario"], "CLASE")
    ctx.update(sesion=sesion, paralelo=sesion.paralelo, curso=sesion.paralelo.curso)
    return render(request, "estudiante/clase_sala.html", ctx)


@estudiante_requerido
@require_POST
def estudiante_clase_salir(request, sesion_pk):
    participante = SesionParticipante.objects.filter(sesion_id=sesion_pk, usuario=request.estudiante.usuario).first()
    if participante:
        participante.registrar_salida()
    return redirect("estudiante_clases_vivo")


@estudiante_requerido
def estudiante_avisos(request):
    ctx = _ctx_estudiante(request)
    ids = [i.paralelo_id for i in ctx["inscripciones"]]
    avisos = list(Aviso.objects.filter(paralelo_id__in=ids).select_related("docente__usuario", "paralelo__curso")[:50])
    hoy, reciente = timezone.localdate(), timezone.now() - timedelta(days=2)
    for a in avisos:
        a.es_hoy = timezone.localtime(a.fecha_publicacion).date() == hoy
        a.nuevo = a.fecha_publicacion >= reciente  # "Nuevo" = publicado en las últimas 48 h
    _marcar_notificaciones(ctx["usuario"], "AVISO")
    ctx["avisos"] = avisos
    return render(request, "estudiante/avisos.html", ctx)


@estudiante_requerido
def estudiante_mensajes(request):
    ctx = _ctx_estudiante(request, request.GET.get("paralelo") or request.POST.get("id_paralelo"), por_defecto=True)
    paralelo, usuario = ctx["paralelo"], ctx["usuario"]
    mensajes, ws_ruta, docente = [], "", None
    if paralelo:
        docente = paralelo.docente
        if request.method == "POST":
            try:
                enviar_mensaje(usuario, docente.pk, paralelo, request.POST.get("texto", ""))
            except ValidationError as e:
                messages.error(request, texto_error(e))
            return redirect(f"{request.path}?paralelo={paralelo.pk}")
        Mensaje.objects.filter(emisor=docente.usuario, receptor=usuario, paralelo=paralelo, leido=False).update(leido=True)
        _marcar_notificaciones(usuario, "MENSAJE")
        mensajes = _historial(usuario, docente.usuario, paralelo, usuario.pk)
        ws_ruta = f"/ws/chat/{paralelo.pk}/{docente.pk}/"
    ctx.update(docente=docente, mensajes=mensajes, ws_ruta=ws_ruta, mi_id=usuario.pk)
    return render(request, "estudiante/mensajes.html", ctx)
