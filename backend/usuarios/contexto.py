from django.http import Http404
from cursos.models import EstudianteParalelo, Paralelo

def inscripciones_activas(paralelo):
    return (
        EstudianteParalelo.objects
        .filter(paralelo=paralelo, estado="ACTIVO")
        .select_related("estudiante__usuario")
        .order_by("estudiante__usuario__ap_pat", "estudiante__usuario__nombres")
    )

def contexto_curso(request, curso_id):
    docente = request.docente
    paralelos = list(
        Paralelo.objects.filter(docente=docente)
        .select_related("curso__idioma", "curso__nivel", "turno")
    )
    del_curso = [p for p in paralelos if p.curso_id == curso_id]
    if not del_curso:
        raise Http404("No tienes paralelos asignados en este curso.")
    elegido = request.GET.get("paralelo")
    paralelo = next((p for p in del_curso if str(p.pk) == elegido), del_curso[0])
    return {
        "usuario": docente.usuario,
        "paralelos": paralelos,
        "curso": paralelo.curso,
        "paralelo": paralelo,
        "cantidad_estudiantes": inscripciones_activas(paralelo).count(),
    }


def texto_error(e):
    if not hasattr(e, "error_dict"):
        return " ".join(e.messages)
    partes = []
    for campo, msgs in e.message_dict.items():
        prefijo = "" if campo == "__all__" else campo.replace("_", " ").capitalize() + ": "
        partes.append(prefijo + " ".join(msgs))
    return " ".join(partes)