from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from usuarios.models import Docente, Estudiante

from .models import Curso, DocenteIdioma, EstudianteParalelo, Idioma, Nivel, Paralelo, Programa, Turno
from .permissions import PermisoAdministrador, PermisoDocente, PermisoEstudiante, usuario_de_sesion
from .serializers import (
    CursoSerializer, EstudianteParaleloSerializer, IdiomaSerializer,
    DocenteIdiomaSerializer, DocenteIdiomaEntradaSerializer,
    InscripcionEntradaSerializer, NivelSerializer, ParaleloEntradaSerializer,
    ProgramaSerializer, TurnoSerializer,
)
from .services import (
    asignar_docente as services_asignar_docente, cambiar_asignacion, crear_o_actualizar_curso,
    crear_paralelo, estudiantes_de_paralelo, inscribir_estudiante,
    habilitar_idioma_docente, listar_paralelos_disponibles,
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


@api_view(['GET', 'POST', 'PATCH'])
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
