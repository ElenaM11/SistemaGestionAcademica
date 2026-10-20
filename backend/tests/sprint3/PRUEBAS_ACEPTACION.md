# Pruebas de aceptación manuales — Sprint 3, Desarrollador B

Ejecutar en navegador con cuentas de prueba y datos del mismo paralelo. No usar cuentas o datos reales de estudiantes en capturas compartidas.

| Historia | Flujo manual | Resultado esperado |
|---|---|---|
| HU-10 | Iniciar sesión como estudiante, abrir un curso y consultar Materiales. | Aparecen título, tipo, descripción, fecha y acceso de cada material de sus paralelos. No aparecen materiales de cursos ajenos. |
| HU-12 | Abrir Tareas y calificaciones con actividades pendientes, entregadas y vencidas. | Cada tarea muestra su fecha límite y estado; las acciones disponibles dependen del estado. El mockup también pide indicadores con conteos por estado. |
| HU-13 | Entregar una respuesta de texto y un archivo; intentar repetir la entrega y probar un plazo vencido permitido y otro no permitido. | Se registra una sola entrega, se conserva el archivo, se marca si fue tardía y se rechaza la segunda entrega o una entrega tardía no permitida. |
| HU-16 | Consultar Tareas y calificaciones con notas y observaciones existentes. | Se muestran promedio, cantidad de actividades calificadas, nota y observación, solo para el estudiante autenticado. |
| HU-19 | Abrir la opción Asistencia de un curso con asistencias presentes y ausentes. | Se muestra el porcentaje, conteos e historial con fecha, tema y estado; solo datos propios. |
| HU-20 | Abrir Mi progreso en un curso con notas, entregas y asistencias. | Los indicadores integran esos tres datos para el curso. El mockup describe también barras de avance. |
| HU-21 | Iniciar sesión como docente, abrir su progreso y luego probar un paralelo asignado a otro docente. | Se muestra el progreso de sus estudiantes y se deniega el paralelo ajeno. El mockup pide identificar a quienes necesitan apoyo. |
| HU-22 | Iniciar sesión como administrador, consultar el resumen, filtrar por curso y buscar por nombre/correo/código de estudiante. | El resumen general mantiene indicadores y agregados por curso; los filtros muestran el curso o los resultados coincidentes. |

**Estado:** las pruebas automatizadas se ejecutan con pytest. Estas pruebas de aceptación requieren navegador y datos de prueba; registrar aquí la fecha y el resultado de cada ejecución antes de declarar aceptación manual.
