"""Lógica de «Verificar»: compara con las respuestas del docente y consulta a la IA solo si hace falta."""
from .cliente_groq import RespuestaIAInvalida
from .prompt import construir_mensaje_usuario
from .resultado import interpretar
from .texto import coincide


def verificar(pregunta, *, idioma, nivel, respuesta, consultar_ia, reintentos_json=1):
    """Devuelve un dict con veredicto, tipo_error, correccion, explicacion, ejercicios,
    origen ('local' o 'ia') y esperada (la respuesta del docente, solo en variantes válidas).

    consultar_ia: función que recibe el mensaje de usuario y devuelve el texto de la IA.
    Puede lanzar ServicioIAError.
    """
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
