from rest_framework import serializers

from .models import Curso, DocenteIdioma, EstudianteParalelo, Idioma, Nivel, Programa, Turno


class IdiomaSerializer(serializers.ModelSerializer):
    """Convierto los datos del catálogo de idiomas a JSON."""
    class Meta:
        """Defino los campos que expongo para los idiomas."""
        model = Idioma
        fields = ('id_idioma', 'nombre', 'codigo', 'activo')


class NivelSerializer(serializers.ModelSerializer):
    """Convierto los niveles académicos a JSON."""
    class Meta:
        """Defino los campos que expongo para los niveles."""
        model = Nivel
        fields = ('id_nivel', 'codigo')


class CursoSerializer(serializers.ModelSerializer):
    """Valido y represento un curso de idioma."""
    idioma_nombre = serializers.CharField(source='idioma.nombre', read_only=True)
    nivel_codigo = serializers.CharField(source='nivel.codigo', read_only=True)

    class Meta:
        """Defino los campos de lectura y escritura para cursos."""
        model = Curso
        fields = ('id_curso', 'idioma', 'idioma_nombre', 'nivel', 'nivel_codigo', 'nombre', 'descripcion', 'activo')


class ProgramaSerializer(serializers.ModelSerializer):
    """Convierto los programas académicos a JSON."""
    class Meta:
        """Defino los campos que expongo para los programas."""
        model = Programa
        fields = ('id_programa', 'nombre', 'duracion_meses', 'descripcion', 'activo')


class TurnoSerializer(serializers.ModelSerializer):
    """Convierto los turnos académicos a JSON."""
    class Meta:
        """Defino los campos que expongo para los turnos."""
        model = Turno
        fields = ('id_turno', 'nombre', 'hora_referencia_inicio', 'hora_referencia_fin')


class HorarioEntradaSerializer(serializers.Serializer):
    """Valido un día y rango horario recibido para un paralelo."""
    dia_semana = serializers.CharField(max_length=20)
    hora_inicio = serializers.TimeField()
    hora_fin = serializers.TimeField()

    def validate(self, datos):
        """Rechazo rangos horarios vacíos o invertidos."""
        if datos['hora_inicio'] >= datos['hora_fin']:
            raise serializers.ValidationError('La hora de inicio debe ser anterior a la hora de fin.')
        return datos


class ParaleloEntradaSerializer(serializers.Serializer):
    """Valido los datos recibidos para crear o actualizar un paralelo."""
    codigo = serializers.CharField(max_length=50, required=False, allow_blank=True)
    id_curso = serializers.IntegerField()
    id_programa = serializers.IntegerField(required=False, allow_null=True)
    id_turno = serializers.IntegerField()
    id_docente = serializers.IntegerField()
    modalidad = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    aula = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    cupo_minimo_apertura = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    cupo_maximo = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    fecha_inicio = serializers.DateField(required=False, allow_null=True)
    fecha_fin = serializers.DateField(required=False, allow_null=True)
    horarios = HorarioEntradaSerializer(many=True, allow_empty=False)

    def validate(self, datos):
        """Verifico que los límites y las fechas del paralelo sean coherentes."""
        minimo, maximo = datos.get('cupo_minimo_apertura'), datos.get('cupo_maximo')
        if minimo is not None and maximo is not None and minimo > maximo:
            raise serializers.ValidationError('El cupo mínimo no puede superar el cupo máximo.')
        inicio, fin = datos.get('fecha_inicio'), datos.get('fecha_fin')
        if inicio and fin and inicio > fin:
            raise serializers.ValidationError('La fecha de inicio debe ser anterior a la fecha de fin.')
        return datos


class ParaleloActualizarSerializer(serializers.Serializer):
    """Valido los campos editables de un paralelo existente."""
    id_curso = serializers.IntegerField(required=False)
    id_programa = serializers.IntegerField(required=False, allow_null=True)
    id_turno = serializers.IntegerField(required=False)
    id_docente = serializers.IntegerField(required=False)
    modalidad = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    aula = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    cupo_minimo_apertura = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    cupo_maximo = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    fecha_inicio = serializers.DateField(required=False, allow_null=True)
    fecha_fin = serializers.DateField(required=False, allow_null=True)
    estado = serializers.ChoiceField(required=False, choices=('ACTIVO', 'INACTIVO'))

    def validate(self, datos):
        """Compruebo que cupos y fechas modificados sean coherentes."""
        minimo, maximo = datos.get('cupo_minimo_apertura'), datos.get('cupo_maximo')
        if minimo is not None and maximo is not None and minimo > maximo:
            raise serializers.ValidationError('El cupo mínimo no puede superar el cupo máximo.')
        inicio, fin = datos.get('fecha_inicio'), datos.get('fecha_fin')
        if inicio and fin and inicio > fin:
            raise serializers.ValidationError('La fecha de inicio debe ser anterior a la fecha de fin.')
        return datos


class InscripcionEntradaSerializer(serializers.Serializer):
    """Valido una inscripción sin aceptar identificadores del estudiante."""
    id_estudiante = serializers.IntegerField()
    id_paralelo = serializers.IntegerField()


class EstudianteParaleloSerializer(serializers.ModelSerializer):
    """Represento una inscripción para las respuestas administrativas."""
    class Meta:
        """Defino los campos que expongo para una inscripción."""
        model = EstudianteParalelo
        fields = ('id_estudiante_paralelo', 'estudiante', 'paralelo', 'fecha_ingreso', 'estado')


class DocenteIdiomaSerializer(serializers.ModelSerializer):
    """Represento la relación entre un docente y un idioma."""
    class Meta:
        """Defino los campos que expongo para los idiomas docentes."""
        model = DocenteIdioma
        fields = ('id_docente_idioma', 'docente', 'idioma')


class DocenteIdiomaEntradaSerializer(serializers.Serializer):
    """Valido el idioma que el administrador habilita para un docente."""
    id_idioma = serializers.IntegerField()
