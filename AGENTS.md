# AGENTS.md

## Lectura obligatoria

Antes de actuar en este proyecto, cualquier agente, IA, CLI o automatizacion debe leer en este orden:

1. `README.md`
2. `ROADMAP.md`
3. `AGENTS.md`
4. `PROJECT_PROTOCOL.md` cuando la tarea afecte comportamiento dentro de proyectos o integraciones reales
5. Los archivos especificos del area que vaya a modificar

No se debe asumir que el chat actual sustituye a estos documentos.

## Regla de runtime

July requiere Python `3.11` o superior.

En Windows es valido tener varias versiones de Python instaladas a la vez. Si `python` apunta a `3.10` u otra version no compatible, el agente debe usar `py -3.11` o cualquier `3.11+` disponible en ese equipo.

Cuando el repo tenga `.venv`, el agente debe preferir `.\scripts\july.ps1 ...` o `.\.venv\Scripts\python.exe -m july ...` frente a `python -m july`.
Para iniciar MCP en Windows, debe preferir `.\scripts\mcp.ps1` o `.\start-july-mcp.cmd`.

## Regla de actualizacion documental

Si un cambio modifica cualquiera de estos puntos, el mismo trabajo debe actualizar `README.md` y `ROADMAP.md`:

- comandos;
- arquitectura;
- flujo MCP;
- proveedor LLM documentado;
- prioridades;
- vision o enfoque del proyecto;
- estado de implementacion.

## Regla de trazabilidad

Cuando una idea, propuesta o enfoque venga de un modelo externo, debe reflejarse en `ROADMAP.md` en la seccion adecuada. No debe quedarse solo en una conversacion temporal.

Ademas, toda contribucion de un modelo debe registrarse usando `model-contribution` o la herramienta MCP `save_model_contribution`. Esto aplica a aportes de:

- Claude
- Codex
- Z.ai
- GPT
- Perplexity
- Genspark
- cualquier otra IA o agente

## Regla de reconciliacion

No se debe sobrescribir la vision de July con propuestas externas tipo Engram, Genspark, Gentle AI u otras sin reconciliarlas antes con el enfoque principal del proyecto:

- July es un orquestador amplio;
- July tiene inbox universal;
- July combina memoria, tareas, contexto, sesiones, topic keys y comparacion entre modelos;
- July tiene recuperacion proactiva y sugerencias de referencias externas;
- July debe comportarse como una capa conversacional orientada a proyectos, no como una UX basada en comandos para el usuario final;
- July no arranca como una replica literal de Engram ni como un stack de equipo.

## Regla de consistencia

`README.md`, `ROADMAP.md` y el estado real del codigo deben mantenerse alineados.

Si hay conflicto entre:

- una propuesta en chat;
- un documento externo;
- el estado real del codigo;

se debe priorizar:

1. estado real del codigo;
2. `README.md` + `ROADMAP.md`;
3. propuesta externa aun no integrada.

## Regla de sesion

Cualquier agente que trabaje sobre July debe:

1. Al empezar: usar `session-start` o la herramienta MCP `session_start` para registrar la sesion.
2. Al terminar: usar `session-summary` con un resumen de lo hecho, descubrimientos y siguientes pasos.
3. Al cerrar: usar `session-end`.

Esto no es opcional. Sin ello, la siguiente sesion empieza ciega.

## Regla de comportamiento en proyectos

Cuando July este conectado a otro proyecto o repo, el agente debe comportarse asi:

El contrato operativo exacto esta en `PROJECT_PROTOCOL.md`.

Resumen obligatorio:

1. Detectar el proyecto actual y consultar primero `project-context` y `session-context`.
2. Distinguir entre proyecto nuevo y proyecto conocido segun la utilidad real del contexto previo, no solo por la existencia de un item aislado.
3. Si el proyecto es nuevo, proponer onboarding o revision inicial y dejar una primera foto util del repo.
4. Si el proyecto es conocido, recuperar contexto antes de pedir al usuario que repita informacion y evitar rehacer onboarding si no hace falta.
5. Durante la iteracion, registrar errores resueltos, decisiones, mejoras de flujo y hallazgos reutilizables.
6. Si un dato es claramente util y durable, puede capturarlo directamente; si hay ambiguedad, debe preguntar al usuario si quiere guardarlo.
7. Al cerrar, debe dejar claro que se hizo, que queda pendiente y que conviene reutilizar en futuras iteraciones.

La finalidad es evitar regresiones de contexto:

- saber en que punto esta el proyecto;
- saber que se ha hecho y que falta;
- no repetir en futuras iteraciones el mismo analisis o las mismas soluciones.

## Regla de UX

CLI y MCP son infraestructura. El agente no debe empujar al usuario a memorizar comandos salvo que este depurando July o trabajando explicitamente sobre la herramienta.

La experiencia preferida es conversacional:

- "Estoy en un proyecto nuevo, quieres que lo revise?"
- "Este proyecto ya tiene contexto en July, te resumo por donde va?"
- "He encontrado una decision reutilizable, quieres que la guarde?"
- "Esto puede servir en otra sesion, quieres que quede registrado?"

## Regla de topic keys

Cuando un agente detecte que un tema se repite entre sesiones o proyectos (por ejemplo "autenticacion JWT", "integracion MCP", "estructura de proyecto"), debe:

1. Crear un topic key si no existe con `topic-create`.
2. Enlazar los items relevantes con `topic-link`.

Esto permite que July agrupe conocimiento disperso bajo un mismo hilo.

## Regla de referencias externas

Cuando July sugiera consultar una referencia externa (skills.sh, agents.md), el agente debe:

1. Considerar la sugerencia.
2. Si la referencia es util, puede usar `fetch-reference` para obtener contenido.
3. Crear su propia implementacion basada en la referencia, no copiar literalmente.
4. Si la referencia cambia arquitectura, prioridades, flujo MCP o vision, reflejar ese aprendizaje en `ROADMAP.md` y mantener `README.md` alineado.

## Herramientas MCP disponibles

| Herramienta | Funcion |
|---|---|
| `capture_input` | Capturar input libre con recall proactivo, fetch URLs y trazabilidad |
| `search_context` | Buscar en inbox, tareas y memoria |
| `project_context` | Contexto por proyecto |
| `list_inbox` | Listar inbox |
| `clarify_input` | Resolver aclaraciones |
| `promote_memory` | Promover memoria candidata a estable |
| `session_start` | Iniciar sesion de trabajo |
| `session_summary` | Guardar resumen de sesion |
| `session_end` | Cerrar sesion |
| `session_context` | Recuperar contexto de sesiones recientes |
| `topic_create` | Crear tema estable |
| `topic_link` | Enlazar item a tema |
| `topic_context` | Ver todo lo vinculado a un tema |
| `save_model_contribution` | Registrar contribucion de un modelo IA |
| `fetch_url` | Extraer metadatos de una URL |
| `fetch_reference` | Consultar fuente de referencia externa |
| `proactive_recall` | Buscar proactivamente en memoria |
| `project_entry` | Detectar si un proyecto es nuevo, parcial o conocido y proponer el siguiente paso |
| `project_onboard` | Hacer onboarding read-only del repo y guardar una primera foto util en July |
| `conversation_checkpoint` | Clasificar hallazgos durante la iteracion como guardables, ambiguos o ignorables; si devuelve `ask_user`, expone `pending_confirmation` para confirmar y persistir |
| `project_action` | Ejecutar la accion elegida tras `project_entry` (`analyze_now`, `resume_context`, `refresh_context`, `continue_without_context`, `close_stale_and_continue`) |
