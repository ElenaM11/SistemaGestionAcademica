from django.test import SimpleTestCase
from asistente_ia.texto import normalizar, palabras, coincide

class TextoUnitTest(SimpleTestCase):
    """Pruebas unitarias para la normalización y comparación de respuestas de texto."""

    def test_normalizar_minusculas_y_espacios(self):
        """Verifica que el texto se convierta a minúsculas y se limpien espacios dobles."""
        entrada = "  HOLA   Mundo  "
        esperado = "hola mundo"
        self.assertEqual(normalizar(entrada), esperado)

    def test_normalizar_puntuacion_extremos(self):
        """Verifica que se eliminen signos de puntuación al inicio y final de la respuesta."""
        entrada = "¡Hello World!"
        esperado = "hello world"
        self.assertEqual(normalizar(entrada), esperado)

    def test_normalizar_apostrofes(self):
        """Verifica que los apóstrofes curvos (de Word/celular) se conviertan a rectos."""
        entrada = "I’m here"  # Apóstrofe curvo
        esperado = "i'm here" # Apóstrofe recto
        self.assertEqual(normalizar(entrada), esperado)

    def test_normalizar_none_o_vacio(self):
        """Verifica que la función no falle si el texto es None o está vacío."""
        self.assertEqual(normalizar(None), "")
        self.assertEqual(normalizar("   "), "")

    def test_palabras(self):
        """Verifica que la función divida correctamente una oración en palabras."""
        entrada = "She walks to school."
        esperado = ["she", "walks", "to", "school"]
        self.assertEqual(palabras(entrada), esperado)
        
        # Si el texto está vacío, debe devolver una lista vacía
        self.assertEqual(palabras(""), [])

    def test_coincide_exito(self):
        """Verifica que detecte una coincidencia ignorando mayúsculas y puntuación."""
        respuesta_estudiante = "She walks to school."
        respuestas_docente = ["hello", "she walks to school", "another one"]
        # Debe devolver True aunque el estudiante puso mayúscula y punto final
        self.assertTrue(coincide(respuesta_estudiante, respuestas_docente))

    def test_coincide_fallo(self):
        """Verifica que devuelva False cuando el texto es diferente."""
        respuesta_estudiante = "She walking to school"
        respuestas_docente = ["she walks to school"]
        self.assertFalse(coincide(respuesta_estudiante, respuestas_docente))

    def test_coincide_vacio(self):
        """Verifica que una respuesta vacía nunca coincida (para evitar falsos positivos)."""
        self.assertFalse(coincide("", ["hello"]))
        self.assertFalse(coincide("   ", ["hello"]))