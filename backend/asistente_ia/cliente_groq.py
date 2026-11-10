
import json
import logging
import os
import time
import urllib.error
import urllib.request

from .prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

URL_DEFECTO = "https://api.groq.com/openai/v1/chat/completions"
MODELO_DEFECTO = "openai/gpt-oss-120b"
REINTENTABLES = (429, 500, 502, 503, 504)


class ServicioIAError(Exception):
    """El servicio de IA no pudo atender la consulta (red, cuota, clave, formato)."""


class RespuestaIAInvalida(ServicioIAError):
    """La IA respondió, pero no con el JSON esperado."""


def ajuste(nombre, defecto=""):
    """Lee un ajuste de django.conf.settings y, si no está, de las variables de entorno."""
    valor = None
    try:
        from django.conf import settings
        valor = getattr(settings, nombre, None)
    except Exception:  # Django no instalado o sin configurar (por ejemplo, en pruebas)
        valor = None
    if valor in (None, ""):
        valor = os.environ.get(nombre, "")
    return valor if valor not in (None, "") else defecto


def modelo_configurado():
    return ajuste("GROQ_MODEL", MODELO_DEFECTO)


def _espera(error):
    try:
        return max(0.0, min(3.0, float(error.headers.get("retry-after", 1))))
    except (TypeError, ValueError, AttributeError):
        return 1.0


def _contenido(payload):
    try:
        return payload["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ServicioIAError("La respuesta del servicio de IA no tiene el formato esperado.")


def consultar(mensaje_usuario, *, system=SYSTEM_PROMPT, clave=None, modelo=None, url=None,
              timeout=None, intentos=2, esperar=time.sleep):
    """Envía la consulta y devuelve el texto de la respuesta. Lanza ServicioIAError si falla."""
    clave = clave or ajuste("GROQ_API_KEY")
    if not clave:
        raise ServicioIAError("Falta configurar GROQ_API_KEY.")
    cuerpo = {
        "model": modelo or modelo_configurado(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": mensaje_usuario},
        ],
        "temperature": 0,
        "max_completion_tokens": int(ajuste("GROQ_MAX_TOKENS", 1500)),
    }
    esfuerzo = ajuste("GROQ_REASONING_EFFORT")
    if esfuerzo:
        cuerpo["reasoning_effort"] = esfuerzo
    datos = json.dumps(cuerpo).encode("utf-8")
    cabeceras = {
        "Authorization": f"Bearer {clave}",
        "Content-Type": "application/json",
        # Algunos filtros bloquean el agente por defecto de urllib.
        "User-Agent": "DaVinciAsistenteIA/1.0",
    }
    destino = url or ajuste("GROQ_API_URL", URL_DEFECTO)
    limite = float(timeout or ajuste("GROQ_TIMEOUT", 25))

    for n in range(intentos):
        ultimo = n == intentos - 1
        peticion = urllib.request.Request(destino, data=datos, headers=cabeceras, method="POST")
        try:
            with urllib.request.urlopen(peticion, timeout=limite) as respuesta:
                return _contenido(json.loads(respuesta.read().decode("utf-8")))
        except urllib.error.HTTPError as e:  # antes que URLError: es una subclase
            logger.warning("Groq respondió HTTP %s", e.code)
            if e.code in REINTENTABLES and not ultimo:
                esperar(_espera(e))
                continue
            raise ServicioIAError(f"El servicio de IA respondió HTTP {e.code}.") from e
        except (urllib.error.URLError, OSError) as e:
            logger.warning("Sin conexión con Groq: %s", e)
            if not ultimo:
                esperar(1)
                continue
            raise ServicioIAError("No hay conexión con el servicio de IA.") from e
        except ValueError as e:
            raise ServicioIAError("El servicio de IA devolvió una respuesta ilegible.") from e
    raise ServicioIAError("El servicio de IA no respondió.")
