import json
import urllib.parse
import urllib.request
import logging

logger = logging.getLogger(__name__)

def revisar(texto, idioma='en-US'):
    try:
        from django.conf import settings
        url = getattr(settings, 'LANGUAGETOOL_URL', 'https://api.languagetool.org/v2/check')
        timeout = float(getattr(settings, 'LANGUAGETOOL_TIMEOUT', 2.0))
        
        datos = urllib.parse.urlencode({'text': texto, 'language': idioma}).encode('utf-8')
        req = urllib.request.Request(url, data=datos, method='POST')
        with urllib.request.urlopen(req, timeout=timeout) as respuesta:
            return json.loads(respuesta.read().decode('utf-8'))
    except Exception as e:
        logger.warning(f"Error al consultar LanguageTool: {e}")
        return {"matches": []}