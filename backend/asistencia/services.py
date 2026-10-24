from django.db.models import Count
from .models import Asistencia

TARDANZA_CUENTA_COMO_ASISTENCIA = True
UMBRAL_RIESGO = 75  # porcentaje

def resumen_asistencia(paralelo, estudiante_ids, desde=None, hasta=None):
    base = Asistencia.objects.filter(sesion__paralelo=paralelo)
    if desde:
        base = base.filter(sesion__fecha__gte=desde)
    if hasta:
        base = base.filter(sesion__fecha__lte=hasta)
    total = base.values("sesion_id").distinct().count()
    conteo = {i: {"presente": 0, "ausente": 0, "tardanza": 0} for i in estudiante_ids}
    for f in base.values("estudiante_id", "estado").annotate(n=Count("pk")):
        if f["estudiante_id"] in conteo and f["estado"] in conteo[f["estudiante_id"]]:
            conteo[f["estudiante_id"]][f["estado"]] = f["n"]

    resumen = {}
    for i, c in conteo.items():
        asistidas = c["presente"] + (c["tardanza"] if TARDANZA_CUENTA_COMO_ASISTENCIA else 0)
        pct = round(asistidas * 100 / total) if total else None
        resumen[i] = {
            "presentes": c["presente"], "ausentes": c["ausente"], "tardanzas": c["tardanza"],
            "asistidas": asistidas, "total_sesiones": total, "pct": pct,
            "en_riesgo": pct is not None and pct < UMBRAL_RIESGO,
        }
    return total, resumen