# AGENTS.md

## Lectura obligatoria

Antes de actuar en este proyecto, cualquier agente, IA, CLI o automatizacion debe leer en este orden:

1. `README.md`
2. `ROADMAP.md`
3. `AGENTS.md`
4. Los archivos especificos del area que vaya a modificar

No se debe asumir que el chat actual sustituye a estos documentos.

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
4. Registrar la referencia con `save_external_reference` si aporta valor al proyecto.

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
