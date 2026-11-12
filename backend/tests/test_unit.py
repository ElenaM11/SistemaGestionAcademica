from django.test import SimpleTestCase
from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.utils import timezone

# Importaciones de TODO tu sistema
from usuarios.views import (
    _inicial, generar_codigo_estudiante, correo_desde_codigo, 
    generar_password, generar_correo_docente, generar_correo_admin, _validar_password_segura
)
from cursos.services import _prefijo_codigo, _siguiente_letra_paralelo
from asistente_ia.texto import normalizar, palabras, coincide
from asistente_ia.cuestionario import parsear_y_validar, CuestionarioInvalido, respuesta_ordenar_valida
from asistente_ia.resultado import interpretar
from asistente_ia.verificacion import verificar
from actividades.models import Actividad
from comunicacion.livekit import crear_token
from comunicacion.permisos import pueden_conversar

class TestUsuariosLogica(SimpleTestCase):
    def test_inicial(self):
        self.assertEqual(_inicial("Juan"), "J")
        self.assertEqual(_inicial("Ángel"), "A")
        self.assertEqual(_inicial("123"), "")

    @patch('usuarios.views.Estudiante.objects.filter')
    def test_generar_codigo_estudiante(self, mock_filter):
        mock_filter.return_value.values_list.return_value = []
        self.assertEqual(generar_codigo_estudiante("Juan", "Perez", "Gomez"), "PGJ001")
        self.assertEqual(generar_codigo_estudiante("Maria", "Lopez", ""), "LM001")

    def test_correo_desde_codigo(self):
        self.assertEqual(correo_desde_codigo("ABC123"), "abc123@davinci.edu.bo")
        self.assertEqual(correo_desde_codigo(""), "")

    def test_generar_password(self):
        p1, p2 = generar_password(), generar_password()
        self.assertEqual(len(p1), 10)
        self.assertNotEqual(p1, p2) # Deben ser aleatorias

    @patch('usuarios.views.Usuario.objects.filter')
    def test_generar_correos(self, mock_filter):
        mock_filter.return_value.exists.return_value = False
        self.assertEqual(generar_correo_docente("Carlos", "Mendoza", ""), "doccmendoza@davinci.edu.bo")
        self.assertEqual(generar_correo_admin("Ana", "Silva", ""), "adminasilva@davinci.edu.bo")

    def test_validar_password_segura(self):
        self.assertFalse(_validar_password_segura("123")[0]) # Muy corta
        self.assertFalse(_validar_password_segura("abcdefgh")[0]) # Sin mayúscula
        self.assertFalse(_validar_password_segura("ABCDEFGH")[0]) # Sin minúscula
        self.assertFalse(_validar_password_segura("Abcdefgh")[0]) # Sin número
        self.assertFalse(_validar_password_segura("Abcdefg1")[0]) # Sin símbolo
        self.assertTrue(_validar_password_segura("Abcdefg1!")[0]) # Válida

class TestCursosLogica(SimpleTestCase):
    def test_prefijo_codigo(self):
        self.assertEqual(_prefijo_codigo("Inglés"), "ING")
        self.assertEqual(_prefijo_codigo("Portugués"), "POR")
        self.assertEqual(_prefijo_codigo(""), "")
        self.assertEqual(_prefijo_codigo("A1"), "A")

    @patch('cursos.services.Paralelo.objects.filter')
    def test_siguiente_letra_paralelo(self, mock_filter):
        mock_filter.return_value.values_list.return_value = ["ING-M-2026-A"]
        self.assertEqual(_siguiente_letra_paralelo("ING-M-2026-"), "B")
        
        mock_filter.return_value.values_list.return_value = ["ING-M-2026-A", "ING-M-2026-B"]
        self.assertEqual(_siguiente_letra_paralelo("ING-M-2026-"), "C")

class TestActividadesLogica(SimpleTestCase):
    def test_esta_vencida(self):
        act = Actividad(fecha_limite=None)
        self.assertFalse(act.esta_vencida())
        
        act.fecha_limite = timezone.now() + timedelta(days=1)
        self.assertFalse(act.esta_vencida())
        
        act.fecha_limite = timezone.now() - timedelta(days=1)
        self.assertTrue(act.esta_vencida())

class TestAsistenteIALogica(SimpleTestCase):
    def test_normalizar(self):
        self.assertEqual(normalizar("  ¡Hola, Mundo!  "), "hola, mundo")
        self.assertEqual(normalizar("It's a test"), "it's a test")

    def test_palabras(self):
        self.assertEqual(palabras("Hello world"), ["hello", "world"])
        self.assertEqual(palabras(""), [])

    def test_coincide(self):
        self.assertTrue(coincide("Hola", ["hola", "hi"]))
        self.assertFalse(coincide("Hola!", ["hello"]))

    def test_parsear_y_validar(self):
        json_ok = '[{"tipo": "escribir", "enunciado": "Saluda", "validas": ["Hello"]}]'
        self.assertEqual(len(parsear_y_validar(json_ok)), 1)
        
        with self.assertRaises(CuestionarioInvalido):
            parsear_y_validar("no es json")
            
        with self.assertRaises(CuestionarioInvalido):
            parsear_y_validar('[{"tipo": "escribir", "enunciado": ""}]')

    def test_respuesta_ordenar_valida(self):
        pregunta = {"palabras": ["she", "walks", "to", "school"]}
        self.assertTrue(respuesta_ordenar_valida(pregunta, "she walks to school"))
        self.assertTrue(respuesta_ordenar_valida(pregunta, "walks she school to")) # Mismas palabras
        self.assertFalse(respuesta_ordenar_valida(pregunta, "she runs to school")) # Falta palabra

    def test_interpretar(self):
        json_ok = '{"veredicto": "correcto", "explicacion": "", "ejercicios": []}'
        res = interpretar(json_ok)
        self.assertEqual(res["veredicto"], "correcto")
        
        self.assertIsNone(interpretar("texto random"))

class TestComunicacionLogica(SimpleTestCase):
    @patch('livekit.api.AccessToken') 
    def test_crear_token_livekit(self, mock_token):
        mock_instance = MagicMock()
        mock_instance.with_identity.return_value = mock_instance
        mock_instance.with_name.return_value = mock_instance
        mock_instance.with_metadata.return_value = mock_instance
        mock_instance.with_grants.return_value = mock_instance
        mock_instance.with_ttl.return_value = mock_instance
        mock_instance.to_jwt.return_value = "jwt_falso"
        mock_token.return_value = mock_instance
        
        token = crear_token(sala="test", identidad="1", nombre="Test", rol="Docente", puede_compartir=True)
        self.assertEqual(token, "jwt_falso")

    @patch('comunicacion.permisos.Docente.objects.filter')
    @patch('comunicacion.permisos.Estudiante.objects.filter')
    def test_pueden_conversar(self, mock_est, mock_doc):
        mock_doc.return_value.values_list.return_value = [1]
        mock_est.return_value.values_list.return_value = [2]
        self.assertTrue(pueden_conversar(1, 2))
        
        self.assertFalse(pueden_conversar(1, 1)) # Mismo usuario