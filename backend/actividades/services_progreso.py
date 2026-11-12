from asistencia.services import resumen_asistencia
from usuarios.contexto import inscripciones_activas
from cursos.services import calcular_promedio_ponderado # <-- IMPORTAMOS LA NUEVA FUNCIÓN
from .models import Actividad, Entrega

UMBRAL_PROMEDIO = 60

def progreso_paralelo(paralelo):
    inscripciones = list(inscripciones_activas(paralelo))
    ids = [i.estudiante_id for i in inscripciones]
    total_actividades = Actividad.objects.filter(paralelo=paralelo).count()

    entregadas = {i: 0 for i in ids}
    entregas = (
        Entrega.objects
        .filter(actividad__paralelo=paralelo, estudiante_id__in=ids)
        .select_related("actividad")
    )
    for e in entregas:
        entregadas[e.estudiante_id] += 1

    _, asistencia = resumen_asistencia(paralelo, ids)

    resultado = []
    for ins in inscripciones:
        i = ins.estudiante_id
        # Llamamos a la función centralizada para obtener el promedio correcto
        promedio = calcular_promedio_ponderado(ins.estudiante, paralelo)
        
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