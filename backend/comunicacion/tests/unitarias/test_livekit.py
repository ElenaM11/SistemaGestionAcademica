import json
from unittest.mock import patch

import jwt
from django.test import SimpleTestCase, override_settings

from comunicacion import livekit

CONF = dict(LIVEKIT_URL="wss://prueba.livekit.cloud", LIVEKIT_API_KEY="APIprueba",
            LIVEKIT_API_SECRET="secreto-de-prueba-bastante-largo-1234567890")


@override_settings(**CONF)
class TokenTests(SimpleTestCase):
    def claims(self, puede_compartir):
        token = livekit.crear_token(sala="clase-7", identidad="u5", nombre="Ana Pérez", rol="Estudiante",
                                    puede_compartir=puede_compartir)
        return jwt.decode(token, CONF["LIVEKIT_API_SECRET"], algorithms=["HS256"], options={"verify_aud": False})

    def test_identifica_a_la_persona_y_la_sala(self):
        c = self.claims(False)
        self.assertEqual(c["sub"], "u5")
        self.assertEqual(c["name"], "Ana Pérez")
        self.assertEqual(c["video"]["room"], "clase-7")
        self.assertTrue(c["video"]["roomJoin"])
        self.assertEqual(json.loads(c["metadata"])["rol"], "Estudiante")

    def test_el_estudiante_puede_publicar_microfono_camara_y_pantalla(self):
        self.assertEqual(
            self.claims(False)["video"]["canPublishSources"],
            ["microphone", "camera", "screen_share"],
        )

    def test_el_docente_no_tiene_restriccion_de_fuentes(self):
        self.assertFalse(self.claims(True)["video"].get("canPublishSources"))

    def test_el_token_expira_en_unas_horas(self):
        c = self.claims(False)
        self.assertGreater(c["exp"] - c["nbf"], 3600)
        self.assertLessEqual(c["exp"] - c["nbf"], 4 * 3600)


class ConfiguracionTests(SimpleTestCase):
    @override_settings(**CONF)
    def test_configurado_con_los_tres_datos(self):
        self.assertTrue(livekit.configurado())

    @override_settings(**{**CONF, "LIVEKIT_API_SECRET": ""})
    def test_no_esta_configurado_si_falta_el_secret(self):
        self.assertFalse(livekit.configurado())

    @override_settings(**{**CONF, "LIVEKIT_URL": ""})
    def test_cerrar_sala_sin_configuracion_no_hace_nada(self):
        self.assertFalse(livekit.cerrar_sala("clase-1"))

    @override_settings(**CONF)
    def test_cerrar_sala_sin_nombre_no_hace_nada(self):
        self.assertFalse(livekit.cerrar_sala(""))

    @override_settings(**CONF)
    def test_si_livekit_falla_cerrar_sala_no_lanza_error(self):
        def falla(corutina):
            corutina.close()
            raise RuntimeError("sin red")
        with patch("comunicacion.livekit.asyncio.run", side_effect=falla), \
                self.assertLogs("comunicacion.livekit", level="ERROR"):
            self.assertFalse(livekit.cerrar_sala("clase-1"))