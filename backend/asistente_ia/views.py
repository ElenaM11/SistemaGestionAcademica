import json
import logging
import time
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from actividades.models import Actividad
from cursos.models import EstudianteParalelo
from usuarios.models import Estudiante, Usuario

from . import cliente_groq, persistencia, languagetool
from .cliente_groq import ServicioIAError
from .cuestionario import MAX_RESPUESTA, obtener_pregunta, respuesta_ordenar_valida
from .verificacion import verificar

logger = logging.getLogger(__name__)

MENSAJE_SERVICIO = "El asistente no está disponible en este momento. Intenta de nuevo en unos minutos."

def _error(codigo, mensaje, estado):
    return JsonResponse({"error": codigo, "mensaje": mensaje}, status=estado)

def _estudiante(request):
    uid = request.session.get("usuario_id")
    if not uid:
        return None
    usuario = Usuario.objects.select_related("rol").filter(id_usuario=uid, estado=True).first()
    if not usuario or usuario.rol.nombre != "Estudiante":
        return None
    return Estudiante.objects.filter(pk=usuario.pk).first()

@require_POST
def verificar_respuesta(request, actividad_id):
    estudiante = _estudiante(request)
    if estudiante is None:
        return _error("sesion", "Inicia sesión como estudiante para continuar.", 401)

    actividad = (
        Actividad.objects.select_related("paralelo__curso__idioma", "paralelo__curso__nivel")
        .filter(pk=actividad_id, tipo__in=[Actividad.Tipo.CUESTIONARIO, Actividad.Tipo.ORDENAR], usa_ia=True)
        .first()
    )
    if actividad is None:
        return _error("actividad", "Esta actividad no tiene apoyo de IA.", 404)
    if not EstudianteParalelo.objects.filter(
        estudiante=estudiante, paralelo=actividad.paralelo, estado="ACTIVO"
    ).exists():
        return _error("acceso", "No tienes acceso a esta actividad.", 403)
    if actividad.esta_vencida() and not actividad.permite_entrega_tardia:
        return _error("vencida", "La actividad ya venció.", 403)

    try:
        cuerpo = json.loads(request.body.decode("utf-8"))
        numero = int(cuerpo["pregunta"])
        respuesta = str(cuerpo["respuesta"]).strip()
    except (ValueError, KeyError, TypeError):
        return _error("formato", "La solicitud no tiene el formato esperado.", 400)

    pregunta = obtener_pregunta(getattr(actividad, "cuestionario", None), numero)
    if pregunta is None:
        return _error("pregunta", "La pregunta no existe.", 404)
    if not respuesta:
        return _error("vacia", "Escribe o arma tu respuesta antes de verificar.", 400)
    if len(respuesta) > MAX_RESPUESTA:
        return _error("larga", f"La respuesta admite como máximo {MAX_RESPUESTA} caracteres.", 400)
    if pregunta["tipo"] == "ordenar" and not respuesta_ordenar_valida(pregunta, respuesta):
        return _error("fichas", "Usa todas las fichas, sin añadir ni quitar palabras.", 400)

    limite = persistencia.max_intentos()
    curso = actividad.paralelo.curso
    try:
        resultado = _resolver(request, actividad, estudiante, numero, pregunta, respuesta, curso, limite)
    except _LimiteAlcanzado:
        return _error("limite", f"Alcanzaste el máximo de {limite} intentos en esta pregunta.", 429)
    except ServicioIAError:
        logger.exception("Falló la consulta al servicio de IA")
        return _error("servicio", MENSAJE_SERVICIO, 503)

    usados = persistencia.contar_intentos(request, actividad, estudiante, numero) if resultado["origen"] == "ia" else 0
    return JsonResponse({
        **resultado,
        "intentos_usados": usados,
        "intentos_max": limite,
    })

class _LimiteAlcanzado(Exception):
    pass

def _resolver(request, actividad, estudiante, numero, pregunta, respuesta, curso, limite):
    def consultar_ia(mensaje):
        if persistencia.contar_intentos(request, actividad, estudiante, numero) >= limite:
            raise _LimiteAlcanzado()
        return cliente_groq.consultar(mensaje)

    resultado = verificar(
        pregunta,
        idioma=curso.idioma.nombre,
        nivel=curso.nivel.codigo,
        respuesta=respuesta,
        consultar_ia=consultar_ia,
    )
    if resultado["origen"] == "ia":
        persistencia.registrar_intento(request, actividad, numero)
    return resultado

@require_POST
def revisar_texto(request):
    """Endpoint de LanguageTool, con límite de 1 req cada 2 segundos por sesión."""
    if not request.session.get("usuario_id"):
        return JsonResponse({"matches": []})
        
    ahora = time.time()
    ultimo = request.session.get("lt_ultimo_intento", 0)
    if ahora - ultimo < 2:
        return JsonResponse({"matches": [], "aviso": "Demasiadas solicitudes"})
    request.session["lt_ultimo_intento"] = ahora

    try:
        cuerpo = json.loads(request.body.decode("utf-8"))
        texto = str(cuerpo.get("texto", ""))
        idioma = str(cuerpo.get("idioma", "en-US"))
    except Exception:
        return JsonResponse({"matches": []})

    if not texto.strip() or len(texto) > 300:
        return JsonResponse({"matches": []})

    # Mapeo de códigos internos a LanguageTool
    mapa = {"EN": "en-US", "FR": "fr", "PT": "pt-BR"}
    idioma_lt = mapa.get(idioma.upper(), "en-US")

    return JsonResponse(languagetool.revisar(texto, idioma_lt))