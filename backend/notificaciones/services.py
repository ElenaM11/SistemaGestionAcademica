from django.apps import apps
from .models import Notificacion

def notificar_usuarios(usuario_ids, tipo, mensaje):
    """Una Notificacion por cada usuario (sin repetir). Devuelve cuántas se crearon."""
    ids = list(dict.fromkeys(usuario_ids))
    Notificacion.objects.bulk_create(
        [Notificacion(usuario_id=i, tipo=tipo, mensaje=mensaje) for i in ids]
    )
    return len(ids)


def notificar_paralelo(paralelo, tipo, mensaje):
    EstudianteParalelo = apps.get_model("cursos", "EstudianteParalelo")
    ids = EstudianteParalelo.objects.filter(
        paralelo=paralelo, estado="ACTIVO"
    ).values_list("estudiante_id", flat=True)
    return notificar_usuarios(ids, tipo, mensaje)