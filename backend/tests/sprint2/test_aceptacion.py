"""Pruebo flujos completos de inscripción del Sprint 2 desde cada rol."""

from rest_framework.test import APIClient
from django.test import TestCase

from cursos.models import Curso, DocenteIdioma, EstudianteParalelo, Idioma, Nivel, Paralelo, Turno
from rol.models import Rol
from usuarios.models import Docente, Estudiante, Usuario


class PruebasAceptacionSprintDos(TestCase):
    """Preparo administrador, docente, estudiante y paralelo para el flujo académico."""

    def setUp(self):
        """Creo los usuarios institucionales y el paralelo disponible para inscribir."""
        self.client = APIClient()
        admin_rol, _ = Rol.objects.get_or_create(nombre='Administrador')
        docente_rol, _ = Rol.objects.get_or_create(nombre='Docente')
        estudiante_rol, _ = Rol.objects.get_or_create(nombre='Estudiante')
        self.admin = Usuario.objects.create(
            nombres='Admin', ap_pat='Prueba', ap_mat='Da Vinci', correo='admin.aceptacion@ejemplo.test',
            password_hash='hash-prueba', rol=admin_rol,
        )
        docente_usuario = Usuario.objects.create(
            nombres='Docente', ap_pat='Prueba', ap_mat='Da Vinci', correo='docente.aceptacion@ejemplo.test',
            password_hash='hash-prueba', rol=docente_rol,
        )
        self.docente = Docente.objects.create(usuario=docente_usuario)
        estudiante_usuario = Usuario.objects.create(
            nombres='Estudiante', ap_pat='Prueba', ap_mat='Da Vinci', correo='estudiante.aceptacion@ejemplo.test',
            password_hash='hash-prueba', rol=estudiante_rol,
        )
        self.estudiante = Estudiante.objects.create(usuario=estudiante_usuario)
        idioma = Idioma.objects.create(nombre='Inglés', codigo='EN')
        nivel = Nivel.objects.create(codigo='A1')
        curso = Curso.objects.create(idioma=idioma, nivel=nivel, nombre='Inglés A1')
        turno = Turno.objects.create(nombre='Mañana')
        DocenteIdioma.objects.create(docente=self.docente, idioma=idioma)
        self.paralelo = Paralelo.objects.create(
            codigo='EN-MAN-2026-A', curso=curso, turno=turno, docente=self.docente, cupo_maximo=10,
        )

    def _iniciar_sesion(self, usuario):
        """Inicio una sesión de API con el rol del usuario indicado."""
        session = self.client.session
        session['usuario_id'] = usuario.pk
        session['usuario_rol'] = usuario.rol.nombre
        session.save()

    def test_administrador_inscribe_y_estudiante_consulta_su_curso(self):
        """Completo la inscripción administrativa y la consulta del curso por el estudiante."""
        self._iniciar_sesion(self.admin)
        alta = self.client.post('/api/admin/cursos/inscripciones/', {
            'id_estudiante': self.estudiante.pk,
            'id_paralelo': self.paralelo.pk,
        }, format='json')
        self.assertEqual(alta.status_code, 201)
        self.assertTrue(EstudianteParalelo.objects.filter(
            estudiante=self.estudiante, paralelo=self.paralelo, estado='ACTIVO',
        ).exists())

        self._iniciar_sesion(self.estudiante.usuario)
        consulta = self.client.get('/api/estudiante/mis-cursos/')

        self.assertEqual(consulta.status_code, 200)
        self.assertEqual([curso['id_paralelo'] for curso in consulta.data], [self.paralelo.pk])
