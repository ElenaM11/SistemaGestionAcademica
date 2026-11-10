import os
import json
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from usuarios.contexto import contexto_curso, inscripciones_activas, texto_error
from usuarios.decorators import docente_requerido
from usuarios.models import Estudiante
from .models import Actividad, Entrega

def _estado(entrega):
    if entrega is None:
        return "sin_entregar"
    if entrega.estado == Entrega.Estado.CALIFICADA:
        return "calificada"
    if not entrega.contenido_texto and not entrega.archivo:
        return "sin_entregar"
    return "tardia" if entrega.es_tardia else "entregada"

def _parsear_feedback(contenido):
    if not contenido:
        return None
    try:
        datos = json.loads(contenido)
        if isinstance(datos, dict) and "respuestas" in datos:
            return datos.get("respuestas")
    except Exception:
        pass
    return None

@docente_requerido
def docente_entregas(request, curso_id, pk):
    ctx = contexto_curso(request, curso_id)
    actividad = get_object_or_404(
        Actividad.objects.select_related("paralelo"),
        pk=pk, paralelo__docente=request.docente, paralelo__curso_id=curso_id,  
    )
    inscripciones = list(inscripciones_activas(actividad.paralelo))
    entregas_db = {e.estudiante_id: e for e in actividad.entregas.all()}

    error = None
    elegido = request.GET.get("estudiante")
    if request.method == "POST":
        elegido = request.POST.get("estudiante")
        entrega = entregas_db.get(int(elegido)) if elegido and elegido.isdigit() else None
        
        # Si no hay entrega, permitimos crear una vacía si el docente decide calificar
        if entrega is None and elegido and elegido.isdigit():
            est_obj = Estudiante.objects.filter(pk=int(elegido)).first()
            if est_obj:
                entrega = Entrega(actividad=actividad, estudiante=est_obj)
                entrega.save()
        elif entrega is None:
            error = "Selecciona un estudiante válido."

        if not error:
            try:
                nota = Decimal((request.POST.get("nota") or "").strip())
                if not nota.is_finite():
                    raise InvalidOperation
            except InvalidOperation:
                error = "Ingresa una calificación válida."
            else:
                try:
                    entrega.calificar(request.docente, nota, request.POST.get("observaciones", "").strip())
                except ValidationError as e:
                    error = texto_error(e)
                else:
                    messages.success(request, "Calificación guardada.")
                    url = reverse("docente_entregas", args=[curso_id, pk])
                    return redirect(f"{url}?estudiante={elegido}")

    filas, seleccionada = [], None
    for ins in inscripciones:
        entrega = entregas_db.get(ins.estudiante_id)
        estado = _estado(entrega)
        filas.append({
            "estudiante": ins.estudiante,
            "fecha_entrega": entrega.fecha_entrega if entrega and estado != "sin_entregar" else None,
            "estado": estado,
            "nota": entrega.calificacion if entrega else None,
        })
        if elegido and str(ins.estudiante_id) == str(elegido):
            feedback = _parsear_feedback(entrega.contenido_texto) if entrega else None
            seleccionada = {
                "estudiante": ins.estudiante,
                "estado": estado,
                "entrega_id": entrega.pk if entrega else None,
                "contenido": entrega.contenido_texto if entrega and not feedback else None,
                "feedback": feedback,
                "tiene_archivo": bool(entrega and entrega.archivo),
                "nota": entrega.calificacion if entrega else None,
                "observaciones": entrega.observaciones if entrega else None,
            }

    ctx.update(
        actividad=actividad, entregas=filas, seleccionada=seleccionada, error=error,
        total_entregadas=sum(1 for f in filas if f["estado"] != "sin_entregar"),
        total_sin_entregar=sum(1 for f in filas if f["estado"] == "sin_entregar"),
    )
    return render(request, "docente/entregas_calificar.html", ctx)

@docente_requerido
def docente_entrega_archivo(request, curso_id, pk, entrega_id):
    entrega = get_object_or_404(
        Entrega, pk=entrega_id, actividad_id=pk,
        actividad__paralelo__docente=request.docente, actividad__paralelo__curso_id=curso_id,
    )
    if not entrega.archivo:
        raise Http404("Esta entrega no tiene archivo.")
    return FileResponse(
        entrega.archivo.open("rb"),
        as_attachment=bool(request.GET.get("descargar")),
        filename=os.path.basename(entrega.archivo.name),
    )