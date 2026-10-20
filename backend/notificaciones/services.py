from django.apps import apps
from .models import Notificacion

def notificar_paralelo(paralelo, tipo, mensaje):
    """Una Notificacion por cada estudiante activo del paralelo. Devuelve cuántos."""
    EstudianteParalelo = apps.get_model("cursos", "EstudianteParalelo")
    ids = list(
        EstudianteParalelo.objects
        .filter(paralelo=paralelo, estado="ACTIVO")
        .values_list("estudiante_id", flat=True)
    )
    Notificacion.objects.bulk_create(
        [Notificacion(usuario_id=i, tipo=tipo, mensaje=mensaje) for i in ids]
    )
    return len(ids)