from datetime import datetime
from django.shortcuts import render
from usuarios.contexto import contexto_curso, inscripciones_activas
from usuarios.decorators import docente_requerido
from .services import resumen_asistencia

def _fecha_o_none(texto):
    try:
        return datetime.strptime(texto or "", "%Y-%m-%d").date()
    except ValueError:
        return None

@docente_requerido
def docente_asistencia_historial(request, curso_id):
    ctx = contexto_curso(request, curso_id)
    paralelo = ctx["paralelo"]
    desde = _fecha_o_none(request.GET.get("desde"))
    hasta = _fecha_o_none(request.GET.get("hasta"))

    error = None
    if desde and hasta and desde > hasta:
        error = "La fecha «Desde» no puede ser posterior a «Hasta»."
        desde = hasta = None

    inscripciones = list(inscripciones_activas(paralelo))
    _, datos = resumen_asistencia(paralelo, [i.estudiante_id for i in inscripciones], desde, hasta)
    porcentajes = [d["pct"] for d in datos.values() if d["pct"] is not None]

    ctx.update(
        resumen=[{"estudiante": i.estudiante, **datos[i.estudiante_id]} for i in inscripciones],
        asistencia_promedio=round(sum(porcentajes) / len(porcentajes)) if porcentajes else 0,
        faltas_acumuladas=sum(d["ausentes"] for d in datos.values()),
        estudiantes_riesgo=sum(1 for d in datos.values() if d["en_riesgo"]),
        desde=desde, hasta=hasta, error=error,
    )
    return render(request, "docente/asistencia_historial.html", ctx)