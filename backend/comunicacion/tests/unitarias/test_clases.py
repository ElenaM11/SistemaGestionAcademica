from datetime import datetime, time
from types import SimpleNamespace

from django.test import SimpleTestCase

from asistencia.models import SesionClase
from comunicacion import views

EN_CURSO = SesionClase.Estado.EN_CURSO


class UtilidadesTests(SimpleTestCase):
    def sesion(self, estado, hora):
        return SimpleNamespace(estado=estado, hora_inicio=hora)

    def ahora(self, h, m):
        return datetime(2026, 11, 2, h, m)

    def test_estado_en_vivo_y_finalizada(self):
        self.assertEqual(views._estado_vista(self.sesion(EN_CURSO, time(8)), self.ahora(8, 5)), "en_vivo")
        self.assertEqual(views._estado_vista(self.sesion("FINALIZADA", time(8)), self.ahora(10, 0)), "finalizada")

    def test_una_clase_proxima_aparece_por_iniciar(self):
        self.assertEqual(views._estado_vista(self.sesion("PROGRAMADA", time(8)), self.ahora(7, 40)), "por_iniciar")
        self.assertEqual(views._estado_vista(self.sesion("PROGRAMADA", time(8)), self.ahora(9, 0)), "por_iniciar")   # atrasada

    def test_una_clase_lejana_aparece_programada(self):
        self.assertEqual(views._estado_vista(self.sesion("PROGRAMADA", time(15)), self.ahora(8, 0)), "programada")

    def test_una_clase_sin_hora_aparece_por_iniciar(self):
        self.assertEqual(views._estado_vista(self.sesion("PROGRAMADA", None), self.ahora(8, 0)), "por_iniciar")

    def test_dias_sin_tildes_ni_mayusculas(self):
        self.assertEqual(views._sin_tildes(" Miércoles "), "miercoles")
        self.assertEqual(views._sin_tildes("SÁBADO"), "sabado")