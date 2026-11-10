"""Lectura y validación del JSON que devuelve la IA."""
import json
import re

VEREDICTOS = ("correcto", "variante_valida", "error")


def _recortar(valor, maximo):
    return valor.strip()[:maximo] if isinstance(valor, str) else ""


def interpretar(texto):
    """Devuelve el resultado limpio (dict) o None si la respuesta no es un JSON válido."""
    if not texto:
        return None
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip(), flags=re.IGNORECASE)
    ini, fin = t.find("{"), t.rfind("}")
    if ini == -1 or fin == -1:
        return None
    try:
        datos = json.loads(t[ini:fin + 1])
    except ValueError:
        return None
    if not isinstance(datos, dict) or datos.get("veredicto") not in VEREDICTOS:
        return None

    ejercicios = datos.get("ejercicios")
    ejercicios = [_recortar(e, 200) for e in ejercicios if _recortar(e, 200)][:3] if isinstance(ejercicios, list) else []
    resultado = {
        "veredicto": datos["veredicto"],
        "tipo_error": _recortar(datos.get("tipo_error"), 80),
        "correccion": _recortar(datos.get("correccion"), 300),
        "explicacion": _recortar(datos.get("explicacion"), 600),
        "ejercicios": ejercicios,
    }
    # Coherencia con las reglas del prompt: el modelo a veces rellena campos de más.
    if resultado["veredicto"] == "correcto":
        resultado.update(tipo_error="", correccion="", explicacion="", ejercicios=[])
    elif resultado["veredicto"] == "variante_valida":
        resultado.update(tipo_error="", correccion="", ejercicios=[])
    return resultado
