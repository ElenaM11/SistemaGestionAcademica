from django.http import HttpResponseForbidden
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_time
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from usuarios.models import Docente, Estudiante, Usuario

from .models import Curso, DocenteIdioma, EstudianteParalelo, Idioma, Nivel, Paralelo, Programa, Turno
from .serializers import CursoSerializer, ParaleloActualizarSerializer, ParaleloEntradaSerializer
from .services import (
    asignar_docente, actualizar_paralelo, crear_elemento_catalogo, crear_o_actualizar_curso,
    crear_paralelo, docente_disponible_para_horarios, inscribir_estudiante, listar_paralelos_disponibles,
    habilitar_idioma_docente, retirar_inscripcion,
)


def registrar_error_pagina(request, error):
    """Muestro errores de validación con mensajes legibles en español."""
    detalle = getattr(error, 'detail', error)
    if isinstance(detalle, dict):
        texto = ' '.join(f'{campo}: {valor}' for campo, valor in detalle.items())
    elif isinstance(detalle, (list, tuple)):
        texto = ' '.join(str(valor) for valor in detalle)
    else:
        texto = str(detalle)
    messages.error(request, texto)


def validar_rol_pagina(request, nombre_rol):
    """Valido la sesión activa y el rol requerido para una página académica."""
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None, redirect('login')
    usuario = Usuario.objects.select_related('rol').filter(id_usuario=usuario_id, estado=True).first()
    if not usuario:
        return None, redirect('login')
    if usuario.rol.nombre != nombre_rol:
        return None, HttpResponseForbidden('No tienes permisos para acceder a esta página.')
    return usuario, None


def catalogo_cursos_pagina(request):
    """Muestro y preparo la edición del catálogo para el administrador."""
    usuario, respuesta = validar_rol_pagina(request, 'Administrador')
    if respuesta:
        return respuesta
    if request.method == 'POST':
        curso_id = request.POST.get('id_curso')
        curso = Curso.objects.filter(pk=curso_id).first() if curso_id else None
        datos = {}
        if request.POST.get('idioma'):
            datos['idioma'] = request.POST['idioma']
        if request.POST.get('nivel'):
            datos['nivel'] = request.POST['nivel']
        if 'nombre' in request.POST:
            datos['nombre'] = request.POST.get('nombre', '').strip()
        if 'descripcion' in request.POST:
            datos['descripcion'] = request.POST.get('descripcion', '').strip()
        if 'activo' in request.POST:
            datos['activo'] = request.POST.get('activo') == '1'
        serializer = CursoSerializer(curso, data=datos, partial=bool(curso))
        if serializer.is_valid():
            try:
                crear_o_actualizar_curso(serializer.validated_data, curso.pk if curso else None)
                messages.success(request, 'El curso se guardó correctamente.')
                return redirect('admin_catalogo_cursos')
            except (ValidationError, IntegrityError) as error:
                registrar_error_pagina(request, error)
        else:
            registrar_error_pagina(request, serializer.errors)
    editar_id = request.POST.get('id_curso') if request.method == 'POST' else request.GET.get('editar')
    curso_editar = Curso.objects.filter(pk=editar_id).first() if editar_id else None
    return render(request, 'admin_panel/catalogo_cursos.html', {
        'usuario': usuario,
        'cursos': Curso.objects.select_related('idioma', 'nivel').order_by('idioma__nombre', 'nivel__codigo'),
        'idiomas': Idioma.objects.filter(activo=True).order_by('nombre'),
        'niveles': Nivel.objects.order_by('codigo'),
        'curso_editar': curso_editar,
        'form_data': request.POST if request.method == 'POST' else {},
        'mostrar_modal': request.method == 'POST' or bool(request.GET.get('editar')),
    })


def catalogos_pagina(request):
    """Muestro y completo los catálogos académicos que alimentan cursos y paralelos."""
    usuario, respuesta = validar_rol_pagina(request, 'Administrador')
    if respuesta:
        return respuesta
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        datos = {}
        try:
            if tipo == 'docente_idioma':
                _, creada = habilitar_idioma_docente(
                    request.POST.get('id_docente'), request.POST.get('id_idioma')
                )
                messages.success(request, 'Idioma habilitado para el docente.' if creada else 'El docente ya tenía habilitado ese idioma.')
                return redirect('admin_catalogos')
            if tipo == 'idioma':
                datos = {'nombre': request.POST.get('nombre', '').strip(), 'codigo': request.POST.get('codigo', '').strip()}
                if not datos['nombre'] or not datos['codigo']:
                    raise ValidationError('El nombre y el código del idioma son obligatorios.')
            elif tipo == 'nivel':
                datos = {'codigo': request.POST.get('codigo', '').strip()}
                if not datos['codigo']:
                    raise ValidationError('El código del nivel es obligatorio.')
            elif tipo == 'programa':
                duracion = request.POST.get('duracion_meses', '').strip()
                datos = {
                    'nombre': request.POST.get('nombre', '').strip(),
                    'duracion_meses': int(duracion) if duracion else None,
                    'descripcion': request.POST.get('descripcion', '').strip() or None,
                }
                if not datos['nombre']:
                    raise ValidationError('El nombre del programa es obligatorio.')
                if datos['duracion_meses'] is not None and datos['duracion_meses'] < 1:
                    raise ValidationError('La duración debe ser mayor a cero meses.')
            elif tipo == 'turno':
                inicio = request.POST.get('hora_referencia_inicio', '').strip()
                fin = request.POST.get('hora_referencia_fin', '').strip()
                datos = {
                    'nombre': request.POST.get('nombre', '').strip(),
                    'hora_referencia_inicio': parse_time(inicio) if inicio else None,
                    'hora_referencia_fin': parse_time(fin) if fin else None,
                }
                if not datos['nombre']:
                    raise ValidationError('El nombre del turno es obligatorio.')
                if (inicio and not datos['hora_referencia_inicio']) or (fin and not datos['hora_referencia_fin']):
                    raise ValidationError('Indica horas válidas para el turno.')
                if datos['hora_referencia_inicio'] and datos['hora_referencia_fin'] and datos['hora_referencia_inicio'] >= datos['hora_referencia_fin']:
                    raise ValidationError('La hora inicial del turno debe ser anterior a la hora final.')
            else:
                raise ValidationError('Selecciona un catálogo válido.')
            crear_elemento_catalogo(tipo, datos)
            messages.success(request, 'El elemento del catálogo se agregó correctamente.')
            return redirect('admin_catalogos')
        except (ValidationError, IntegrityError, ValueError) as error:
            if isinstance(error, IntegrityError):
                messages.error(request, 'Ese idioma, nivel o turno ya existe en el catálogo.')
            else:
                registrar_error_pagina(request, error)
    return render(request, 'admin_panel/catalogos.html', {
        'usuario': usuario,
        'idiomas': Idioma.objects.order_by('nombre'),
        'niveles': Nivel.objects.order_by('codigo'),
        'programas': Programa.objects.order_by('nombre'),
        'turnos': Turno.objects.order_by('nombre'),
        'docentes': Docente.objects.filter(usuario__estado=True).select_related('usuario').order_by(
            'usuario__ap_pat', 'usuario__nombres'
        ),
        'docentes_idiomas': Docente.objects.filter(usuario__estado=True).select_related(
            'usuario'
        ).prefetch_related('idiomas_docente__idioma'),
    })


def paralelos_pagina(request):
    """Muestro la oferta de paralelos y los catálogos para crear uno."""
    usuario, respuesta = validar_rol_pagina(request, 'Administrador')
    if respuesta:
        return respuesta
    editar_id = request.POST.get('id_paralelo') if request.method == 'POST' else request.GET.get('editar')
    paralelo_editar = get_object_or_404(
        Paralelo.objects.select_related('curso', 'programa', 'turno', 'docente__usuario').prefetch_related('horarios'),
        pk=editar_id,
    ) if editar_id else None
    horarios_form = [{
        'dia_semana': dia, 'hora_inicio': hora_inicio, 'hora_fin': hora_fin,
    } for dia, hora_inicio, hora_fin in zip(
        request.POST.getlist('dia_semana'),
        request.POST.getlist('hora_inicio'),
        request.POST.getlist('hora_fin'),
    )] if request.method == 'POST' else [{}]
    if request.method == 'POST':
        if request.POST.get('accion') == 'cambiar_estado':
            try:
                estado = request.POST.get('estado')
                if estado not in ('ACTIVO', 'INACTIVO'):
                    raise ValidationError('Selecciona un estado válido para el paralelo.')
                actualizar_paralelo(request.POST.get('id_paralelo'), {'estado': estado})
                messages.success(request, 'El paralelo se activó correctamente.' if estado == 'ACTIVO' else 'El paralelo se desactivó correctamente.')
                return redirect('admin_paralelos')
            except (ValidationError, IntegrityError) as error:
                registrar_error_pagina(request, error)
        datos = {
            'id_curso': request.POST.get('id_curso'),
            'id_programa': request.POST.get('id_programa') or None,
            'id_turno': request.POST.get('id_turno'),
            'id_docente': request.POST.get('id_docente'),
            'modalidad': request.POST.get('modalidad') or None,
            'aula': request.POST.get('aula') or None,
            'cupo_minimo_apertura': request.POST.get('cupo_minimo_apertura') or None,
            'cupo_maximo': request.POST.get('cupo_maximo') or None,
            'fecha_inicio': request.POST.get('fecha_inicio') or None,
            'fecha_fin': request.POST.get('fecha_fin') or None,
        }
        serializer_class = ParaleloActualizarSerializer if paralelo_editar else ParaleloEntradaSerializer
        if not paralelo_editar:
            datos['horarios'] = horarios_form
        serializer = serializer_class(data=datos)
        if serializer.is_valid():
            try:
                if paralelo_editar:
                    actualizar_paralelo(paralelo_editar.pk, serializer.validated_data)
                    messages.success(request, 'El paralelo se actualizó correctamente.')
                else:
                    crear_paralelo(serializer.validated_data)
                    messages.success(request, 'El paralelo se creó correctamente.')
                return redirect('admin_paralelos')
            except (ValidationError, IntegrityError) as error:
                registrar_error_pagina(request, error)
        else:
            registrar_error_pagina(request, serializer.errors)
    return render(request, 'admin_panel/paralelos.html', {
        'usuario': usuario,
        'paralelos': Paralelo.objects.select_related(
            'curso__idioma', 'curso__nivel', 'turno', 'docente__usuario'
        ).prefetch_related('horarios').annotate(
            inscritos_activos=Count('inscripciones', filter=Q(inscripciones__estado='ACTIVO'))
        ).order_by('codigo'),
        'cursos': Curso.objects.filter(
            Q(activo=True) | Q(pk=paralelo_editar.curso_id if paralelo_editar else None)
        ).select_related('idioma', 'nivel').order_by('nombre'),
        'programas': Programa.objects.filter(
            Q(activo=True) | Q(pk=paralelo_editar.programa_id if paralelo_editar else None)
        ).order_by('nombre'),
        'turnos': Turno.objects.order_by('nombre'),
        'docentes': Docente.objects.select_related('usuario').filter(
            Q(usuario__estado=True) | Q(pk=paralelo_editar.docente_id if paralelo_editar else None)
        ).order_by(
            'usuario__ap_pat', 'usuario__nombres'
        ),
        'form_data': request.POST if request.method == 'POST' else {},
        'paralelo_editar': paralelo_editar,
        'mostrar_modal': request.method == 'POST' or bool(request.GET.get('editar')),
        'horarios_form': horarios_form,
        'gestion_actual': timezone.localdate().year,
    })


def asignar_docente_pagina(request):
    """Muestro un paralelo y los controles para asignar o reasignar su docente."""
    usuario, respuesta = validar_rol_pagina(request, 'Administrador')
    if respuesta:
        return respuesta
    paralelo = get_object_or_404(
        Paralelo.objects.select_related('curso__idioma', 'curso__nivel', 'turno', 'docente__usuario').prefetch_related('horarios'),
        pk=request.GET.get('id_paralelo'),
    )
    if request.method == 'POST':
        datos = {
            'modalidad': request.POST.get('modalidad', ''),
            'aula': request.POST.get('aula', ''),
            'fecha_inicio': request.POST.get('fecha_inicio') or None,
            'fecha_fin': request.POST.get('fecha_fin') or None,
        }
        try:
            asignar_docente(paralelo.pk, request.POST.get('id_docente'), datos)
            messages.success(request, 'El docente se asignó correctamente.')
            return redirect('admin_paralelos')
        except (ValidationError, IntegrityError) as error:
            registrar_error_pagina(request, error)
    docentes = list(Docente.objects.filter(
        usuario__estado=True, idiomas_docente__idioma=paralelo.curso.idioma
    ).select_related('usuario').distinct().order_by('usuario__ap_pat', 'usuario__nombres'))
    docente_seleccionado_id = request.POST.get('id_docente') if request.method == 'POST' else str(paralelo.docente_id)
    horarios_paralelo = list(paralelo.horarios.values('dia_semana', 'hora_inicio', 'hora_fin'))
    for opcion_docente in docentes:
        opcion_docente.sin_cruce = docente_disponible_para_horarios(
            opcion_docente, horarios_paralelo, paralelo.pk
        )
    docente_seleccionado = next(
        (docente for docente in docentes if str(docente.pk) == str(docente_seleccionado_id)), None
    )
    docente_sin_cruce = docente_disponible_para_horarios(
        docente_seleccionado, horarios_paralelo, paralelo.pk
    ) if docente_seleccionado else False
    paralelos_docente = docente_seleccionado.paralelos.select_related('curso', 'turno').exclude(
        pk=paralelo.pk
    ).order_by('codigo') if docente_seleccionado else Paralelo.objects.none()
    return render(request, 'admin_panel/asignar_docente.html', {
        'usuario': usuario,
        'paralelo': paralelo,
        'horarios': paralelo.horarios.all(),
        'docentes': docentes,
        'docente_seleccionado': docente_seleccionado_id,
        'docente_seleccionado_obj': docente_seleccionado,
        'docente_habilitado_idioma': bool(docente_seleccionado and DocenteIdioma.objects.filter(
            docente=docente_seleccionado, idioma=paralelo.curso.idioma
        ).exists()),
        'docente_sin_cruce': docente_sin_cruce,
        'form_data': request.POST if request.method == 'POST' else {},
        'paralelos_docente': paralelos_docente,
    })


def inscripciones_pagina(request):
    """Muestro el formulario de inscripción con estudiantes y catálogos activos."""
    usuario, respuesta = validar_rol_pagina(request, 'Administrador')
    if respuesta:
        return respuesta
    if request.method == 'POST':
        if request.POST.get('accion') == 'retirar':
            paralelo_id = request.POST.get('id_paralelo')
            try:
                retirar_inscripcion(request.POST.get('id_inscripcion'))
                messages.success(request, 'La inscripción se retiró correctamente; el registro se conservó en el historial.')
                return redirect(f'{request.path}?vista=cursos&id_paralelo={paralelo_id}')
            except (ValidationError, IntegrityError) as error:
                registrar_error_pagina(request, error)
        else:
            try:
                inscribir_estudiante(
                    request.POST.get('id_estudiante'), request.POST.get('id_paralelo')
                )
                messages.success(request, 'La inscripción se registró correctamente.')
                return redirect(f'{request.path}?vista=inscribir')
            except (ValidationError, IntegrityError) as error:
                registrar_error_pagina(request, error)
    disponibilidad = []
    parametros = request.POST if request.method == 'POST' else request.GET
    filtros = ('id_idioma', 'id_nivel', 'id_turno')
    if all(parametros.get(campo) for campo in filtros):
        try:
            disponibilidad = listar_paralelos_disponibles(*(parametros[campo] for campo in filtros))
        except (TypeError, ValueError):
            messages.error(request, 'Selecciona un idioma, nivel y turno válidos.')
    paralelos_gestion = Paralelo.objects.filter(
        estado='ACTIVO', curso__activo=True,
    ).select_related('curso__idioma', 'curso__nivel', 'turno', 'docente__usuario').annotate(
        inscritos_activos=Count('inscripciones', filter=Q(inscripciones__estado='ACTIVO'))
    ).prefetch_related('horarios').order_by('curso__idioma__nombre', 'curso__nivel__codigo', 'codigo')
    paralelo_seleccionado = None
    inscripciones_paralelo = EstudianteParalelo.objects.none()
    if parametros.get('id_paralelo'):
        paralelo_seleccionado = get_object_or_404(
            paralelos_gestion, pk=parametros['id_paralelo'],
        )
        inscripciones_paralelo = EstudianteParalelo.objects.filter(
            paralelo=paralelo_seleccionado, estado='ACTIVO',
        ).select_related('estudiante__usuario').order_by(
            'estudiante__usuario__ap_pat', 'estudiante__usuario__ap_mat', 'estudiante__usuario__nombres'
        )
    return render(request, 'admin_panel/inscripciones.html', {
        'usuario': usuario,
        'estudiantes': Estudiante.objects.select_related('usuario').filter(usuario__estado=True).order_by(
            'usuario__ap_pat', 'usuario__ap_mat', 'usuario__nombres'
        ),
        'idiomas': Idioma.objects.filter(activo=True).order_by('nombre'),
        'niveles': Nivel.objects.order_by('codigo'),
        'turnos': Turno.objects.order_by('nombre'),
        'disponibilidad': disponibilidad,
        'filtros': parametros,
        'id_estudiante_seleccionado': parametros.get('id_estudiante', ''),
        'paralelos_gestion': paralelos_gestion,
        'paralelo_seleccionado': paralelo_seleccionado,
        'inscripciones_paralelo': inscripciones_paralelo,
        'vista': parametros.get('vista', 'inscribir'),
    })


def docente_cursos_pagina(request):
    """Muestro los paralelos asignados al docente para acceder a sus estudiantes."""
    usuario, respuesta = validar_rol_pagina(request, 'Docente')
    if respuesta:
        return respuesta
    docente = get_object_or_404(Docente, pk=usuario.pk)
    paralelos = Paralelo.objects.filter(docente=docente, estado='ACTIVO').select_related(
        'curso__idioma', 'curso__nivel', 'turno'
    ).prefetch_related('horarios').annotate(
        inscritos_activos=Count('inscripciones', filter=Q(inscripciones__estado='ACTIVO'))
    ).order_by('curso__nombre', 'codigo')
    return render(request, 'docente/dashboard.html', {'usuario': usuario, 'paralelos': paralelos})


def estudiantes_curso_pagina(request, curso_id):
    """Muestro estudiantes solo de los paralelos asignados al docente autenticado."""
    usuario, respuesta = validar_rol_pagina(request, 'Docente')
    if respuesta:
        return respuesta
    docente = get_object_or_404(Docente, pk=usuario.pk)
    curso = get_object_or_404(Curso.objects.select_related('idioma', 'nivel'), pk=curso_id)
    paralelos = Paralelo.objects.filter(docente=docente, curso=curso, estado='ACTIVO').select_related(
        'turno'
    ).prefetch_related('horarios')
    if not paralelos.exists():
        return HttpResponseForbidden('No tienes acceso a los estudiantes de este curso.')
    inscripciones = EstudianteParalelo.objects.filter(
        paralelo__in=paralelos, estado='ACTIVO'
    ).select_related('estudiante__usuario', 'paralelo').order_by(
        'estudiante__usuario__ap_pat', 'estudiante__usuario__nombres'
    )
    return render(request, 'docente/estudiantes_curso.html', {
        'usuario': usuario,
        'curso': curso,
        'paralelos': paralelos,
        'inscripciones': inscripciones,
        'cantidad_estudiantes': inscripciones.count(),
    })


def mis_cursos_pagina(request):
    """Muestro únicamente los cursos activos del estudiante autenticado."""
    usuario, respuesta = validar_rol_pagina(request, 'Estudiante')
    if respuesta:
        return respuesta
    estudiante = get_object_or_404(Estudiante, pk=usuario.pk)
    inscripciones = EstudianteParalelo.objects.filter(
        estudiante=estudiante, estado='ACTIVO', paralelo__estado='ACTIVO'
    ).select_related(
        'paralelo__curso__idioma', 'paralelo__curso__nivel', 'paralelo__turno',
        'paralelo__programa', 'paralelo__docente__usuario'
    ).prefetch_related('paralelo__horarios').order_by('paralelo__curso__nombre')
    return render(request, 'estudiante/mis_cursos.html', {
        'usuario': usuario,
        'inscripciones': inscripciones,
    })
