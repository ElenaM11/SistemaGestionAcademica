import itertools

from django.apps import apps

_n = itertools.count(1)


def modelo(nombre):
    for m in apps.get_models():
        if m.__name__ == nombre:
            return m
    raise LookupError(f"No encontré el modelo {nombre}")


def _crear(clase, **datos):
    campos = {f.name for f in clase._meta.get_fields()}   # ignora los campos que tu modelo no tenga
    return clase.objects.create(**{k: v for k, v in datos.items() if k in campos})


def rol(nombre):
    return modelo("Rol").objects.get_or_create(nombre=nombre)[0]


def usuario(nombre_rol="Estudiante", **extra):
    n = next(_n)
    clase = modelo("Usuario")
    datos = dict(nombres=f"Nombre{n}", ap_pat=f"Apellido{n}", ap_mat="Mat", ci=f"CI{n}", correo=f"u{n}@prueba.com",
                 telefono="70000000", rol=rol(nombre_rol), estado=True,
                 password_hash="x", password="x", contrasena="x")
    for f in clase._meta.get_fields():   # banderas tipo "debe cambiar la contraseña" apagadas
        if getattr(f, "get_internal_type", None) and f.get_internal_type() == "BooleanField" \
                and any(p in f.name for p in ("cambiar", "temporal", "forzar")):
            datos[f.name] = False
    datos.update(extra)
    return _crear(clase, **datos)


def docente(**extra):
    return _crear(modelo("Docente"), usuario=usuario("Docente", **extra), especialidad="Idiomas")


def estudiante(**extra):
    return _crear(modelo("Estudiante"), usuario=usuario("Estudiante", **extra), codigo_estudiante=f"EST{next(_n)}")


def administrador(**extra):
    return usuario("Administrador", **extra)


def curso(nombre="Inglés A1"):
    n = next(_n)
    idioma = _crear(modelo("Idioma"), nombre=f"Idioma{n}", codigo=f"I{n}")
    nivel = _crear(modelo("Nivel"), codigo=f"N{n}", nombre="Básico", orden=1)
    return _crear(modelo("Curso"), idioma=idioma, nivel=nivel, nombre=nombre)


def paralelo(docente_, curso_=None, estado="ACTIVO"):
    turno = modelo("Turno").objects.get_or_create(nombre="Mañana")[0]
    return _crear(modelo("Paralelo"), codigo=f"P{next(_n)}", curso=curso_ or curso(), turno=turno,
                  docente=docente_, estado=estado)


def inscribir(estudiante_, paralelo_, estado="ACTIVO"):
    return _crear(modelo("EstudianteParalelo"), estudiante=estudiante_, paralelo=paralelo_, estado=estado)


def iniciar_sesion(client, persona):
    """Deja la sesión iniciada como esa persona (Usuario, Docente o Estudiante)."""
    sesion = client.session
    sesion["usuario_id"] = persona.pk
    sesion.save()