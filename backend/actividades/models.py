from datetime import timezone as dt_timezone
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.utils import timezone


def _aware(dt):
    if dt is not None and timezone.is_naive(dt):
        return timezone.make_aware(dt, dt_timezone.utc)
    return dt

class Actividad(models.Model):
    class Tipo(models.TextChoices):
        ESCRITA = "ESCRITA", "Escrita"
        ORAL = "ORAL", "Oral"

    class Estado(models.TextChoices):
        ACTIVA = "ACTIVA", "Activa"
        CERRADA = "CERRADA", "Cerrada"

    id = models.AutoField(primary_key=True, db_column="idactividad")
    paralelo = models.ForeignKey(
        "cursos.Paralelo", on_delete=models.CASCADE,
        db_column="idparalelo", related_name="actividades",
    )
    docente = models.ForeignKey(
        "usuarios.Docente", on_delete=models.PROTECT,
        db_column="iddocente", related_name="actividades",
    )
    titulo = models.CharField(max_length=200)
    instrucciones = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=50, choices=Tipo.choices, blank=True, null=True)
    fecha_publicacion = models.DateTimeField(default=timezone.now, db_column="fechapublicacion")
    fecha_limite = models.DateTimeField(blank=True, null=True, db_column="fechalimite")
    puntaje_maximo = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True, db_column="puntajemaximo"
    )
    permite_entrega_tardia = models.BooleanField(default=False, db_column="permiteentregatardia")
    usa_ia = models.BooleanField(default=False, db_column="usaia")  # lo habilita el admin en el Sprint 4
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.ACTIVA)

    class Meta:
        db_table = "actividad"
        ordering = ["-fecha_publicacion"]

    def clean(self):
        if self.puntaje_maximo is not None and self.puntaje_maximo <= 0:
            raise ValidationError("El puntaje máximo debe ser mayor a 0.")
        if self.docente_id and self.paralelo_id and self.paralelo.docente_id != self.docente_id:
            raise ValidationError("El docente no está asignado a este paralelo.")

    def acepta_entregas(self, ahora=None):
        """True si todavía se puede entregar (plazo y entrega tardía). Lo usa B en HU-13."""
        ahora = ahora or timezone.now()
        limite = _aware(self.fecha_limite)
        if self.estado != self.Estado.ACTIVA:
            return False
        if limite is None or ahora <= limite:
            return True
        return self.permite_entrega_tardia

    def __str__(self):
        return self.titulo


class Entrega(models.Model):
    class Estado(models.TextChoices):
        ENTREGADA = "ENTREGADA", "Entregada"
        CALIFICADA = "CALIFICADA", "Calificada"

    id = models.AutoField(primary_key=True, db_column="identrega")
    actividad = models.ForeignKey(
        Actividad, on_delete=models.CASCADE,
        db_column="idactividad", related_name="entregas",
    )
    estudiante = models.ForeignKey(
        "usuarios.Estudiante", on_delete=models.CASCADE,
        db_column="idestudiante", related_name="entregas",
    )
    contenido_texto = models.TextField(blank=True, null=True, db_column="contenidotexto")
    archivo = models.FileField(upload_to="entregas/", max_length=500, blank=True, null=True)
    fecha_entrega = models.DateTimeField(default=timezone.now, db_column="fechaentrega")
    es_tardia = models.BooleanField(default=False, db_column="estardia")
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.ENTREGADA)
    # --- calificación (HU-15, la usa A) ---
    calificacion = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    fecha_calificacion = models.DateTimeField(blank=True, null=True, db_column="fechacalificacion")
    docente_calificador = models.ForeignKey(
        "usuarios.Docente", on_delete=models.PROTECT, blank=True, null=True,
        db_column="iddocentecalificador", related_name="entregas_calificadas",
    )

    class Meta:
        db_table = "entrega"

    def clean(self):
        # La BD no tiene UNIQUE (actividad, estudiante): se valida aquí
        if self.actividad_id and self.estudiante_id:
            ya = Entrega.objects.filter(
                actividad_id=self.actividad_id, estudiante_id=self.estudiante_id
            ).exclude(pk=self.pk)
            if ya.exists():
                raise ValidationError("El estudiante ya entregó esta actividad.")

    def calificar(self, docente, nota, observaciones=""):
        """HU-15: registra o modifica la calificación y las observaciones."""
        if self.actividad.paralelo.docente_id != docente.pk:
            raise PermissionDenied("Solo el docente del paralelo puede calificar.")
        maximo = self.actividad.puntaje_maximo
        if nota < 0 or (maximo is not None and nota > maximo):
            raise ValidationError(f"La nota debe estar entre 0 y {maximo}.")
        self.calificacion = nota
        self.observaciones = observaciones
        self.estado = self.Estado.CALIFICADA
        self.fecha_calificacion = timezone.now()
        self.docente_calificador = docente
        self.save(update_fields=[
            "calificacion", "observaciones", "estado",
            "fecha_calificacion", "docente_calificador",
        ])

    def __str__(self):
        return f"{self.actividad_id} / {self.estudiante_id}"
