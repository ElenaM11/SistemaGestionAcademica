from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace
import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory
from django.utils import timezone
from actividades.models import Actividad, Entrega, _aware
from actividades.views import _fecha_limite, _leer_post
from actividades.views_entregas import _estado
from cursos.models import Paralelo
from usuarios.models import Docente

AHORA = datetime(2026, 10, 20, 12, 0, tzinfo=dt_timezone.utc)


def _post(**datos):
    base = {"titulo": "Tarea 1", "fecha_limite": (timezone.localdate() + timedelta(days=10)).strftime("%Y-%m-%d")}
    base.update(datos)
    return RequestFactory().post("/", base)


# PRUEBAS UNITARIAS: _aware

class TestAware:

    def test_fecha_naive_se_convierte_a_utc(self, settings):
        settings.USE_TZ = True
        resultado = _aware(datetime(2026, 10, 20, 12, 0))
        assert resultado.tzinfo is not None
        assert resultado.utcoffset() == timedelta(0)

    def test_sin_zonas_horarias_no_se_modifica(self, settings):
        settings.USE_TZ = False
        naive = datetime(2026, 10, 20, 12, 0)
        assert _aware(naive) == naive

    def test_none_devuelve_none(self):
        assert _aware(None) is None


# PRUEBAS UNITARIAS: Actividad.esta_vencida y acepta_entregas

class TestPlazoActividad:

    def test_sin_fecha_limite_no_esta_vencida(self):
        assert Actividad(fecha_limite=None).esta_vencida(AHORA) is False

    def test_fecha_pasada_esta_vencida(self):
        assert Actividad(fecha_limite=AHORA - timedelta(days=1)).esta_vencida(AHORA) is True

    def test_fecha_futura_no_esta_vencida(self):
        assert Actividad(fecha_limite=AHORA + timedelta(days=1)).esta_vencida(AHORA) is False

    def test_activa_dentro_del_plazo_acepta_entregas(self):
        a = Actividad(fecha_limite=AHORA + timedelta(days=1), estado=Actividad.Estado.ACTIVA)
        assert a.acepta_entregas(AHORA) is True

    def test_vencida_sin_entrega_tardia_no_acepta(self):
        a = Actividad(fecha_limite=AHORA - timedelta(days=1), permite_entrega_tardia=False)
        assert a.acepta_entregas(AHORA) is False

    def test_vencida_con_entrega_tardia_si_acepta(self):
        a = Actividad(fecha_limite=AHORA - timedelta(days=1), permite_entrega_tardia=True)
        assert a.acepta_entregas(AHORA) is True

    def test_cerrada_no_acepta_aunque_permita_tardias(self):
        a = Actividad(
            fecha_limite=AHORA + timedelta(days=1), permite_entrega_tardia=True,
            estado=Actividad.Estado.CERRADA,
        )
        assert a.acepta_entregas(AHORA) is False


# PRUEBAS UNITARIAS: Actividad.clean

class TestActividadClean:

    def test_puntaje_cero_falla(self):
        with pytest.raises(ValidationError) as e:
            Actividad(puntaje_maximo=Decimal("0")).clean()
        assert "mayor a 0" in str(e.value)

    def test_puntaje_negativo_falla(self):
        with pytest.raises(ValidationError):
            Actividad(puntaje_maximo=Decimal("-5")).clean()

    def test_docente_no_asignado_al_paralelo_falla(self):
        """RNF-08: el docente debe ser el del paralelo."""
        actividad = Actividad(paralelo=Paralelo(pk=1, docente_id=5), docente_id=9, puntaje_maximo=Decimal("100"))
        with pytest.raises(ValidationError) as e:
            actividad.clean()
        assert "no está asignado" in str(e.value)

    def test_actividad_valida(self):
        Actividad(paralelo=Paralelo(pk=1, docente_id=5), docente_id=5, puntaje_maximo=Decimal("100")).clean()


# PRUEBAS UNITARIAS: _fecha_limite

class TestFechaLimite:

    def test_fecha_valida_se_fija_a_las_2359(self):
        limite = _fecha_limite("2026-11-05")
        assert (limite.year, limite.month, limite.day) == (2026, 11, 5)
        assert (limite.hour, limite.minute) == (23, 59)

    def test_fecha_con_formato_invalido_falla(self):
        with pytest.raises(ValidationError) as e:
            _fecha_limite("05/11/2026")
        assert "no es válida" in str(e.value)

    def test_fecha_vacia_falla(self):
        with pytest.raises(ValidationError):
            _fecha_limite("")


# PRUEBAS UNITARIAS: _leer_post (formulario de actividad)

class TestLeerPost:

    def test_fecha_limite_en_el_pasado_falla(self):
        with pytest.raises(ValidationError) as e:
            _leer_post(_post(fecha_limite="2020-01-01"))
        assert "pasado" in str(e.value)

    def test_puntaje_vacio_usa_100_por_defecto(self):
        assert _leer_post(_post(puntaje_maximo=""))["puntaje_maximo"] == Decimal("100")

    def test_puntaje_no_numerico_falla(self):
        with pytest.raises(ValidationError) as e:
            _leer_post(_post(puntaje_maximo="abc"))
        assert "puntaje máximo no es válido" in str(e.value)

    def test_casillas_marcadas_y_sin_marcar(self):
        marcadas = _leer_post(_post(permitir_tardia="on", asistente_ia="on"))
        sin_marcar = _leer_post(_post())
        assert marcadas["permite_entrega_tardia"] is True and marcadas["usa_ia"] is True
        assert sin_marcar["permite_entrega_tardia"] is False and sin_marcar["usa_ia"] is False

    def test_limpia_titulo_y_vacios_a_none(self):
        datos = _leer_post(_post(titulo="  Tarea 1  ", instrucciones="  ", tipo=""))
        assert datos["titulo"] == "Tarea 1"
        assert datos["instrucciones"] is None
        assert datos["tipo"] is None


# PRUEBAS UNITARIAS: Entrega.calificar (HU-15)

class TestCalificarEntrega:

    @pytest.fixture(autouse=True)
    def _sin_guardar(self, monkeypatch):
        """Reemplaza save() para no tocar la base de datos."""
        monkeypatch.setattr(Entrega, "save", lambda self, *a, **k: None)

    @staticmethod
    def _entrega(maximo="100"):
        actividad = Actividad(
            paralelo=Paralelo(pk=1, docente_id=5),
            puntaje_maximo=Decimal(maximo) if maximo is not None else None,
        )
        return Entrega(actividad=actividad)

    def test_nota_valida_registra_calificacion_y_estado(self):
        entrega = self._entrega()
        entrega.calificar(Docente(pk=5), Decimal("85"), "Buen trabajo")
        assert entrega.calificacion == Decimal("85")
        assert entrega.observaciones == "Buen trabajo"
        assert entrega.estado == Entrega.Estado.CALIFICADA
        assert entrega.fecha_calificacion is not None

    def test_nota_cero_es_valida(self):
        entrega = self._entrega()
        entrega.calificar(Docente(pk=5), Decimal("0"))
        assert entrega.calificacion == Decimal("0")

    def test_nota_sobre_el_maximo_falla(self):
        with pytest.raises(ValidationError) as e:
            self._entrega("100").calificar(Docente(pk=5), Decimal("101"))
        assert "entre 0 y 100" in str(e.value)

    def test_nota_negativa_falla(self):
        with pytest.raises(ValidationError):
            self._entrega().calificar(Docente(pk=5), Decimal("-1"))

    def test_docente_ajeno_no_puede_calificar(self):
        with pytest.raises(PermissionDenied):
            self._entrega().calificar(SimpleNamespace(pk=9), Decimal("80"))

    def test_observaciones_vacias_se_guardan_como_none(self):
        entrega = self._entrega()
        entrega.calificar(Docente(pk=5), Decimal("80"), "")
        assert entrega.observaciones is None

    def test_sin_puntaje_maximo_solo_exige_nota_no_negativa(self):
        entrega = self._entrega(maximo=None)
        entrega.calificar(Docente(pk=5), Decimal("250"))
        assert entrega.calificacion == Decimal("250")

    def test_modificar_calificacion_reemplaza_la_anterior(self):
        entrega = self._entrega()
        entrega.calificar(Docente(pk=5), Decimal("60"), "Regular")
        entrega.calificar(Docente(pk=5), Decimal("90"), "Corregida")
        assert entrega.calificacion == Decimal("90")
        assert entrega.observaciones == "Corregida"


# PRUEBAS UNITARIAS: _estado (lista de entregas)

class TestEstadoEntrega:

    def test_sin_entrega(self):
        assert _estado(None) == "sin_entregar"

    def test_entrega_calificada(self):
        assert _estado(SimpleNamespace(estado=Entrega.Estado.CALIFICADA, es_tardia=False)) == "calificada"

    def test_entrega_tardia(self):
        assert _estado(SimpleNamespace(estado=Entrega.Estado.ENTREGADA, es_tardia=True)) == "tardia"

    def test_entrega_a_tiempo(self):
        assert _estado(SimpleNamespace(estado=Entrega.Estado.ENTREGADA, es_tardia=False)) == "entregada"
