"""Pruebo los permisos y reglas académicas implementados para Sprint 2."""

import json

from django.test import TestCase
from rest_framework.test import APIClient
from datetime import time

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
        self.otro_docente_usuario = self._crear_usuario('Docente', 'docente2@ejemplo.test')
        self.otro_docente = Docente.objects.create(usuario=self.otro_docente_usuario)
        self.estudiante = Estudiante.objects.create(usuario=self.estudiante_usuario)
        otro_estudiante_usuario = self._crear_usuario('Estudiante', 'estudiante2@ejemplo.test')
        self.otro_estudiante = Estudiante.objects.create(usuario=otro_estudiante_usuario)
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

    def _crear_paralelo(self, codigo, docente=None, curso=None, inicio=time(9), fin=time(10)):
        """Creo un paralelo de prueba con un horario para las historias académicas."""
        paralelo = Paralelo.objects.create(
            codigo=codigo, curso=curso or self.curso, turno=self.turno,
            docente=docente or self.docente, cupo_maximo=10,
        )
        paralelo.horarios.create(dia_semana='Lunes', hora_inicio=inicio, hora_fin=fin)
        return paralelo

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

    def test_hu05_admin_reasigna_docente_habilitado(self):
        """Reasigno el paralelo cuando el nuevo docente puede enseñar el idioma."""
        paralelo = self._crear_paralelo('ING-A1-M1')
        DocenteIdioma.objects.create(docente=self.otro_docente, idioma=self.idioma)
        self._sesion(self.admin)

        respuesta = self.client.post(
            f'/api/admin/cursos/paralelos/{paralelo.pk}/asignar-docente/',
            {'id_docente': self.otro_docente.pk}, format='json',
        )

        self.assertEqual(respuesta.status_code, 200)
        paralelo.refresh_from_db()
        self.assertEqual(paralelo.docente_id, self.otro_docente.pk)

    def test_hu05_rechaza_docente_sin_idioma_habilitado(self):
        """Rechazo asignar un docente que no está habilitado para el idioma."""
        paralelo = self._crear_paralelo('ING-A1-M1')
        self._sesion(self.admin)

        respuesta = self.client.post(
            f'/api/admin/cursos/paralelos/{paralelo.pk}/asignar-docente/',
            {'id_docente': self.otro_docente.pk}, format='json',
        )

        self.assertEqual(respuesta.status_code, 400)
        paralelo.refresh_from_db()
        self.assertEqual(paralelo.docente_id, self.docente.pk)

    def test_hu05_rechaza_reasignacion_con_cruce_horario(self):
        """Rechazo asignar un paralelo si el nuevo docente ya tiene cruce horario."""
        DocenteIdioma.objects.create(docente=self.otro_docente, idioma=self.idioma)
        self._crear_paralelo('ING-A1-M1', docente=self.docente, inicio=time(9), fin=time(10))
        destino = self._crear_paralelo('ING-A1-M2', docente=self.otro_docente, inicio=time(9, 30), fin=time(10, 30))
        self._sesion(self.admin)

        respuesta = self.client.post(
            f'/api/admin/cursos/paralelos/{destino.pk}/asignar-docente/',
            {'id_docente': self.docente.pk}, format='json',
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_hu06_admin_inscribe_estudiante_existente(self):
        """Inscribo en un paralelo una cuenta de estudiante ya registrada."""
        paralelo = self._crear_paralelo('ING-A1-M1')
        self._sesion(self.admin)

        respuesta = self.client.post('/api/admin/cursos/inscripciones/', {
            'id_estudiante': self.estudiante.pk,
            'id_paralelo': paralelo.pk,
        }, format='json')

        self.assertEqual(respuesta.status_code, 201)
        self.assertTrue(EstudianteParalelo.objects.filter(
            estudiante=self.estudiante, paralelo=paralelo, estado='ACTIVO',
        ).exists())

    def test_hu06_admin_cambia_estudiante_de_paralelo(self):
        """Cambio una inscripción activa al paralelo elegido por el administrador."""
        anterior = self._crear_paralelo('ING-A1-M1')
        nuevo = self._crear_paralelo('ING-A1-M2', inicio=time(11), fin=time(12))
        inscripcion = EstudianteParalelo.objects.create(estudiante=self.estudiante, paralelo=anterior)
        self._sesion(self.admin)

        respuesta = self.client.patch(
            f'/api/admin/cursos/inscripciones/{inscripcion.pk}/',
            {'id_paralelo': nuevo.pk}, format='json',
        )

        self.assertEqual(respuesta.status_code, 200)
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.paralelo_id, nuevo.pk)
        self.assertEqual(inscripcion.estado, 'ACTIVO')

    def test_hu06_estudiante_no_puede_gestionar_inscripciones(self):
        """Deniego que un estudiante acceda a la gestión administrativa de inscripciones."""
        paralelo = self._crear_paralelo('ING-A1-M1')
        self._sesion(self.estudiante_usuario)

        respuesta = self.client.post('/api/admin/cursos/inscripciones/', {
            'id_estudiante': self.estudiante.pk,
            'id_paralelo': paralelo.pk,
        }, format='json')

        self.assertEqual(respuesta.status_code, 403)

    def test_hu07_docente_consulta_solo_estudiantes_de_su_paralelo(self):
        """Devuelvo al docente únicamente los estudiantes de su paralelo asignado."""
        propio = self._crear_paralelo('ING-A1-M1', docente=self.docente)
        ajeno = self._crear_paralelo('ING-A1-M2', docente=self.otro_docente, inicio=time(11), fin=time(12))
        EstudianteParalelo.objects.create(estudiante=self.estudiante, paralelo=propio)
        EstudianteParalelo.objects.create(estudiante=self.otro_estudiante, paralelo=ajeno)
        self._sesion(self.docente_usuario)

        respuesta = self.client.get(f'/api/docente/paralelos/{propio.pk}/estudiantes/')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([fila['id_estudiante'] for fila in respuesta.data], [self.estudiante.pk])

    def test_hu07_docente_recibe_403_para_paralelo_ajeno(self):
        """Deniego al docente la lista de estudiantes de un paralelo ajeno."""
        paralelo = self._crear_paralelo('ING-A1-M1', docente=self.otro_docente)
        self._sesion(self.docente_usuario)

        respuesta = self.client.get(f'/api/docente/paralelos/{paralelo.pk}/estudiantes/')

        self.assertEqual(respuesta.status_code, 403)

    def test_hu08_estudiante_consulta_solo_sus_cursos(self):
        """Muestro al estudiante autenticado sus cursos y excluyo los de otra cuenta."""
        propio = self._crear_paralelo('ING-A1-M1')
        ajeno = self._crear_paralelo('ING-A1-M2', inicio=time(11), fin=time(12))
        EstudianteParalelo.objects.create(estudiante=self.estudiante, paralelo=propio)
        EstudianteParalelo.objects.create(estudiante=self.otro_estudiante, paralelo=ajeno)
        self._sesion(self.estudiante_usuario)

        respuesta = self.client.get('/api/estudiante/mis-cursos/')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([fila['id_paralelo'] for fila in respuesta.data], [propio.pk])

    def test_docente_ve_tarjeta_de_paralelo_asignado(self):
        """Muestro la tarjeta del paralelo activo asignado al docente."""
        paralelo = Paralelo.objects.create(
            codigo='ING-A1-M1', curso=self.curso, turno=self.turno,
            docente=self.docente, cupo_maximo=10,
        )
        EstudianteParalelo.objects.create(estudiante=self.estudiante, paralelo=paralelo)
        self._sesion(self.docente_usuario)

        respuesta = self.client.get('/docente/cursos/')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'teacher-course-card')
        self.assertContains(respuesta, 'Inglés A1')
        self.assertContains(respuesta, 'ING-A1-M1')
        self.assertContains(respuesta, '1 estudiante')

    def test_admin_edita_cupos_y_cambia_idioma_del_paralelo(self):
        """Actualizo cupos y curso cuando el nuevo docente está habilitado para su idioma."""
        paralelo = self._crear_paralelo('ING-A1-M1')
        idioma_es = Idioma.objects.create(nombre='Español', codigo='ES')
        curso_es = Curso.objects.create(idioma=idioma_es, nivel=self.nivel, nombre='Español A1')
        DocenteIdioma.objects.create(docente=self.otro_docente, idioma=idioma_es)
        self._sesion(self.admin)

        respuesta = self.client.patch(
            f'/api/admin/cursos/paralelos/{paralelo.pk}/',
            {'id_curso': curso_es.pk, 'id_docente': self.otro_docente.pk, 'cupo_maximo': 18},
            format='json',
        )

        self.assertEqual(respuesta.status_code, 200)
        paralelo.refresh_from_db()
        self.assertEqual(paralelo.curso_id, curso_es.pk)
        self.assertEqual(paralelo.docente_id, self.otro_docente.pk)
        self.assertEqual(paralelo.cupo_maximo, 18)

    def test_admin_no_reduce_cupo_bajo_inscritos(self):
        """Rechazo bajar el cupo máximo por debajo de las inscripciones activas."""
        paralelo = self._crear_paralelo('ING-A1-M1', inicio=time(9), fin=time(10))
        otro_estudiante = Estudiante.objects.create(
            usuario=self._crear_usuario('Estudiante', 'cupo2@ejemplo.test')
        )
        EstudianteParalelo.objects.create(estudiante=self.estudiante, paralelo=paralelo)
        EstudianteParalelo.objects.create(estudiante=otro_estudiante, paralelo=paralelo)
        self._sesion(self.admin)

        respuesta = self.client.patch(
            f'/api/admin/cursos/paralelos/{paralelo.pk}/',
            {'cupo_maximo': 1}, format='json',
        )

        self.assertEqual(respuesta.status_code, 400)
        paralelo.refresh_from_db()
        self.assertEqual(paralelo.cupo_maximo, 10)

    def test_admin_desactiva_paralelo_sin_borrar_inscripciones(self):
        """Desactivo un paralelo conservando el registro y sus inscripciones."""
        paralelo = self._crear_paralelo('ING-A1-M1')
        inscripcion = EstudianteParalelo.objects.create(estudiante=self.estudiante, paralelo=paralelo)
        self._sesion(self.admin)

        respuesta = self.client.patch(
            f'/api/admin/cursos/paralelos/{paralelo.pk}/',
            {'estado': 'INACTIVO'}, format='json',
        )

        self.assertEqual(respuesta.status_code, 200)
        paralelo.refresh_from_db()
        self.assertEqual(paralelo.estado, 'INACTIVO')
        self.assertTrue(EstudianteParalelo.objects.filter(pk=inscripcion.pk).exists())

    def test_admin_puede_abrir_edicion_de_paralelo(self):
        """Muestro el formulario con los datos actuales al editar un paralelo."""
        paralelo = self._crear_paralelo('ING-A1-M1')
        self._sesion(self.admin)

        respuesta = self.client.get(f'/admin/cursos/paralelos/?editar={paralelo.pk}')

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f'Editar paralelo {paralelo.codigo}')
        self.assertContains(respuesta, 'name="cupo_maximo"')
