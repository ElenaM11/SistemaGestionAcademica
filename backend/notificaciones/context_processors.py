from .models import Notificacion

def no_leidas(request):
    uid = request.session.get("usuario_id") if hasattr(request, "session") else None
    if not uid:
        return {}
    n = Notificacion.objects.filter(usuario_id=uid, leida=False).count()
    return {"notif_no_leidas": n, "notif_no_leidas_texto": "99+" if n > 99 else str(n)}