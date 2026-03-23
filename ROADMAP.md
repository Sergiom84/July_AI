# ROADMAP

## Estado actual implementado

Lo que ya existe hoy en el codigo:

### Nucleo original (v0.1)

- Base de datos local en SQLite.
- Inbox libre para capturar inputs sin formulario fijo.
- Clasificacion heuristica de intenciones.
- Tareas derivadas de ciertos inputs.
- Memoria candidata y memoria estable.
- Resolucion de aclaraciones con `clarify`.
- Promocion de memoria con `promote-memory`.
- Contexto por proyecto con `project-context`.
- MCP server por `stdio`.
- Proveedor LLM configurable y desacoplado.

### Bloque v0.2 (implementado)

- Protocolo de sesion completo: `session-start`, `session-summary`, `session-end`, `session-context`.
- Recuperacion de contexto entre sesiones: al iniciar trabajo, se puede consultar que paso en sesiones anteriores del mismo proyecto.
- Hilos tematicos con `topic_key`: crear temas estables, enlazar items/memorias/sesiones, consultar todo lo vinculado a un tema.
- Recuperacion proactiva: al capturar un input, July busca automaticamente en memoria y sesiones previas y sugiere reutilizar conocimiento (reuse_memory, cross_project).
- Extraccion de metadatos de URLs: titulo, descripcion, tipo de contenido. Manejo especial de YouTube (video id, canal, duracion).
- Trazabilidad de modelos: registrar contribuciones de cualquier IA, marcar como adoptadas, comparar propuestas.
- Referencias externas: July sugiere consultar skills.sh y agents.md cuando detecta inputs que se beneficiarian de una skill o un patron de agente.
- 17 herramientas MCP (antes 6).
- 27 comandos CLI (antes 11).
- 12 tablas en la base de datos (antes 6).
- Runtime oficial: Python `3.11+`. En Windows, si `python` apunta a `3.10`, hay que usar `py -3.11` o cualquier `3.11+` disponible.
- Flujo de arranque recomendado en Windows: `.\scripts\bootstrap.ps1` para crear `.venv` y `.\scripts\july.ps1` para ejecutar July con el runtime del proyecto.
- Lanzador dedicado de MCP en Windows: `.\scripts\mcp.ps1` y `.\start-july-mcp.cmd`.
- Soporte multi-entorno: scripts bash equivalentes (`scripts/july.sh`, `scripts/mcp.sh`, `start-july-mcp.sh`) para WSL, Linux y macOS.
- Documentacion de configuracion MCP multi-entorno en `MCP_SETUP.md`.

### Bloque v0.3 (implementado)

- Primera capa conversacional por proyecto: `project-entry`, `project-onboard`, `project-action`, `conversation-checkpoint`.
- `project_entry` detecta si un repo es nuevo, parcial o conocido usando contexto real del proyecto.
- `project_onboard` hace onboarding read-only del repositorio y guarda una primera foto util en la BD de July.
- `project_action` ejecuta la respuesta del wizard sin empujar al usuario a memorizar infraestructura.
- `conversation_checkpoint` permite registrar decisiones, errores resueltos y mejoras de flujo de forma curada.
- 21 herramientas MCP expuestas.
- 31 comandos CLI.

### Bloque v0.4 (implementado)

- Primer cockpit local por proyecto en `localhost`, con ownership claro: el agente ejecuta; July organiza y recuerda.
- Registro canonico de proyectos en SQLite para resolver `project_key -> repo_root` y soportar deep links estables.
- `ProjectCockpitService` como capa agregadora para vistas operativas y acciones explicitas.
- UI web local con `FastAPI + Jinja2 + uvicorn`, renderizado server-side y formularios HTML simples.
- Refinamiento inicial de la UX del cockpit hacia una consola de contexto: timeline, memoria y sesiones primero; escrituras manuales en acciones plegables.
- Nuevos comandos CLI: `ui` y `ui-link`.
- Nuevo launcher local: `scripts/ui.ps1` y `scripts/ui.sh`.
- Nuevo tool MCP: `project_ui_link`.
- 22 herramientas MCP expuestas.
- 33 comandos CLI.
- 13 tablas en la base de datos.

Estado resumido:

- Implementado: nucleo local-first del orquestador + protocolo de sesion + topic keys + proactive recall + URL metadata + model traceability + external references + primer wizard conversacional por proyecto + primer cockpit local por proyecto.
- Documentado y validado manualmente: protocolo operativo por proyecto (`PROJECT_PROTOCOL.md`) con distincion entre proyecto nuevo, proyecto conocido, iteracion, cierre, reglas de guardado y Fase 1/Fase 2.
- Parcial: uso de LLM para refinado de clasificacion y memoria (funcional pero requiere API key).
- Pendiente: refinar el cockpit local, continuidad conversacional, staleness, refresh selectivo y sugerencias cross-project mas utiles.

## Prioridad de producto aclarada

July no se orienta a que el usuario final "pique comandos" para acordarse de todo. La direccion del producto es esta:

- July se conecta a un proyecto;
- entiende donde esta y si ese contexto ya existe;
- propone onboarding o revision si el repo es nuevo;
- registra avances, decisiones, errores resueltos y mejoras de flujo durante la iteracion;
- recupera ese conocimiento en conversaciones futuras para evitar repetir trabajo.

El objetivo practico de esa memoria es triple:

1. Saber en que punto esta un proyecto.
2. Saber que se ha hecho y que queda por hacer.
3. Evitar dar pasos atras o rehacer en cada iteracion lo que ya se resolvio antes.

## Protocolo por proyecto ya definido

El contrato operativo ya no esta solo en conversaciones temporales. Queda fijado en `PROJECT_PROTOCOL.md`.

Ese protocolo deja cerrado:

- como distinguir proyecto nuevo frente a proyecto conocido;
- como actuar durante la iteracion;
- como cerrar una sesion sin perder contexto;
- que debe guardarse, que debe preguntarse y que no debe persistirse;
- como encajan Fase 1 y Fase 2.

Primer caso real usado para validacion manual:

- `Vocabulario`, tratado como proyecto conocido con contexto previo en inbox/memoria pero sin sesiones consolidadas.

## Siguiente bloque logico

1. Refinar el cockpit local por proyecto.
   Seguir mejorando densidad visual, filtros y recuperacion una vez resuelto el primer giro hacia consola de contexto memory-first.

2. Continuidad conversacional real.
   Hacer que July gestione mejor el paso entre `project_entry`, `project_action`, checkpoints y protocolo de sesion sin dejar sesiones ciegas o decisiones sueltas.

3. Refresco selectivo y staleness.
   Distinguir mejor entre contexto vigente, contexto parcial y contexto envejecido para no rehacer onboarding sin necesidad.

4. Sugerencias cross-project mas utiles.
   Mejorar cuando July trae una solucion de otro repo para que ayude de verdad sin volverse ruidosa.

5. UX conversacional para almacenamiento.
   Afinar las reglas de "guardar directo", "preguntar" o "ignorar" para evitar ruido y mantener memoria curada.

6. Embeddings y reranking.
   Anadir busqueda semantica ademas de FTS5 para mejorar la recuperacion cuando las palabras no coinciden literalmente.

7. Conectores de entrada.
   Telegram, email, importacion de Markdown y Obsidian como fuentes de captura.

## Aporte de Engram

Engram aporta una referencia fuerte para los cimientos del sistema:

- memoria persistente local;
- SQLite + FTS5;
- CLI y MCP como interfaces principales;
- pensamiento agente-agnostico;
- gestion de sesion;
- protocolo claro de memoria;
- recuperacion de contexto entre sesiones;
- higiene de memoria con temas evolutivos, observaciones y trazabilidad.

Lo mas valioso de Engram para July, ya absorbido en v0.2:

- Memory Protocol -> implementado como protocolo de sesion.
- Session summary -> implementado con session-summary.
- Context recovery -> implementado con session-context y proactive recall.
- Topic hygiene -> implementado con topic_key.
- Memoria como infraestructura reusable entre herramientas -> implementado via MCP con 17 herramientas.
- Primer corte wizard conversacional por proyecto -> implementado en v0.3 sobre la base propia de July, sin introducir dependencias nuevas ni cambiar el esquema SQLite.

## Aporte de Genspark

`July_Genspark.txt` plantea una vision apoyada en Engram como motor principal combinado con:

- Gentle AI como capa de orquestacion;
- Obsidian como memoria personal;
- OpenSpec para estructura por proyecto;
- sincronizacion entre dispositivos o equipo.

Lo que se tomo de valor:

- una arquitectura por capas facil de visualizar;
- importancia de MCP como interfaz universal;
- utilidad de una estructura por proyecto;
- idea de separar memoria tecnica y memoria personal.

Lo que no encaja como punto de partida de July:

- enfoque de equipo;
- sincronizacion cloud como prioridad;
- Engram como nucleo obligatorio en v1;
- Obsidian como base principal.

Genspark se usa como referencia analizada, no como documento rector.

## Aporte de Z.AI

`July_Z.AI.txt` empuja una postura pragmatica:

- Engram es la referencia principal y mas alineada;
- Google Docs no debe ser el nucleo;
- SQLite + FTS5 + MCP es la base correcta;
- la memoria debe registrarse de forma curada;
- el valor esta en enchufar la misma memoria a varios agentes.

Lo que se tomo de valor:

- insistencia en un arranque sencillo y util;
- validacion fuerte del enfoque MCP + SQLite;
- idea de curacion de memoria por parte del agente;
- recomendacion de usar Engram como referencia.

Z.AI se toma como referencia muy buena para el bloque de memoria.

## Aporte de GPT

`July_GPT.txt` aporta una lectura amplia y cercana a la vision actual de July:

- el sistema debe dividirse en captura, memoria y orquestacion;
- no hay que guardar solo conversaciones, sino activos de conocimiento;
- la memoria debe separarse por tipos y por clases;
- OpenSpec puede servir por proyecto, no como memoria global;
- Engram es una referencia fuerte para memoria, no necesariamente el producto entero.

Lo que se tomo de valor:

- arquitectura de capas alineada con July;
- distincion entre memoria episodica, semantica y procedimental;
- distincion entre memoria global, por proyecto, de sesion y destilada;
- idea de destilar conocimiento reutilizable en vez de acumular chats brutos.

GPT se toma como la referencia externa que mas refuerza la direccion de July como orquestador y memoria viva.

## Aporte de Codex

En esta sesion de marzo de 2026, Codex empujo una distincion importante que se adopta como direccion oficial:

- July ya tiene una base de memoria y orquestacion util;
- lo siguiente no es hacer mas comandos, sino construir la capa de comportamiento conversacional sobre esa base;
- CLI y MCP deben entenderse como infraestructura;
- la UX objetivo debe sentirse como un agente que entiende el proyecto, sugiere revision, guarda avances utiles y ayuda a no repetir trabajo entre iteraciones.

Este aporte no sustituye la vision de July: la refuerza con una prioridad concreta para el siguiente bloque.

En una sesion posterior del mismo mes, Codex empujo el siguiente paso de esa idea y tambien se adopta:

- July necesitaba una ventana operativa por proyecto, no otra interfaz de chat;
- la forma sana de montarla era como cockpit local en `localhost`, enlazado por `project_key`;
- las acciones debian ser explicitas: revisar proyecto, registrar decision, guardar hallazgo, recuperar contexto, organizar pendientes y preparar siguiente sesion;
- el ownership debia quedar visible: July organiza y recuerda; el agente ejecuta.

Este aporte tampoco cambia la vision del producto: la vuelve operativa con una primera UI local concreta.

En una iteracion posterior, la misma referencia de Engram ayudo a corregir una desviacion de superficie:

- el problema no era abrir una ventana local, sino haber hecho la primera pantalla demasiado form-first;
- se adopto reordenar la UX del cockpit para que contexto, timeline, memoria y sesiones entren primero;
- las escrituras manuales pasaron a acciones plegables, manteniendo el ownership original de July.

Esto no convierte July en una copia de Engram. Solo usa su claridad de consola como referencia para ordenar mejor la vista operativa.

## Aporte de Genspark (sesion v0.2)

En la sesion de implementacion de v0.2, Genspark aporto:

- implementacion completa del protocolo de sesion inspirado en Engram;
- sistema de topic keys para hilos tematicos;
- recuperacion proactiva automatica al capturar;
- extraccion de metadatos de URLs con manejo especial de YouTube;
- trazabilidad de contribuciones de modelos;
- integracion de referencias externas (skills.sh, agents.md) como puntos de apoyo;
- ampliacion del MCP server de 6 a 17 herramientas;
- ampliacion de la CLI de 11 a 27 comandos.

## Coincidencias

Las visiones de Engram, Genspark, Z.AI y GPT coinciden en un nucleo comun:

- local-first;
- memoria persistente;
- SQLite y FTS como cimiento razonable;
- MCP como interfaz universal;
- contexto entre sesiones y proyectos;
- recuperacion proactiva del conocimiento ya aprendido;
- necesidad de que varios agentes puedan usar la misma base.

## Propuesta unificada para July

Secuencia concreta, actualizada tras v0.4:

1. ~~Mantener el nucleo actual de July.~~ Completado.
2. ~~Incorporar protocolo de sesion inspirado en Engram.~~ Completado.
3. ~~Incorporar topic_key para agrupar conocimiento.~~ Completado.
4. ~~Anadir recuperacion proactiva.~~ Completado.
5. ~~Anadir trazabilidad de modelos.~~ Completado.
6. ~~Construir el protocolo de comportamiento por proyecto.~~ Completado a nivel documental y validado manualmente con Vocabulario.
7. ~~Anadir onboarding conversacional y registro de avance anti-regresion como comportamiento automatizado.~~ Primer corte implementado en v0.3; queda refinar continuidad, staleness y sugerencias.
8. ~~Anadir un primer cockpit local por proyecto con deep links y workflows explicitos.~~ Completado en v0.4.
9. Mejorar la recuperacion con embeddings y reranking.
10. Expandir canales (Telegram, email, Obsidian).
11. Evaluar integraciones mayores (OpenSpec, backends mas sofisticados).

## Backlog posterior

Bloques que quedan para despues:

- embeddings y reranking para recuperacion semantica;
- sugerencias proactivas avanzadas (deteccion de patrones repetidos);
- consolidacion automatica (daily review);
- refinamiento del wizard conversacional de nuevos proyectos;
- registro estructurado de progreso por proyecto e iteracion;
- reglas de guardado conversacional y confirmacion al usuario;
- relaciones explicitas entre memorias;
- timeline de contexto;
- evolucion del cockpit local por proyecto;
- Telegram como canal de entrada;
- email como canal de entrada;
- importacion desde Obsidian y Markdown;
- exportaciones y backups mas ricos;
- sync multi-dispositivo;
- evaluacion de OpenSpec como capa por proyecto;
- evaluacion de Obsidian como conector, no como fuente de verdad;
- posible comparativa formal entre backend propio y Engram como motor subyacente.

## Reglas de mantenimiento

Este roadmap debe actualizarse cuando cambie cualquiera de estas cosas:

- arquitectura;
- prioridades;
- proveedor LLM principal documentado;
- flujo MCP;
- bloques implementados;
- decisiones nuevas aportadas por otros modelos.

No debe quedarse desalineado respecto a `README.md` ni respecto al estado real del codigo.
