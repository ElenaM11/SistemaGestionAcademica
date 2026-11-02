from usuarios.models import Docente, Estudiante


def pueden_conversar(uid_a, uid_b):

    if uid_a == uid_b:
        return False
    ids = set(Docente.objects.filter(pk__in=[uid_a, uid_b], usuario__estado=True).values_list("pk", flat=True))
    ids |= set(Estudiante.objects.filter(pk__in=[uid_a, uid_b], usuario__estado=True).values_list("pk", flat=True))
    return ids == {uid_a, uid_b}