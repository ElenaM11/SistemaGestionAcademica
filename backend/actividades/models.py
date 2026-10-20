from datetime import timezone as dt_timezone
from django.conf import settings
from django.db import models
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

def _aware(dt):
    """Las columnas son `timestamp` (sin zona): al leerlas pueden venir naive.
    Se asumen UTC, que es como las guarda Django cuando USE_TZ=True."""
    if dt is not None and timezone.is_naive(dt) and settings.USE_TZ:
        return timezone.make_aware(dt, dt_timezone.utc)
    return dt

class Actividad(models.Model):
    class Tipo(models.TextChoices):  # valores que envía el desplegable de la plantilla
        ESCRITA = "escrita", "Escrita"
        ORAL = "oral", "Oral"
        CUESTIONARIO = "cuestionario", "Cuestionario"

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
    usa_ia = models.BooleanField(default=False, db_column="usaia")
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.ACTIVA)

    class Meta:
        db_table = "actividad"
        ordering = ["-fecha_publicacion"]

    def clean(self):
        if self.puntaje_maximo is not None and self.puntaje_maximo <= 0:
            raise ValidationError("El puntaje máximo debe ser mayor a 0.")
        if self.docente_id and self.paralelo_id and self.paralelo.docente_id != self.docente_id:
            raise ValidationError("El docente no está asignado a este paralelo.")

    def esta_vencida(self, ahora=None):
        limite = _aware(self.fecha_limite)
        return limite is not None and (ahora or timezone.now()) > limite
    def acepta_entregas(self, ahora=None):
        if self.estado != self.Estado.ACTIVA:
            return False
        return (not self.esta_vencida(ahora)) or self.permite_entrega_tardia

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
    calificacion = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    fecha_calificacion = models.DateTimeField(blank=True, null=True, db_column="fechacalificacion")
    docente_calificador = models.ForeignKey(
        "usuarios.Docente", on_delete=models.PROTECT, blank=True, null=True,
        db_column="iddocentecalificador", related_name="entregas_calificadas",
    )

    class Meta:
        db_table = "entrega"

    def calificar(self, docente, nota, observaciones=""):
        """HU-15: registra o MODIFICA la calificación y las observaciones."""
        if self.actividad.paralelo.docente_id != docente.pk:
            raise PermissionDenied("Solo el docente del paralelo puede calificar.")
        maximo = self.actividad.puntaje_maximo
        if nota < 0 or (maximo is not None and nota > maximo):
            rango = f"entre 0 y {maximo}" if maximo is not None else "mayor o igual a 0"
            raise ValidationError(f"La calificación debe estar {rango}.")
        self.calificacion = nota
        self.observaciones = observaciones or None
        self.estado = self.Estado.CALIFICADA
        self.fecha_calificacion = timezone.now()
        self.docente_calificador = docente
        self.save(update_fields=[
            "calificacion", "observaciones", "estado",
            "fecha_calificacion", "docente_calificador",
        ])

    def __str__(self):
        return f"{self.actividad_id} / {self.estudiante_id}"