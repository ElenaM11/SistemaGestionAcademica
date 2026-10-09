"""Pruebo los permisos y reglas académicas implementados para Sprint 2."""

import json

from django.test import TestCase
from rest_framework.test import APIClient

from cursos.models import Curso, DocenteIdioma, EstudianteParalelo, Idioma, Nivel, Paralelo, Turno
from rol.models import Rol
from usuarios.models import Docente, Estudiante, Usuario


class PruebasSprintDos(TestCase):
    """Preparo usuarios y catálogos aislados para verificar Sprint 2."""

    def setUp(self):
        """Creo los roles, usuarios y referencias necesarias para las pruebas."""
        self.client = APIClient()
        self.admin = self._crear_usuario('Administrador', 'admin@ejemplo.test')
        self.docente_usuario = self._crear_usuario('Docente', 'docente@ejemplo.test')
        self.estudiante_usuario = self._crear_usuario('Estudiante', 'estudiante@ejemplo.test')
        self.docente = Docente.objects.create(usuario=self.docente_usuario)
        self.estudiante = Estudiante.objects.create(usuario=self.estudiante_usuario)
        self.idioma = Idioma.objects.create(nombre='Inglés', codigo='EN')
        self.nivel = Nivel.objects.create(codigo='A1')
        self.curso = Curso.objects.create(idioma=self.idioma, nivel=self.nivel, nombre='Inglés A1')
        self.turno = Turno.objects.create(nombre='Mañana')
        DocenteIdioma.objects.create(docente=self.docente, idioma=self.idioma)

    def _crear_usuario(self, nombre_rol, correo):
        """Creo una cuenta activa asociada al rol indicado."""
        rol, _ = Rol.objects.get_or_create(nombre=nombre_rol)
        return Usuario.objects.create(
            nombres=nombre_rol,
            ap_pat='Prueba',
            ap_mat='Da Vinci',
            correo=correo,
            password_hash='hash-no-utilizado',
            rol=rol,
        )

    def _sesion(self, usuario):
        """Guardo en la sesión la identidad utilizada por el backend actual."""
        session = self.client.session
        session['usuario_id'] = usuario.pk
        session['usuario_rol'] = usuario.rol.nombre
        session.save()

    def test_administrador_crea_curso(self):
        """Verifico que el administrador pueda agregar un curso al catálogo."""
        self._sesion(self.admin)
        respuesta = self.client.post('/api/admin/cursos/catalogo/', {
            'idioma': self.idioma.pk,
            'nivel': self.nivel.pk,
            'nombre': 'Inglés A2',
            'descripcion': 'Nivel siguiente',
        }, format='json')
        self.assertEqual(respuesta.status_code, 201)
        self.assertTrue(Curso.objects.filter(nombre='Inglés A2').exists())

    def test_estudiante_no_puede_gestionar_catalogo(self):
        """Verifico que un estudiante reciba 403 al acceder a la administración."""
        self._sesion(self.estudiante_usuario)
        respuesta = self.client.get('/api/admin/cursos/catalogo/')
        self.assertEqual(respuesta.status_code, 403)

    def test_no_inscribo_si_el_paralelo_esta_lleno(self):
        """Verifico que la regla de cupo máximo rechace una inscripción adicional."""
        otro_usuario = self._crear_usuario('Estudiante', 'otro@ejemplo.test')
        otro_estudiante = Estudiante.objects.create(usuario=otro_usuario)
        paralelo = Paralelo.objects.create(
            codigo='ING-A1-M1', curso=self.curso, turno=self.turno, docente=self.docente, cupo_maximo=1,
        )
        EstudianteParalelo.objects.create(estudiante=otro_estudiante, paralelo=paralelo)
        self._sesion(self.admin)
        respuesta = self.client.post('/api/admin/cursos/inscripciones/', {
            'id_estudiante': self.estudiante.pk,
            'id_paralelo': paralelo.pk,
        }, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('cupo', str(json.loads(respuesta.content)).lower())
