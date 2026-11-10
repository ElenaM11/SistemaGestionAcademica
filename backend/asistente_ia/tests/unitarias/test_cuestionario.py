from django.test import SimpleTestCase
from asistente_ia.cuestionario import parsear_y_validar, CuestionarioInvalido, preguntas_publicas

class CuestionarioTestCase(SimpleTestCase):
    def test_parsear_ordenar_exito(self):
        """Prueba que un JSON válido de ordenar se procese correctamente."""
        json_prueba = '[{"tipo": "ordenar", "enunciado": "Ordena", "palabras": ["Hola", "mundo"], "validas": ["Hola mundo"]}]'
        resultado = parsear_y_validar(json_prueba, usa_ia=False)
        self.assertEqual(resultado[0]['tipo'], 'ordenar')
        self.assertEqual(len(resultado[0]['palabras']), 2)

    def test_parsear_sin_ia_exige_respuestas(self):
        """Si usa_ia=False, debe fallar si no hay respuestas válidas."""
        json_prueba = '[{"tipo": "escribir", "enunciado": "Di hola", "validas": []}]'
        with self.assertRaises(CuestionarioInvalido):
            parsear_y_validar(json_prueba, usa_ia=False)

    def test_preguntas_publicas_no_muestran_respuestas(self):
        """Verifica que la función de seguridad elimine la llave 'validas' para el estudiante."""
        json_prueba = '[{"tipo": "escribir", "enunciado": "Di hola", "validas": ["hello"]}]'
        publicas = preguntas_publicas(json_prueba)
        self.assertNotIn("validas", publicas[0])