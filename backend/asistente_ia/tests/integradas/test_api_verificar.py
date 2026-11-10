from django.test import TestCase, Client
from django.urls import reverse
from usuarios.models import Usuario, Estudiante, Docente, Rol
from cursos.models import Curso, Paralelo, Idioma, Nivel, Turno, EstudianteParalelo
from actividades.models import Actividad

class VerificarRespuestaAPITest(TestCase):
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
            tipo="cuestionario", usa_ia=True, 
            cuestionario='[{"tipo": "escribir", "enunciado": "Di hola", "validas": ["hello"]}]'
        )
        
        # 5. Cliente (Logueado como ESTUDIANTE)
        self.client = Client()
        session = self.client.session
        session['usuario_id'] = self.user_est.id_usuario
        session.save()

    def test_verificar_respuesta_local(self):
        url = reverse('estudiante_cuestionario_verificar', args=[self.actividad.pk])
        respuesta = self.client.post(
            url, 
            data='{"pregunta": 1, "respuesta": "hello"}', 
            content_type='application/json'
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['veredicto'], 'correcto')
        self.assertEqual(respuesta.json()['origen'], 'local')