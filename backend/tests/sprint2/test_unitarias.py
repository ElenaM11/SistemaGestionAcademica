"""Pruebo unidades de las reglas académicas del Sprint 2."""

from datetime import time

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from cursos.models import Curso, DocenteIdioma, HorarioParalelo, Idioma, Nivel, Paralelo, Turno
from cursos.services import docente_disponible_para_horarios, generar_codigo_paralelo
from rol.models import Rol
from usuarios.models import Docente, Usuario


class PruebasUnitariasSprintDos(TestCase):
    """Preparo referencias mínimas para probar reglas individuales del Sprint 2."""

    def setUp(self):
        """Creo catálogos y un docente habilitado para las pruebas unitarias."""
        rol, _ = Rol.objects.get_or_create(nombre='Docente')
        usuario = Usuario.objects.create(
            nombres='Ada', ap_pat='Prueba', ap_mat='Da Vinci',
            correo='ada.unitaria@ejemplo.test', password_hash='hash-prueba', rol=rol,
        )
        self.docente = Docente.objects.create(usuario=usuario)
        self.idioma = Idioma.objects.create(nombre='Inglés', codigo='EN')
        nivel = Nivel.objects.create(codigo='A1')
        self.curso = Curso.objects.create(idioma=self.idioma, nivel=nivel, nombre='Inglés A1')
        self.turno = Turno.objects.create(nombre='Mañana')
        DocenteIdioma.objects.create(docente=self.docente, idioma=self.idioma)

    def test_genero_codigo_de_paralelo_y_siguiente_letra(self):
        """Genero una letra inicial y avanzo la secuencia del código de paralelo."""
        codigo = generar_codigo_paralelo(self.curso, self.turno, gestion=2026)
        self.assertEqual(codigo, 'EN-MAN-2026-A')

        Paralelo.objects.create(codigo=codigo, curso=self.curso, turno=self.turno, docente=self.docente)
        self.assertEqual(generar_codigo_paralelo(self.curso, self.turno, gestion=2026), 'EN-MAN-2026-B')

    def test_rechazo_codigo_si_no_hay_prefijo_de_idioma_o_turno(self):
        """Rechazo generar el código si sus datos no producen prefijos válidos."""
        idioma_sin_codigo = Idioma.objects.create(nombre='!!!', codigo='')
        curso = Curso.objects.create(idioma=idioma_sin_codigo, nivel=self.curso.nivel, nombre='Curso sin prefijo')
        turno_sin_prefijo = Turno.objects.create(nombre='???')

        with self.assertRaises(ValidationError):
            generar_codigo_paralelo(curso, turno_sin_prefijo, gestion=2026)

    def test_detecto_disponibilidad_horaria_correcta_y_en_cruce(self):
        """Indico disponibilidad sin solapamiento y rechazo un horario cruzado."""
        paralelo = Paralelo.objects.create(
            codigo='EN-MAN-2026-A', curso=self.curso, turno=self.turno, docente=self.docente,
        )
        HorarioParalelo.objects.create(
            paralelo=paralelo, dia_semana='Lunes', hora_inicio=time(9), hora_fin=time(10),
        )

        libre = [{'dia_semana': 'Lunes', 'hora_inicio': time(10), 'hora_fin': time(11)}]
        cruzado = [{'dia_semana': 'Lunes', 'hora_inicio': time(9, 30), 'hora_fin': time(10, 30)}]

        self.assertTrue(docente_disponible_para_horarios(self.docente, libre))
        self.assertFalse(docente_disponible_para_horarios(self.docente, cruzado))
