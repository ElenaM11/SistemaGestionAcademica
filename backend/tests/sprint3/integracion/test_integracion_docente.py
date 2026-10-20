from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
import pytest
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from actividades.models import Actividad, Entrega
from asistencia.models import Asistencia, SesionClase
from cursos.models import Curso, EstudianteParalelo, Idioma, Nivel, Paralelo, Turno
from materiales.models import Material
from notificaciones.models import Notificacion
from rol.models import Rol
from usuarios.models import Docente, Estudiante, Usuario


# DATOS DE APOYO

def _usuario(rol, correo, nombres):
    """Crea un Usuario con el rol indicado (el hash no se usa: la sesión se arma a mano)."""
    rol_obj, _ = Rol.objects.get_or_create(nombre=rol)
    return Usuario.objects.create(
        nombres=nombres, ap_pat="Prueba", correo=correo, password_hash="no-usado", rol=rol_obj,
    )


def _iniciar_sesion(client, usuario):
    sesion = client.session
    sesion["usuario_id"] = usuario.pk
    sesion["usuario_rol"] = usuario.rol.nombre
    sesion.save()


def _fecha(dias):
    #Fecha en formato AAAA-MM-DD, `dias` días a partir de hoy
    return (timezone.localdate() + timedelta(days=dias)).strftime("%Y-%m-%d")


def _mensajes(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


@pytest.fixture(autouse=True)
def _media_temporal(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture
def e(db, client):
    idioma = Idioma.objects.create(nombre="Inglés", codigo="ING")
    nivel = Nivel.objects.create(codigo="A1")
    curso = Curso.objects.create(idioma=idioma, nivel=nivel, nombre="Inglés A1")
    turno = Turno.objects.create(nombre="Tarde")

    docente = Docente.objects.create(usuario=_usuario("Docente", "laura@davinci.edu.bo", "Laura"))
    otro = Docente.objects.create(usuario=_usuario("Docente", "pedro@davinci.edu.bo", "Pedro"))
    paralelo = Paralelo.objects.create(codigo="ING-TAR-2026-A", curso=curso, turno=turno, docente=docente)
    paralelo_otro = Paralelo.objects.create(codigo="ING-TAR-2026-B", curso=curso, turno=turno, docente=otro)

    estudiantes, inscripciones = [], []
    for i in range(1, 4):
        est = Estudiante.objects.create(
            usuario=_usuario("Estudiante", f"est{i}@davinci.edu.bo", f"Estudiante{i}"),
            codigo_estudiante=f"EST{i:03d}",
        )
        estudiantes.append(est)
        inscripciones.append(EstudianteParalelo.objects.create(estudiante=est, paralelo=paralelo))

    _iniciar_sesion(client, docente.usuario)
    return SimpleNamespace(
        client=client, curso=curso, docente=docente, otro=otro, paralelo=paralelo,
        paralelo_otro=paralelo_otro, estudiantes=estudiantes, inscripciones=inscripciones,
    )


def _url(nombre, e, **extra):
    return reverse(nombre, kwargs={"curso_id": e.curso.pk, **extra})


def _material(e, **campos):
    datos = {"paralelo": e.paralelo, "docente": e.docente, "titulo": "Guía 1", "tipo": "enlace",
             "url": "https://ejemplo.com/guia"}
    datos.update(campos)
    return Material.objects.create(**datos)


def _actividad(e, **campos):
    datos = {"paralelo": e.paralelo, "docente": e.docente, "titulo": "Tarea 1", "tipo": "escrita",
             "fecha_limite": timezone.now() + timedelta(days=5), "puntaje_maximo": Decimal("100")}
    datos.update(campos)
    return Actividad.objects.create(**datos)


# PRUEBAS DE INTEGRACIÓN: docente_materiales (HU-09)

class TestMateriales:

    def test_publicar_material_con_enlace(self, e):
        """Caso 1: publicar con enlace crea el material y notifica a los inscritos."""
        antes = Notificacion.objects.count()
        r = e.client.post(_url("docente_materiales", e), {
            "titulo": "Unidad 1", "tipo": "enlace", "enlace": "https://ejemplo.com/u1",
            "descripcion": "Lectura inicial",
        })
        assert r.status_code == 302
        material = Material.objects.get()
        assert (material.titulo, material.url) == ("Unidad 1", "https://ejemplo.com/u1")
        assert material.paralelo == e.paralelo and material.docente == e.docente
        assert Notificacion.objects.count() - antes == 3
        assert any("Material publicado" in m for m in _mensajes(r))

    def test_publicar_material_con_archivo_pdf(self, e):
        """Caso 2: publicar con un PDF guarda el archivo en el almacenamiento."""
        pdf = SimpleUploadedFile("guia.pdf", b"%PDF-1.4 contenido", content_type="application/pdf")
        r = e.client.post(_url("docente_materiales", e), {"titulo": "Guía PDF", "tipo": "pdf", "archivo": pdf})
        assert r.status_code == 302
        material = Material.objects.get()
        assert material.archivo.name.startswith("materiales/")
        assert material.archivo.storage.exists(material.archivo.name)

    def test_publicar_sin_archivo_ni_enlace(self, e):
        """Caso 3: sin archivo ni enlace vuelve al formulario con error y no crea nada."""
        r = e.client.post(_url("docente_materiales", e), {"titulo": "Vacío", "tipo": "pdf"})
        assert r.status_code == 200
        assert "archivo o indicar un enlace" in r.context["error"]
        assert Material.objects.count() == 0

    def test_publicar_archivo_con_extension_no_permitida(self, e):
        """Caso 4: un .exe es rechazado y no se crea el material."""
        exe = SimpleUploadedFile("virus.exe", b"MZ")
        r = e.client.post(_url("docente_materiales", e), {"titulo": "Malo", "tipo": "pdf", "archivo": exe})
        assert r.status_code == 200
        assert "no permitido" in r.context["error"]
        assert Material.objects.count() == 0

    def test_editar_material_reemplaza_el_archivo_anterior(self, e):
        """Caso 5: al subir un archivo nuevo se actualiza el registro y se borra el anterior."""
        material = _material(e, tipo="pdf", url=None, archivo=SimpleUploadedFile("guia.pdf", b"v1"))
        almacenamiento, viejo = material.archivo.storage, material.archivo.name
        r = e.client.post(_url("docente_material_editar", e, pk=material.pk), {
            "titulo": "Guía 2", "tipo": "pdf", "archivo": SimpleUploadedFile("guia_v2.pdf", b"v2"),
        })
        assert r.status_code == 302
        material.refresh_from_db()
        assert material.titulo == "Guía 2"
        assert not almacenamiento.exists(viejo)
        assert almacenamiento.exists(material.archivo.name)

    def test_eliminar_material_borra_registro_y_archivo(self, e):
        """Caso 6: eliminar quita el registro de la BD y el archivo del almacenamiento."""
        material = _material(e, tipo="pdf", url=None, archivo=SimpleUploadedFile("guia.pdf", b"v1"))
        almacenamiento, nombre = material.archivo.storage, material.archivo.name
        r = e.client.post(_url("docente_material_eliminar", e, pk=material.pk))
        assert r.status_code == 302
        assert not Material.objects.filter(pk=material.pk).exists()
        assert not almacenamiento.exists(nombre)

# PRUEBAS DE INTEGRACIÓN: docente_actividades

class TestActividades:

    def test_crear_actividad_valida(self, e):
        """Caso 7: crea la actividad con sus opciones y notifica a los inscritos."""
        antes = Notificacion.objects.count()
        r = e.client.post(_url("docente_actividades", e), {
            "titulo": "Tarea 1", "instrucciones": "Resolver la guía", "tipo": "escrita",
            "fecha_limite": _fecha(10), "puntaje_maximo": "50", "asistente_ia": "on",
        })
        assert r.status_code == 302
        a = Actividad.objects.get()
        assert a.paralelo == e.paralelo and a.docente == e.docente
        assert a.puntaje_maximo == Decimal("50")
        assert a.usa_ia is True and a.permite_entrega_tardia is False
        assert Notificacion.objects.count() - antes == 3
        assert any("Actividad publicada" in m for m in _mensajes(r))

    def test_crear_actividad_con_fecha_pasada(self, e):
        """Caso 8: una fecha límite en el pasado es rechazada y no se crea la actividad."""
        r = e.client.post(_url("docente_actividades", e), {
            "titulo": "Tarea vieja", "fecha_limite": "2020-01-01", "puntaje_maximo": "100",
        })
        assert r.status_code == 200
        assert "pasado" in r.context["error"]
        assert Actividad.objects.count() == 0

    def test_editar_actividad_vigente(self, e):
        """Caso 9: una actividad vigente se puede modificar."""
        a = _actividad(e)
        r = e.client.post(_url("docente_actividad_editar", e, pk=a.pk), {
            "titulo": "Tarea 1 corregida", "tipo": "oral", "fecha_limite": _fecha(15), "puntaje_maximo": "80",
        })
        assert r.status_code == 302
        a.refresh_from_db()
        assert (a.titulo, a.tipo, a.puntaje_maximo) == ("Tarea 1 corregida", "oral", Decimal("80"))

    def test_eliminar_actividad_con_entregas_es_rechazado(self, e):
        """Caso 10: no se elimina una actividad que ya tiene entregas."""
        a = _actividad(e)
        Entrega.objects.create(actividad=a, estudiante=e.estudiantes[0], contenido_texto="Mi respuesta")
        r = e.client.post(_url("docente_actividad_eliminar", e, pk=a.pk))
        assert r.status_code == 200
        assert "ya tiene entregas" in r.context["error"]
        assert Actividad.objects.filter(pk=a.pk).exists()

    def test_eliminar_actividad_sin_entregas(self, e):
        """Caso 11: una actividad sin entregas se elimina."""
        a = _actividad(e)
        r = e.client.post(_url("docente_actividad_eliminar", e, pk=a.pk))
        assert r.status_code == 302
        assert not Actividad.objects.filter(pk=a.pk).exists()


# PRUEBAS DE INTEGRACIÓN: docente_entregas 

class TestEntregasYCalificaciones:

    def test_listado_incluye_a_quienes_no_entregaron(self, e):
        """Caso 12: el listado muestra a todos los inscritos con su estado y los totales."""
        a = _actividad(e)
        e1, e2, e3 = e.estudiantes
        Entrega.objects.create(actividad=a, estudiante=e1, contenido_texto="A tiempo")
        Entrega.objects.create(actividad=a, estudiante=e2, contenido_texto="Tarde", es_tardia=True)
        r = e.client.get(_url("docente_entregas", e, pk=a.pk))
        assert r.status_code == 200
        estados = {f["estudiante"].pk: f["estado"] for f in r.context["entregas"]}
        assert estados == {e1.pk: "entregada", e2.pk: "tardia", e3.pk: "sin_entregar"}
        assert r.context["total_entregadas"] == 2
        assert r.context["total_sin_entregar"] == 1

    def test_calificar_entrega_valida(self, e):
        """Caso 13: guarda la nota, las observaciones y el docente calificador."""
        a = _actividad(e)
        entrega = Entrega.objects.create(actividad=a, estudiante=e.estudiantes[0], contenido_texto="Resp")
        r = e.client.post(_url("docente_entregas", e, pk=a.pk), {
            "estudiante": e.estudiantes[0].pk, "nota": "85", "observaciones": "Buen trabajo",
        })
        assert r.status_code == 302 and f"estudiante={e.estudiantes[0].pk}" in r.url
        entrega.refresh_from_db()
        assert entrega.calificacion == Decimal("85")
        assert entrega.observaciones == "Buen trabajo"
        assert entrega.estado == Entrega.Estado.CALIFICADA
        assert entrega.docente_calificador_id == e.docente.pk
        assert entrega.fecha_calificacion is not None

    def test_calificar_con_nota_sobre_el_maximo(self, e):
        """Caso 14: una nota mayor al puntaje máximo es rechazada y no se guarda."""
        a = _actividad(e, puntaje_maximo=Decimal("100"))
        entrega = Entrega.objects.create(actividad=a, estudiante=e.estudiantes[0], contenido_texto="Resp")
        r = e.client.post(_url("docente_entregas", e, pk=a.pk), {
            "estudiante": e.estudiantes[0].pk, "nota": "101",
        })
        assert r.status_code == 200
        assert "entre 0 y 100" in r.context["error"]
        entrega.refresh_from_db()
        assert entrega.calificacion is None and entrega.estado == Entrega.Estado.ENTREGADA

    def test_modificar_una_calificacion_existente(self, e):
        """Caso 15: calificar de nuevo reemplaza la nota y las observaciones anteriores."""
        a = _actividad(e)
        entrega = Entrega.objects.create(actividad=a, estudiante=e.estudiantes[0], contenido_texto="Resp")
        url = _url("docente_entregas", e, pk=a.pk)
        e.client.post(url, {"estudiante": e.estudiantes[0].pk, "nota": "60", "observaciones": "Regular"})
        e.client.post(url, {"estudiante": e.estudiantes[0].pk, "nota": "90", "observaciones": "Corregida"})
        entrega.refresh_from_db()
        assert entrega.calificacion == Decimal("90")
        assert entrega.observaciones == "Corregida"
        assert Entrega.objects.count() == 1

    def test_calificar_a_un_estudiante_que_no_entrego(self, e):
        """Caso 16: no se puede calificar a quien no entregó la actividad."""
        a = _actividad(e)
        r = e.client.post(_url("docente_entregas", e, pk=a.pk), {"estudiante": e.estudiantes[2].pk, "nota": "70"})
        assert r.status_code == 200
        assert "aún no entregó" in r.context["error"]
        assert Entrega.objects.count() == 0


# PRUEBAS DE INTEGRACIÓN: docente_asistencia y docente_asistencia_historial 

class TestAsistencia:
    def test_registrar_asistencia_en_lote(self, e):
        hoy = timezone.localdate()
        datos = {"fecha": hoy.strftime("%Y-%m-%d")}
        for ins, estado in zip(e.inscripciones, ["presente", "ausente", "tardanza"]):
            datos[f"estado_{ins.pk}"] = estado
        datos[f"obs_{e.inscripciones[1].pk}"] = "Avisó que estaba enfermo"
        r = e.client.post(_url("docente_asistencia", e), datos)
        assert r.status_code == 302 and "fecha=" in r.url
        sesion = SesionClase.objects.get()
        assert (sesion.paralelo, sesion.fecha) == (e.paralelo, hoy)
        registros = {a.estudiante_id: a for a in Asistencia.objects.filter(sesion=sesion)}
        assert len(registros) == 3
        assert [registros[s.pk].estado for s in e.estudiantes] == ["presente", "ausente", "tardanza"]
        assert registros[e.estudiantes[1].pk].observacion == "Avisó que estaba enfermo"
        assert all(a.registrado_por_id == e.docente.pk for a in registros.values())

    def test_modificar_asistencia_ya_registrada(self, e):
        fecha = timezone.localdate().strftime("%Y-%m-%d")
        url = _url("docente_asistencia", e)
        e.client.post(url, {"fecha": fecha, **{f"estado_{i.pk}": "presente" for i in e.inscripciones}})
        e.client.post(url, {
            "fecha": fecha, f"estado_{e.inscripciones[0].pk}": "tardanza",
            f"obs_{e.inscripciones[0].pk}": "Llegó 15 minutos tarde",
        })
        assert SesionClase.objects.count() == 1
        assert Asistencia.objects.count() == 3
        corregido = Asistencia.objects.get(estudiante=e.estudiantes[0])
        assert corregido.estado == "tardanza"
        assert corregido.observacion == "Llegó 15 minutos tarde"

    def test_no_se_registra_asistencia_de_fecha_futura(self, e):
        r = e.client.post(_url("docente_asistencia", e), {
            "fecha": _fecha(1), **{f"estado_{i.pk}": "presente" for i in e.inscripciones},
        })
        assert r.status_code == 200
        assert "fecha futura" in r.context["error"]
        assert SesionClase.objects.count() == 0 and Asistencia.objects.count() == 0

    def test_historial_calcula_porcentajes_y_riesgo(self, e):
        """Caso 20: el historial resume presentes, ausentes y porcentaje por estudiante."""
        e1, e2, e3 = e.estudiantes
        hoy = timezone.localdate()
        for dias, est1, est2 in [(1, "presente", "presente"), (2, "presente", "presente"),
                                 (3, "presente", "ausente"), (4, "ausente", "ausente")]:
            sesion = SesionClase.objects.create(paralelo=e.paralelo, fecha=hoy - timedelta(days=dias))
            Asistencia.objects.create(sesion=sesion, estudiante=e1, estado=est1)
            Asistencia.objects.create(sesion=sesion, estudiante=e2, estado=est2)
        r = e.client.get(_url("docente_asistencia_historial", e))
        assert r.status_code == 200
        resumen = {f["estudiante"].pk: f for f in r.context["resumen"]}
        assert (resumen[e1.pk]["pct"], resumen[e1.pk]["en_riesgo"]) == (75, False)
        assert (resumen[e2.pk]["pct"], resumen[e2.pk]["en_riesgo"]) == (50, True)
        assert (resumen[e3.pk]["pct"], resumen[e3.pk]["en_riesgo"]) == (0, True)
        assert r.context["faltas_acumuladas"] == 3
        assert r.context["estudiantes_riesgo"] == 2

# PRUEBAS DE INTEGRACIÓN: control de acceso

class TestControlDeAcceso:

    def test_sin_sesion_redirige_al_login(self, e):
        e.client.logout()
        r = e.client.get(_url("docente_materiales", e))
        assert r.status_code == 302 and r.url == reverse("login")

    def test_estudiante_no_accede_a_vistas_del_docente(self, e):
        e.client.logout()
        _iniciar_sesion(e.client, e.estudiantes[0].usuario)
        for nombre in ("docente_materiales", "docente_actividades", "docente_asistencia"):
            assert e.client.get(_url(nombre, e)).status_code == 403

    def test_docente_ajeno_no_modifica_recursos_de_otro_paralelo(self, e):
        material = _material(e)
        actividad = _actividad(e)
        e.client.logout()
        _iniciar_sesion(e.client, e.otro.usuario)
        r1 = e.client.post(_url("docente_material_editar", e, pk=material.pk), {
            "titulo": "Hackeado", "tipo": "enlace", "enlace": "https://malo.com",
        })
        r2 = e.client.get(_url("docente_entregas", e, pk=actividad.pk))
        assert r1.status_code == 404 and r2.status_code == 404
        material.refresh_from_db()
        assert material.titulo == "Guía 1"
