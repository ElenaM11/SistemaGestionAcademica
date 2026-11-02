from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from comunicacion.models import Mensaje
from comunicacion.routing import websocket_urlpatterns

from comunicacion.tests import factories as f

APP = URLRouter(websocket_urlpatterns)


def comunicador(ruta, usuario_id=None):
    c = WebsocketCommunicator(APP, ruta)
    c.scope["session"] = {"usuario_id": usuario_id} if usuario_id else {}
    return c


class ChatConsumerTests(TransactionTestCase):
    def setUp(self):
        self.ana, self.beto = f.estudiante(), f.estudiante()

    async def test_sin_sesion_se_rechaza_la_conexion(self):
        conectado, _ = await comunicador(f"/ws/chat/{self.beto.pk}/").connect()
        self.assertFalse(conectado)

    async def test_no_se_puede_abrir_un_chat_con_uno_mismo(self):
        conectado, _ = await comunicador(f"/ws/chat/{self.ana.pk}/", self.ana.pk).connect()
        self.assertFalse(conectado)

    async def test_no_se_puede_abrir_un_chat_con_un_administrador(self):
        admin = await self._admin()
        conectado, _ = await comunicador(f"/ws/chat/{admin.pk}/", self.ana.pk).connect()
        self.assertFalse(conectado)

    async def test_el_mensaje_llega_a_los_dos_y_se_guarda(self):
        de_ana = comunicador(f"/ws/chat/{self.beto.pk}/", self.ana.pk)
        de_beto = comunicador(f"/ws/chat/{self.ana.pk}/", self.beto.pk)
        self.assertTrue((await de_ana.connect())[0])
        self.assertTrue((await de_beto.connect())[0])

        await de_ana.send_json_to({"texto": "Hola Beto"})
        recibido = await de_beto.receive_json_from()
        propio = await de_ana.receive_json_from()
        self.assertEqual(recibido["texto"], "Hola Beto")
        self.assertEqual(recibido["emisor_id"], self.ana.pk)
        self.assertEqual(propio["id"], recibido["id"])
        self.assertTrue(await self._guardado("Hola Beto"))
        await de_ana.disconnect()
        await de_beto.disconnect()

    async def test_un_mensaje_vacio_no_se_envia(self):
        c = comunicador(f"/ws/chat/{self.beto.pk}/", self.ana.pk)
        await c.connect()
        await c.send_json_to({"texto": "   "})
        self.assertTrue(await c.receive_nothing())
        await c.disconnect()

    async def test_la_bandeja_del_receptor_recibe_el_aviso(self):
        bandeja = comunicador("/ws/bandeja/", self.beto.pk)
        self.assertTrue((await bandeja.connect())[0])
        de_ana = comunicador(f"/ws/chat/{self.beto.pk}/", self.ana.pk)
        await de_ana.connect()
        await de_ana.send_json_to({"texto": "¿Vienes?"})
        aviso = await bandeja.receive_json_from()
        self.assertEqual((aviso["de_id"], aviso["texto"]), (self.ana.pk, "¿Vienes?"))
        await de_ana.disconnect()
        await bandeja.disconnect()

    async def test_la_bandeja_exige_sesion(self):
        conectado, _ = await comunicador("/ws/bandeja/").connect()
        self.assertFalse(conectado)

    # --- ayudas que tocan la base de datos desde código asíncrono
    async def _guardado(self, texto):
        from asgiref.sync import sync_to_async
        return await sync_to_async(Mensaje.objects.filter(contenido=texto).exists)()

    async def _admin(self):
        from asgiref.sync import sync_to_async
        return await sync_to_async(f.administrador)()