from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.exceptions import ValidationError

from usuarios.models import Usuario

from .models import Mensaje
from .permisos import pueden_conversar
from .servicios import enviar_mensaje


@database_sync_to_async
def _uid_de_sesion(scope):
    sesion = scope.get("session")
    valor = sesion.get("usuario_id") if sesion is not None else None
    return int(valor) if valor else None


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Conversación entre dos personas. ws://host/ws/chat/<otro_usuario_id>/"""

    async def connect(self):
        self.otro_id = self.scope["url_route"]["kwargs"]["otro_id"]
        self.uid = await _uid_de_sesion(self.scope)
        if not self.uid or not await self._autorizado():
            await self.close(code=4403)
            return
        self.grupo = f"chat_{min(self.uid, self.otro_id)}_{max(self.uid, self.otro_id)}"
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
        # Aviso a la bandeja del receptor
        await self.channel_layer.group_send(f"bandeja_{self.otro_id}", {
            "type": "bandeja.nuevo", "de_id": datos["emisor_id"], "nombre": datos["emisor_nombre"],
            "iniciales": datos["iniciales"], "texto": datos["texto"],
        })

    async def chat_mensaje(self, event):
        datos = {k: v for k, v in event.items() if k != "type"}
        await self.send_json(datos)
        if datos["emisor_id"] != self.uid:  # lo recibe quien tiene la conversación abierta: queda leído
            await self._marcar_leido(datos["id"])

    @database_sync_to_async
    def _autorizado(self):
        return pueden_conversar(self.uid, self.otro_id)

    @database_sync_to_async
    def _guardar(self, texto):
        emisor = Usuario.objects.get(pk=self.uid)
        m = enviar_mensaje(emisor, self.otro_id, texto)
        return {
            "id": m.pk, "emisor_id": m.emisor_id, "texto": m.contenido, "fecha": m.fecha_envio.isoformat(),
            "emisor_nombre": f"{emisor.nombres} {emisor.ap_pat}",
            "iniciales": f"{emisor.nombres[:1]}{emisor.ap_pat[:1]}".upper(),
        }

    @database_sync_to_async
    def _marcar_leido(self, pk):
        Mensaje.objects.filter(pk=pk, receptor_id=self.uid).update(leido=True)

    @database_sync_to_async
    def _marcar_todo_leido(self):
        Mensaje.objects.filter(emisor_id=self.otro_id, receptor_id=self.uid, leido=False).update(leido=True)


class BandejaConsumer(AsyncJsonWebsocketConsumer):
    """Avisos en vivo para la lista de chats de cada persona. ws://host/ws/bandeja/"""

    async def connect(self):
        self.uid = await _uid_de_sesion(self.scope)
        if not self.uid:
            await self.close(code=4401)
            return
        self.grupo = f"bandeja_{self.uid}"
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "grupo"):
            await self.channel_layer.group_discard(self.grupo, self.channel_name)

    async def bandeja_nuevo(self, event):
        await self.send_json({k: v for k, v in event.items() if k != "type"})