from django.db import models

from usuarios.models import Docente, Estudiante


class Idioma(models.Model):
    """Defino un idioma disponible en el catálogo académico."""
    id_idioma = models.AutoField(primary_key=True, db_column='ididioma')
    nombre = models.CharField(max_length=100, unique=True, db_column='nombre')
    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True, db_column='codigo')
    activo = models.BooleanField(default=True, db_column='activo')

    class Meta:
        """Mapeo el modelo a la tabla física de idiomas."""
        db_table = 'idioma'


class Nivel(models.Model):
    """Defino un nivel académico disponible para los cursos."""
    id_nivel = models.AutoField(primary_key=True, db_column='idnivel')
    codigo = models.CharField(max_length=20, unique=True, db_column='codigo')

    class Meta:
        """Mapeo el modelo a la tabla física de niveles."""
        db_table = 'nivel'


class Curso(models.Model):
    """Defino un curso asociado a un idioma y a un nivel."""
    id_curso = models.AutoField(primary_key=True, db_column='idcurso')
    idioma = models.ForeignKey(Idioma, on_delete=models.PROTECT, db_column='ididioma', related_name='cursos')
    nivel = models.ForeignKey(Nivel, on_delete=models.PROTECT, db_column='idnivel', related_name='cursos')
    nombre = models.CharField(max_length=150, db_column='nombre')
    descripcion = models.TextField(null=True, blank=True, db_column='descripcion')
    activo = models.BooleanField(default=True, db_column='activo')

    class Meta:
        """Mapeo el modelo a la tabla física de cursos."""
        db_table = 'curso'


class Programa(models.Model):
    """Defino un programa académico sin agregar campos ajenos al esquema."""
    id_programa = models.AutoField(primary_key=True, db_column='idprograma')
    nombre = models.CharField(max_length=150, db_column='nombre')
    duracion_meses = models.IntegerField(null=True, blank=True, db_column='duracionmeses')
    descripcion = models.TextField(null=True, blank=True, db_column='descripcion')
    activo = models.BooleanField(default=True, db_column='activo')

    class Meta:
        """Mapeo el modelo a la tabla física de programas."""
        db_table = 'programa'


class ProgramaIdioma(models.Model):
    """Relaciono un programa con un idioma y su nivel máximo."""
    id_programa_idioma = models.AutoField(primary_key=True, db_column='idprogramaidioma')
    programa = models.ForeignKey(Programa, on_delete=models.CASCADE, db_column='idprograma', related_name='idiomas')
    idioma = models.ForeignKey(Idioma, on_delete=models.PROTECT, db_column='ididioma', related_name='programas')
    nivel_maximo = models.ForeignKey(Nivel, on_delete=models.PROTECT, db_column='nivelmaximoid', related_name='programas')

    class Meta:
        """Aplico la unicidad definida para programa e idioma."""
        db_table = 'programa_idioma'
        constraints = [models.UniqueConstraint(fields=['programa', 'idioma'], name='uq_programa_idioma')]


class Turno(models.Model):
    """Defino un turno con sus horas referenciales."""
    id_turno = models.AutoField(primary_key=True, db_column='idturno')
    nombre = models.CharField(max_length=50, unique=True, db_column='nombre')
    hora_referencia_inicio = models.TimeField(null=True, blank=True, db_column='horareferenciainicio')
    hora_referencia_fin = models.TimeField(null=True, blank=True, db_column='horareferenciafin')

    class Meta:
        """Mapeo el modelo a la tabla física de turnos."""
        db_table = 'turno'


class DocenteIdioma(models.Model):
    """Registro los idiomas que cada docente está habilitado para enseñar."""
    id_docente_idioma = models.AutoField(primary_key=True, db_column='iddocenteidioma')
    docente = models.ForeignKey(Docente, on_delete=models.CASCADE, db_column='iddocente', related_name='idiomas_docente')
    idioma = models.ForeignKey(Idioma, on_delete=models.CASCADE, db_column='ididioma', related_name='docentes')

    class Meta:
        """Aplico la unicidad definida para docente e idioma."""
        db_table = 'docente_idioma'
        constraints = [models.UniqueConstraint(fields=['docente', 'idioma'], name='uq_docente_idioma')]


class Paralelo(models.Model):
    """Defino un paralelo y sus asignaciones académicas."""
    id_paralelo = models.AutoField(primary_key=True, db_column='idparalelo')
    codigo = models.CharField(max_length=50, unique=True, db_column='codigo')
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, db_column='idcurso', related_name='paralelos')
    programa = models.ForeignKey(Programa, on_delete=models.PROTECT, null=True, blank=True, db_column='idprograma', related_name='paralelos')
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, db_column='idturno', related_name='paralelos')
    docente = models.ForeignKey(Docente, on_delete=models.PROTECT, db_column='iddocente', related_name='paralelos')
    modalidad = models.CharField(max_length=50, null=True, blank=True, db_column='modalidad')
    aula = models.CharField(max_length=100, null=True, blank=True, db_column='aula')
    cupo_minimo_apertura = models.IntegerField(null=True, blank=True, db_column='cupominimoapertura')
    cupo_maximo = models.IntegerField(null=True, blank=True, db_column='cupomaximo')
    fecha_inicio = models.DateField(null=True, blank=True, db_column='fechainicio')
    fecha_fin = models.DateField(null=True, blank=True, db_column='fechafin')
    estado = models.CharField(max_length=30, default='ACTIVO', db_column='estado')

    class Meta:
        """Mapeo el modelo al paralelo y su clave física."""
        db_table = 'paralelo'


class HorarioParalelo(models.Model):
    """Defino el día y el intervalo horario de un paralelo."""
    id_horario = models.AutoField(primary_key=True, db_column='idhorario')
    paralelo = models.ForeignKey(Paralelo, on_delete=models.CASCADE, db_column='idparalelo', related_name='horarios')
    dia_semana = models.CharField(max_length=20, db_column='diasemana')
    hora_inicio = models.TimeField(db_column='horainicio')
    hora_fin = models.TimeField(db_column='horafin')

    class Meta:
        """Mapeo el modelo a los horarios físicos de paralelos."""
        db_table = 'horario_paralelo'


class EstudianteParalelo(models.Model):
    """Registro la inscripción y el estado académico del estudiante."""
    id_estudiante_paralelo = models.AutoField(primary_key=True, db_column='idestudianteparalelo')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, db_column='idestudiante', related_name='inscripciones')
    paralelo = models.ForeignKey(Paralelo, on_delete=models.CASCADE, db_column='idparalelo', related_name='inscripciones')
    fecha_ingreso = models.DateField(auto_now_add=True, db_column='fechaingreso')
    estado = models.CharField(max_length=30, default='ACTIVO', db_column='estado')

    class Meta:
        """Aplico la unicidad definida para estudiante y paralelo."""
        db_table = 'estudiante_paralelo'
        constraints = [models.UniqueConstraint(fields=['estudiante', 'paralelo'], name='uq_estudiante_paralelo')]
