"""Verifico las consultas y reglas del módulo académico del Sprint 3."""

from datetime import timedelta
from decimal import Decimal
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from cursos.models import Actividad, Asistencia, Curso, Entrega, EstudianteParalelo, Idioma, Nivel, Paralelo, SesionClase, Turno
from rol.models import Rol
from usuarios.models import Docente, Estudiante, Usuario


class PruebasModuloAcademicoSprintTres(TestCase):
    """Preparo estudiantes y un paralelo para verificar el módulo académico."""

    def setUp(self):
        """Creo identidades de estudiante, docente y administrador con datos aislados."""
        self.client = APIClient()
        self.estudiante_usuario = self.crear_usuario('Estudiante', 'alumna@sprint3.test')
        self.otro_usuario = self.crear_usuario('Estudiante', 'otra@sprint3.test')
        self.docente_usuario = self.crear_usuario('Docente', 'docente@sprint3.test')
        self.otro_docente_usuario = self.crear_usuario('Docente', 'ajeno@sprint3.test')
        self.admin = self.crear_usuario('Administrador', 'admin@sprint3.test')
        self.estudiante = Estudiante.objects.create(usuario=self.estudiante_usuario)
        self.otro_estudiante = Estudiante.objects.create(usuario=self.otro_usuario)
        self.docente = Docente.objects.create(usuario=self.docente_usuario)
        self.otro_docente = Docente.objects.create(usuario=self.otro_docente_usuario)
        idioma = Idioma.objects.create(nombre='Inglés', codigo='EN')
        nivel = Nivel.objects.create(codigo='A1')
        self.curso = Curso.objects.create(idioma=idioma, nivel=nivel, nombre='Inglés A1')
        turno = Turno.objects.create(nombre='Mañana')
        self.paralelo = Paralelo.objects.create(codigo='EN-MAN-2026-A', curso=self.curso, turno=turno, docente=self.docente)
        self.ajeno = Paralelo.objects.create(codigo='EN-MAN-2026-B', curso=self.curso, turno=turno, docente=self.otro_docente)
        EstudianteParalelo.objects.create(estudiante=self.estudiante, paralelo=self.paralelo)
        EstudianteParalelo.objects.create(estudiante=self.otro_estudiante, paralelo=self.ajeno)

    def crear_usuario(self, nombre_rol, correo):
        """Creo un usuario activo asociado al rol indicado."""
        rol, _ = Rol.objects.get_or_create(nombre=nombre_rol)
        return Usuario.objects.create(nombres=nombre_rol, ap_pat='Prueba', ap_mat='DV', correo=correo, password_hash='hash', rol=rol)

    def iniciar_sesion(self, usuario):
        """Inicio una sesión de la aplicación con la identidad indicada."""
        sesion = self.client.session
        sesion['usuario_id'] = usuario.pk
        sesion['usuario_rol'] = usuario.rol.nombre
        sesion.save()

    def test_estudiante_consulta_materiales_y_actividades_de_sus_cursos(self):
        """Devuelvo recursos y actividades únicamente de inscripciones propias."""
        self.paralelo.materiales.create(docente=self.docente, titulo='Guía', tipo='PDF')
        self.ajeno.materiales.create(docente=self.otro_docente, titulo='Material ajeno', tipo='PDF')
        self.paralelo.actividades.create(docente=self.docente, titulo='Unidad 1', fecha_limite=timezone.now() + timedelta(days=2))
        self.ajeno.actividades.create(docente=self.otro_docente, titulo='Ajena')
        self.iniciar_sesion(self.estudiante_usuario)

        materiales = self.client.get('/api/estudiante/mis-materiales/')
        actividades = self.client.get('/api/estudiante/mis-actividades/')

        self.assertEqual(materiales.status_code, 200)
        self.assertEqual([x['titulo'] for x in materiales.data], ['Guía'])
        self.assertEqual([x['titulo'] for x in actividades.data], ['Unidad 1'])
        self.assertEqual(actividades.data[0]['estado_estudiante'], 'PENDIENTE')
        self.assertEqual(actividades.data[0]['curso_nombre'], 'Inglés A1')

    def test_endpoint_de_actividades_expone_estados_pendiente_entregada_y_vencida(self):
        """Calculo los tres estados de actividades en la consulta del estudiante."""
        pendiente = Actividad.objects.create(
            paralelo=self.paralelo, docente=self.docente, titulo='Pendiente',
            fecha_limite=timezone.now() + timedelta(days=1),
        )
        entregada = Actividad.objects.create(
            paralelo=self.paralelo, docente=self.docente, titulo='Entregada',
            fecha_limite=timezone.now() + timedelta(days=1),
        )
        vencida = Actividad.objects.create(
            paralelo=self.paralelo, docente=self.docente, titulo='Vencida',
            fecha_limite=timezone.now() - timedelta(days=1),
        )
        Entrega.objects.create(actividad=entregada, estudiante=self.estudiante)
        self.iniciar_sesion(self.estudiante_usuario)

        respuesta = self.client.get('/api/estudiante/mis-actividades/')

        self.assertEqual(respuesta.status_code, 200)
        estados = {actividad['titulo']: actividad['estado_estudiante'] for actividad in respuesta.data}
        self.assertEqual(estados, {
            'Pendiente': 'PENDIENTE',
            'Entregada': 'ENTREGADA',
            'Vencida': 'VENCIDA',
        })

    def test_estudiante_consulta_secciones_de_un_curso_y_no_puede_abrir_otro(self):
        """Muestro la sección del curso propio y rechazo seleccionar un paralelo ajeno."""
        self.iniciar_sesion(self.estudiante_usuario)
        pagina = self.client.get(f'/estudiante/academico/?id_paralelo={self.paralelo.pk}')
        materiales = self.client.get(f'/api/estudiante/mis-materiales/?id_paralelo={self.paralelo.pk}')
        ajeno = self.client.get(f'/estudiante/academico/?id_paralelo={self.ajeno.pk}')

        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Materiales')
        self.assertEqual(materiales.status_code, 200)
        self.assertEqual(ajeno.status_code, 404)

    def test_estudiante_entrega_una_sola_vez_y_se_marca_tardia(self):
        """Registro una entrega tardía permitida y rechazo su duplicado."""
        actividad = Actividad.objects.create(paralelo=self.paralelo, docente=self.docente, titulo='Tarea',
            fecha_limite=timezone.now() - timedelta(hours=1), permite_entrega_tardia=True)
        self.iniciar_sesion(self.estudiante_usuario)
        primera = self.client.post(f'/api/estudiante/actividades/{actividad.pk}/entregar/', {'contenido_texto': 'Respuesta'}, format='json')
        segunda = self.client.post(f'/api/estudiante/actividades/{actividad.pk}/entregar/', {'contenido_texto': 'Otra'}, format='json')

        self.assertEqual(primera.status_code, 201)
        self.assertTrue(primera.data['es_tardia'])
        self.assertEqual(segunda.status_code, 400)

    def test_rechazo_entrega_fuera_de_plazo_si_no_se_permite(self):
        """Rechazo la entrega vencida cuando la actividad no acepta tardías."""
        actividad = Actividad.objects.create(paralelo=self.paralelo, docente=self.docente,
            titulo='Vencida', fecha_limite=timezone.now() - timedelta(hours=1))
        self.iniciar_sesion(self.estudiante_usuario)
        respuesta = self.client.post(f'/api/estudiante/actividades/{actividad.pk}/entregar/', {'contenido_texto': 'Respuesta'}, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Entrega.objects.exists())

    def test_estudiante_entrega_un_archivo(self):
        """Guardo un archivo enviado como parte de una entrega multipart."""
        actividad = Actividad.objects.create(
            paralelo=self.paralelo, docente=self.docente, titulo='Con archivo',
            fecha_limite=timezone.now() + timedelta(days=1),
        )
        self.iniciar_sesion(self.estudiante_usuario)
        archivo = SimpleUploadedFile('respuesta.txt', b'Respuesta de prueba', content_type='text/plain')

        with tempfile.TemporaryDirectory() as carpeta_media:
            with override_settings(MEDIA_ROOT=carpeta_media):
                respuesta = self.client.post(
                    f'/api/estudiante/actividades/{actividad.pk}/entregar/',
                    {'archivo': archivo},
                    format='multipart',
                )

        self.assertEqual(respuesta.status_code, 201)
        entrega = Entrega.objects.get(actividad=actividad, estudiante=self.estudiante)
        self.assertTrue(entrega.archivo.name.startswith('entregas/'))

    def test_estudiante_recibe_progreso_personal_y_no_puede_ver_panel_docente(self):
        """Calculo el progreso propio y niego el recurso de seguimiento docente."""
        actividad = Actividad.objects.create(paralelo=self.paralelo, docente=self.docente, titulo='Tarea')
        Entrega.objects.create(actividad=actividad, estudiante=self.estudiante, calificacion=Decimal('80'))
        sesion = SesionClase.objects.create(paralelo=self.paralelo, fecha=timezone.localdate(), tema='Saludos')
        Asistencia.objects.create(sesion=sesion, estudiante=self.estudiante, estado='PRESENTE')
        self.iniciar_sesion(self.estudiante_usuario)

        progreso = self.client.get('/api/estudiante/mi-progreso/')
        docente = self.client.get('/api/docente/mi-progreso/')

        self.assertEqual(progreso.status_code, 200)
        self.assertEqual(progreso.data[0]['promedio'], 80.0)
        self.assertEqual(progreso.data[0]['asistencia_porcentaje'], 100.0)
        self.assertEqual(docente.status_code, 403)

    def test_calificaciones_son_propias_y_muestran_promedio_y_observaciones(self):
        """Devuelvo las calificaciones propias aunque se solicite otro estudiante."""
        actividad_a = Actividad.objects.create(paralelo=self.paralelo, docente=self.docente, titulo='Nota uno')
        actividad_b = Actividad.objects.create(paralelo=self.paralelo, docente=self.docente, titulo='Nota dos')
        Entrega.objects.create(
            actividad=actividad_a, estudiante=self.estudiante, calificacion=Decimal('80'),
            observaciones='Revisa los verbos.',
        )
        Entrega.objects.create(
            actividad=actividad_b, estudiante=self.estudiante, calificacion=Decimal('100'),
            observaciones='Excelente.',
        )
        Entrega.objects.create(actividad=actividad_a, estudiante=self.otro_estudiante, calificacion=Decimal('10'))
        self.iniciar_sesion(self.estudiante_usuario)

        respuesta = self.client.get(f'/api/estudiante/mis-calificaciones/?id_estudiante={self.otro_estudiante.pk}')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['promedio'], 90.0)
        self.assertEqual(respuesta.data['actividades_calificadas'], 2)
        self.assertEqual(len(respuesta.data['calificaciones']), 2)
        self.assertIn('Revisa los verbos.', [nota['observaciones'] for nota in respuesta.data['calificaciones']])

    def test_endpoint_de_asistencia_calcula_porcentaje_y_solo_muestra_al_estudiante(self):
        """Muestro el historial propio y calculo el porcentaje de asistencia."""
        sesion_presente = SesionClase.objects.create(
            paralelo=self.paralelo, fecha=timezone.localdate(), tema='Presente',
        )
        sesion_ausente = SesionClase.objects.create(
            paralelo=self.paralelo, fecha=timezone.localdate(), tema='Ausencia',
        )
        Asistencia.objects.create(sesion=sesion_presente, estudiante=self.estudiante, estado='PRESENTE')
        Asistencia.objects.create(sesion=sesion_ausente, estudiante=self.estudiante, estado='AUSENTE')
        Asistencia.objects.create(sesion=sesion_presente, estudiante=self.otro_estudiante, estado='PRESENTE')
        self.iniciar_sesion(self.estudiante_usuario)

        respuesta = self.client.get('/api/estudiante/mi-asistencia/')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['presentes'], 1)
        self.assertEqual(respuesta.data['ausentes'], 1)
        self.assertEqual(respuesta.data['porcentaje'], 50.0)
        self.assertEqual(len(respuesta.data['historial']), 2)

    def test_docente_solo_consulta_sus_paralelos_y_admin_recibe_agregados(self):
        """Limito el progreso del docente y la vista administrativa omite identidades."""
        self.iniciar_sesion(self.docente_usuario)
        prohibido = self.client.get(f'/api/docente/paralelos/{self.ajeno.pk}/progreso/')
        propio = self.client.get('/api/docente/mi-progreso/')
        self.assertEqual(prohibido.status_code, 403)
        self.assertEqual(propio.status_code, 200)

        self.iniciar_sesion(self.admin)
        general = self.client.get('/api/admin/resumen-academico/')
        self.assertEqual(general.status_code, 200)
        self.assertEqual(general.data['estudiantes_activos'], 2)
        self.assertNotIn('id_estudiante', str(general.data).lower())
        self.assertNotIn('@', str(general.data))

    def test_admin_filtra_resumen_por_curso_y_busca_estudiantes(self):
        """Filtro el resumen académico por curso y busco un estudiante por nombre."""
        self.iniciar_sesion(self.admin)

        respuesta = self.client.get(
            f'/api/admin/resumen-academico/?curso_id={self.curso.pk}&busqueda=alumna'
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.data['cursos']), 1)
        self.assertEqual(respuesta.data['cursos'][0]['id_curso'], self.curso.pk)
        self.assertEqual(len(respuesta.data['estudiantes']), 1)
        self.assertEqual(respuesta.data['estudiantes'][0]['estudiante'], 'Estudiante Prueba DV')

    def test_admin_resumen_rechaza_filtro_de_curso_invalido_y_rol_no_admin(self):
        """Valido el filtro de curso y restrinjo el resumen administrativo al administrador."""
        self.iniciar_sesion(self.admin)
        invalido = self.client.get('/api/admin/resumen-academico/?curso_id=curso')
        self.assertEqual(invalido.status_code, 400)

        self.iniciar_sesion(self.estudiante_usuario)
        denegado = self.client.get('/api/admin/resumen-academico/')
        self.assertEqual(denegado.status_code, 403)
