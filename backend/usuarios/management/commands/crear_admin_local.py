"""Creo un administrador interactivo únicamente en la base SQLite local."""

from getpass import getpass

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from rol.models import Rol
from usuarios.models import Usuario


class Command(BaseCommand):
    """Pido los datos del administrador y los guardo en la base local."""

    help = 'Crea una cuenta Administrador únicamente en backend/local.sqlite3.'

    def handle(self, *args, **options):
        """Valido que use SQLite y creo el administrador con contraseña cifrada."""
        if connections['default'].vendor != 'sqlite':
            raise CommandError('Este comando solo funciona con la configuración local SQLite.')

        nombres = input('Nombres: ').strip()
        ap_pat = input('Apellido paterno: ').strip()
        ap_mat = input('Apellido materno (opcional): ').strip()
        correo = input('Correo: ').strip().lower()
        password = getpass('Contraseña: ')
        confirmacion = getpass('Confirma la contraseña: ')

        if not all((nombres, ap_pat, correo, password)):
            raise CommandError('Nombres, apellido, correo y contraseña son obligatorios.')
        if password != confirmacion:
            raise CommandError('Las contraseñas no coinciden.')
        if Usuario.objects.filter(correo=correo).exists():
            raise CommandError('Ya existe una cuenta con ese correo en la base local.')

        rol, _ = Rol.objects.get_or_create(nombre='Administrador')
        Usuario.objects.create(
            nombres=nombres,
            ap_pat=ap_pat,
            ap_mat=ap_mat,
            correo=correo,
            password_hash=make_password(password),
            rol=rol,
            debe_cambiar_password=False,
        )
        self.stdout.write(self.style.SUCCESS('Administrador local creado correctamente.'))
