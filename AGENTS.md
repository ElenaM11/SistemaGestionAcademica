# Proyecto
Sistema de gestión académica para un instituto de idiomas (Da Vinci).
Backend en Python con Django y Django REST Framework, base de datos PostgreSQL en Azure.
El desarrollo sigue Scrum, organizado en 5 Sprints. Cada historia de usuario se identifica como `HU-XX`.

# Estructura del repositorio
* `backend/`: proyecto Django.
  * `config/`: configuración (`settings.py`, `urls.py`).
  * `usuarios/` y `rol/`: autenticación, usuarios y roles (Sprint 1).
  * `cursos/`: gestión académica (Sprint 2).
  * `tests/`: pruebas con pytest.
* `frontend/`: plantillas HTML (`templates/`) y estilos (`static/css/`).
* `.github/`: workflow de GitHub Actions que ejecuta las pruebas.
* `.env`: credenciales locales. Está en la raíz del repositorio y NO se sube a GitHub.

# Base de datos
La estructura de la base de datos está definida en:
`database/schema_davinci.sql`

Antes de escribir modelos, consultas o vistas:
* Revisar el esquema de la base de datos.
* No inventar tablas ni columnas.
* Verificar claves primarias y foráneas.
* Respetar los nombres de tabla y de columna del esquema (en minúsculas, usando `db_table` y `db_column` en los modelos).
* Los cambios de estructura se hacen únicamente con migraciones de Django (`makemigrations` y `migrate`). No modificar tablas a mano.

La base de datos de Azure es compartida por todo el equipo. Está prohibido ejecutar sobre ella:
* `DROP`, `TRUNCATE`, `ALTER` o `DELETE` sin `WHERE`.
* `python manage.py flush`.
* `python manage.py migrate` hacia una migración anterior.
* Cualquier comando que borre o reemplace datos.

Para pruebas automáticas, usar la base de datos temporal de pytest-django, nunca la de Azure.

# Credenciales y seguridad
* Las credenciales viven solo en el archivo `.env` y se leen desde `settings.py`.
* Nunca leer, mostrar, copiar ni escribir el contenido de `.env` en el chat, en el código o en commits.
* Nunca escribir contraseñas, hosts ni usuarios dentro del código.
* Si hace falta una variable nueva, agregarla con un valor de ejemplo en `.env.example`, no en `.env`.
* La conexión a Azure requiere SSL (`sslmode=require`).

# Entorno Python
El entorno oficial del proyecto es el entorno virtual:
`backend/venv`

* Python 3.13.
* Activar con `venv\Scripts\activate` (Windows) antes de ejecutar cualquier comando.
* Instalar dependencias con `pip install -r requirements.txt`.
* Si se agrega una librería nueva, actualizar `requirements.txt` con `pip freeze > requirements.txt`.
* Todos los comandos de Django se ejecutan desde la carpeta `backend/`.

# Roles del sistema
Los nombres de los roles, escritos exactamente así, son:
* `Administrador`
* `Docente`
* `Estudiante`

Reglas de acceso:
* Todo endpoint debe tener una clase de permisos por rol (`cursos/permissions.py`).
* El docente solo accede a los paralelos que tiene asignados.
* El estudiante solo accede a su propia información.
* El identificador del docente o del estudiante se toma de la sesión (`request.user`), nunca de un parámetro enviado por el cliente.
* Si un usuario no tiene permiso sobre un recurso, responder 403.

# Arquitectura del backend
Cada petición sigue esta cadena y cada capa tiene una sola responsabilidad:

`urls.py` → `permissions.py` → `views.py` → `serializers.py` → `services.py` → `models.py`

* `models.py`: solo definición de tablas.
* `serializers.py`: validación del formato de los datos y construcción del JSON de respuesta.
* `services.py`: reglas de negocio (cupos, cruces de horario, idioma del docente, duplicados).
* `views.py`: recibe la petición y llama a los servicios. No contiene reglas de negocio complejas.
* Las operaciones que modifican varias tablas o dependen de un cupo deben usar `transaction.atomic()` y `select_for_update()`.
* No se borran registros académicos: se desactivan cambiando `estado` o `activo`.

# Forma de trabajo del agente
Antes de modificar código:
- Trabajar siempre de manera incremental, una historia de usuario a la vez.
- No generar todo el Sprint ni toda la aplicación salvo que se solicite explícitamente.
- Generar solamente el bloque solicitado.
- Explicar brevemente el propósito del código.
- Mantener el código sencillo y educativo.
- No abstraer prematuramente en clases o funciones complejas.
- Usar el ORM de Django. No escribir SQL a mano salvo que se pida.
- No modificar código de Sprints anteriores salvo que exista un error.
- Antes de escribir código nuevo, reutilizar modelos, serializers, servicios y permisos ya existentes.
- Si falta un dato (nombre de un campo, regla de negocio), preguntar. No suponerlo.
- Las reglas de negocio y los criterios de aceptación salen de las historias de usuario del documento del proyecto (Capítulo III).

## Documentación obligatoria del código
- Cada función, clase o servicio nuevo DEBE comenzar con un comentario o docstring de una sola línea.
- El comentario debe estar escrito en español y en primera persona, y describir brevemente qué realiza.
- No sustituir este comentario por una explicación en el chat.
- No crear una función o clase nueva sin este comentario inicial.

Ejemplo:

`# Valido que el docente enseñe el idioma del curso y que sus horarios no se crucen`

## Pruebas
- Escribir las pruebas junto con cada historia de usuario, en `backend/tests/`.
- Ejecutar `pytest` desde `backend/` antes de proponer un commit.
- Cubrir al menos: el caso correcto, un permiso denegado (403) y una regla de negocio incumplida.
- No dar una historia por terminada si las pruebas fallan.

## Git
- Trabajar en la rama del Sprint (por ejemplo `sprint-2`). No hacer commits directos en `main`.
- Hacer un commit pequeño por cada historia de usuario.
- Formato del mensaje: `HU-05: asignación de docentes a paralelos`.
- Hacer commit o push solo cuando el usuario lo pida.

# Convenciones
* Modelos: clases en `PascalCase` y singular (`Paralelo`, `EstudianteParalelo`).
* Campos, variables y funciones: `snake_case` (`id_paralelo`, `cupo_maximo`).
* Tablas: nombre en minúsculas con `db_table` (`estudiante_paralelo`).
* Endpoints: en minúsculas, en español y con guiones (`/api/paralelos/`, `/api/estudiante/mis-cursos/`).
* Estados: texto en mayúsculas (`ACTIVO`, `INACTIVO`, `RETIRADO`).
* Mensajes de error al usuario: en español.
* Idioma del código: nombres de modelos y campos en español, igual que el modelo físico del proyecto.

# Comandos frecuentes
```bash
cd backend
venv\Scripts\activate
python manage.py makemigrations <app>
python manage.py migrate
python manage.py runserver
pytest
```