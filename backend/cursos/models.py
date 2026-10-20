from django.db import models
from django.utils import timezone

from usuarios.models import Docente, Estudiante


class Idioma(models.Model):
    """Defino un idioma disponible en el catálogo académico."""
    id_idioma = models.AutoField(primary_key=True, db_column='IdIdioma')
    nombre = models.CharField(max_length=100, unique=True, db_column='Nombre')
    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True, db_column='Codigo')
    activo = models.BooleanField(default=True, db_column='Activo')

    class Meta:
        """Mapeo el modelo a la tabla física de idiomas."""
        db_table = 'idioma'


class Nivel(models.Model):
    """Defino un nivel académico disponible para los cursos."""
    id_nivel = models.AutoField(primary_key=True, db_column='IdNivel')
    codigo = models.CharField(max_length=20, unique=True, db_column='Codigo')

    class Meta:
        """Mapeo el modelo a la tabla física de niveles."""
        db_table = 'nivel'


class Curso(models.Model):
    """Defino un curso asociado a un idioma y a un nivel."""
    id_curso = models.AutoField(primary_key=True, db_column='IdCurso')
    idioma = models.ForeignKey(Idioma, on_delete=models.PROTECT, db_column='IdIdioma', related_name='cursos')
    nivel = models.ForeignKey(Nivel, on_delete=models.PROTECT, db_column='IdNivel', related_name='cursos')
    nombre = models.CharField(max_length=150, db_column='Nombre')
    descripcion = models.TextField(null=True, blank=True, db_column='Descripcion')
    activo = models.BooleanField(default=True, db_column='Activo')

    class Meta:
        """Mapeo el modelo a la tabla física de cursos."""
        db_table = 'curso'


class Programa(models.Model):
    """Defino un programa académico sin agregar campos ajenos al esquema."""
    id_programa = models.AutoField(primary_key=True, db_column='IdPrograma')
    nombre = models.CharField(max_length=150, db_column='Nombre')
    duracion_meses = models.IntegerField(null=True, blank=True, db_column='DuracionMeses')
    descripcion = models.TextField(null=True, blank=True, db_column='Descripcion')
    activo = models.BooleanField(default=True, db_column='Activo')

    class Meta:
        """Mapeo el modelo a la tabla física de programas."""
        db_table = 'programa'


class ProgramaIdioma(models.Model):
    """Relaciono un programa con un idioma y su nivel máximo."""
    id_programa_idioma = models.AutoField(primary_key=True, db_column='IdProgramaIdioma')
    programa = models.ForeignKey(Programa, on_delete=models.CASCADE, db_column='IdPrograma', related_name='idiomas')
    idioma = models.ForeignKey(Idioma, on_delete=models.PROTECT, db_column='IdIdioma', related_name='programas')
    nivel_maximo = models.ForeignKey(Nivel, on_delete=models.PROTECT, db_column='NivelMaximoId', related_name='programas')

    class Meta:
        """Aplico la unicidad definida para programa e idioma."""
        db_table = 'programa_idioma'
        constraints = [models.UniqueConstraint(fields=['programa', 'idioma'], name='uq_programa_idioma')]


class Turno(models.Model):
    """Defino un turno con sus horas referenciales."""
    id_turno = models.AutoField(primary_key=True, db_column='IdTurno')
    nombre = models.CharField(max_length=50, unique=True, db_column='Nombre')
    hora_referencia_inicio = models.TimeField(null=True, blank=True, db_column='HoraReferenciaInicio')
    hora_referencia_fin = models.TimeField(null=True, blank=True, db_column='HoraReferenciaFin')

    class Meta:
        """Mapeo el modelo a la tabla física de turnos."""
        db_table = 'turno'


class DocenteIdioma(models.Model):
    """Registro los idiomas que cada docente está habilitado para enseñar."""
    id_docente_idioma = models.AutoField(primary_key=True, db_column='IdDocenteIdioma')
    docente = models.ForeignKey(Docente, on_delete=models.CASCADE, db_column='IdDocente', related_name='idiomas_docente')
    idioma = models.ForeignKey(Idioma, on_delete=models.CASCADE, db_column='IdIdioma', related_name='docentes')

    class Meta:
        """Aplico la unicidad definida para docente e idioma."""
        db_table = 'docente_idioma'
        constraints = [models.UniqueConstraint(fields=['docente', 'idioma'], name='uq_docente_idioma')]


class Paralelo(models.Model):
    """Defino un paralelo y sus asignaciones académicas."""
    id_paralelo = models.AutoField(primary_key=True, db_column='IdParalelo')
    codigo = models.CharField(max_length=50, unique=True, db_column='Codigo')
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, db_column='IdCurso', related_name='paralelos')
    programa = models.ForeignKey(Programa, on_delete=models.PROTECT, null=True, blank=True, db_column='IdPrograma', related_name='paralelos')
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, db_column='IdTurno', related_name='paralelos')
    docente = models.ForeignKey(Docente, on_delete=models.PROTECT, db_column='IdDocente', related_name='paralelos')
    modalidad = models.CharField(max_length=50, null=True, blank=True, db_column='Modalidad')
    aula = models.CharField(max_length=100, null=True, blank=True, db_column='Aula')
    cupo_minimo_apertura = models.IntegerField(null=True, blank=True, db_column='CupoMinimoApertura')
    cupo_maximo = models.IntegerField(null=True, blank=True, db_column='CupoMaximo')
    fecha_inicio = models.DateField(null=True, blank=True, db_column='FechaInicio')
    fecha_fin = models.DateField(null=True, blank=True, db_column='FechaFin')
    estado = models.CharField(max_length=30, default='ACTIVO', db_column='Estado')

    class Meta:
        """Mapeo el modelo al paralelo y su clave física."""
        db_table = 'paralelo'


class HorarioParalelo(models.Model):
    """Defino el día y el intervalo horario de un paralelo."""
    id_horario = models.AutoField(primary_key=True, db_column='IdHorario')
    paralelo = models.ForeignKey(Paralelo, on_delete=models.CASCADE, db_column='IdParalelo', related_name='horarios')
    dia_semana = models.CharField(max_length=20, db_column='DiaSemana')
    hora_inicio = models.TimeField(db_column='HoraInicio')
    hora_fin = models.TimeField(db_column='HoraFin')

    class Meta:
        """Mapeo el modelo a los horarios físicos de paralelos."""
        db_table = 'horario_paralelo'


class EstudianteParalelo(models.Model):
    """Registro la inscripción y el estado académico del estudiante."""
    id_estudiante_paralelo = models.AutoField(primary_key=True, db_column='IdEstudianteParalelo')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, db_column='IdEstudiante', related_name='inscripciones')
    paralelo = models.ForeignKey(Paralelo, on_delete=models.CASCADE, db_column='IdParalelo', related_name='inscripciones')
    fecha_ingreso = models.DateField(auto_now_add=True, db_column='FechaIngreso')
    estado = models.CharField(max_length=30, default='ACTIVO', db_column='Estado')

    class Meta:
        """Aplico la unicidad definida para estudiante y paralelo."""
        db_table = 'estudiante_paralelo'
        constraints = [models.UniqueConstraint(fields=['estudiante', 'paralelo'], name='uq_estudiante_paralelo')]


class Material(models.Model):
    """Represento un recurso publicado por un docente para su paralelo."""
    id_material = models.AutoField(primary_key=True, db_column='idmaterial')
    paralelo = models.ForeignKey(Paralelo, on_delete=models.CASCADE, db_column='idparalelo', related_name='materiales')
    docente = models.ForeignKey(Docente, on_delete=models.PROTECT, db_column='iddocente')
    titulo = models.CharField(max_length=200, db_column='titulo')
    descripcion = models.TextField(null=True, blank=True, db_column='descripcion')
    tipo = models.CharField(max_length=50, null=True, blank=True, db_column='tipo')
    archivo = models.FileField(upload_to='materiales/', max_length=500, null=True, blank=True, db_column='archivo')
    url = models.CharField(max_length=500, null=True, blank=True, db_column='url')
    fecha_publicacion = models.DateTimeField(default=timezone.now, db_column='fechapublicacion')

    class Meta:
        """Mapeo los materiales a la tabla física existente."""
        db_table = 'material'


class Actividad(models.Model):
    """Represento una actividad asignada a los estudiantes de un paralelo."""
    id_actividad = models.AutoField(primary_key=True, db_column='idactividad')
    paralelo = models.ForeignKey(Paralelo, on_delete=models.CASCADE, db_column='idparalelo', related_name='actividades')
    docente = models.ForeignKey(Docente, on_delete=models.PROTECT, db_column='iddocente')
    titulo = models.CharField(max_length=200, db_column='titulo')
    instrucciones = models.TextField(null=True, blank=True, db_column='instrucciones')
    tipo = models.CharField(max_length=50, null=True, blank=True, db_column='tipo')
    fecha_publicacion = models.DateTimeField(default=timezone.now, db_column='fechapublicacion')
    fecha_limite = models.DateTimeField(null=True, blank=True, db_column='fechalimite')
    puntaje_maximo = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, db_column='puntajemaximo')
    permite_entrega_tardia = models.BooleanField(default=False, db_column='permiteentregatardia')
    usa_ia = models.BooleanField(default=False, db_column='usaia')
    estado = models.CharField(max_length=30, default='ACTIVA', db_column='estado')

    class Meta:
        """Mapeo las actividades a la tabla física existente."""
        db_table = 'actividad'


class Entrega(models.Model):
    """Represento la respuesta y calificación de un estudiante."""
    id_entrega = models.AutoField(primary_key=True, db_column='identrega')
    actividad = models.ForeignKey(Actividad, on_delete=models.CASCADE, db_column='idactividad', related_name='entregas')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, db_column='idestudiante', related_name='entregas')
    contenido_texto = models.TextField(null=True, blank=True, db_column='contenidotexto')
    archivo = models.FileField(upload_to='entregas/', max_length=500, null=True, blank=True, db_column='archivo')
    fecha_entrega = models.DateTimeField(default=timezone.now, db_column='fechaentrega')
    es_tardia = models.BooleanField(default=False, db_column='estardia')
    estado = models.CharField(max_length=30, default='ENTREGADA', db_column='estado')
    calificacion = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, db_column='calificacion')
    observaciones = models.TextField(null=True, blank=True, db_column='observaciones')
    fecha_calificacion = models.DateTimeField(null=True, blank=True, db_column='fechacalificacion')
    docente_calificador = models.ForeignKey(Docente, on_delete=models.PROTECT, null=True, blank=True, db_column='iddocentecalificador', related_name='entregas_calificadas')

    class Meta:
        """Mapeo las entregas a la tabla física existente."""
        db_table = 'entrega'


class SesionClase(models.Model):
    """Represento una sesión programada de un paralelo."""
    id_sesion = models.AutoField(primary_key=True, db_column='idsesion')
    paralelo = models.ForeignKey(Paralelo, on_delete=models.CASCADE, db_column='idparalelo', related_name='sesiones')
    fecha = models.DateField(db_column='fecha')
    hora_inicio = models.TimeField(null=True, blank=True, db_column='horainicio')
    hora_fin = models.TimeField(null=True, blank=True, db_column='horafin')
    tema = models.CharField(max_length=200, null=True, blank=True, db_column='tema')
    tipo = models.CharField(max_length=50, null=True, blank=True, db_column='tipo')
    sala_livekit = models.CharField(max_length=200, null=True, blank=True, db_column='salalivekit')
    estado = models.CharField(max_length=30, default='PROGRAMADA', db_column='estado')
    inicio_real = models.DateTimeField(null=True, blank=True, db_column='inicioreal')
    fin_real = models.DateTimeField(null=True, blank=True, db_column='finreal')

    class Meta:
        """Mapeo las sesiones a la tabla física existente."""
        db_table = 'sesion_clase'


class Asistencia(models.Model):
    """Represento el estado de asistencia en una sesión de clase."""
    id_asistencia = models.AutoField(primary_key=True, db_column='idasistencia')
    sesion = models.ForeignKey(SesionClase, on_delete=models.CASCADE, db_column='idsesion', related_name='asistencias')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, db_column='idestudiante', related_name='asistencias')
    estado = models.CharField(max_length=30, db_column='estado')
    observacion = models.CharField(max_length=500, null=True, blank=True, db_column='observacion')
    registrado_por = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True, db_column='registradopor')

    class Meta:
        """Aplico la unicidad de asistencia por sesión y estudiante."""
        db_table = 'asistencia'
        constraints = [models.UniqueConstraint(fields=['sesion', 'estudiante'], name='uq_asistencia')]


class Notificacion(models.Model):
    """Represento una notificación asociada a un usuario."""
    id_notificacion = models.AutoField(primary_key=True, db_column='idnotificacion')
    usuario = models.ForeignKey('usuarios.Usuario', on_delete=models.CASCADE, db_column='idusuario', related_name='notificaciones')
    tipo = models.CharField(max_length=50, null=True, blank=True, db_column='tipo')
    mensaje = models.TextField(db_column='mensaje')
    leida = models.BooleanField(default=False, db_column='leida')
    fecha = models.DateTimeField(default=timezone.now, db_column='fecha')

    class Meta:
        """Mapeo las notificaciones a la tabla física existente."""
        db_table = 'notificacion'
