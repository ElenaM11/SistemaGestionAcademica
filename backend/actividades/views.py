from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from notificaciones.models import Notificacion
from notificaciones.services import notificar_paralelo
from usuarios.contexto import contexto_curso, texto_error
from usuarios.decorators import docente_requerido
from .models import Actividad

def _fecha_limite(texto):
    try:
        dia = datetime.strptime(texto or "", "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError("La fecha límite no es válida.")
    limite = datetime.combine(dia, time(23, 59))
    return timezone.make_aware(limite) if settings.USE_TZ else limite

def _leer_post(request):
    p = request.POST
    limite = _fecha_limite(p.get("fecha_limite"))
    if limite < timezone.now():
        raise ValidationError("La fecha límite no puede estar en el pasado.")
    try:
        puntaje = Decimal(p.get("puntaje_maximo") or "100")
    except InvalidOperation:
        raise ValidationError("El puntaje máximo no es válido.")
    return {
        "titulo": p.get("titulo", "").strip(),
        "instrucciones": p.get("instrucciones", "").strip() or None,
        "tipo": p.get("tipo") or None,
        "fecha_limite": limite,
        "puntaje_maximo": puntaje,
        "permite_entrega_tardia": bool(p.get("permitir_tardia")),
        "usa_ia": bool(p.get("asistente_ia")),  # ver nota sobre HU-32
    }


def _render_lista(request, ctx, error=None):
    actividades = list(
        Actividad.objects.filter(paralelo=ctx["paralelo"])
        .annotate(entregadas=Count("entregas"))
        .order_by("-fecha_publicacion")
    )
    for a in actividades:
        a.editable = not a.esta_vencida()  # la plantilla muestra Editar/Eliminar solo si es True
    ctx.update(actividades=actividades, error=error)
    return render(request, "docente/actividad_crear.html", ctx)


def _actividad_del_docente(request, curso_id, pk):
    return get_object_or_404(
        Actividad, pk=pk, paralelo__docente=request.docente, paralelo__curso_id=curso_id
    )


@docente_requerido
def docente_actividades(request, curso_id):
    ctx = contexto_curso(request, curso_id)
    error = None
    if request.method == "POST":
        try:
            actividad = Actividad(paralelo=ctx["paralelo"], docente=request.docente, **_leer_post(request))
            actividad.full_clean()  
            with transaction.atomic():
                actividad.save()
                n = notificar_paralelo(
                    ctx["paralelo"], Notificacion.Tipo.ACTIVIDAD, f"Nueva actividad: {actividad.titulo}"
                )
        except ValidationError as e:
            error = texto_error(e)
        else:
            messages.success(request, f"Actividad publicada. Se notificó a {n} estudiantes.")
            return redirect("docente_actividades", curso_id=curso_id)
    return _render_lista(request, ctx, error)


@docente_requerido
def docente_actividad_editar(request, curso_id, pk):
    ctx = contexto_curso(request, curso_id)
    actividad = _actividad_del_docente(request, curso_id, pk)
    if actividad.esta_vencida():
        return _render_lista(request, ctx, "La actividad ya venció y no se puede editar.")
    error = None
    if request.method == "POST":
        try:
            for campo, valor in _leer_post(request).items():
                setattr(actividad, campo, valor)
            actividad.full_clean()
            actividad.save()
        except ValidationError as e:
            error = texto_error(e)
        else:
            messages.success(request, "Actividad actualizada.")
            return redirect("docente_actividades", curso_id=curso_id)
    ctx.update(actividad=actividad, error=error)
    return render(request, "docente/actividad_editar.html", ctx)


@docente_requerido
@require_POST
def docente_actividad_eliminar(request, curso_id, pk):
    ctx = contexto_curso(request, curso_id)
    actividad = _actividad_del_docente(request, curso_id, pk)
    if actividad.esta_vencida():
        return _render_lista(request, ctx, "La actividad ya venció y no se puede eliminar.")

    if actividad.entregas.exists():
        return _render_lista(request, ctx, "La actividad ya tiene entregas, no se puede eliminar.")
    actividad.delete()
    messages.success(request, "Actividad eliminada.")
    return redirect("docente_actividades", curso_id=curso_id)


from cursos.models import Paralelo

@docente_requerido
def docente_tareas(request):
    paralelo = (Paralelo.objects
                .filter(docente=request.docente, estado="ACTIVO")
                .order_by("curso__nombre", "codigo").first())
    if paralelo is None:
        messages.info(request, "Aún no tienes cursos asignados.")
        return redirect("docente_dashboard")
    return redirect("docente_actividades", curso_id=paralelo.curso_id)