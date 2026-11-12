from django.test import TestCase, Client
from django.urls import reverse
from usuarios.models import Usuario
from rol.models import Rol

class TestSeguridadSistema(TestCase):
    def setUp(self):
        # Usamos get_or_create para evitar el error UNIQUE
        self.rol_est, _ = Rol.objects.get_or_create(nombre="Estudiante")
        self.rol_admin, _ = Rol.objects.get_or_create(nombre="Administrador")
        
        self.estudiante, _ = Usuario.objects.get_or_create(
            correo="est@test.com", 
            defaults={'nombres': 'Est', 'password_hash': 'hash', 'rol': self.rol_est}
        )
        self.admin, _ = Usuario.objects.get_or_create(
            correo="admin@test.com", 
            defaults={'nombres': 'Admin', 'password_hash': 'hash', 'rol': self.rol_admin}
        )
        self.client = Client()

    def test_estudiante_no_puede_entrar_al_panel_admin(self):
        """Prueba de control de acceso (Un estudiante no puede ver el dashboard del admin)."""
        session = self.client.session
        session['usuario_id'] = self.estudiante.id_usuario
        session['usuario_rol'] = 'Estudiante'
        session.save()

        response = self.client.get(reverse('admin_dashboard'))
        
        # Verificamos que el sistema lo bloquea (redirección al login o error 403)
        self.assertNotEqual(response.status_code, 200)
        self.assertIn(response.status_code, [302, 403])

    def test_proteccion_csrf(self):
        """Prueba que el formulario rechaza peticiones sin token CSRF."""
        # Creamos un cliente especial que NO usa la seguridad CSRF (simula un atacante)
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(reverse('login'), {'correo': 'est@test.com', 'password': '123'})
        
        # Debe dar error 403 porque no enviamos el token
        self.assertEqual(response.status_code, 403)
    def test_estudiante_no_puede_entrar_al_chat_admin(self):
        """Un estudiante no debe poder acceder a la ruta de chat del administrador."""
        session = self.client.session
        session['usuario_id'] = self.estudiante.id_usuario
        session['usuario_rol'] = 'Estudiante'
        session.save()

        # Intenta acceder a la vista del chat del admin
        response = self.client.get(reverse('admin_mensajes'))
        
        # Verifica que lo redirige al login o le da error
        self.assertNotEqual(response.status_code, 200)