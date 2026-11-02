from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from comunicacion.models import Mensaje


class MensajeValidacionTests(SimpleTestCase):
    """Reglas que no necesitan base de datos."""

    def test_no_se_puede_escribir_a_uno_mismo(self):
        with self.assertRaises(ValidationError):
            Mensaje(emisor_id=1, receptor_id=1, contenido="hola").clean()

    def test_el_mensaje_no_puede_estar_vacio(self):
        with self.assertRaises(ValidationError):
            Mensaje(emisor_id=1, receptor_id=2, contenido="   ").clean()

    def test_el_mensaje_no_puede_superar_1000_caracteres(self):
        with self.assertRaises(ValidationError):
            Mensaje(emisor_id=1, receptor_id=2, contenido="a" * 1001).clean()