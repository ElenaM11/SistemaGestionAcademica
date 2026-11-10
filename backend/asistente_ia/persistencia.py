"""Intentos por pregunta y guardado en RETROALIMENTACION_IA.

MODO POR DEFECTO (ASISTENTE_IA_GUARDAR = False):
    Los intentos se cuentan en la sesión del navegador y no se escribe nada en la base de datos.
    Sirve para probar el flujo completo sin afectar las listas de entregas.

MODO BASE DE DATOS (ASISTENTE_IA_GUARDAR = True):
    Cada consulta a la IA crea una fila en RETROALIMENTACION_IA, enlazada a una ENTREGA en estado
    BORRADOR. Requiere que los modelos de abajo existan con esos nombres de campo.
    >>> AJUSTAR _modelos() y los nombres de campo si en tu proyecto son distintos. <<<
"""
import logging

logger = logging.getLogger(__name__)


def _ajuste(nombre, defecto):
    try:
        from django.conf import settings
        return getattr(settings, nombre, defecto)
    except Exception:
        return defecto


def habilitada():
    return bool(_ajuste("ASISTENTE_IA_GUARDAR", False))


def max_intentos():
    return int(_ajuste("ASISTENTE_IA_MAX_INTENTOS", 3))


def _modelos():
    # AJUSTAR: ubicación y nombre de los modelos reales.
    from actividades.models import Entrega, RetroalimentacionIA
    return Entrega, RetroalimentacionIA


def _clave_sesion(actividad):
    return f"ia_intentos_{actividad.pk}"


def contar_intentos(request, actividad, estudiante, numero):
    if habilitada():
        _, Retro = _modelos()
        return Retro.objects.filter(
            entrega__actividad=actividad, entrega__estudiante=estudiante, numero_pregunta=numero
        ).count()
    return int(request.session.get(_clave_sesion(actividad), {}).get(str(numero), 0))


def intentos_por_pregunta(request, actividad, estudiante):
    """{numero_de_pregunta: intentos usados}, para pintar «Intento k de 3» al abrir el cuestionario."""
    try:
        if habilitada():
            _, Retro = _modelos()
            filas = Retro.objects.filter(
                entrega__actividad=actividad, entrega__estudiante=estudiante
            ).values_list("numero_pregunta", flat=True)
            conteo = {}
            for n in filas:
                conteo[int(n)] = conteo.get(int(n), 0) + 1
            return conteo
        return {int(k): int(v) for k, v in request.session.get(_clave_sesion(actividad), {}).items()}
    except Exception:
        logger.exception("No se pudieron leer los intentos del asistente de IA")
        return {}


def registrar_intento(request, actividad, numero):
    """En modo sesión suma un intento. En modo base de datos el intento queda en la fila guardada."""
    if habilitada():
        return
    clave = _clave_sesion(actividad)
    datos = dict(request.session.get(clave, {}))
    datos[str(numero)] = int(datos.get(str(numero), 0)) + 1
    request.session[clave] = datos


def guardar(actividad, estudiante, numero, respuesta, resultado, modelo):
    """Crea la retroalimentación (y la entrega en BORRADOR si todavía no existe)."""
    Entrega, Retro = _modelos()
    entrega, _ = Entrega.objects.get_or_create(
        actividad=actividad, estudiante=estudiante, defaults={"estado": "BORRADOR"}
    )
    return Retro.objects.create(
        entrega=entrega,
        numero_pregunta=numero,
        modelo_ia=modelo,
        texto_original=respuesta,
        veredicto=resultado["veredicto"],
        tipo_error=resultado["tipo_error"],
        correccion=resultado["correccion"],
        explicacion=resultado["explicacion"],
        ejercicios_sugeridos="\n".join(resultado["ejercicios"]),
    )
