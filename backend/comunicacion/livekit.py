import asyncio
import json
import logging
from datetime import timedelta

from django.conf import settings

log = logging.getLogger(__name__)


def configurado():
    return all(getattr(settings, k, "") for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"))


def crear_token(*, sala, identidad, nombre, rol, puede_compartir):
    # JWT para entrar a la sala. El docente puede publicar todo (audio, cámara y pantalla);
    # el estudiante solo micrófono y cámara, así no puede compartir pantalla aunque manipule el navegador.
    from livekit import api
    permisos = api.VideoGrants(
        room_join=True, room=sala, can_subscribe=True, can_publish=True, can_publish_data=False,
        can_publish_sources=None if puede_compartir else ["microphone", "camera", "screen_share"],
    )
    return (
        api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(identidad).with_name(nombre).with_metadata(json.dumps({"rol": rol}))
        .with_grants(permisos).with_ttl(timedelta(hours=3)).to_jwt()
    )


def cerrar_sala(sala):
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
    except Exception:  # noqa: BLE001 - cualquier falla del servicio externo se registra y se ignora
        log.exception("No se pudo cerrar la sala %s en LiveKit", sala)
        return False