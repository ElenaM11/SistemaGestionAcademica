import os
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from notificaciones.models import Notificacion
from notificaciones.services import notificar_paralelo
from usuarios.contexto import contexto_curso, texto_error
from usuarios.decorators import docente_requerido
from .models import Material
EXTENSIONES_PERMITIDAS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".png", ".jpg", ".jpeg",
}
MAX_MB = 20

_DOCUMENTOS = {".pdf": "PDF", ".doc": "DOC", ".docx": "DOC", ".ppt": "PPT", ".pptx": "PPT", ".xls": "XLS", ".xlsx": "XLS"}
_AUDIOS = {".mp3": "MP3", ".wav": "AUD", ".m4a": "AUD"}
_VIDEOS = {".mp4", ".mov"}
_IMAGENES = {".png", ".jpg", ".jpeg"}


def _chip(material):
    """Etiqueta y estilo del icono según la extensión del archivo (o el tipo si es un enlace)."""
    ext = os.path.splitext(material.archivo.name)[1].lower() if material.archivo else ""
    if ext in _DOCUMENTOS:
        return _DOCUMENTOS[ext], "pdf"
    if ext in _AUDIOS:
        return _AUDIOS[ext], "mp3"
    if ext in _VIDEOS:
        return "VID", "url"
    if ext in _IMAGENES:
        return "IMG", "url"
    return {"pdf": ("PDF", "pdf"), "audio": ("MP3", "mp3"), "video": ("VID", "url")}.get(material.tipo, ("URL", "url"))


def _validar_archivo(archivo):
    ext = os.path.splitext(archivo.name)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise ValidationError(f"Tipo de archivo no permitido ({ext or 'sin extensión'}).")
    if archivo.size > MAX_MB * 1024 * 1024:
        raise ValidationError(f"El archivo supera el máximo de {MAX_MB} MB.")


def _campos(request):
    p = request.POST
    return {
        "titulo": p.get("titulo", "").strip(),
        "tipo": p.get("tipo") or None,
        "url": p.get("enlace", "").strip() or None,
        "descripcion": p.get("descripcion", "").strip() or None,
    }


@docente_requerido
def docente_materiales(request, curso_id):
    ctx = contexto_curso(request, curso_id)
    paralelo = ctx["paralelo"]
    error = None
    if request.method == "POST":
        archivo = request.FILES.get("archivo")
        material = Material(paralelo=paralelo, docente=request.docente, archivo=archivo, **_campos(request))
        try:
            if archivo:
                _validar_archivo(archivo)
            material.full_clean()  # incluye Material.clean(): archivo o enlace, y RNF-08
            with transaction.atomic():
                material.save()
                n = notificar_paralelo(paralelo, Notificacion.Tipo.MATERIAL, f"Nuevo material: {material.titulo}")
        except ValidationError as e:
            error = texto_error(e)
        else:
            messages.success(request, f"Material publicado. Se notificó a {n} estudiantes.")
            return redirect("docente_materiales", curso_id=curso_id)
    materiales = list(Material.objects.filter(paralelo=paralelo))
    for m in materiales:
        m.etiqueta, m.estilo = _chip(m)
    ctx.update(materiales=materiales, error=error)
    return render(request, "docente/materiales.html", ctx)


@docente_requerido
def docente_material_editar(request, curso_id, pk):
    ctx = contexto_curso(request, curso_id)
    material = get_object_or_404(
        Material, pk=pk, paralelo__docente=request.docente, paralelo__curso_id=curso_id
    )
    error = None
    if request.method == "POST":
        for campo, valor in _campos(request).items():
            setattr(material, campo, valor)
        nuevo = request.FILES.get("archivo")
        viejo = material.archivo.name if material.archivo else None
        try:
            if nuevo:
                _validar_archivo(nuevo)
                material.archivo = nuevo
            material.full_clean()
            material.save()
        except ValidationError as e:
            error = texto_error(e)
        else:
            if nuevo and viejo:
                material.archivo.storage.delete(viejo)  # no dejar el archivo anterior huérfano
            messages.success(request, "Material actualizado.")
            return redirect("docente_materiales", curso_id=curso_id)
    ctx.update(material=material, error=error)
    return render(request, "docente/material_editar.html", ctx)


@docente_requerido
@require_POST
def docente_material_eliminar(request, curso_id, pk):
    material = get_object_or_404(
        Material, pk=pk, paralelo__docente=request.docente, paralelo__curso_id=curso_id
    )
    almacenamiento, nombre = material.archivo.storage, material.archivo.name
    material.delete()
    if nombre:
        almacenamiento.delete(nombre)  # primero el registro, después el archivo
    messages.success(request, "Material eliminado.")
    return redirect("docente_materiales", curso_id=curso_id)