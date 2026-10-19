from django.db import models
from django.utils import timezone

class Notificacion(models.Model):
    class Tipo(models.TextChoices):
        MATERIAL = "MATERIAL", "Nuevo material"
        ACTIVIDAD = "ACTIVIDAD", "Nueva actividad"
        CALIFICACION = "CALIFICACION", "Calificación registrada"
        OTRO = "OTRO", "Otro"

    id = models.AutoField(primary_key=True, db_column="idnotificacion")
    usuario = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.CASCADE,
        db_column="idusuario", related_name="notificaciones",
    )
    tipo = models.CharField(max_length=50, choices=Tipo.choices, blank=True, null=True)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "notificacion"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.usuario_id}: {self.mensaje[:40]}"
