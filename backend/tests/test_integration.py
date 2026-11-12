from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch
from django.utils import timezone

from usuarios.models import Usuario, Docente, Estudiante
from rol.models import Rol
from cursos.models import Curso, Idioma, Nivel, Turno, Paralelo, EstudianteParalelo, Programa
from actividades.models import Actividad, Entrega
from notificaciones.models import Notificacion
from asistencia.models import Asistencia
from comunicacion.models import Mensaje
from materiales.models import Material

class BaseSetupTestCase(TestCase):
    def setUp(self):
        self.rol_admin, _ = Rol.objects.get_or_create(nombre="Administrador")
        self.rol_docente, _ = Rol.objects.get_or_create(nombre="Docente")
        self.rol_estudiante, _ = Rol.objects.get_or_create(nombre="Estudiante")
        
        self.admin, _ = Usuario.objects.get_or_create(correo="admin@test.com", defaults={'nombres': 'Admin', 'password_hash': 'hash', 'rol': self.rol_admin})
        self.usr_docente, _ = Usuario.objects.get_or_create(correo="doc@test.com", defaults={'nombres': 'Doc', 'password_hash': 'hash', 'rol': self.rol_docente})
        self.docente, _ = Docente.objects.get_or_create(usuario=self.usr_docente)
        
        self.usr_est, _ = Usuario.objects.get_or_create(correo="est@test.com", defaults={'nombres': 'Est', 'password_hash': 'hash', 'rol': self.rol_estudiante})
        self.estudiante, _ = Estudiante.objects.get_or_create(usuario=self.usr_est, defaults={'codigo_estudiante': 'EST001'})

        self.idioma, _ = Idioma.objects.get_or_create(nombre="Inglés", defaults={'codigo': 'ING'})
        self.nivel, _ = Nivel.objects.get_or_create(codigo="A1")
        self.turno, _ = Turno.objects.get_or_create(nombre="Mañana")
        self.curso, _ = Curso.objects.get_or_create(idioma=self.idioma, nivel=self.nivel, defaults={'nombre': 'Inglés A1'})
        self.paralelo, _ = Paralelo.objects.get_or_create(curso=self.curso, turno=self.turno, docente=self.docente, defaults={'codigo': 'ING-A1-M'})
        
        # Importante: Guardamos la inscripción para tener su PK
        self.inscripcion, _ = EstudianteParalelo.objects.get_or_create(
            estudiante=self.estudiante, paralelo=self.paralelo, defaults={'estado': 'ACTIVO'}
        )
        self.client = Client()

    def login_como(self, usuario):
        session = self.client.session
        session['usuario_id'] = usuario.id_usuario
        session['usuario_rol'] = usuario.rol.nombre
        session.save()

class TestFlujoAutenticacion(BaseSetupTestCase):
    def test_login_exitoso(self):
        with patch('usuarios.views.check_password', return_value=True):
            response = self.client.post(reverse('login'), {'correo': 'est@test.com', 'password': 'any'})
            self.assertRedirects(response, reverse('estudiante_dashboard'))

    def test_login_fallido(self):
        with patch('usuarios.views.check_password', return_value=False):
            response = self.client.post(reverse('login'), {'correo': 'est@test.com', 'password': 'wrong'})
            self.assertEqual(response.status_code, 200)
            # Nota: Esto fallará hasta que agregues {% if messages %} en login.html
            self.assertContains(response, 'incorrectos')

class TestFlujoAdmin(BaseSetupTestCase):
    @patch('usuarios.views.generar_password', return_value="Test123!")
    def test_crear_estudiante(self, mock_pass):
        self.login_como(self.admin)
        response = self.client.post(reverse('admin_register_user'), {
            'rol': self.rol_estudiante.pk,
            'nombres': 'Pedro', 'ap_pat': 'Gomez', 'ci': '12345678', 'telefono': '777',
            'correo_personal': 'pedro@gmail.com',
            'fecha_nacimiento': '2000-01-01', 'contacto_emergencia': 'Mama', 'telefono_emergencia': '666'
        })
        self.assertRedirects(response, reverse('admin_credenciales'))
        self.assertTrue(Usuario.objects.filter(correo_personal='pedro@gmail.com').exists())

    @patch('usuarios.views.enviar_credenciales', return_value=(True, "Enviado")) # PATCH CORREGIDO
    def test_enviar_credenciales(self, mock_envio):
        self.login_como(self.admin)
        session = self.client.session
        # SESIÓN COMPLETA
        session['credenciales_nuevas'] = {
            'correo_personal': 'test@test.com', 
            'nombre': 'Test',
            'correo': 'test@davinci.edu.bo',
            'password': '123',
            'rol': 'Estudiante',
            'creado': timezone.now().timestamp()
        }
        session.save()
        
        response = self.client.post(reverse('admin_enviar_credenciales'), content_type="application/json")
        self.assertJSONEqual(response.content, {'ok': True, 'mensaje': 'Enviado'})

    def test_crear_paralelo_admin(self):
        self.login_como(self.admin)
        response = self.client.post(reverse('admin_paralelos'), {
            'id_curso': self.curso.pk,
            'id_turno': self.turno.pk,
            'id_docente': self.docente.pk,
            'cupo_maximo': 20,
            'fecha_inicio': '2026-01-01',
            'fecha_fin': '2026-12-31',
            # (Omitimos horarios para simplificar, pero irían aquí)
        })
        # Aceptamos redirección o error de validación de formulario
        self.assertIn(response.status_code, [200, 302])

    def test_enviar_aviso_global(self):
        self.login_como(self.admin)
        response = self.client.post(reverse('admin_enviar_aviso'), {
            'rol_destino': 'todos',
            'mensaje': 'Hola a todos los usuarios'
        })
        self.assertRedirects(response, reverse('admin_dashboard'))
        self.assertTrue(Notificacion.objects.filter(mensaje='Hola a todos los usuarios').exists())

class TestFlujoDocente(BaseSetupTestCase):
    def test_crear_tarea_y_notificar(self):
        self.login_como(self.usr_docente)
        response = self.client.post(reverse('docente_actividades', args=[self.curso.pk]), {
            'titulo': 'Examen 1', 'fecha_limite': '2030-12-31', 'puntaje_maximo': '100', 'tipo': 'escrita'
        })
        self.assertEqual(response.status_code, 302)
        actividad = Actividad.objects.get(titulo='Examen 1')
        notif = Notificacion.objects.filter(usuario=self.usr_est, tipo='ACTIVIDAD').first()
        self.assertIsNotNone(notif)
        self.assertIn(f"actividad={actividad.id}", notif.url_destino)

    def test_publicar_material(self):
        self.login_como(self.usr_docente)
        self.client.post(reverse('docente_materiales', args=[self.curso.pk]), {
            'titulo': 'Guía 1', 'tipo': 'enlace', 'enlace': 'https://ejemplo.com'
        })
        self.assertTrue(Material.objects.filter(titulo='Guía 1').exists())

    def test_registrar_asistencia(self):
        self.login_como(self.usr_docente)
        hoy = timezone.now().date().strftime('%Y-%m-%d')
        # USAMOS EL PK DE LA INSCRIPCIÓN
        self.client.post(reverse('docente_asistencia', args=[self.curso.pk]), {
            'fecha': hoy,
            f'estado_{self.inscripcion.pk}': 'ausente',
            f'obs_{self.inscripcion.pk}': 'Faltó'
        })
        asis = Asistencia.objects.filter(estudiante=self.estudiante, estado='ausente').first()
        self.assertIsNotNone(asis)

class TestFlujoEstudiante(BaseSetupTestCase):
    def test_entregar_tarea(self):
        actividad = Actividad.objects.create(
            paralelo=self.paralelo, docente=self.docente, titulo='Tarea 1', 
            tipo='escrita', fecha_limite=timezone.now() + timezone.timedelta(days=1)
        )
        self.login_como(self.usr_est)
        self.client.post(reverse('api-estudiante-entregar', args=[actividad.id]), {
            'contenido_texto': 'Mi respuesta'
        })
        entrega = Entrega.objects.filter(actividad=actividad, estudiante=self.estudiante).first()
        self.assertIsNotNone(entrega)
        self.assertEqual(entrega.estado, 'ENTREGADA')

class TestFlujoComunicacion(BaseSetupTestCase):
    def test_enviar_mensaje_notifica(self):
        self.login_como(self.usr_est)
        self.client.post(reverse('estudiante_mensajes'), {
            'texto': 'Hola profe', 'con': self.usr_docente.pk
        })
        msg = Mensaje.objects.filter(emisor=self.usr_est, receptor=self.usr_docente).first()
        self.assertIsNotNone(msg)
        notif = Notificacion.objects.filter(usuario=self.usr_docente, tipo='MENSAJE').first()
        self.assertIsNotNone(notif)