from django.db import migrations


def crear_roles(apps, schema_editor):
    Rol = apps.get_model('rol', 'Rol')

    Rol.objects.get_or_create(nombre='Administrador')
    Rol.objects.get_or_create(nombre='Docente')
    Rol.objects.get_or_create(nombre='Estudiante')


def eliminar_roles(apps, schema_editor):
    Rol = apps.get_model('rol', 'Rol')

    Rol.objects.filter(
        nombre__in=['Administrador', 'Docente', 'Estudiante']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('rol', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_roles, eliminar_roles),
    ]