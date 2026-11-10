from django.test import SimpleTestCase
from unittest.mock import patch
from asistente_ia import languagetool

class LanguageToolTestCase(SimpleTestCase):
    @patch('urllib.request.urlopen')
    def test_fallo_de_red_es_silencioso(self, mock_urlopen):
        """Prueba que si LanguageTool falla, el sistema no explota, solo devuelve vacío."""
        mock_urlopen.side_effect = Exception("Error de conexión simulado")
        resultado = languagetool.revisar("She walk", "en-US")
        self.assertEqual(resultado, {"matches": []})