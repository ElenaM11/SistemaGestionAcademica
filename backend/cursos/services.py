import re
import unicodedata

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from usuarios.models import Docente, Estudiante

from .models import (
    Actividad, Asistencia, Curso, DocenteIdioma, Entrega, EstudianteParalelo,
    HorarioParalelo, Idioma, Material, Nivel, Paralelo, Programa,
    SesionClase, Turno,
)


def _prefijo_codigo(texto):
    """Normalizo un nombre de idioma o turno a un prefijo de tres letras."""
    normalizado = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode('ascii')
    letras = re.sub(r'[^A-Za-z]', '', normalizado).upper()
    return letras[:3]


def _siguiente_letra_paralelo(codigo):
    """Busco la siguiente letra disponible en la serie alfabética de paralelos."""
    encontrados = []
    patron = re.compile(r'^[A-Z]+$')
    for existente in Paralelo.objects.filter(codigo__startswith=codigo).values_list('codigo', flat=True):
        sufijo = existente.removeprefix(codigo)
        if patron.fullmatch(sufijo):
            encontrados.append(sufijo)
    if not encontrados:
        return 'A'
    valor = max(sum((ord(letra) - 64) * (26 ** posicion) for posicion, letra in enumerate(reversed(sufijo)))
                for sufijo in encontrados) + 1
    letras = ''
    while valor:
        valor, resto = divmod(valor - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def generar_codigo_paralelo(curso, turno, gestion=None):
    """Genero un código por idioma, turno, gestión y siguiente letra disponible."""
    codigo_idioma = _prefijo_codigo(curso.idioma.codigo or curso.idioma.nombre)
    codigo_turno = _prefijo_codigo(turno.nombre)
    if not codigo_idioma or not codigo_turno:
        raise ValidationError('Configura el código del idioma y el nombre del turno para generar el paralelo.')
    gestion = gestion or timezone.localdate().year
    prefijo = f'{codigo_idioma.upper()}-{codigo_turno}-{gestion}-'
    return f'{prefijo}{_siguiente_letra_paralelo(prefijo)}'


def crear_elemento_catalogo(tipo, datos):
    """Creo un elemento de catálogo auxiliar con los campos definidos en el esquema."""
    if tipo == 'idioma':
        datos['codigo'] = (datos.get('codigo') or '').strip().upper() or None
        return Idioma.objects.create(**datos)
    if tipo == 'nivel':
        datos['codigo'] = datos['codigo'].strip().upper()
        return Nivel.objects.create(**datos)
    if tipo == 'programa':
        return Programa.objects.create(**datos)
    if tipo == 'turno':
        return Turno.objects.create(**datos)
    raise ValidationError('El tipo de catálogo solicitado no es válido.')


def crear_o_actualizar_curso(datos, curso_id=None):
    """Guardo un curso validando sus referencias del catálogo."""
    curso = get_object_or_404(Curso, pk=curso_id) if curso_id else Curso()
    idioma = datos.get('idioma', curso.idioma if curso.pk else None)
    nivel = datos.get('nivel', curso.nivel if curso.pk else None)
    idioma = get_object_or_404(Idioma, pk=idioma.pk, activo=True)
    nivel = get_object_or_404(Nivel, pk=nivel.pk)
    for campo in ('nombre', 'descripcion', 'activo'):
        if campo in datos:
            setattr(curso, campo, datos[campo])
    curso.idioma, curso.nivel = idioma, nivel
    curso.save()
    return curso


def _validar_idioma_docente(docente, curso):
    """Compruebo que el docente activo enseñe el idioma del curso."""
    if not docente.usuario.estado:
        raise ValidationError('El docente está desactivado.')
    if not DocenteIdioma.objects.filter(docente=docente, idioma=curso.idioma).exists():
        raise ValidationError('El docente no está habilitado para enseñar el idioma del curso.')


def habilitar_idioma_docente(docente_id, idioma_id):
    """Registro que un docente está habilitado para enseñar un idioma."""
    docente = get_object_or_404(Docente.objects.select_related('usuario'), pk=docente_id)
    idioma = get_object_or_404(Idioma, pk=idioma_id, activo=True)
    if not docente.usuario.estado:
        raise ValidationError('No se puede habilitar un docente desactivado.')
    relacion, creada = DocenteIdioma.objects.get_or_create(docente=docente, idioma=idioma)
    return relacion, creada


def _hay_cruce_horario(docente, horarios, paralelo_id=None):
    """Detecto cruces entre los horarios nuevos y los paralelos del docente."""
    existentes = HorarioParalelo.objects.filter(paralelo__docente=docente, paralelo__estado='ACTIVO')
    if paralelo_id:
        existentes = existentes.exclude(paralelo_id=paralelo_id)
    for horario in horarios:
        if existentes.filter(
            dia_semana__iexact=horario['dia_semana'],
            hora_inicio__lt=horario['hora_fin'],
            hora_fin__gt=horario['hora_inicio'],
        ).exists():
            return True
        for otro in horarios:
            if otro is horario or otro['dia_semana'].casefold() != horario['dia_semana'].casefold():
                continue
            if otro['hora_inicio'] < horario['hora_fin'] and otro['hora_fin'] > horario['hora_inicio']:
                raise ValidationError('El paralelo contiene horarios que se cruzan entre sí.')
    return False


def docente_disponible_para_horarios(docente, horarios, paralelo_id=None):
    """Compruebo si el docente puede asumir los horarios mostrados en la página."""
    return not _hay_cruce_horario(docente, horarios, paralelo_id)


def _obtener_referencias_paralelo(datos):
    """Busco curso, docente, turno y programa que se usarán en el paralelo."""
    curso = get_object_or_404(Curso.objects.select_related('idioma'), pk=datos['id_curso'], activo=True)
    docente = get_object_or_404(Docente.objects.select_for_update().select_related('usuario'), pk=datos['id_docente'])
    turno = get_object_or_404(Turno, pk=datos['id_turno'])
    programa_id = datos.get('id_programa')
    programa = get_object_or_404(Programa, pk=programa_id, activo=True) if programa_id else None
    _validar_idioma_docente(docente, curso)
    return curso, docente, turno, programa


@transaction.atomic
def crear_paralelo(datos):
    """Creo un paralelo y sus horarios después de validar la carga docente."""
    curso, docente, turno, programa = _obtener_referencias_paralelo(datos)
    horarios = datos['horarios']
    if _hay_cruce_horario(docente, horarios):
        raise ValidationError('El docente ya tiene un curso asignado en ese horario.')
    Idioma.objects.select_for_update().get(pk=curso.idioma_id)
    fecha_inicio = datos.get('fecha_inicio')
    gestion = fecha_inicio.year if fecha_inicio else datos.get('gestion')
    codigo = generar_codigo_paralelo(curso, turno, gestion)
    paralelo = Paralelo.objects.create(
        codigo=codigo, curso=curso, docente=docente, turno=turno, programa=programa,
        modalidad=datos.get('modalidad'), aula=datos.get('aula'),
        cupo_minimo_apertura=datos.get('cupo_minimo_apertura'), cupo_maximo=datos.get('cupo_maximo'),
        fecha_inicio=datos.get('fecha_inicio'), fecha_fin=datos.get('fecha_fin'),
    )
    HorarioParalelo.objects.bulk_create([
        HorarioParalelo(paralelo=paralelo, **horario) for horario in horarios
    ])
    return paralelo


@transaction.atomic
def actualizar_paralelo(paralelo_id, datos):
    """Actualizo un paralelo validando idioma, cruces de horario y cupos ocupados."""
    paralelo = get_object_or_404(
        Paralelo.objects.select_for_update().select_related('curso__idioma'), pk=paralelo_id,
    )
    if datos == {'estado': 'INACTIVO'}:
        paralelo.estado = 'INACTIVO'
        paralelo.save(update_fields=['estado'])
        return paralelo
    curso_id = datos.get('id_curso', paralelo.curso_id)
    curso = get_object_or_404(Curso.objects.select_related('idioma'), pk=curso_id)
    if not curso.activo and curso.pk != paralelo.curso_id:
        raise ValidationError('No se puede asignar un curso inactivo a un paralelo.')
    docente = get_object_or_404(
        Docente.objects.select_for_update().select_related('usuario'),
        pk=datos.get('id_docente', paralelo.docente_id),
    )
    turno = get_object_or_404(Turno, pk=datos.get('id_turno', paralelo.turno_id))
    programa_id = datos.get('id_programa', paralelo.programa_id)
    programa = get_object_or_404(Programa, pk=programa_id) if programa_id else None
    if programa and not programa.activo and programa.pk != paralelo.programa_id:
        raise ValidationError('No se puede asignar un programa inactivo a un paralelo.')
    cambio_docente = docente.pk != paralelo.docente_id
    cambio_idioma = curso.idioma_id != paralelo.curso.idioma_id
    reactivacion = datos.get('estado') == 'ACTIVO' and paralelo.estado != 'ACTIVO'
    if reactivacion and not curso.activo:
        raise ValidationError('No se puede activar un paralelo cuyo curso está inactivo.')
    if reactivacion and programa and not programa.activo:
        raise ValidationError('No se puede activar un paralelo cuyo programa está inactivo.')
    if cambio_docente or cambio_idioma or reactivacion:
        _validar_idioma_docente(docente, curso)

    horarios = list(paralelo.horarios.values('dia_semana', 'hora_inicio', 'hora_fin'))
    if (cambio_docente or cambio_idioma or reactivacion) and _hay_cruce_horario(docente, horarios, paralelo.pk):
        raise ValidationError('El docente ya tiene un curso asignado en ese horario.')

    minimo = datos.get('cupo_minimo_apertura', paralelo.cupo_minimo_apertura)
    maximo = datos.get('cupo_maximo', paralelo.cupo_maximo)
    if minimo is not None and maximo is not None and minimo > maximo:
        raise ValidationError('El cupo mínimo no puede superar el cupo máximo.')
    inscritos = EstudianteParalelo.objects.select_for_update().filter(
        paralelo=paralelo, estado='ACTIVO',
    ).count()
    if maximo is not None and maximo < inscritos:
        raise ValidationError('El cupo máximo no puede ser menor que los estudiantes inscritos actualmente.')

    paralelo.curso = curso
    paralelo.programa = programa
    paralelo.turno = turno
    paralelo.docente = docente
    for campo in (
        'modalidad', 'aula', 'cupo_minimo_apertura', 'cupo_maximo',
        'fecha_inicio', 'fecha_fin', 'estado',
    ):
        if campo in datos:
            setattr(paralelo, campo, datos[campo])
    paralelo.save()
    return paralelo


@transaction.atomic
def asignar_docente(paralelo_id, docente_id, cambios=None):
    """Asigno o reasigno un docente si cumple idioma y disponibilidad horaria."""
    paralelo = get_object_or_404(Paralelo.objects.select_for_update().select_related('curso__idioma'), pk=paralelo_id)
    docente = get_object_or_404(Docente.objects.select_for_update().select_related('usuario'), pk=docente_id)
    horarios = list(paralelo.horarios.values('dia_semana', 'hora_inicio', 'hora_fin'))
    _validar_idioma_docente(docente, paralelo.curso)
    if _hay_cruce_horario(docente, horarios, paralelo.pk):
        raise ValidationError('El docente ya tiene un curso asignado en ese horario.')
    paralelo.docente = docente
    for campo in ('modalidad', 'aula', 'fecha_inicio', 'fecha_fin'):
        if cambios and campo in cambios:
            setattr(paralelo, campo, cambios[campo])
    paralelo.save()
    return paralelo


def listar_paralelos_disponibles(idioma_id, nivel_id, turno_id):
    """Busco paralelos activos por idioma, nivel y turno con sus cupos libres."""
    paralelos = Paralelo.objects.filter(
        estado='ACTIVO', curso__activo=True, curso__idioma_id=idioma_id,
        curso__nivel_id=nivel_id, turno_id=turno_id,
    ).select_related('curso__idioma', 'curso__nivel', 'turno', 'programa', 'docente__usuario').annotate(
        inscritos=Count('inscripciones', filter=Q(inscripciones__estado='ACTIVO'))
    )
    resultado = []
    for paralelo in paralelos:
        cupo_libre = None if paralelo.cupo_maximo is None else max(paralelo.cupo_maximo - paralelo.inscritos, 0)
        if cupo_libre != 0:
            resultado.append({'paralelo': paralelo, 'inscritos': paralelo.inscritos, 'cupo_libre': cupo_libre})
    return resultado


@transaction.atomic
def inscribir_estudiante(estudiante_id, paralelo_id):
    """Inscribo al estudiante en un paralelo respetando duplicados y cupos."""
    paralelo = get_object_or_404(Paralelo.objects.select_for_update(), pk=paralelo_id, estado='ACTIVO')
    estudiante = get_object_or_404(Estudiante.objects.select_related('usuario'), pk=estudiante_id)
    if not estudiante.usuario.estado:
        raise ValidationError('El estudiante está desactivado.')
    inscripcion = EstudianteParalelo.objects.filter(estudiante=estudiante, paralelo=paralelo).first()
    if inscripcion and inscripcion.estado == 'ACTIVO':
        raise ValidationError('El estudiante ya está inscrito en este paralelo.')
    inscritos = EstudianteParalelo.objects.filter(paralelo=paralelo, estado='ACTIVO').count()
    if paralelo.cupo_maximo is not None and inscritos >= paralelo.cupo_maximo:
        raise ValidationError('El paralelo no tiene cupos disponibles.')
    if inscripcion:
        inscripcion.estado = 'ACTIVO'
        inscripcion.save(update_fields=['estado'])
        return inscripcion
    return EstudianteParalelo.objects.create(estudiante=estudiante, paralelo=paralelo)


@transaction.atomic
def retirar_inscripcion(inscripcion_id):
    """Retiro una inscripción activa y conservo su registro académico."""
    inscripcion = get_object_or_404(
        EstudianteParalelo.objects.select_for_update(),
        pk=inscripcion_id,
    )
    if inscripcion.estado != 'ACTIVO':
        raise ValidationError('La inscripción ya está retirada.')
    inscripcion.estado = 'RETIRADO'
    inscripcion.save(update_fields=['estado'])
    return inscripcion


@transaction.atomic
def cambiar_asignacion(estudiante_paralelo_id, paralelo_id):
    """Muevo una inscripción activa tras verificar el cupo del paralelo destino."""
    inscripcion = get_object_or_404(EstudianteParalelo.objects.select_for_update(), pk=estudiante_paralelo_id)
    if inscripcion.estado != 'ACTIVO':
        raise ValidationError('Solo se puede modificar una inscripción activa.')
    nuevo = get_object_or_404(Paralelo.objects.select_for_update(), pk=paralelo_id, estado='ACTIVO')
    if inscripcion.paralelo_id == nuevo.pk:
        return inscripcion
    anterior_destino = EstudianteParalelo.objects.select_for_update().filter(
        estudiante=inscripcion.estudiante, paralelo=nuevo
    ).first()
    if anterior_destino and anterior_destino.estado == 'ACTIVO':
        raise ValidationError('El estudiante ya está inscrito en este paralelo.')
    inscritos = EstudianteParalelo.objects.filter(paralelo=nuevo, estado='ACTIVO').count()
    if nuevo.cupo_maximo is not None and inscritos >= nuevo.cupo_maximo:
        raise ValidationError('El paralelo no tiene cupos disponibles.')
    if anterior_destino:
        inscripcion.estado = 'RETIRADO'
        inscripcion.save(update_fields=['estado'])
        anterior_destino.estado = 'ACTIVO'
        anterior_destino.save(update_fields=['estado'])
        return anterior_destino
    inscripcion.paralelo = nuevo
    inscripcion.save(update_fields=['paralelo'])
    return inscripcion


def estudiantes_de_paralelo(paralelo_id, docente):
    """Devuelvo estudiantes solo si el paralelo pertenece al docente autenticado."""
    paralelo = get_object_or_404(Paralelo, pk=paralelo_id)
    if paralelo.docente_id != docente.pk:
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('No tienes acceso a los estudiantes de este paralelo.')
    return EstudianteParalelo.objects.filter(paralelo=paralelo, estado='ACTIVO').select_related(
        'estudiante__usuario'
    ).order_by('estudiante__usuario__ap_pat', 'estudiante__usuario__ap_mat', 'estudiante__usuario__nombres')


def _inscripciones_estudiante(estudiante):
    """Obtengo los paralelos activos en los que está inscrito el estudiante."""
    return EstudianteParalelo.objects.filter(estudiante=estudiante, estado='ACTIVO', paralelo__estado='ACTIVO')


def materiales_estudiante(estudiante, paralelo_id=None):
    """Listo los materiales recientes de los paralelos activos del estudiante."""
    materiales = Material.objects.filter(paralelo__inscripciones__in=_inscripciones_estudiante(estudiante)).select_related(
        'paralelo', 'paralelo__curso'
    ).order_by('-fecha_publicacion')
    return materiales.filter(paralelo_id=paralelo_id) if paralelo_id else materiales


def actividades_estudiante(estudiante, paralelo_id=None):
    """Listo actividades con su estado calculado para el estudiante autenticado."""
    resultado = []
    ahora = timezone.now()
    qs = Actividad.objects.filter(paralelo__inscripciones__in=_inscripciones_estudiante(estudiante), estado='ACTIVA').select_related(
        'paralelo', 'paralelo__curso'
    ).prefetch_related('entregas').order_by('fecha_limite', '-fecha_publicacion')
    if paralelo_id:
        qs = qs.filter(paralelo_id=paralelo_id)
    for actividad in qs:
        entrega = actividad.entregas.filter(estudiante=estudiante).first()
        estado = 'ENTREGADA' if entrega else ('VENCIDA' if actividad.fecha_limite and actividad.fecha_limite < ahora else 'PENDIENTE')
        resultado.append((actividad, entrega, estado))
    return resultado


@transaction.atomic
def entregar_actividad(estudiante, actividad_id, contenido_texto='', archivo=None):
    """Registro una única entrega y valido inscripción, estado y plazo."""
    actividad = get_object_or_404(Actividad.objects.select_for_update(), pk=actividad_id, estado='ACTIVA')
    if not _inscripciones_estudiante(estudiante).filter(paralelo=actividad.paralelo).exists():
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('No estás inscrito en el paralelo de esta actividad.')
    if Entrega.objects.filter(actividad=actividad, estudiante=estudiante).exists():
        raise ValidationError('Esta actividad ya tiene una entrega registrada y no admite una segunda entrega.')
    tardia = bool(actividad.fecha_limite and timezone.now() > actividad.fecha_limite)
    if tardia and not actividad.permite_entrega_tardia:
        raise ValidationError('El plazo de entrega venció y esta actividad no permite entregas tardías.')
    return Entrega.objects.create(
        actividad=actividad, estudiante=estudiante, contenido_texto=contenido_texto,
        archivo=archivo, es_tardia=tardia, estado='ENTREGADA',
    )


def resumen_progreso(estudiante, paralelo):
    """Integro calificaciones, entregas y asistencia de un estudiante en un paralelo."""
    entregas = Entrega.objects.filter(estudiante=estudiante, actividad__paralelo=paralelo)
    calificadas = entregas.filter(calificacion__isnull=False)
    notas = list(calificadas.values_list('calificacion', flat=True))
    asistencias = Asistencia.objects.filter(estudiante=estudiante, sesion__paralelo=paralelo)
    total_asistencia = asistencias.count()
    presentes = asistencias.filter(estado__in=['PRESENTE', 'TARDANZA']).count()
    return {
        'id_paralelo': paralelo.pk, 'codigo_paralelo': paralelo.codigo, 'curso': paralelo.curso.nombre,
        'promedio': round(sum(notas) / len(notas), 2) if notas else None,
        'actividades_entregadas': entregas.count(),
        'actividades_totales': Actividad.objects.filter(paralelo=paralelo, estado='ACTIVA').count(),
        'actividades_calificadas': calificadas.count(),
        'asistencias_presentes': presentes, 'asistencias_ausentes': asistencias.filter(estado='AUSENTE').count(),
        'asistencia_porcentaje': round(presentes * 100 / total_asistencia, 2) if total_asistencia else None,
    }


def progreso_estudiantes_docente(docente, paralelo_id=None):
    """Reutilizo el resumen de progreso para estudiantes de paralelos docentes."""
    paralelos = Paralelo.objects.filter(docente=docente, estado='ACTIVO')
    if paralelo_id:
        if not paralelos.filter(pk=paralelo_id).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('No tienes acceso al progreso de este paralelo.')
        paralelos = paralelos.filter(pk=paralelo_id)
    resultado = []
    for inscripcion in EstudianteParalelo.objects.filter(paralelo__in=paralelos, estado='ACTIVO').select_related('estudiante__usuario', 'paralelo__curso'):
        resultado.append({
            'id_estudiante': inscripcion.estudiante_id,
            'estudiante': str(inscripcion.estudiante.usuario),
            **resumen_progreso(inscripcion.estudiante, inscripcion.paralelo),
        })
    return resultado


def informacion_general_cursos(curso_id=None):
    """Agrego estudiantes, calificaciones y asistencia por curso sin datos personales."""
    resultado = []
    cursos = Curso.objects.filter(paralelos__estado='ACTIVO').distinct().order_by('nombre')
    if curso_id:
        cursos = cursos.filter(pk=curso_id)
    for curso in cursos:
        paralelos = Paralelo.objects.filter(curso=curso, estado='ACTIVO')
        inscripciones = EstudianteParalelo.objects.filter(paralelo__in=paralelos, estado='ACTIVO')
        calificaciones = Entrega.objects.filter(actividad__paralelo__in=paralelos, calificacion__isnull=False).values_list('calificacion', flat=True)
        notas = list(calificaciones)
        asistencias = Asistencia.objects.filter(sesion__paralelo__in=paralelos)
        total = asistencias.count()
        presentes = asistencias.filter(estado__in=['PRESENTE', 'TARDANZA']).count()
        resultado.append({
            'id_curso': curso.pk, 'curso': curso.nombre,
            'docentes': sorted(set(Paralelo.objects.filter(pk__in=paralelos.values('pk')).values_list('docente__usuario__nombres', flat=True))),
            'estudiantes_activos': inscripciones.values('estudiante').distinct().count(),
            'promedio': round(sum(notas) / len(notas), 2) if notas else None,
            'asistencia_porcentaje': round(presentes * 100 / total, 2) if total else None,
        })
    return resultado


def buscar_estudiantes_resumen(busqueda, curso_id=None):
    """Busco el progreso académico de estudiantes para el panel administrativo."""
    filtro = (
        Q(estudiante__usuario__nombres__icontains=busqueda)
        | Q(estudiante__usuario__ap_pat__icontains=busqueda)
        | Q(estudiante__usuario__ap_mat__icontains=busqueda)
        | Q(estudiante__usuario__correo__icontains=busqueda)
        | Q(estudiante__codigo_estudiante__icontains=busqueda)
    )
    inscripciones = EstudianteParalelo.objects.filter(
        filtro, estado='ACTIVO', paralelo__estado='ACTIVO'
    )
    if curso_id:
        inscripciones = inscripciones.filter(paralelo__curso_id=curso_id)

    resultados = []
    ids_estudiantes = list(
        inscripciones.values_list('estudiante_id', flat=True).distinct()[:100]
    )
    for estudiante in Estudiante.objects.filter(pk__in=ids_estudiantes).select_related('usuario'):
        cursos_estudiante = inscripciones.filter(
            estudiante=estudiante
        ).values_list('paralelo__curso_id', 'paralelo__curso__nombre').distinct()
        for id_curso, nombre_curso in cursos_estudiante:
            inscripciones_curso = EstudianteParalelo.objects.filter(
                estudiante=estudiante, estado='ACTIVO',
                paralelo__estado='ACTIVO', paralelo__curso_id=id_curso,
            )
            if curso_id:
                inscripciones_curso = inscripciones_curso.filter(paralelo__curso_id=curso_id)
            paralelos = Paralelo.objects.filter(
                pk__in=inscripciones_curso.values('paralelo_id')
            )
            actividades = Actividad.objects.filter(paralelo__in=paralelos, estado='ACTIVA')
            entregas = Entrega.objects.filter(
                estudiante=estudiante, actividad__in=actividades
            )
            calificadas = entregas.filter(calificacion__isnull=False)
            asistencia = Asistencia.objects.filter(
                estudiante=estudiante, sesion__paralelo__in=paralelos
            )
            total_asistencia = asistencia.count()
            presentes = asistencia.filter(estado__in=('PRESENTE', 'TARDANZA')).count()
            resultados.append({
                'estudiante': str(estudiante.usuario),
                'codigo_estudiante': estudiante.codigo_estudiante,
                'curso': nombre_curso,
                'paralelos': list(paralelos.values_list('codigo', flat=True)),
                'promedio': calificadas.aggregate(promedio=Avg('calificacion'))['promedio'],
                'entregas': entregas.count(),
                'actividades_totales': actividades.count(),
                'asistencia_porcentaje': round(presentes * 100 / total_asistencia, 2)
                if total_asistencia else None,
            })
    return resultados
