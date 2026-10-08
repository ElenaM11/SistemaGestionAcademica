from django.db import models


class Rol(models.Model):
    """Roles del sistema: Administrador, Docente, Estudiante"""
    nombre = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'rol'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'