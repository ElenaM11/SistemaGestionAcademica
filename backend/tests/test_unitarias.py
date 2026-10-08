import pytest
from usuarios.views import generar_password, _validar_password_segura, generar_codigo_estudiante, correo_desde_codigo

# PRUEBAS UNITARIAS: generar_password
class TestGenerarPassword:

    def test_longitud_correcta(self):
        """La contraseña debe tener 10 caracteres."""
        pwd = generar_password()
        assert len(pwd) == 10

    def test_contiene_mayuscula(self):
        """Debe contener al menos una mayúscula."""
        pwd = generar_password()
        assert any(c.isupper() for c in pwd)

    def test_contiene_minuscula(self):
        """Debe contener al menos una minúscula."""
        pwd = generar_password()
        assert any(c.islower() for c in pwd)

    def test_contiene_numero(self):
        """Debe contener al menos un número."""
        pwd = generar_password()
        assert any(c.isdigit() for c in pwd)

    def test_contiene_simbolo(self):
        """Debe contener al menos un símbolo."""
        pwd = generar_password()
        assert any(c in '$#@%*!?' for c in pwd)

    def test_sin_caracteres_ambiguos(self):
        """No debe contener caracteres ambiguos (0, O, 1, l, I)."""
        pwd = generar_password()
        for c in '0O1lI':
            assert c not in pwd


# PRUEBAS UNITARIAS: _validar_password_segura

class TestValidarPasswordSegura:

    def test_password_muy_corta(self):
        """Contraseña de menos de 8 caracteres es rechazada."""
        ok, msg = _validar_password_segura('Ab1!')
        assert ok is False
        assert '8 caracteres' in msg

    def test_sin_mayuscula(self):
        """Sin mayúscula es rechazada."""
        ok, msg = _validar_password_segura('miclave2026!')
        assert ok is False
        assert 'mayúscula' in msg

    def test_sin_minuscula(self):
        """Sin minúscula es rechazada."""
        ok, msg = _validar_password_segura('MICLAVE2026!')
        assert ok is False
        assert 'minúscula' in msg

    def test_sin_numero(self):
        """Sin número es rechazada."""
        ok, msg = _validar_password_segura('MiClave!!!')
        assert ok is False
        assert 'número' in msg

    def test_sin_simbolo(self):
        """Sin símbolo es rechazada."""
        ok, msg = _validar_password_segura('MiClave2026')
        assert ok is False
        assert 'símbolo' in msg

    def test_password_comun(self):
        """Contraseña común es rechazada."""
        ok, msg = _validar_password_segura('password')
        assert ok is False
        assert 'común' in msg

    def test_password_valida(self):
        """Contraseña válida es aceptada."""
        ok, msg = _validar_password_segura('MiClave2026!')
        assert ok is True
        assert msg == ''


# PRUEBAS UNITARIAS: generar_codigo_estudiante

class TestGenerarCodigoEstudiante:

    @pytest.mark.django_db
    def test_codigo_primero(self):
        """El primer código debe ser QMM001."""
        codigo = generar_codigo_estudiante('Mariela', 'Quispe', 'Mamani')
        assert codigo == 'QMM001'

    @pytest.mark.django_db
    def test_codigo_sin_datos(self):
        """Sin datos debe devolver cadena vacía."""
        codigo = generar_codigo_estudiante('', '', '')
        assert codigo == ''


# PRUEBAS UNITARIAS: correo_desde_codigo

class TestCorreoDesdeCodigo:

    def test_correo_correcto(self):
        """Convierte QMM001 en correo."""
        correo = correo_desde_codigo('QMM001')
        assert correo == 'qmm001@davinci.edu.bo'

    def test_correo_vacio(self):
        """Código vacío devuelve cadena vacía."""
        correo = correo_desde_codigo('')
        assert correo == ''