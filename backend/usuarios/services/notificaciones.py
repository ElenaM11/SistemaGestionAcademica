import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def enviar_credenciales(correo_personal, nombre, correo_institucional, password_temporal, rol):
    if not correo_personal:
        return False, "El usuario no tiene un correo personal registrado."
        
    url = getattr(settings, 'GOOGLE_SCRIPT_URL', None)
    token = getattr(settings, 'GOOGLE_SCRIPT_SECRET', None)
    
    if not url or not token or url == 'TU_URL_EXEC_AQUI':
        return False, "Faltan configurar las credenciales de Google Apps Script."

    # AQUÍ ESTÁ LA MAGIA: Los nombres coinciden exactamente con tu script de Google
    payload = {
        "token": token,
        "correo": correo_personal,
        "usuario": correo_institucional,
        "contraseña": password_temporal,
        "nombre": nombre,
        "rol": rol
    }
    
    try:
        # Hacemos la petición a Google
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        # Leemos la respuesta
        data = response.json()
        
        # Tu script devuelve "success", no "status" ni "ok"
        if data.get('success'): 
            return True, data.get('message', "Correo enviado correctamente.")
            
        return False, data.get('message', "El script de Google reportó un error interno.")
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout al enviar correo a {correo_personal}")
        return False, "Tiempo de espera agotado al conectar con Google."
  
    except Exception as e:
        logger.error(f"Error al enviar correo a {correo_personal}: {e}")
        # Cambia el mensaje genérico por el error real temporalmente
        return False, f"Error técnico: {str(e)}"