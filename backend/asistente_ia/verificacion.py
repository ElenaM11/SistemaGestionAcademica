from .cliente_groq import RespuestaIAInvalida
from .prompt import construir_mensaje_usuario
from .resultado import interpretar
from .texto import coincide

def verificar(pregunta, *, idioma, nivel, respuesta, consultar_ia, reintentos_json=1):
    if coincide(respuesta, pregunta["validas"]):
        return {
            "veredicto": "correcto", "tipo_error": "", "correccion": "", "explicacion": "",
            "ejercicios": [], "origen": "local", "esperada": "",
        }
    mensaje = construir_mensaje_usuario(idioma, nivel, pregunta, respuesta)
    resultado = None
    for _ in range(1 + reintentos_json):
        resultado = interpretar(consultar_ia(mensaje))
        if resultado:
            break
    if not resultado:
        raise RespuestaIAInvalida("La IA no devolvió un JSON válido.")

    resultado["origen"] = "ia"
    resultado["esperada"] = pregunta["validas"][0] if resultado["veredicto"] == "variante_valida" else ""
    return resultado
