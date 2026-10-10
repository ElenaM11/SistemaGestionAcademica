from getpass import getpass

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from rol.models import Rol
from usuarios.models import Usuario

# para ejecutar -> python manage.py crear_admin_azure
class Command(BaseCommand):
    """Creo interactivamente un administrador en la base PostgreSQL configurada."""

    help = 'Crea una cuenta Administrador en la base PostgreSQL configurada.'

    def handle(self, *args, **options):
        """Valido la conexión y guardo un administrador con la contraseña cifrada."""
        if connection.vendor != 'postgresql':
            raise CommandError('Este comando requiere la conexión PostgreSQL configurada para Azure.')

        try:
            rol = Rol.objects.get(nombre='Administrador')
        except Rol.DoesNotExist as error:
            raise CommandError('No existe el rol Administrador. Revisa las migraciones de roles.') from error

        nombres = input('Nombres: ').strip()
        ap_pat = input('Apellido paterno: ').strip()
        ap_mat = input('Apellido materno (opcional): ').strip()
        correo = input('Correo: ').strip().lower()
        password = getpass('Contraseña para el administrador: ')
        confirmacion = getpass('Confirma la contraseña: ')

        if not all((nombres, ap_pat, correo, password)):
            raise CommandError('Nombres, apellido paterno, correo y contraseña son obligatorios.')
        if password != confirmacion:
            raise CommandError('Las contraseñas no coinciden.')
        with transaction.atomic():
            if Usuario.objects.filter(correo__iexact=correo).exists():
                raise CommandError('Ya existe un usuario con ese correo.')

            Usuario.objects.create(
                nombres=nombres,
                ap_pat=ap_pat,
                ap_mat=ap_mat,
                correo=correo,
                password_hash=make_password(password),
                rol=rol,
                estado=True,
                debe_cambiar_password=False,
            )
        self.stdout.write(self.style.SUCCESS(f'Administrador {correo} creado correctamente.'))
