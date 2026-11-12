from notificaciones.models import Notificacion
from notificaciones.services import notificar_usuarios
from django.urls import reverse
from usuarios.models import Usuario
from cursos.models import Paralelo
from .models import Mensaje

def enviar_mensaje(emisor, receptor_id, texto):
    mensaje = Mensaje(emisor=emisor, receptor_id=receptor_id, contenido=(texto or "").strip())
    mensaje.enviar()  
    aviso = f"Nuevo mensaje de {emisor.nombres} {emisor.ap_pat}"
    
    # Calculamos la URL exacta según quién recibe
    receptor = Usuario.objects.get(pk=receptor_id)
    url_destino = None
    
    if receptor.rol.nombre == 'Estudiante':
        url_destino = f"{reverse('estudiante_mensajes')}?con={emisor.pk}"
    elif receptor.rol.nombre == 'Docente':
        # Buscamos el primer curso del docente para armar la URL
        curso_id = Paralelo.objects.filter(docente_id=receptor.pk, estado='ACTIVO').values_list('curso_id', flat=True).first()
        if curso_id:
            url_destino = f"{reverse('docente_mensajes', args=[curso_id])}?con={emisor.pk}"
        else:
            url_destino = f"{reverse('docente_dashboard')}" 
    elif receptor.rol.nombre == 'Administrador':
        url_destino = f"{reverse('admin_mensajes')}?con={emisor.pk}"

    # Evitamos notificaciones duplicadas
    if not Notificacion.objects.filter(usuario_id=receptor_id, tipo="MENSAJE", leida=False, mensaje=aviso).exists():
        notificar_usuarios([receptor_id], "MENSAJE", aviso, url_destino=url_destino)
        
    return mensaje