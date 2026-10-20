from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

class Material(models.Model):
    class Tipo(models.TextChoices):  # valores que envía el desplegable de la plantilla
        PDF = "pdf", "Documento PDF"
        AUDIO = "audio", "Audio MP3"
        VIDEO = "video", "Video"
        ENLACE = "enlace", "Enlace externo"

    id = models.AutoField(primary_key=True, db_column="idmaterial")
    paralelo = models.ForeignKey(
        "cursos.Paralelo", on_delete=models.CASCADE,
        db_column="idparalelo", related_name="materiales",
    )
    docente = models.ForeignKey(
        "usuarios.Docente", on_delete=models.PROTECT,
        db_column="iddocente", related_name="materiales",
    )
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    tipo = models.CharField(max_length=50, choices=Tipo.choices, blank=True, null=True)
    archivo = models.FileField(upload_to="materiales/", max_length=500, blank=True, null=True)
    url = models.URLField(max_length=500, blank=True, null=True)
    fecha_publicacion = models.DateTimeField(default=timezone.now, db_column="fechapublicacion")

    class Meta:
        db_table = "material"
        ordering = ["-fecha_publicacion"]

    def clean(self):
        if not self.archivo and not self.url:
            raise ValidationError("Debes adjuntar un archivo o indicar un enlace.")
        if self.docente_id and self.paralelo_id and self.paralelo.docente_id != self.docente_id:
            raise ValidationError("El docente no está asignado a este paralelo.")

    def __str__(self):
        return self.titulo