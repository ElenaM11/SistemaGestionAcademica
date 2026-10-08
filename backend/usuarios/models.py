from django.db import models
from rol.models import Rol


class Usuario(models.Model):
    id_usuario = models.AutoField(
        primary_key=True,
        db_column='IdUsuario'
    )

    nombres = models.CharField(
        max_length=100,
        db_column='Nombres'
    )

    ap_pat = models.CharField(
        max_length=100,
        db_column='ApPat'
    )

    ap_mat = models.CharField(
        max_length=100,
        db_column='ApMat'
    )

    ci = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        db_column='Ci'
    )

    correo = models.EmailField(
        max_length=150,
        unique=True,
        db_column='Correo'
    )

    password_hash = models.CharField(
        max_length=255,
        db_column='PasswordHash'
    )

    telefono = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        db_column='Telefono'
    )

    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        db_column='IdRol',
        related_name='usuarios'
    )

    estado = models.BooleanField(
        default=True,
        db_column='Estado'
    )

    fecha_registro = models.DateTimeField(
        auto_now_add=True,
        db_column='FechaRegistro'
    )

    def __str__(self):
        return f"{self.nombres} {self.ap_pat} {self.ap_mat}"

    class Meta:
        db_table = 'usuario'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'


class Estudiante(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='IdUsuario',
        related_name='estudiante'
    )

    codigo_estudiante = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        db_column='CodigoEstudiante'
    )

    fecha_nacimiento = models.DateField(
        null=True,
        blank=True,
        db_column='FechaNacimiento'
    )

    contacto_emergencia = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        db_column='ContactoEmergencia'
    )

    telefono_emergencia = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        db_column='TelefonoEmergencia'
    )

    def __str__(self):
        return f"{self.usuario} - {self.codigo_estudiante}"

    class Meta:
        db_table = 'estudiante'
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'


class Docente(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='IdUsuario',
        related_name='docente'
    )

    especialidad = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        db_column='Especialidad'
    )

    def __str__(self):
        return str(self.usuario)

    class Meta:
        db_table = 'docente'
        verbose_name = 'Docente'
        verbose_name_plural = 'Docentes'