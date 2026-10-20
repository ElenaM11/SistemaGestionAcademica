"""Pruebo directamente las reglas de negocio académicas del Sprint 3."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from cursos.models import Actividad, Asistencia, Curso, Entrega, EstudianteParalelo, Idioma, Nivel, Paralelo, SesionClase, Turno
from cursos.services import actividades_estudiante, entregar_actividad, resumen_progreso
from rol.models import Rol
from usuarios.models import Docente, Estudiante, Usuario


class PruebasReglasAcademicasSprintTres(TestCase):
    """Preparo un curso con docente y estudiantes para probar reglas aisladas."""

    def setUp(self):
        """Creo las entidades mínimas para evaluar las reglas del Sprint 3."""
        self.estudiante = self._crear_estudiante('unidad@sprint3.test')
        self.otro_estudiante = self._crear_estudiante('otra.unidad@sprint3.test')
        docente_usuario = self._crear_usuario('Docente', 'docente.unidad@sprint3.test')
        self.docente = Docente.objects.create(usuario=docente_usuario)
        idioma = Idioma.objects.create(nombre='Idioma Unidad', codigo='IU')
        nivel = Nivel.objects.create(codigo='U-A1')
        curso = Curso.objects.create(idioma=idioma, nivel=nivel, nombre='Curso Unidad')
        turno = Turno.objects.create(nombre='Turno Unidad')
        self.paralelo = Paralelo.objects.create(
            codigo='U-2026-A', curso=curso, turno=turno, docente=self.docente,
        )
        EstudianteParalelo.objects.create(estudiante=self.estudiante, paralelo=self.paralelo)

    def _crear_usuario(self, rol_nombre, correo):
        """Creo una identidad activa con el rol requerido por la prueba."""
        rol, _ = Rol.objects.get_or_create(nombre=rol_nombre)
        return Usuario.objects.create(
            nombres='Cuenta', ap_pat='Unidad', ap_mat='Prueba',
            correo=correo, password_hash='hash-prueba', rol=rol,
        )

    def _crear_estudiante(self, correo):
        """Creo un estudiante activo aislado para la prueba."""
        return Estudiante.objects.create(usuario=self._crear_usuario('Estudiante', correo))

    def test_servicio_calcula_estado_pendiente_entregada_y_vencida(self):
        """Calculo los estados de actividades sin pasar por una vista HTTP."""
        pendiente = Actividad.objects.create(
            paralelo=self.paralelo, docente=self.docente, titulo='Pendiente',
            fecha_limite=timezone.now() + timedelta(days=1),
        )
        entregada = Actividad.objects.create(
            paralelo=self.paralelo, docente=self.docente, titulo='Entregada',
        )
        vencida = Actividad.objects.create(
            paralelo=self.paralelo, docente=self.docente, titulo='Vencida',
            fecha_limite=timezone.now() - timedelta(days=1),
        )
        Entrega.objects.create(actividad=entregada, estudiante=self.estudiante)

        estados = {
            actividad.titulo: estado
            for actividad, _, estado in actividades_estudiante(self.estudiante, self.paralelo.pk)
        }

        self.assertEqual(estados, {
            'Pendiente': 'PENDIENTE',
            'Entregada': 'ENTREGADA',
            'Vencida': 'VENCIDA',
        })

    def test_servicio_rechaza_entrega_tardia_no_permitida_y_paralelo_ajeno(self):
        """Rechazo la entrega vencida y la entrega desde una inscripción ajena."""
        vencida = Actividad.objects.create(
            paralelo=self.paralelo, docente=self.docente, titulo='Vencida',
            fecha_limite=timezone.now() - timedelta(days=1),
        )
        no_inscrito = Actividad.objects.create(
            paralelo=self.paralelo, docente=self.docente, titulo='No inscrito',
        )

        with self.assertRaises(ValidationError):
            entregar_actividad(self.estudiante, vencida.pk, contenido_texto='Tarde')
        with self.assertRaises(PermissionDenied):
            entregar_actividad(self.otro_estudiante, no_inscrito.pk, contenido_texto='Ajena')
        self.assertFalse(Entrega.objects.exists())

    def test_servicio_integra_notas_entregas_y_asistencia(self):
        """Integro los indicadores de progreso del estudiante en su paralelo."""
        actividad_calificada = Actividad.objects.create(
            paralelo=self.paralelo, docente=self.docente, titulo='Calificada',
        )
        Actividad.objects.create(paralelo=self.paralelo, docente=self.docente, titulo='Pendiente')
        Entrega.objects.create(
            actividad=actividad_calificada, estudiante=self.estudiante,
            calificacion=Decimal('80'),
        )
        sesion_presente = SesionClase.objects.create(
            paralelo=self.paralelo, fecha=timezone.localdate(), tema='Presente',
        )
        sesion_ausente = SesionClase.objects.create(
            paralelo=self.paralelo, fecha=timezone.localdate(), tema='Ausente',
        )
        Asistencia.objects.create(sesion=sesion_presente, estudiante=self.estudiante, estado='PRESENTE')
        Asistencia.objects.create(sesion=sesion_ausente, estudiante=self.estudiante, estado='AUSENTE')

        progreso = resumen_progreso(self.estudiante, self.paralelo)

        self.assertEqual(progreso['promedio'], 80.0)
        self.assertEqual(progreso['actividades_entregadas'], 1)
        self.assertEqual(progreso['actividades_totales'], 2)
        self.assertEqual(progreso['asistencias_presentes'], 1)
        self.assertEqual(progreso['asistencias_ausentes'], 1)
        self.assertEqual(progreso['asistencia_porcentaje'], 50.0)
