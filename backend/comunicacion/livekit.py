"""Integración con LiveKit (WebRTC). Requiere: pip install livekit-api

settings.py:  LIVEKIT_URL = "wss://TU-PROYECTO.livekit.cloud"
              LIVEKIT_API_KEY = "..."   LIVEKIT_API_SECRET = "..."   (mejor desde variables de entorno)
"""
import asyncio
import json
import logging
from datetime import timedelta

from django.conf import settings

log = logging.getLogger(__name__)


def configurado():
    return all(getattr(settings, k, "") for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"))


def crear_token(*, sala, identidad, nombre, rol, puede_compartir):
    """JWT para entrar a la sala. El docente puede publicar todo (audio y pantalla);
    el estudiante solo el micrófono, así no puede compartir pantalla aunque manipule el navegador."""
    from livekit import api
    permisos = api.VideoGrants(
        room_join=True, room=sala, can_subscribe=True, can_publish=True, can_publish_data=False,
        can_publish_sources=None if puede_compartir else ["microphone"],
    )
    return (
        api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(identidad).with_name(nombre).with_metadata(json.dumps({"rol": rol}))
        .with_grants(permisos).with_ttl(timedelta(hours=3)).to_jwt()
    )


def cerrar_sala(sala):
    """Expulsa a todos y borra la sala. Si falla no impide finalizar la clase: la sala vacía se cierra sola."""
    if not sala or not configurado():
        return False
    try:
        from livekit import api
        url = settings.LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")

        async def borrar():
            async with api.LiveKitAPI(url, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) as lk:
                await lk.room.delete_room(api.DeleteRoomRequest(room=sala))

        asyncio.run(borrar())
        return True
    except Exception:  #cualquier falla del servicio externo se registra y se ignora
        log.exception("No se pudo cerrar la sala %s en LiveKit", sala)
        return False
