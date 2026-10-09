from rest_framework.permissions import BasePermission

from usuarios.models import Usuario


def usuario_de_sesion(request):
    """Obtengo el usuario activo usando el identificador guardado en la sesión."""
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None
    return Usuario.objects.select_related('rol').filter(id_usuario=usuario_id, estado=True).first()


class PermisoPorRol(BasePermission):
    """Compruebo que la sesión corresponda a uno de los roles permitidos."""
    roles_permitidos = ()

    def has_permission(self, request, view):
        """Autorizo la petición si el usuario activo posee el rol requerido."""
        usuario = usuario_de_sesion(request)
        return bool(usuario and usuario.rol.nombre in self.roles_permitidos)


class PermisoAdministrador(PermisoPorRol):
    """Limito la gestión del catálogo al administrador."""
    roles_permitidos = ('Administrador',)


class PermisoDocente(PermisoPorRol):
    """Limito las consultas de grupos al docente autenticado."""
    roles_permitidos = ('Docente',)


class PermisoEstudiante(PermisoPorRol):
    """Limito las consultas de cursos al estudiante autenticado."""
    roles_permitidos = ('Estudiante',)
