from asistencia.services import resumen_asistencia
from usuarios.contexto import inscripciones_activas
from .models import Actividad, Entrega

UMBRAL_PROMEDIO = 60

def progreso_paralelo(paralelo):
    inscripciones = list(inscripciones_activas(paralelo))
    ids = [i.estudiante_id for i in inscripciones]
    total_actividades = Actividad.objects.filter(paralelo=paralelo).count()

    notas = {i: [] for i in ids}
    entregadas = {i: 0 for i in ids}
    entregas = (
        Entrega.objects
        .filter(actividad__paralelo=paralelo, estudiante_id__in=ids)
        .select_related("actividad")
    )
    for e in entregas:
        entregadas[e.estudiante_id] += 1
        if e.calificacion is not None:
            maximo = float(e.actividad.puntaje_maximo or 100)
            notas[e.estudiante_id].append(float(e.calificacion) / maximo * 100)

    _, asistencia = resumen_asistencia(paralelo, ids)

    resultado = []
    for ins in inscripciones:
        i = ins.estudiante_id
        promedio = round(sum(notas[i]) / len(notas[i]), 1) if notas[i] else None
        a = asistencia[i]
        resultado.append({
            "estudiante": ins.estudiante,
            "promedio": promedio,
            "entregadas": entregadas[i],
            "total_actividades": total_actividades,
            "asistencia_pct": a["pct"] or 0,
            "necesita_apoyo": (promedio is not None and promedio < UMBRAL_PROMEDIO) or a["en_riesgo"],
        })
    return resultado