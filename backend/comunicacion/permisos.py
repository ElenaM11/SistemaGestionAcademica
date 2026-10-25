from cursos.models import EstudianteParalelo, Paralelo

def pueden_conversar(uid_a, uid_b, paralelo_id):
    if uid_a == uid_b:
        return False
    try:
        docente_id = Paralelo.objects.values_list("docente_id", flat=True).get(pk=paralelo_id)
    except Paralelo.DoesNotExist:
        return False
    if docente_id == uid_a:
        estudiante_id = uid_b
    elif docente_id == uid_b:
        estudiante_id = uid_a
    else:
        return False
    return EstudianteParalelo.objects.filter(
        paralelo_id=paralelo_id, estudiante_id=estudiante_id, estado="ACTIVO").exists()
