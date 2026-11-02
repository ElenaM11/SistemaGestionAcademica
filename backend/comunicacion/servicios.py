from notificaciones.models import Notificacion
from notificaciones.services import notificar_usuarios

from .models import Mensaje

def enviar_mensaje(emisor, receptor_id, texto):
    mensaje = Mensaje(emisor=emisor, receptor_id=receptor_id, contenido=(texto or "").strip())
    mensaje.enviar()  
    aviso = f"Nuevo mensaje de {emisor.nombres} {emisor.ap_pat}"
    if not Notificacion.objects.filter(usuario_id=receptor_id, tipo="MENSAJE", leida=False, mensaje=aviso).exists():
        notificar_usuarios([receptor_id], "MENSAJE", aviso)
    return mensaje