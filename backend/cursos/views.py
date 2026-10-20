from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from usuarios.models import Docente, Estudiante

from .models import Actividad, Asistencia, Curso, DocenteIdioma, Entrega, EstudianteParalelo, Idioma, Material, Nivel, Paralelo, Programa, Turno
from .permissions import PermisoAdministrador, PermisoDocente, PermisoEstudiante, usuario_de_sesion
from .serializers import (
    CursoSerializer, EstudianteParaleloSerializer, IdiomaSerializer,
    DocenteIdiomaSerializer, DocenteIdiomaEntradaSerializer,
    InscripcionEntradaSerializer, NivelSerializer, ParaleloActualizarSerializer, ParaleloEntradaSerializer,
    ProgramaSerializer, TurnoSerializer,
    ActividadSerializer, EntregaEntradaSerializer, MaterialSerializer,
)
from .services import (
    asignar_docente as services_asignar_docente, actualizar_paralelo, cambiar_asignacion, crear_o_actualizar_curso,
    crear_paralelo, estudiantes_de_paralelo, inscribir_estudiante, retirar_inscripcion,
    habilitar_idioma_docente, listar_paralelos_disponibles,
    actividades_estudiante, buscar_estudiantes_resumen, entregar_actividad, informacion_general_cursos,
    materiales_estudiante, progreso_estudiantes_docente, resumen_progreso,
)


@api_view(['GET', 'POST'])
@permission_classes([PermisoAdministrador])
def catalogo_cursos(request):
    """Listo o creo cursos para el administrador."""
    if request.method == 'GET':
        cursos = Curso.objects.select_related('idioma', 'nivel').order_by('nombre')
        return Response(CursoSerializer(cursos, many=True).data)

    serializer = CursoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        curso = crear_o_actualizar_curso(serializer.validated_data)
    except IntegrityError:
        return Response({'error': 'El curso no se pudo guardar por un dato duplicado.'}, status=status.HTTP_400_BAD_REQUEST)
    return Response(CursoSerializer(curso).data, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([PermisoAdministrador])
def curso_detalle(request, curso_id):
    """Actualizo parcialmente un curso del catÃ¡logo."""
    curso = get_object_or_404(Curso, pk=curso_id)
    serializer = CursoSerializer(curso, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    curso = crear_o_actualizar_curso(serializer.validated_data, curso_id)
    return Response(CursoSerializer(curso).data)


@api_view(['GET'])
@permission_classes([PermisoAdministrador])
def catalogo_simple(request, catalogo):
    """Devuelvo los catÃ¡logos auxiliares de cursos y paralelos."""
    opciones = {
        'idiomas': (Idioma.objects.order_by('nombre'), IdiomaSerializer),
        'niveles': (Nivel.objects.order_by('codigo'), NivelSerializer),
        'programas': (Programa.objects.filter(activo=True).order_by('nombre'), ProgramaSerializer),
        'turnos': (Turno.objects.order_by('nombre'), TurnoSerializer),
    }
    if catalogo not in opciones:
        raise NotFound('El catÃ¡logo solicitado no existe.')
    queryset, serializer_class = opciones[catalogo]
    return Response(serializer_class(queryset, many=True).data)


@api_view(['GET'])
@permission_classes([PermisoAdministrador])
def docentes_por_idioma(request, idioma_id):
    """Listo docentes activos habilitados para el idioma solicitado."""
    idioma = get_object_or_404(Idioma, pk=idioma_id, activo=True)
    docentes = Docente.objects.filter(
        usuario__estado=True, idiomas_docente__idioma=idioma
    ).select_related('usuario').order_by('usuario__ap_pat', 'usuario__nombres')
    return Response([{
        'id_docente': docente.pk,
        'nombre': f'{docente.usuario.nombres} {docente.usuario.ap_pat} {docente.usuario.ap_mat}'.strip(),
        'correo': docente.usuario.correo,
        'paralelos_asignados': list(docente.paralelos.values('id_paralelo', 'codigo')),
    } for docente in docentes])


@api_view(['GET', 'POST'])
@permission_classes([PermisoAdministrador])
def idiomas_docente(request, docente_id):
    """Consulto o habilito idiomas para un docente."""
    if request.method == 'GET':
        docente = get_object_or_404(Docente, pk=docente_id)
        relaciones = DocenteIdioma.objects.filter(docente=docente).select_related('idioma')
        return Response(DocenteIdiomaSerializer(relaciones, many=True).data)

    serializer = DocenteIdiomaEntradaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    relacion, creada = habilitar_idioma_docente(docente_id, serializer.validated_data['id_idioma'])
    codigo = status.HTTP_201_CREATED if creada else status.HTTP_200_OK
    return Response(DocenteIdiomaSerializer(relacion).data, status=codigo)


@api_view(['GET', 'POST'])
@permission_classes([PermisoAdministrador])
def paralelos(request):
    """Listo o creo paralelos para el administrador."""
    if request.method == 'GET':
        queryset = Paralelo.objects.select_related(
            'curso__idioma', 'curso__nivel', 'turno', 'docente__usuario'
        ).prefetch_related('horarios', 'inscripciones').order_by('codigo')
        return Response([{
            'id_paralelo': paralelo.pk,
            'codigo': paralelo.codigo,
            'curso': paralelo.curso.nombre,
            'idioma': paralelo.curso.idioma.nombre,
            'nivel': paralelo.curso.nivel.codigo,
            'turno': paralelo.turno.nombre,
            'programa': paralelo.programa.nombre if paralelo.programa else None,
            'docente': f'{paralelo.docente.usuario.nombres} {paralelo.docente.usuario.ap_pat}'.strip(),
            'modalidad': paralelo.modalidad,
            'aula': paralelo.aula,
            'estado': paralelo.estado,
            'inscritos': sum(inscripcion.estado == 'ACTIVO' for inscripcion in paralelo.inscripciones.all()),
            'cupo_maximo': paralelo.cupo_maximo,
            'horarios': [{
                'dia_semana': horario.dia_semana,
                'hora_inicio': horario.hora_inicio,
                'hora_fin': horario.hora_fin,
            } for horario in paralelo.horarios.all()],
        } for paralelo in queryset])

    serializer = ParaleloEntradaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        paralelo = crear_paralelo(serializer.validated_data)
    except IntegrityError:
        return Response({'error': 'El cÃ³digo del paralelo ya existe.'}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'id_paralelo': paralelo.pk, 'codigo': paralelo.codigo}, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([PermisoAdministrador])
def paralelo_detalle(request, paralelo_id):
    """Actualizo datos de un paralelo o lo desactivo sin eliminar sus registros."""
    serializer = ParaleloActualizarSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    paralelo = actualizar_paralelo(paralelo_id, serializer.validated_data)
    return Response({
        'id_paralelo': paralelo.pk,
        'codigo': paralelo.codigo,
        'id_curso': paralelo.curso_id,
        'id_docente': paralelo.docente_id,
        'cupo_maximo': paralelo.cupo_maximo,
        'estado': paralelo.estado,
    })


@api_view(['POST'])
@permission_classes([PermisoAdministrador])
def asignar_docente(request, paralelo_id=None):
    """Asigno o reasigno un docente a un paralelo."""
    docente_id = request.data.get('id_docente')
    paralelo_id = paralelo_id or request.data.get('id_paralelo')
    if not docente_id or not paralelo_id:
        return Response({'error': 'Debes indicar el paralelo y el docente.'}, status=status.HTTP_400_BAD_REQUEST)
    paralelo = services_asignar_docente(paralelo_id, docente_id, request.data)
    return Response({'id_paralelo': paralelo.pk, 'id_docente': paralelo.docente_id, 'estado': paralelo.estado})


@api_view(['GET', 'POST', 'PATCH', 'DELETE'])
@permission_classes([PermisoAdministrador])
def inscripciones(request, inscripcion_id=None):
    """Consulto, creo o cambio de paralelo una inscripciÃ³n."""
    if request.method == 'GET':
        if all(request.query_params.get(campo) for campo in ('id_idioma', 'id_nivel', 'id_turno')):
            disponibles = listar_paralelos_disponibles(
                request.query_params['id_idioma'], request.query_params['id_nivel'], request.query_params['id_turno']
            )
            return Response([{
                'id_paralelo': item['paralelo'].pk,
                'codigo': item['paralelo'].codigo,
                'programa': item['paralelo'].programa.nombre if item['paralelo'].programa else None,
                'docente': str(item['paralelo'].docente.usuario),
                'horarios': list(item['paralelo'].horarios.values('dia_semana', 'hora_inicio', 'hora_fin')),
                'inscritos': item['inscritos'],
                'cupo_libre': item['cupo_libre'],
            } for item in disponibles])
        queryset = EstudianteParalelo.objects.select_related(
            'estudiante__usuario', 'paralelo__curso', 'paralelo__turno'
        ).order_by('-fecha_ingreso')
        estudiante_id = request.query_params.get('id_estudiante')
        if estudiante_id:
            queryset = queryset.filter(estudiante_id=estudiante_id)
        return Response(EstudianteParaleloSerializer(queryset, many=True).data)

    if request.method == 'POST':
        serializer = InscripcionEntradaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inscripcion = inscribir_estudiante(
            estudiante_id=serializer.validated_data['id_estudiante'],
            paralelo_id=serializer.validated_data['id_paralelo'],
        )
        return Response(EstudianteParaleloSerializer(inscripcion).data, status=status.HTTP_201_CREATED)

    if request.method == 'DELETE':
        if inscripcion_id is None:
            return Response({'error': 'Debes indicar la inscripción que deseas retirar.'}, status=status.HTTP_400_BAD_REQUEST)
        retirar_inscripcion(inscripcion_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    if inscripcion_id is None or not request.data.get('id_paralelo'):
        return Response({'error': 'Debes indicar la inscripciÃ³n y el paralelo destino.'}, status=status.HTTP_400_BAD_REQUEST)
    inscripcion = cambiar_asignacion(inscripcion_id, request.data['id_paralelo'])
    return Response(EstudianteParaleloSerializer(inscripcion).data)


@api_view(['GET'])
@permission_classes([PermisoDocente])
def estudiantes_del_paralelo(request, paralelo_id):
    """Listo los estudiantes del paralelo asignado al docente autenticado."""
    usuario = usuario_de_sesion(request)
    docente = get_object_or_404(Docente, pk=usuario.pk)
    queryset = estudiantes_de_paralelo(paralelo_id, docente)
    return Response([{
        'id_estudiante': item.estudiante_id,
        'nombre': str(item.estudiante.usuario),
        'codigo_estudiante': item.estudiante.codigo_estudiante,
        'correo': item.estudiante.usuario.correo,
        'telefono': item.estudiante.usuario.telefono,
        'estado': item.estado,
    } for item in queryset])


@api_view(['GET'])
@permission_classes([PermisoEstudiante])
def mis_cursos(request):
    """Listo solo los cursos del estudiante autenticado."""
    usuario = usuario_de_sesion(request)
    estudiante = get_object_or_404(Estudiante, pk=usuario.pk)
    inscripciones = EstudianteParalelo.objects.filter(
        estudiante=estudiante, estado='ACTIVO', paralelo__estado='ACTIVO'
    ).select_related(
        'paralelo__curso__idioma', 'paralelo__curso__nivel', 'paralelo__turno', 'paralelo__docente__usuario'
    ).prefetch_related('paralelo__horarios').order_by('paralelo__curso__nombre')
    return Response([{
        'id_paralelo': inscripcion.paralelo_id,
        'codigo_paralelo': inscripcion.paralelo.codigo,
        'curso': inscripcion.paralelo.curso.nombre,
        'idioma': inscripcion.paralelo.curso.idioma.nombre,
        'nivel': inscripcion.paralelo.curso.nivel.codigo,
        'turno': inscripcion.paralelo.turno.nombre,
        'docente': str(inscripcion.paralelo.docente.usuario),
        'modalidad': inscripcion.paralelo.modalidad,
        'aula': inscripcion.paralelo.aula,
        'horarios': [{
            'dia_semana': horario.dia_semana,
            'hora_inicio': horario.hora_inicio,
            'hora_fin': horario.hora_fin,
        } for horario in inscripcion.paralelo.horarios.all()],
    } for inscripcion in inscripciones])


@api_view(['GET'])
@permission_classes([PermisoDocente])
def cursos_del_docente(request):
    """Listo los paralelos asignados al docente autenticado."""
    usuario = usuario_de_sesion(request)
    docente = get_object_or_404(Docente, pk=usuario.pk)
    queryset = Paralelo.objects.filter(docente=docente, estado='ACTIVO').select_related(
        'curso__idioma', 'curso__nivel', 'turno'
    ).prefetch_related('horarios').order_by('curso__nombre', 'codigo')
    return Response([{
        'id_paralelo': paralelo.pk,
        'codigo': paralelo.codigo,
        'curso': paralelo.curso.nombre,
        'idioma': paralelo.curso.idioma.nombre,
        'nivel': paralelo.curso.nivel.codigo,
        'turno': paralelo.turno.nombre,
        'aula': paralelo.aula,
        'modalidad': paralelo.modalidad,
        'horarios': [{
            'dia_semana': horario.dia_semana,
            'hora_inicio': horario.hora_inicio,
            'hora_fin': horario.hora_fin,
        } for horario in paralelo.horarios.all()],
    } for paralelo in queryset])


@api_view(['GET'])
@permission_classes([PermisoDocente])
def estudiantes_del_curso(request, curso_id):
    """Listo estudiantes de un curso que tiene asignado el docente."""
    usuario = usuario_de_sesion(request)
    docente = get_object_or_404(Docente, pk=usuario.pk)
    paralelos_docente = Paralelo.objects.filter(docente=docente, curso_id=curso_id, estado='ACTIVO')
    if not paralelos_docente.exists():
        raise PermissionDenied('No tienes acceso a los estudiantes de este curso.')
    inscripciones = EstudianteParalelo.objects.filter(
        paralelo__in=paralelos_docente, estado='ACTIVO'
    ).select_related('estudiante__usuario', 'paralelo').order_by('estudiante__usuario__ap_pat')
    return Response([{
        'id_estudiante': inscripcion.estudiante_id,
        'nombre': str(inscripcion.estudiante.usuario),
        'codigo_estudiante': inscripcion.estudiante.codigo_estudiante,
        'correo': inscripcion.estudiante.usuario.correo,
        'telefono': inscripcion.estudiante.usuario.telefono,
        'paralelo': inscripcion.paralelo.codigo,
        'estado': inscripcion.estado,
    } for inscripcion in inscripciones])


@api_view(['GET'])
@permission_classes([PermisoEstudiante])
def mis_materiales(request):
    """Listo los materiales recientes de los cursos del estudiante autenticado."""
    usuario = usuario_de_sesion(request)
    estudiante = get_object_or_404(Estudiante, pk=usuario.pk)
    paralelo_id = _paralelo_solicitado_estudiante(request, estudiante)
    return Response(MaterialSerializer(materiales_estudiante(estudiante, paralelo_id), many=True).data)


def _paralelo_solicitado_estudiante(request, estudiante):
    """Valido que el paralelo opcional pertenezca a las inscripciones del estudiante."""
    paralelo_id = request.query_params.get('id_paralelo')
    if not paralelo_id:
        return None
    try:
        paralelo_id = int(paralelo_id)
    except (TypeError, ValueError):
        raise ValidationError('El identificador del curso no es válido.')
    if not EstudianteParalelo.objects.filter(
        estudiante=estudiante, paralelo_id=paralelo_id, estado='ACTIVO', paralelo__estado='ACTIVO'
    ).exists():
        raise PermissionDenied('No tienes acceso a la información de este curso.')
    return paralelo_id


@api_view(['GET'])
@permission_classes([PermisoEstudiante])
def mis_actividades(request):
    """Muestro las actividades con plazo y estado del estudiante autenticado."""
    estudiante = get_object_or_404(Estudiante, pk=usuario_de_sesion(request).pk)
    paralelo_id = _paralelo_solicitado_estudiante(request, estudiante)
    resultado = []
    for actividad, entrega, estado in actividades_estudiante(estudiante, paralelo_id):
        item = ActividadSerializer(actividad).data
        item.update({'estado_estudiante': estado, 'id_entrega': entrega.pk if entrega else None,
                     'es_tardia': entrega.es_tardia if entrega else False,
                     'calificacion': entrega.calificacion if entrega else None,
                     'observaciones': entrega.observaciones if entrega else None})
        resultado.append(item)
    return Response(resultado)


@api_view(['POST'])
@permission_classes([PermisoEstudiante])
def entregar_actividad_api(request, actividad_id):
    """Registro la entrega del estudiante después de validar sus datos."""
    serializer = EntregaEntradaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    estudiante = get_object_or_404(Estudiante, pk=usuario_de_sesion(request).pk)
    from .services import entregar_actividad as guardar_entrega
    entrega = guardar_entrega(estudiante, actividad_id, **serializer.validated_data)
    return Response({'id_entrega': entrega.pk, 'estado': entrega.estado, 'es_tardia': entrega.es_tardia,
                     'fecha_entrega': entrega.fecha_entrega}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([PermisoEstudiante])
def mis_calificaciones(request):
    """Muestro las notas y observaciones propias junto con el promedio."""
    estudiante = get_object_or_404(Estudiante, pk=usuario_de_sesion(request).pk)
    paralelo_id = _paralelo_solicitado_estudiante(request, estudiante)
    entregas = Entrega.objects.filter(estudiante=estudiante, calificacion__isnull=False).select_related(
        'actividad__paralelo__curso'
    ).order_by('-fecha_calificacion')
    if paralelo_id:
        entregas = entregas.filter(actividad__paralelo_id=paralelo_id)
    notas = [item.calificacion for item in entregas]
    return Response({'promedio': round(sum(notas) / len(notas), 2) if notas else None,
                     'actividades_calificadas': len(notas), 'calificaciones': [{
                         'id_entrega': item.pk, 'actividad': item.actividad.titulo,
                         'curso': item.actividad.paralelo.curso.nombre,
                         'calificacion': item.calificacion, 'puntaje_maximo': item.actividad.puntaje_maximo,
                         'observaciones': item.observaciones, 'fecha_calificacion': item.fecha_calificacion,
                     } for item in entregas]})


@api_view(['GET'])
@permission_classes([PermisoEstudiante])
def mi_asistencia(request):
    """Muestro historial y porcentaje de asistencia del estudiante autenticado."""
    estudiante = get_object_or_404(Estudiante, pk=usuario_de_sesion(request).pk)
    paralelo_id = _paralelo_solicitado_estudiante(request, estudiante)
    asistencias = Asistencia.objects.filter(estudiante=estudiante).select_related(
        'sesion__paralelo__curso'
    ).order_by('-sesion__fecha')
    if paralelo_id:
        asistencias = asistencias.filter(sesion__paralelo_id=paralelo_id)
    total = asistencias.count()
    presentes = asistencias.filter(estado__in=('PRESENTE', 'TARDANZA')).count()
    return Response({'presentes': presentes, 'ausentes': asistencias.filter(estado='AUSENTE').count(),
                     'porcentaje': round(presentes * 100 / total, 2) if total else None,
                     'historial': [{'curso': a.sesion.paralelo.curso.nombre, 'fecha': a.sesion.fecha,
                                    'tema': a.sesion.tema, 'estado': a.estado, 'observacion': a.observacion}
                                   for a in asistencias]})


@api_view(['GET'])
@permission_classes([PermisoEstudiante])
def mi_progreso(request):
    """Integro las calificaciones, entregas y asistencia de mis paralelos."""
    estudiante = get_object_or_404(Estudiante, pk=usuario_de_sesion(request).pk)
    inscripciones = EstudianteParalelo.objects.filter(estudiante=estudiante, estado='ACTIVO', paralelo__estado='ACTIVO').select_related('paralelo__curso')
    paralelo_id = _paralelo_solicitado_estudiante(request, estudiante)
    if paralelo_id:
        inscripciones = inscripciones.filter(paralelo_id=paralelo_id)
    return Response([resumen_progreso(estudiante, i.paralelo) for i in inscripciones])


@api_view(['GET'])
@permission_classes([PermisoDocente])
def progreso_de_mis_estudiantes(request, paralelo_id=None):
    """Muestro progreso agregado de estudiantes en paralelos docentes."""
    docente = get_object_or_404(Docente, pk=usuario_de_sesion(request).pk)
    return Response(progreso_estudiantes_docente(docente, paralelo_id))


@api_view(['GET'])
@permission_classes([PermisoAdministrador])
def resumen_academico_admin(request):
    """Muestro el resumen por curso y la búsqueda administrativa de estudiantes."""
    curso_id = request.query_params.get('curso_id') or None
    if curso_id and not curso_id.isdigit():
        return Response({'detalle': 'El identificador del curso no es válido.'}, status=status.HTTP_400_BAD_REQUEST)
    busqueda = request.query_params.get('busqueda', '').strip()
    if len(busqueda) > 100:
        return Response({'detalle': 'La búsqueda no puede superar 100 caracteres.'}, status=status.HTTP_400_BAD_REQUEST)

    cursos = informacion_general_cursos(curso_id)
    promedios = [c['promedio'] for c in cursos if c['promedio'] is not None]
    asistencias = [c['asistencia_porcentaje'] for c in cursos if c['asistencia_porcentaje'] is not None]
    inscripciones = EstudianteParalelo.objects.filter(
        estado='ACTIVO', paralelo__estado='ACTIVO'
    )
    if curso_id:
        inscripciones = inscripciones.filter(paralelo__curso_id=curso_id)
    activos = inscripciones.values('estudiante').distinct().count()
    return Response({'estudiantes_activos': activos,
                     'promedio_general': round(sum(promedios) / len(promedios), 2) if promedios else None,
                     'asistencia_general': round(sum(asistencias) / len(asistencias), 2) if asistencias else None,
                     'cursos': cursos,
                     'estudiantes': buscar_estudiantes_resumen(busqueda, curso_id) if busqueda else []})
