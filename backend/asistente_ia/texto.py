"""Normalización y comparación de respuestas. No depende de Django."""
import re

_APOSTROFES = str.maketrans({"’": "'", "‘": "'", "´": "'", "`": "'"})
# Caracteres que se ignoran en los extremos de la respuesta (espacios y puntuación).
_BORDES = " \t\n.,;:!?¡¿\"«»"


def normalizar(texto):
    """Minúsculas, apóstrofes rectos, espacios simples y sin puntuación en los extremos."""
    if texto is None:
        return ""
    t = str(texto).translate(_APOSTROFES).lower()
    t = re.sub(r"\s+", " ", t).strip(_BORDES)
    return t.strip()


def palabras(texto):
    """Lista de palabras de un texto ya normalizado."""
    n = normalizar(texto)
    return n.split(" ") if n else []


def coincide(respuesta, validas):
    """True si la respuesta es igual (normalizada) a alguna respuesta válida del docente."""
    n = normalizar(respuesta)
    return bool(n) and any(n == normalizar(v) for v in validas)
