from types import SimpleNamespace
import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from cursos.models import Paralelo
from materiales.models import Material
from materiales.views import MAX_MB, _campos, _chip, _validar_archivo

def _archivo_falso(nombre, tamano):
    """Archivo simulado: evita crear un archivo real de varios MB."""
    return SimpleNamespace(name=nombre, size=tamano)

# PRUEBAS UNITARIAS: _validar_archivo
class TestValidarArchivo:

    def test_pdf_valido_es_aceptado(self):
        """Un PDF pequeño no lanza error."""
        _validar_archivo(SimpleUploadedFile("guia.pdf", b"contenido"))

    def test_extension_en_mayusculas_es_aceptada(self):
        """La extensión se compara sin distinguir mayúsculas (.PDF)."""
        _validar_archivo(SimpleUploadedFile("GUIA.PDF", b"contenido"))

    def test_extension_no_permitida_es_rechazada(self):
        """Un .exe es rechazado con error de validación."""
        with pytest.raises(ValidationError) as e:
            _validar_archivo(SimpleUploadedFile("virus.exe", b"x"))
        assert "no permitido" in str(e.value)

    def test_archivo_sin_extension_es_rechazado(self):
        """Un archivo sin extensión es rechazado."""
        with pytest.raises(ValidationError):
            _validar_archivo(SimpleUploadedFile("archivo", b"x"))

    def test_archivo_justo_en_el_limite_es_aceptado(self):
        """Un archivo de exactamente 20 MB es aceptado."""
        _validar_archivo(_archivo_falso("a.pdf", MAX_MB * 1024 * 1024))

    def test_archivo_sobre_el_limite_es_rechazado(self):
        """Un archivo de 20 MB + 1 byte es rechazado."""
        with pytest.raises(ValidationError) as e:
            _validar_archivo(_archivo_falso("a.pdf", MAX_MB * 1024 * 1024 + 1))
        assert "20 MB" in str(e.value)


# PRUEBAS UNITARIAS: _chip (etiqueta e icono del material)

class TestChipMaterial:

    @staticmethod
    def _material(nombre_archivo=None, tipo=None):
        archivo = SimpleNamespace(name=nombre_archivo) if nombre_archivo else None
        return SimpleNamespace(archivo=archivo, tipo=tipo)

    def test_pdf(self):
        assert _chip(self._material("a.pdf")) == ("PDF", "pdf")

    def test_documento_word(self):
        assert _chip(self._material("a.docx")) == ("DOC", "pdf")

    def test_audio_mp3(self):
        assert _chip(self._material("a.mp3")) == ("MP3", "mp3")

    def test_video_mp4(self):
        assert _chip(self._material("a.mp4")) == ("VID", "url")

    def test_imagen_png(self):
        assert _chip(self._material("a.png")) == ("IMG", "url")

    def test_enlace_usa_el_tipo_elegido(self):
        """Sin archivo, la etiqueta sale del tipo (video)."""
        assert _chip(self._material(tipo="video")) == ("VID", "url")

    def test_enlace_sin_tipo_es_url(self):
        """Sin archivo ni tipo, la etiqueta por defecto es URL."""
        assert _chip(self._material()) == ("URL", "url")


# PRUEBAS UNITARIAS: _campos (lectura del formulario)

class TestCamposMaterial:

    def test_limpia_espacios_en_titulo_y_descripcion(self):
        request = RequestFactory().post("/", {
            "titulo": "  Unidad 1  ", "descripcion": "  Resumen  ",
            "tipo": "pdf", "enlace": " https://ejemplo.com ",
        })
        campos = _campos(request)
        assert campos["titulo"] == "Unidad 1"
        assert campos["descripcion"] == "Resumen"
        assert campos["url"] == "https://ejemplo.com"

    def test_campos_vacios_se_convierten_en_none(self):
        request = RequestFactory().post("/", {
            "titulo": "Unidad 1", "descripcion": "  ", "tipo": "", "enlace": "",
        })
        campos = _campos(request)
        assert campos["descripcion"] is None
        assert campos["tipo"] is None
        assert campos["url"] is None


# PRUEBAS UNITARIAS: Material.clean

class TestMaterialClean:

    def test_sin_archivo_ni_enlace_falla(self):
        with pytest.raises(ValidationError) as e:
            Material(titulo="Unidad 1").clean()
        assert "archivo o indicar un enlace" in str(e.value)

    def test_con_enlace_es_valido(self):
        Material(titulo="Unidad 1", url="https://ejemplo.com").clean()

    def test_docente_no_asignado_al_paralelo_falla(self):
        """RNF-08: el docente debe ser el del paralelo."""
        paralelo = Paralelo(pk=1, docente_id=5)
        material = Material(paralelo=paralelo, docente_id=9, titulo="U1", url="https://ejemplo.com")
        with pytest.raises(ValidationError) as e:
            material.clean()
        assert "no está asignado" in str(e.value)

    def test_docente_asignado_al_paralelo_es_valido(self):
        paralelo = Paralelo(pk=1, docente_id=5)
        Material(paralelo=paralelo, docente_id=5, titulo="U1", url="https://ejemplo.com").clean()
