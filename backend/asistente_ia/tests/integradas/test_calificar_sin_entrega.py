from django.test import TestCase, Client
from django.urls import reverse
from usuarios.models import Usuario, Estudiante, Docente, Rol
from cursos.models import Curso, Paralelo, Idioma, Nivel, Turno, EstudianteParalelo
from actividades.models import Actividad, Entrega

class CalificarSinEntregaTest(TestCase):
    def setUp(self):
        # 1. Roles
        self.rol_doc, _ = Rol.objects.get_or_create(nombre="Docente")
        self.rol_est, _ = Rol.objects.get_or_create(nombre="Estudiante")
        
        # 2. Usuarios con correos únicos
        self.user_doc, _ = Usuario.objects.get_or_create(
            id_usuario=2, 
            defaults={'nombres': "Docente", 'rol': self.rol_doc, 'correo': 'docente@test.com'}
        )
        self.docente, _ = Docente.objects.get_or_create(usuario=self.user_doc)
        
        self.user_est, _ = Usuario.objects.get_or_create(
            id_usuario=1, 
            defaults={'nombres': "Estudiante", 'rol': self.rol_est, 'correo': 'est@test.com'}
        )
        self.estudiante, _ = Estudiante.objects.get_or_create(usuario=self.user_est)
        
        # 3. Curso y Paralelo
        self.idioma = Idioma.objects.create(nombre="Inglés", codigo="EN")
        self.nivel = Nivel.objects.create(codigo="A1")
        self.turno = Turno.objects.create(nombre="Mañana")
        self.curso = Curso.objects.create(nombre="Inglés", idioma=self.idioma, nivel=self.nivel)
        self.paralelo = Paralelo.objects.create(codigo="ING-A1", curso=self.curso, turno=self.turno, docente=self.docente)
        
        EstudianteParalelo.objects.create(estudiante=self.estudiante, paralelo=self.paralelo, estado="ACTIVO")
        
        # 4. Actividad
        self.actividad = Actividad.objects.create(
            paralelo=self.paralelo, docente=self.docente, titulo="Test", 
            tipo="escrita", usa_ia=False
        )
        
        # 5. Cliente (Logueado como DOCENTE)
        self.client = Client()
        session = self.client.session
        session['usuario_id'] = self.user_doc.id_usuario
        session.save()

    def test_docente_califica_alumno_sin_entrega(self):
        # Aseguramos que no hay entrega
        self.assertFalse(Entrega.objects.filter(estudiante=self.estudiante, actividad=self.actividad).exists())
        
        url = reverse('docente_entregas', args=[self.curso.pk, self.actividad.pk])
        datos = {
            'estudiante': self.estudiante.pk,
            'nota': '0',
            'observaciones': 'No entregó la tarea.'
        }
        
        respuesta = self.client.post(url, data=datos)
        
        # Verificamos redirección
        self.assertEqual(respuesta.status_code, 302)
        
        # Verificamos que la entrega fantasma se creó
        entrega = Entrega.objects.filter(estudiante=self.estudiante, actividad=self.actividad).first()
        self.assertIsNotNone(entrega)
        self.assertEqual(entrega.calificacion, 0)
        self.assertEqual(entrega.estado, Entrega.Estado.CALIFICADA)