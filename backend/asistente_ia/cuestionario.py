import json
import re
from .texto import palabras

TIPOS = ("escribir", "ordenar")
MAX_PREGUNTAS = 20
MAX_FICHAS = 15
MAX_ENUNCIADO = 300
MAX_RESPUESTA = 300

class CuestionarioInvalido(ValueError):
    """El cuestionario enviado por el docente no cumple el formato o las reglas."""
    pass

def _texto(valor, maximo, etiqueta):
    if not isinstance(valor, str):
        return ""
    limpio = re.sub(r"\s+", " ", valor).strip()
    if len(limpio) > maximo:
        raise CuestionarioInvalido(f"{etiqueta}: el texto es demasiado largo (máximo {maximo} caracteres).")
    return limpio

def _lista_textos(valores, maximo, etiqueta):
    if not isinstance(valores, list):
        return []
    vistos, salida = set(), []
    for v in valores:
        t = _texto(v, maximo, etiqueta)
        if t and t.lower() not in vistos:
            vistos.add(t.lower())
            salida.append(t)
    return salida

def parsear_y_validar(bruto, usa_ia=False):
    if bruto is None or not str(bruto).strip():
        raise CuestionarioInvalido("Agrega al menos una pregunta al cuestionario.")
    try:
        datos = json.loads(bruto)
    except (TypeError, ValueError):
        raise CuestionarioInvalido("El cuestionario no tiene un formato válido.")
    if not isinstance(datos, list) or not datos:
        raise CuestionarioInvalido("Agrega al menos una pregunta al cuestionario.")
    if len(datos) > MAX_PREGUNTAS:
        raise CuestionarioInvalido(f"Un cuestionario admite como máximo {MAX_PREGUNTAS} preguntas.")

    limpio = []
    for n, q in enumerate(datos, start=1):
        etiqueta = f"Pregunta {n}"
        if not isinstance(q, dict):
            raise CuestionarioInvalido(f"{etiqueta}: formato no válido.")
        tipo = q.get("tipo")
        if tipo not in TIPOS:
            raise CuestionarioInvalido(f"{etiqueta}: elige el tipo Escribir u Ordenar.")
        enunciado = _texto(q.get("enunciado"), MAX_ENUNCIADO, etiqueta)
        if not enunciado:
            raise CuestionarioInvalido(f"{etiqueta}: escribe el enunciado.")
        
        validas = _lista_textos(q.get("validas"), MAX_RESPUESTA, etiqueta)
        if not validas and not usa_ia:
            raise CuestionarioInvalido(f"{etiqueta}: agrega al menos una respuesta válida (o habilita el apoyo de IA).")
            
        item = {"tipo": tipo, "enunciado": enunciado, "validas": validas}
        if tipo == "ordenar":
            fichas = _lista_textos(q.get("palabras"), 60, etiqueta)
            if len(fichas) < 2:
                raise CuestionarioInvalido(f"{etiqueta}: agrega al menos dos fichas (palabras o frases).")
            if len(fichas) > MAX_FICHAS:
                raise CuestionarioInvalido(f"{etiqueta}: usa como máximo {MAX_FICHAS} fichas.")
            
            if validas:
                esperado = sorted(palabras(" ".join(fichas)))
                for v in validas:
                    if sorted(palabras(v)) != esperado:
                        raise CuestionarioInvalido(
                            f"{etiqueta}: la respuesta válida «{v}» debe usar exactamente las mismas palabras de las fichas."
                        )
            item["palabras"] = fichas
        limpio.append(item)
    return limpio

def _cargar(bruto):
    try:
        datos = json.loads(bruto) if bruto else []
    except (TypeError, ValueError):
        return []
    return datos if isinstance(datos, list) else []

def preguntas_publicas(bruto):
    """Preguntas para el navegador del estudiante: NUNCA incluye las respuestas válidas."""
    salida = []
    for q in _cargar(bruto):
        if not isinstance(q, dict) or q.get("tipo") not in TIPOS:
            continue
        item = {"tipo": q["tipo"], "enunciado": str(q.get("enunciado", ""))}
        if q["tipo"] == "ordenar":
            item["palabras"] = [str(p) for p in q.get("palabras", [])]
        salida.append(item)
    return salida

def obtener_pregunta(bruto, numero):
    """Pregunta completa (con respuestas válidas) por número, empezando en 1. None si no existe."""
    datos = _cargar(bruto)
    if isinstance(numero, int) and 1 <= numero <= len(datos) and isinstance(datos[numero - 1], dict):
        return datos[numero - 1]
    return None

def respuesta_ordenar_valida(pregunta, respuesta):
    """En 'ordenar' la respuesta debe usar exactamente las palabras de las fichas."""
    esperado = sorted(palabras(" ".join(pregunta.get("palabras", []))))
    return sorted(palabras(respuesta)) == esperado