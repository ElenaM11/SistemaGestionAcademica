from .models import Notificacion
from django.apps import apps

def no_leidas(request):
    uid = request.session.get("usuario_id") if hasattr(request, "session") else None
    if not uid:
        return {}
    
    # 1. Notificaciones (la campanita de Actividad)
    n = Notificacion.objects.filter(usuario_id=uid, leida=False).count()
    
    # 2. Mensajes de chat (la burbuja en el riel)
    Mensaje = apps.get_model('comunicacion', 'Mensaje') 
    m = Mensaje.objects.filter(receptor_id=uid, leido=False).count()

    return {
        "notif_no_leidas": n, 
        "notif_no_leidas_texto": "99+" if n > 99 else str(n),
        "chat_no_leidos": m,
        "chat_no_leidos_texto": "99+" if m > 99 else str(m)
    }