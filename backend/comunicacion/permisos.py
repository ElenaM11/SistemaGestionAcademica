from usuarios.models import Docente, Estudiante, Usuario

def pueden_conversar(uid_a, uid_b):
    if uid_a == uid_b:
        return False
        
    if Usuario.objects.filter(pk__in=[uid_a, uid_b], rol__nombre='Administrador').exists():
        return True

    ids = set(Docente.objects.filter(pk__in=[uid_a, uid_b], usuario__estado=True).values_list("pk", flat=True))
    ids |= set(Estudiante.objects.filter(pk__in=[uid_a, uid_b], usuario__estado=True).values_list("pk", flat=True))
    return ids == {uid_a, uid_b}