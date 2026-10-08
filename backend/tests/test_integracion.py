import pytest
from django.test import Client
from django.contrib.auth.hashers import make_password, check_password
from usuarios.models import Usuario, Estudiante, Docente
from rol.models import Rol


# FIXTURES (datos de prueba reutilizables)


@pytest.fixture
def roles(db):
    """Crea los 3 roles básicos (o los obtiene si ya existen)."""
    admin, _ = Rol.objects.get_or_create(nombre='Administrador')
    docente, _ = Rol.objects.get_or_create(nombre='Docente')
    estudiante, _ = Rol.objects.get_or_create(nombre='Estudiante')
    return {'admin': admin, 'docente': docente, 'estudiante': estudiante}


@pytest.fixture
def usuario_admin(db, roles):
    """Crea (o reutiliza) un usuario admin para las pruebas."""
    admin, _ = Usuario.objects.get_or_create(
        correo='admin@davinci.edu.bo',
        defaults={
            'nombres': 'Admin',
            'ap_pat': 'Sistema',
            'ap_mat': 'Principal',
            'ci': '1111111',
            'telefono': '70000001',
            'rol': roles['admin'],
            'password_hash': make_password('Admin2026!'),
            'debe_cambiar_password': False,
        }
    )
    return admin


@pytest.fixture
def usuario_estudiante(db, roles):
    """Crea (o reutiliza) un usuario estudiante para las pruebas."""
    u, _ = Usuario.objects.get_or_create(
        correo='cmamani@davinci.edu.bo',
        defaults={
            'nombres': 'Carlos',
            'ap_pat': 'Mamani',
            'ap_mat': 'Flores',
            'ci': '3333333',
            'telefono': '70000003',
            'rol': roles['estudiante'],
            'password_hash': make_password('Estudiante2026!'),
            'debe_cambiar_password': False,
        }
    )
    Estudiante.objects.get_or_create(
        usuario=u,
        defaults={
            'codigo_estudiante': 'CMF001',
            'fecha_nacimiento': '2005-05-15',
            'contacto_emergencia': 'Ana Flores',
            'telefono_emergencia': '70000004',
        }
    )
    return u


# PRUEBAS DE INTEGRACIÓN: login_view

class TestLoginView:

    def test_login_correcto(self, db, usuario_admin):
        """Login con credenciales válidas redirige al dashboard."""
        client = Client()
        response = client.post('/', {
            'correo': 'admin@davinci.edu.bo',
            'password': 'Admin2026!',
        })
        assert response.status_code == 302
        assert response.url == '/panel/dashboard/'

    def test_login_password_incorrecta(self, db, usuario_admin):
        """Login con contraseña incorrecta no redirige."""
        client = Client()
        response = client.post('/', {
            'correo': 'admin@davinci.edu.bo',
            'password': 'WrongPassword',
        })
        assert response.status_code == 200

    def test_login_usuario_inexistente(self, db):
        """Login con correo no registrado no redirige."""
        client = Client()
        response = client.post('/', {
            'correo': 'noexiste@davinci.edu.bo',
            'password': 'Cualquiera123!',
        })
        assert response.status_code == 200

    def test_login_usuario_inactivo(self, db, usuario_admin):
        """Login con usuario inactivo es rechazado."""
        usuario_admin.estado = False
        usuario_admin.save()
        client = Client()
        response = client.post('/', {
            'correo': 'admin@davinci.edu.bo',
            'password': 'Admin2026!',
        })
        assert response.status_code == 200


# PRUEBAS DE INTEGRACIÓN: admin_register_user

class TestAdminRegisterUser:

    def _login_admin(self, client, usuario_admin):
        """Helper: inicia sesión como admin."""
        client.post('/', {
            'correo': 'admin@davinci.edu.bo',
            'password': 'Admin2026!',
        })

    def test_registrar_estudiante(self, db, usuario_admin, roles):
        """Registrar estudiante crea Usuario + Estudiante."""
        # Limpiamos por si quedó de otro test
        Usuario.objects.filter(ci='9999999').delete()

        client = Client()
        self._login_admin(client, usuario_admin)

        response = client.post('/panel/registro/', {
            'nombres': 'Mariela',
            'ap_pat': 'Quispe',
            'ap_mat': 'Mamani',
            'ci': '9999999',
            'telefono': '70099999',
            'rol': roles['estudiante'].id,
            'fecha_nacimiento': '2005-01-01',
            'contacto_emergencia': 'Juan Quispe',
            'telefono_emergencia': '70088888',
        })

        assert response.status_code == 302
        assert Usuario.objects.filter(ci='9999999').exists()

        u = Usuario.objects.get(ci='9999999')
        assert u.rol.nombre == 'Estudiante'
        assert Estudiante.objects.filter(usuario=u).exists()
        assert u.debe_cambiar_password is True

    def test_registrar_con_ci_duplicado(self, db, usuario_admin, roles):
        """CI duplicado devuelve error."""
        client = Client()
        self._login_admin(client, usuario_admin)

        response = client.post('/panel/registro/', {
            'nombres': 'Otro',
            'ap_pat': 'Usuario',
            'ap_mat': 'Test',
            'ci': '1111111',  # ya existe
            'telefono': '70077777',
            'rol': roles['estudiante'].id,
            'fecha_nacimiento': '2005-01-01',
            'contacto_emergencia': 'X',
            'telefono_emergencia': '70066666',
        })

        assert response.status_code == 200
        assert not Usuario.objects.filter(ci='9999999').exists()

# PRUEBAS DE INTEGRACIÓN: cambiar_password

class TestCambiarPassword:

    def test_password_actual_incorrecta(self, db, usuario_admin):
        """Contraseña actual incorrecta devuelve error."""
        client = Client()
        client.post('/', {
            'correo': 'admin@davinci.edu.bo',
            'password': 'Admin2026!',
        })
        response = client.post('/cambiar-password/', {
            'actual': 'WrongPassword',
            'nueva': 'NuevaClave2026!',
            'confirmar': 'NuevaClave2026!',
        })
        assert response.status_code == 200
        usuario_admin.refresh_from_db()
        assert check_password('Admin2026!', usuario_admin.password_hash)

    def test_cambio_exitoso(self, db, usuario_admin):
        """Cambio exitoso actualiza el hash."""
        client = Client()
        client.post('/', {
            'correo': 'admin@davinci.edu.bo',
            'password': 'Admin2026!',
        })
        response = client.post('/cambiar-password/', {
            'actual': 'Admin2026!',
            'nueva': 'NuevaClave2026!',
            'confirmar': 'NuevaClave2026!',
        })
        assert response.status_code == 302

        usuario_admin.refresh_from_db()
        assert check_password('NuevaClave2026!', usuario_admin.password_hash)
        assert usuario_admin.debe_cambiar_password is False

# PRUEBAS DE INTEGRACIÓN: control de acceso

class TestControlAcceso:

    def test_estudiante_no_puede_registrar(self, db, usuario_estudiante):
        """Estudiante no puede acceder a /panel/registro/."""
        client = Client()
        client.post('/', {
            'correo': 'cmamani@davinci.edu.bo',
            'password': 'Estudiante2026!',
        })
        response = client.get('/panel/registro/')
        assert response.status_code == 302
        assert response.url == '/'

    def test_sin_sesion_redirige_al_login(self, db):
        """Sin sesión, cualquier vista protegida redirige al login."""
        client = Client()
        response = client.get('/panel/registro/')
        assert response.status_code == 302
        assert response.url == '/'