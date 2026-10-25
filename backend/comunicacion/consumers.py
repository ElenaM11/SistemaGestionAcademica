from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.exceptions import ValidationError

from cursos.models import Paralelo
from usuarios.models import Usuario

from .models import Mensaje
from .permisos import pueden_conversar
from .servicios import enviar_mensaje


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        kw = self.scope["url_route"]["kwargs"]
        self.paralelo_id, self.otro_id = kw["paralelo_id"], kw["otro_id"]
        self.uid = await self._usuario_id()
        if not self.uid or not await self._autorizado():
            await self.close(code=4403)
            return
        self.grupo = f"chat_{self.paralelo_id}_{min(self.uid, self.otro_id)}_{max(self.uid, self.otro_id)}"
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept()
        await self._marcar_todo_leido()

    async def disconnect(self, code):
        if hasattr(self, "grupo"):
            await self.channel_layer.group_discard(self.grupo, self.channel_name)

    async def receive_json(self, content, **kwargs):
        texto = str(content.get("texto", "")).strip()
        if not texto:
            return
        try:
            datos = await self._guardar(texto)
        except ValidationError as e:
            await self.send_json({"error": " ".join(e.messages)})
            return
        await self.channel_layer.group_send(self.grupo, {"type": "chat.mensaje", **datos})

    async def chat_mensaje(self, event):
        datos = {k: v for k, v in event.items() if k != "type"}
        await self.send_json(datos)
        if datos["emisor_id"] != self.uid:  # lo recibe quien tiene la conversación abierta: queda leído
            await self._marcar_leido(datos["id"])

    @database_sync_to_async
    def _usuario_id(self):
        sesion = self.scope.get("session")
        valor = sesion.get("usuario_id") if sesion is not None else None
        return int(valor) if valor else None

    @database_sync_to_async
    def _autorizado(self):
        return pueden_conversar(self.uid, self.otro_id, self.paralelo_id)

    @database_sync_to_async
    def _guardar(self, texto):
        emisor = Usuario.objects.get(pk=self.uid)
        paralelo = Paralelo.objects.get(pk=self.paralelo_id)
        m = enviar_mensaje(emisor, self.otro_id, paralelo, texto)
        return {"id": m.pk, "emisor_id": m.emisor_id, "texto": m.contenido, "fecha": m.fecha_envio.isoformat()}

    @database_sync_to_async
    def _marcar_leido(self, pk):
        Mensaje.objects.filter(pk=pk, receptor_id=self.uid).update(leido=True)

    @database_sync_to_async
    def _marcar_todo_leido(self):
        Mensaje.objects.filter(emisor_id=self.otro_id, receptor_id=self.uid,
                               paralelo_id=self.paralelo_id, leido=False).update(leido=True)
