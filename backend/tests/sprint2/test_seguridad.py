"""Pruebo las restricciones de acceso a datos académicos del Sprint 2."""

from django.test import TestCase
from rest_framework.test import APIClient

from cursos.models import Curso, EstudianteParalelo, Idioma, Nivel, Paralelo, Turno
from rol.models import Rol
from usuarios.models import Docente, Estudiante, Usuario


class PruebasSeguridadSprintDos(TestCase):
    """Preparo dos estudiantes y sus cursos para verificar aislamiento de datos."""

    def setUp(self):
        """Creo usuarios de estudiante y paralelos con inscripciones independientes."""
        self.client = APIClient()
        rol_estudiante, _ = Rol.objects.get_or_create(nombre='Estudiante')
        rol_docente, _ = Rol.objects.get_or_create(nombre='Docente')
        self.usuario = self._crear_usuario('alumna.seguridad@ejemplo.test', rol_estudiante)
        otro_usuario = self._crear_usuario('otra.seguridad@ejemplo.test', rol_estudiante)
        docente_usuario = self._crear_usuario('docente.seguridad@ejemplo.test', rol_docente)
        self.estudiante = Estudiante.objects.create(usuario=self.usuario)
        otro_estudiante = Estudiante.objects.create(usuario=otro_usuario)
        docente = Docente.objects.create(usuario=docente_usuario)
        idioma = Idioma.objects.create(nombre='Inglés', codigo='EN')
        nivel = Nivel.objects.create(codigo='A1')
        curso = Curso.objects.create(idioma=idioma, nivel=nivel, nombre='Inglés A1')
        turno = Turno.objects.create(nombre='Mañana')
        propio = Paralelo.objects.create(codigo='EN-MAN-2026-A', curso=curso, turno=turno, docente=docente)
        ajeno = Paralelo.objects.create(codigo='EN-MAN-2026-B', curso=curso, turno=turno, docente=docente)
        EstudianteParalelo.objects.create(estudiante=self.estudiante, paralelo=propio)
        EstudianteParalelo.objects.create(estudiante=otro_estudiante, paralelo=ajeno)

    def _crear_usuario(self, correo, rol):
        """Creo un usuario activo asociado al rol de la prueba."""
        return Usuario.objects.create(
            nombres='Cuenta', ap_pat='Prueba', ap_mat='Da Vinci', correo=correo,
            password_hash='hash-prueba', rol=rol,
        )

    def _iniciar_sesion(self, usuario):
        """Inicio una sesión simulada con la identidad guardada por la aplicación."""
        session = self.client.session
        session['usuario_id'] = usuario.pk
        session['usuario_rol'] = usuario.rol.nombre
        session.save()

    def test_estudiante_no_puede_suplantar_id_en_consulta_de_cursos(self):
        """Ignoro un identificador ajeno enviado por query y devuelvo solo cursos propios."""
        self._iniciar_sesion(self.usuario)

        respuesta = self.client.get(
            '/api/estudiante/mis-cursos/', {'id_estudiante': Estudiante.objects.exclude(pk=self.estudiante.pk).get().pk},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.data), 1)
        self.assertEqual(respuesta.data[0]['id_paralelo'], self.estudiante.inscripciones.get().paralelo_id)
