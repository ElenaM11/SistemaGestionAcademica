from django.core.exceptions import ValidationError
from django.db import models

class SesionClase(models.Model):
    class Estado(models.TextChoices):
        PROGRAMADA = "PROGRAMADA", "Programada"
        EN_CURSO = "EN_CURSO", "En curso"      # lo usa el Sprint 4 (clase en vivo)
        FINALIZADA = "FINALIZADA", "Finalizada"

    id = models.AutoField(primary_key=True, db_column="idsesion")
    paralelo = models.ForeignKey(
        "cursos.Paralelo", on_delete=models.CASCADE,
        db_column="idparalelo", related_name="sesiones",
    )
    fecha = models.DateField()
    hora_inicio = models.TimeField(blank=True, null=True, db_column="horainicio")
    hora_fin = models.TimeField(blank=True, null=True, db_column="horafin")
    tema = models.CharField(max_length=200, blank=True, null=True)
    tipo = models.CharField(max_length=50, blank=True, null=True)
    sala_livekit = models.CharField(max_length=200, blank=True, null=True, db_column="salalivekit")  
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.PROGRAMADA)
    inicio_real = models.DateTimeField(blank=True, null=True, db_column="inicioreal")                
    fin_real = models.DateTimeField(blank=True, null=True, db_column="finreal")                     

    class Meta:
        db_table = "sesion_clase"
        ordering = ["-fecha", "-hora_inicio"]

    def clean(self):
        # La BD no impide duplicar la misma sesión: se valida aquí
        if self.paralelo_id and self.fecha:
            ya = SesionClase.objects.filter(
                paralelo_id=self.paralelo_id, fecha=self.fecha, hora_inicio=self.hora_inicio
            ).exclude(pk=self.pk)
            if ya.exists():
                raise ValidationError("Ya existe una sesión de este paralelo en esa fecha y hora.")

    def __str__(self):
        return f"{self.paralelo_id} · {self.fecha}"


class Asistencia(models.Model):
    class Estado(models.TextChoices):  # solo valida en Django, la BD acepta texto libre
        PRESENTE = "presente", "Presente"
        AUSENTE = "ausente", "Ausente"
        TARDANZA = "tardanza", "Tardanza"

    id = models.AutoField(primary_key=True, db_column="idasistencia")
    sesion = models.ForeignKey(
        SesionClase, on_delete=models.CASCADE,
        db_column="idsesion", related_name="asistencias",
    )
    estudiante = models.ForeignKey(
        "usuarios.Estudiante", on_delete=models.CASCADE,
        db_column="idestudiante", related_name="asistencias",
    )
    estado = models.CharField(max_length=30, choices=Estado.choices)
    observacion = models.CharField(max_length=500, blank=True, null=True)
    registrado_por = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.PROTECT, blank=True, null=True,
        db_column="registradopor", related_name="asistencias_registradas",
    )

    class Meta:
        db_table = "asistencia"
        constraints = [
            models.UniqueConstraint(fields=["sesion", "estudiante"], name="uq_asistencia"),  # ya existe en la BD
        ]

    def __str__(self):
        return f"{self.sesion_id} / {self.estudiante_id}: {self.estado}"