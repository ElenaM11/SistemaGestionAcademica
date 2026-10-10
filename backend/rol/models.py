from django.db import models


class Rol(models.Model):
    """Defino los roles Administrador, Docente y Estudiante."""
    nombre = models.CharField(max_length=50, unique=True, db_column='nombre')

    def __str__(self):
        return self.nombre

    class Meta:
        """Asocio los roles a la tabla física definida en el esquema."""
        db_table = 'rol'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'
