from notificaciones.models import Notificacion
from notificaciones.services import notificar_usuarios

from .models import Mensaje

def enviar_mensaje(emisor, receptor_id, paralelo, texto):
    mensaje = Mensaje(emisor=emisor, receptor_id=receptor_id, paralelo=paralelo, contenido=(texto or "").strip())
    mensaje.enviar()  # full_clean(): vacío, largo y relación docente-estudiante
    aviso = f"Nuevo mensaje de {emisor.nombres} {emisor.ap_pat}"
    if not Notificacion.objects.filter(usuario_id=receptor_id, tipo="MENSAJE", leida=False, mensaje=aviso).exists():
        notificar_usuarios([receptor_id], "MENSAJE", aviso)
    return mensaje
