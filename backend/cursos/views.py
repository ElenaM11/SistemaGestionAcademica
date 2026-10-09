from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound

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
    asignar_docente, cambiar_asignacion, crear_o_actualizar_curso,
    crear_paralelo, estudiantes_de_paralelo, inscribir_estudiante,
    habilitar_idioma_docente, listar_paralelos_disponibles,
)


class CatalogoCursosView(APIView):
    """Gestiono el catálogo de cursos para el administrador."""
    permission_classes = [PermisoAdministrador]

    def get(self, request):
        """Devuelvo los cursos activos e inactivos del catálogo."""
        cursos = Curso.objects.select_related('idioma', 'nivel').order_by('nombre')
        return Response(CursoSerializer(cursos, many=True).data)

    def post(self, request):
        """Creo un curso después de validar idioma y nivel."""
        serializer = CursoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            curso = crear_o_actualizar_curso(serializer.validated_data)
        except IntegrityError:
            return Response({'error': 'El curso no se pudo guardar por un dato duplicado.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CursoSerializer(curso).data, status=status.HTTP_201_CREATED)


class CursoDetalleView(APIView):
    """Consulto o actualizo un curso del catálogo."""
    permission_classes = [PermisoAdministrador]

    def patch(self, request, curso_id):
        """Actualizo los datos recibidos sin desactivar el curso por omisión."""
        curso = get_object_or_404(Curso, pk=curso_id)
        serializer = CursoSerializer(curso, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        curso = crear_o_actualizar_curso(serializer.validated_data, curso_id)
        return Response(CursoSerializer(curso).data)


class CatalogoSimpleView(APIView):
    """Consulto los catálogos auxiliares usados por cursos y paralelos."""
    permission_classes = [PermisoAdministrador]

    def get(self, request, catalogo):
        """Devuelvo idiomas, niveles, programas o turnos según la ruta."""
        opciones = {
            'idiomas': (Idioma.objects.order_by('nombre'), IdiomaSerializer),
            'niveles': (Nivel.objects.order_by('codigo'), NivelSerializer),
            'programas': (Programa.objects.filter(activo=True).order_by('nombre'), ProgramaSerializer),
            'turnos': (Turno.objects.order_by('nombre'), TurnoSerializer),
        }
        if catalogo not in opciones:
            raise NotFound('El catálogo solicitado no existe.')
        queryset, serializer_class = opciones[catalogo]
        return Response(serializer_class(queryset, many=True).data)


class DocentesIdiomaView(APIView):
    """Listo docentes activos habilitados para un idioma."""
    permission_classes = [PermisoAdministrador]

    def get(self, request, idioma_id):
        """Devuelvo docentes que enseñan el idioma solicitado."""
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


class IdiomasDocenteView(APIView):
    """Administro los idiomas que habilitan la asignación de cada docente."""
    permission_classes = [PermisoAdministrador]

    def get(self, request, docente_id):
        """Devuelvo los idiomas ya habilitados para el docente indicado."""
        docente = get_object_or_404(Docente, pk=docente_id)
        return Response(DocenteIdiomaSerializer(
            DocenteIdioma.objects.filter(docente=docente).select_related('idioma'), many=True
        ).data)

    def post(self, request, docente_id):
        """Habilito un idioma para el docente sin crear relaciones duplicadas."""
        serializer = DocenteIdiomaEntradaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        relacion, creada = habilitar_idioma_docente(docente_id, serializer.validated_data['id_idioma'])
        return Response(DocenteIdiomaSerializer(relacion).data, status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK)


class ParalelosView(APIView):
    """Gestiono los paralelos y presento sus cupos ocupados."""
    permission_classes = [PermisoAdministrador]

    def get(self, request):
        """Devuelvo los paralelos con curso, docente, horario e inscritos."""
        paralelos = Paralelo.objects.select_related(
            'curso__idioma', 'curso__nivel', 'turno', 'docente__usuario'
        ).prefetch_related('horarios', 'inscripciones').order_by('codigo')
        return Response([{
            'id_paralelo': p.pk,
            'codigo': p.codigo,
            'curso': p.curso.nombre,
            'idioma': p.curso.idioma.nombre,
            'nivel': p.curso.nivel.codigo,
            'turno': p.turno.nombre,
            'programa': p.programa.nombre if p.programa else None,
            'docente': f'{p.docente.usuario.nombres} {p.docente.usuario.ap_pat}'.strip(),
            'modalidad': p.modalidad,
            'aula': p.aula,
            'estado': p.estado,
            'inscritos': sum(i.estado == 'ACTIVO' for i in p.inscripciones.all()),
            'cupo_maximo': p.cupo_maximo,
            'horarios': [{'dia_semana': h.dia_semana, 'hora_inicio': h.hora_inicio, 'hora_fin': h.hora_fin} for h in p.horarios.all()],
        } for p in paralelos])

    def post(self, request):
        """Creo un paralelo y sus horarios con validación de carga docente."""
        serializer = ParaleloEntradaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            paralelo = crear_paralelo(serializer.validated_data)
        except IntegrityError:
            return Response({'error': 'El código del paralelo ya existe.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'id_paralelo': paralelo.pk, 'codigo': paralelo.codigo}, status=status.HTTP_201_CREATED)


class AsignarDocenteView(APIView):
    """Asigno o reasigno docentes a paralelos desde la administración."""
    permission_classes = [PermisoAdministrador]

    def post(self, request, paralelo_id=None):
        """Cambio el docente y los datos operativos autorizados del paralelo."""
        docente_id = request.data.get('id_docente')
        paralelo_id = paralelo_id or request.data.get('id_paralelo')
        if not docente_id or not paralelo_id:
            return Response({'error': 'Debes indicar el paralelo y el docente.'}, status=status.HTTP_400_BAD_REQUEST)
        paralelo = asignar_docente(paralelo_id, docente_id, request.data)
        return Response({'id_paralelo': paralelo.pk, 'id_docente': paralelo.docente_id, 'estado': paralelo.estado})


class InscripcionesView(APIView):
    """Busco paralelos disponibles y gestiono inscripciones de estudiantes."""
    permission_classes = [PermisoAdministrador]

    def get(self, request):
        """Devuelvo inscripciones o paralelos disponibles para los filtros recibidos."""
        if all(request.query_params.get(k) for k in ('id_idioma', 'id_nivel', 'id_turno')):
            paralelos = listar_paralelos_disponibles(
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
            } for item in paralelos])
        queryset = EstudianteParalelo.objects.select_related(
            'estudiante__usuario', 'paralelo__curso', 'paralelo__turno'
        ).order_by('-fecha_ingreso')
        estudiante_id = request.query_params.get('id_estudiante')
        if estudiante_id:
            queryset = queryset.filter(estudiante_id=estudiante_id)
        return Response(EstudianteParaleloSerializer(queryset, many=True).data)

    def post(self, request):
        """Inscribo a un estudiante y verifico el cupo disponible."""
        serializer = InscripcionEntradaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inscripcion = inscribir_estudiante(**{
            'estudiante_id': serializer.validated_data['id_estudiante'],
            'paralelo_id': serializer.validated_data['id_paralelo'],
        })
        return Response(EstudianteParaleloSerializer(inscripcion).data, status=status.HTTP_201_CREATED)

    def patch(self, request, inscripcion_id=None):
        """Muevo una inscripción existente al paralelo solicitado."""
        if inscripcion_id is None or not request.data.get('id_paralelo'):
            return Response({'error': 'Debes indicar la inscripción y el paralelo destino.'}, status=status.HTTP_400_BAD_REQUEST)
        inscripcion = cambiar_asignacion(inscripcion_id, request.data['id_paralelo'])
        return Response(EstudianteParaleloSerializer(inscripcion).data)


class EstudiantesDelDocenteView(APIView):
    """Consulto estudiantes únicamente de un paralelo del docente autenticado."""
    permission_classes = [PermisoDocente]

    def get(self, request, paralelo_id):
        """Devuelvo datos básicos de estudiantes del paralelo autorizado."""
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


class MisCursosView(APIView):
    """Consulto los cursos inscritos del estudiante autenticado."""
    permission_classes = [PermisoEstudiante]

    def get(self, request):
        """Devuelvo solo los cursos y paralelos del estudiante de la sesión."""
        usuario = usuario_de_sesion(request)
        estudiante = get_object_or_404(Estudiante, pk=usuario.pk)
        inscripciones = EstudianteParalelo.objects.filter(
            estudiante=estudiante, estado='ACTIVO', paralelo__estado='ACTIVO'
        ).select_related(
            'paralelo__curso__idioma', 'paralelo__curso__nivel', 'paralelo__turno', 'paralelo__docente__usuario'
        ).prefetch_related('paralelo__horarios').order_by('paralelo__curso__nombre')
        return Response([{
            'id_paralelo': i.paralelo_id,
            'codigo_paralelo': i.paralelo.codigo,
            'curso': i.paralelo.curso.nombre,
            'idioma': i.paralelo.curso.idioma.nombre,
            'nivel': i.paralelo.curso.nivel.codigo,
            'turno': i.paralelo.turno.nombre,
            'docente': str(i.paralelo.docente.usuario),
            'modalidad': i.paralelo.modalidad,
            'aula': i.paralelo.aula,
            'horarios': [{'dia_semana': h.dia_semana, 'hora_inicio': h.hora_inicio, 'hora_fin': h.hora_fin} for h in i.paralelo.horarios.all()],
        } for i in inscripciones])


class CursosDelDocenteView(APIView):
    """Consulto los paralelos y cursos asignados al docente autenticado."""
    permission_classes = [PermisoDocente]

    def get(self, request):
        """Devuelvo solo los paralelos asignados al docente de la sesión."""
        usuario = usuario_de_sesion(request)
        docente = get_object_or_404(Docente, pk=usuario.pk)
        paralelos = Paralelo.objects.filter(docente=docente, estado='ACTIVO').select_related(
            'curso__idioma', 'curso__nivel', 'turno'
        ).prefetch_related('horarios').order_by('curso__nombre', 'codigo')
        return Response([{
            'id_paralelo': p.pk, 'codigo': p.codigo, 'curso': p.curso.nombre,
            'idioma': p.curso.idioma.nombre, 'nivel': p.curso.nivel.codigo,
            'turno': p.turno.nombre, 'aula': p.aula, 'modalidad': p.modalidad,
            'horarios': [{'dia_semana': h.dia_semana, 'hora_inicio': h.hora_inicio, 'hora_fin': h.hora_fin} for h in p.horarios.all()],
        } for p in paralelos])


class EstudiantesDelCursoView(APIView):
    """Consulto estudiantes inscritos en paralelos del curso del docente."""
    permission_classes = [PermisoDocente]

    def get(self, request, curso_id):
        """Devuelvo estudiantes de ese curso solo cuando el docente lo tiene asignado."""
        usuario = usuario_de_sesion(request)
        docente = get_object_or_404(Docente, pk=usuario.pk)
        paralelos = Paralelo.objects.filter(docente=docente, curso_id=curso_id, estado='ACTIVO')
        if not paralelos.exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No tienes acceso a los estudiantes de este curso.')
        inscripciones = EstudianteParalelo.objects.filter(
            paralelo__in=paralelos, estado='ACTIVO'
        ).select_related('estudiante__usuario', 'paralelo').order_by('estudiante__usuario__ap_pat')
        return Response([{
            'id_estudiante': i.estudiante_id,
            'nombre': str(i.estudiante.usuario),
            'codigo_estudiante': i.estudiante.codigo_estudiante,
            'correo': i.estudiante.usuario.correo,
            'telefono': i.estudiante.usuario.telefono,
            'paralelo': i.paralelo.codigo,
            'estado': i.estado,
        } for i in inscripciones])


