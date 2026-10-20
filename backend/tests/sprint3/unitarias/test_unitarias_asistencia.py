from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from asistencia import services
from asistencia.services import resumen_asistencia
from asistencia.views import _fecha, _horario, _sin_tildes
from asistencia.views_historial import _fecha_o_none

def _orm_falso(total_sesiones, filas):
    """Simula Asistencia.objects.filter(...) con el total de sesiones y los conteos por estado."""
    consulta = MagicMock()
    consulta.filter.return_value = consulta

    def values(*campos):
        resultado = MagicMock()
        if campos == ("sesion_id",):
            resultado.distinct.return_value.count.return_value = total_sesiones
        else:
            resultado.annotate.return_value = filas
        return resultado

    consulta.values.side_effect = values
    modelo = MagicMock()
    modelo.objects.filter.return_value = consulta
    return modelo, consulta


@pytest.fixture
def orm(monkeypatch):
    """Instala el simulacro en el servicio y devuelve una función para configurarlo."""
    def configurar(total, filas):
        modelo, consulta = _orm_falso(total, filas)
        monkeypatch.setattr(services, "Asistencia", modelo)
        return consulta
    return configurar


# PRUEBAS UNITARIAS: _sin_tildes

class TestSinTildes:

    def test_quita_tildes_y_pasa_a_minusculas(self):
        assert _sin_tildes("Miércoles") == "miercoles"

    def test_mayusculas_con_tilde(self):
        assert _sin_tildes("SÁBADO") == "sabado"

    def test_none_devuelve_cadena_vacia(self):
        assert _sin_tildes(None) == ""


# PRUEBAS UNITARIAS: _fecha y _fecha_o_none

class TestLecturaDeFechas:

    def test_fecha_valida(self):
        assert _fecha("2026-10-20", date(2000, 1, 1)) == date(2026, 10, 20)

    def test_fecha_invalida_devuelve_la_de_por_defecto(self):
        assert _fecha("20/10/2026", date(2000, 1, 1)) == date(2000, 1, 1)

    def test_fecha_none_devuelve_la_de_por_defecto(self):
        assert _fecha(None, date(2000, 1, 1)) == date(2000, 1, 1)

    def test_fecha_o_none_valida(self):
        assert _fecha_o_none("2026-10-20") == date(2026, 10, 20)

    def test_fecha_o_none_invalida_devuelve_none(self):
        assert _fecha_o_none("20/10/2026") is None

    def test_fecha_o_none_vacia_devuelve_none(self):
        assert _fecha_o_none("") is None


# PRUEBAS UNITARIAS: _horario

class TestHorarioDelParalelo:

    @staticmethod
    def _paralelo(*dias):
        horarios = [SimpleNamespace(dia_semana=d) for d in dias]
        return SimpleNamespace(horarios=SimpleNamespace(all=lambda: horarios))

    def test_encuentra_el_horario_del_dia_con_tilde(self):
        paralelo = self._paralelo("Lunes", "Miércoles")
        assert _horario(paralelo, date(2026, 10, 21)).dia_semana == "Miércoles"  # miércoles

    def test_encuentra_el_horario_del_sabado(self):
        paralelo = self._paralelo("Sábado")
        assert _horario(paralelo, date(2026, 10, 24)).dia_semana == "Sábado"

    def test_dia_sin_horario_devuelve_none(self):
        paralelo = self._paralelo("Lunes", "Miércoles")
        assert _horario(paralelo, date(2026, 10, 22)) is None  # jueves


# PRUEBAS UNITARIAS: resumen_asistencia

class TestResumenAsistencia:

    def test_cuenta_presentes_ausentes_y_tardanzas(self, orm):
        orm(4, [
            {"estudiante_id": 1, "estado": "presente", "n": 2},
            {"estudiante_id": 1, "estado": "tardanza", "n": 1},
            {"estudiante_id": 1, "estado": "ausente", "n": 1},
        ])
        _, r = resumen_asistencia(object(), [1])
        assert (r[1]["presentes"], r[1]["tardanzas"], r[1]["ausentes"]) == (2, 1, 1)

    def test_tardanza_cuenta_como_asistencia(self, orm):
        orm(4, [
            {"estudiante_id": 1, "estado": "presente", "n": 2},
            {"estudiante_id": 1, "estado": "tardanza", "n": 1},
            {"estudiante_id": 1, "estado": "ausente", "n": 1},
        ])
        _, r = resumen_asistencia(object(), [1])
        assert r[1]["asistidas"] == 3
        assert r[1]["pct"] == 75

    def test_justo_en_el_umbral_no_esta_en_riesgo(self, orm):
        orm(4, [{"estudiante_id": 1, "estado": "presente", "n": 3}])
        _, r = resumen_asistencia(object(), [1])
        assert r[1]["pct"] == 75 and r[1]["en_riesgo"] is False

    def test_bajo_el_umbral_esta_en_riesgo(self, orm):
        orm(4, [{"estudiante_id": 1, "estado": "presente", "n": 2}])
        _, r = resumen_asistencia(object(), [1])
        assert r[1]["pct"] == 50 and r[1]["en_riesgo"] is True

    def test_sin_sesiones_el_porcentaje_es_none(self, orm):
        orm(0, [])
        total, r = resumen_asistencia(object(), [1])
        assert total == 0
        assert r[1]["pct"] is None and r[1]["en_riesgo"] is False

    def test_estudiante_sin_registros_tiene_cero_por_ciento(self, orm):
        orm(3, [])
        _, r = resumen_asistencia(object(), [1])
        assert r[1]["pct"] == 0 and r[1]["en_riesgo"] is True

    def test_el_porcentaje_se_redondea(self, orm):
        orm(3, [{"estudiante_id": 1, "estado": "presente", "n": 2}])
        _, r = resumen_asistencia(object(), [1])
        assert r[1]["pct"] == 67

    def test_ignora_estudiantes_y_estados_desconocidos(self, orm):
        orm(2, [
            {"estudiante_id": 99, "estado": "presente", "n": 2},  # no está en la lista
            {"estudiante_id": 1, "estado": "justificado", "n": 1},  # estado inválido
        ])
        _, r = resumen_asistencia(object(), [1])
        assert list(r) == [1]
        assert r[1]["presentes"] == 0 and r[1]["ausentes"] == 0

    def test_tardanza_no_cuenta_si_la_regla_esta_desactivada(self, orm, monkeypatch):
        monkeypatch.setattr(services, "TARDANZA_CUENTA_COMO_ASISTENCIA", False)
        orm(4, [
            {"estudiante_id": 1, "estado": "presente", "n": 2},
            {"estudiante_id": 1, "estado": "tardanza", "n": 1},
        ])
        _, r = resumen_asistencia(object(), [1])
        assert r[1]["asistidas"] == 2 and r[1]["pct"] == 50

    def test_aplica_el_filtro_de_fechas(self, orm):
        consulta = orm(0, [])
        desde, hasta = date(2026, 10, 1), date(2026, 10, 31)
        resumen_asistencia(object(), [1], desde, hasta)
        consulta.filter.assert_any_call(sesion__fecha__gte=desde)
        consulta.filter.assert_any_call(sesion__fecha__lte=hasta)
