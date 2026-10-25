from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SesionParticipante(models.Model):
    id = models.AutoField(primary_key=True, db_column="idparticipante")
    sesion = models.ForeignKey(
        "asistencia.SesionClase", on_delete=models.CASCADE,
        db_column="idsesion", related_name="participantes",
    )
    usuario = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.CASCADE,
        db_column="idusuario", related_name="participaciones",
    )
    hora_ingreso = models.DateTimeField(blank=True, null=True, db_column="horaingreso")
    hora_salida = models.DateTimeField(blank=True, null=True, db_column="horasalida")

    class Meta:
        db_table = "sesion_participante"
        constraints = [
            models.UniqueConstraint(fields=["sesion", "usuario"], name="uq_sesion_participante"),  # ya existe en la BD
        ]

    @classmethod
    def registrar_ingreso(cls, sesion, usuario):
        """Crea la participación, o la reabre si la persona había salido (conserva el primer ingreso)."""
        participante, creado = cls.objects.get_or_create(
            sesion=sesion, usuario=usuario, defaults={"hora_ingreso": timezone.now()},
        )
        if not creado:
            participante.hora_salida = None
            participante.save(update_fields=["hora_salida"])
        return participante

    def registrar_salida(self):
        if self.hora_salida is None:
            self.hora_salida = timezone.now()
            self.save(update_fields=["hora_salida"])

    def __str__(self):
        return f"{self.sesion_id} / {self.usuario_id}"


class Aviso(models.Model):
    id = models.AutoField(primary_key=True, db_column="idaviso")
    paralelo = models.ForeignKey(
        "cursos.Paralelo", on_delete=models.CASCADE,
        db_column="idparalelo", related_name="avisos",
    )
    docente = models.ForeignKey(
        "usuarios.Docente", on_delete=models.PROTECT,
        db_column="iddocente", related_name="avisos",
    )
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    fecha_publicacion = models.DateTimeField(default=timezone.now, db_column="fechapublicacion")

    class Meta:
        db_table = "aviso"
        ordering = ["-fecha_publicacion"]  

    def clean(self):
        if self.docente_id and self.paralelo_id and self.paralelo.docente_id != self.docente_id:
            raise ValidationError("El docente no está asignado a este paralelo.")

    def publicar(self):
        self.full_clean()
        self.save()
        return self

    def __str__(self):
        return self.titulo


class Mensaje(models.Model):
    id = models.AutoField(primary_key=True, db_column="idmensaje")
    emisor = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.CASCADE,
        db_column="idemisor", related_name="mensajes_enviados",
    )
    receptor = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.CASCADE,
        db_column="idreceptor", related_name="mensajes_recibidos",
    )
    paralelo = models.ForeignKey(
        "cursos.Paralelo", on_delete=models.SET_NULL, blank=True, null=True,
        db_column="idparalelo", related_name="mensajes",
    )
    contenido = models.TextField()
    fecha_envio = models.DateTimeField(default=timezone.now, db_column="fechaenvio")
    leido = models.BooleanField(default=False)

    class Meta:
        db_table = "mensaje"
        ordering = ["fecha_envio"]

    def clean(self):
        if self.emisor_id and self.emisor_id == self.receptor_id:
            raise ValidationError("No puedes enviarte un mensaje a ti mismo.")
        if not (self.contenido or "").strip():
            raise ValidationError("El mensaje no puede estar vacío.")
        if len(self.contenido) > 1000:
            raise ValidationError("El mensaje no puede superar los 1000 caracteres.")
        if self.paralelo_id and self.emisor_id and self.receptor_id:
            from .permisos import pueden_conversar
            if not pueden_conversar(self.emisor_id, self.receptor_id, self.paralelo_id):
                raise ValidationError("No puedes enviar mensajes a este usuario en este curso.")

    def enviar(self):
        """Valida y guarda el mensaje (no leído)."""
        self.full_clean()
        self.save()
        return self

    def marcar_leido(self):
        if not self.leido:
            self.leido = True
            self.save(update_fields=["leido"])

    @classmethod
    def conversacion(cls, usuario_a, usuario_b, paralelo=None):
        qs = cls.objects.filter(
            models.Q(emisor=usuario_a, receptor=usuario_b) | models.Q(emisor=usuario_b, receptor=usuario_a)
        )
        return qs.filter(paralelo=paralelo) if paralelo else qs

    def __str__(self):
        return f"{self.emisor_id} -> {self.receptor_id}"