import unicodedata
from datetime import datetime
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from usuarios.contexto import contexto_curso, inscripciones_activas
from usuarios.decorators import docente_requerido
from .models import Asistencia, SesionClase

DIAS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]

def _sin_tildes(texto):
    t = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()

def _fecha(texto, por_defecto):
    try:
        return datetime.strptime(texto or "", "%Y-%m-%d").date()
    except ValueError:
        return por_defecto

def _horario(paralelo, fecha):
    dia = DIAS[fecha.weekday()]
    for h in paralelo.horarios.all():
        if _sin_tildes(h.dia_semana).startswith(dia):
            return h
    return None

@docente_requerido
def docente_asistencia(request, curso_id):
    ctx = contexto_curso(request, curso_id)
    paralelo = ctx["paralelo"]
    hoy = timezone.localdate()
    es_post = request.method == "POST"
    fecha = _fecha(request.POST.get("fecha") if es_post else request.GET.get("fecha"), hoy)

    error = None
    if fecha > hoy:
        error = "No se puede registrar la asistencia de una fecha futura."
        fecha, es_post = hoy, False  # no se guarda nada
    horario = _horario(paralelo, fecha)
    inscripciones = list(inscripciones_activas(paralelo))

    if es_post:
        with transaction.atomic():
            sesion = SesionClase.objects.filter(paralelo=paralelo, fecha=fecha).first()
            if sesion is None:
                sesion = SesionClase.objects.create(
                    paralelo=paralelo, fecha=fecha,
                    hora_inicio=horario.hora_inicio if horario else None,
                    hora_fin=horario.hora_fin if horario else None,
                )
            for ins in inscripciones:
                estado = request.POST.get(f"estado_{ins.pk}")
                if estado not in Asistencia.Estado.values:
                    continue
                observacion = request.POST.get(f"obs_{ins.pk}", "").strip()[:200] or None
                # update_or_create: si ya había registro de esa sesión, lo MODIFICA
                Asistencia.objects.update_or_create(
                    sesion=sesion, estudiante_id=ins.estudiante_id,
                    defaults={
                        "estado": estado,
                        "observacion": observacion,
                        "registrado_por_id": request.docente.pk,
                    },
                )
        messages.success(request, "Asistencia guardada.")
        return redirect(f"{reverse('docente_asistencia', args=[curso_id])}?fecha={fecha:%Y-%m-%d}")

    sesion = SesionClase.objects.filter(paralelo=paralelo, fecha=fecha).first()
    if sesion is None:  # sesión aún no registrada: se muestra con el horario del paralelo
        sesion = SesionClase(
            paralelo=paralelo, fecha=fecha,
            hora_inicio=horario.hora_inicio if horario else None,
            hora_fin=horario.hora_fin if horario else None,
        )
    previas = {a.estudiante_id: a for a in Asistencia.objects.filter(sesion=sesion)} if sesion.pk else {}
    for ins in inscripciones:
        a = previas.get(ins.estudiante_id)
        ins.estado_actual = a.estado if a else None   # la plantilla marca 'presente' si es None
        ins.observacion = a.observacion if a else ""

    ctx.update(sesion=sesion, inscripciones=inscripciones, hoy=hoy, error=error)
    return render(request, "docente/asistencia_registrar.html", ctx)