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

Estado resumido:

- Implementado: nucleo local-first del orquestador + protocolo de sesion + topic keys + proactive recall + URL metadata + model traceability + external references.
- Documentado y validado manualmente: protocolo operativo por proyecto (`PROJECT_PROTOCOL.md`) con distincion entre proyecto nuevo, proyecto conocido, iteracion, cierre, reglas de guardado y Fase 1/Fase 2.
- Parcial: uso de LLM para refinado de clasificacion y memoria (funcional pero requiere API key).
- Pendiente: automatizar la capa conversacional orientada a proyectos, onboarding automatico de repos, consolidacion de progreso entre iteraciones y conectores externos.

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

1. Automatizar el protocolo de comportamiento por proyecto ya definido.
   Convertir `PROJECT_PROTOCOL.md` en comportamiento reproducible del agente usando las primitivas actuales de July.

2. Onboarding conversacional del repositorio.
   Hacer que July pueda proponer "quieres que revise este proyecto?" y guardar una primera foto util del repo, su arquitectura y su estado.

3. Registro de avance y anti-regresion.
   Consolidar decisiones, errores resueltos, pendientes y mejoras de flujo para que el proyecto pueda retomarse sin repetir analisis.

4. UX conversacional para almacenamiento.
   Preguntas tipo "quieres que lo guarde?", "quieres que esto quede como referencia?" y reglas para guardar automaticamente cuando la senal sea clara.

5. Embeddings y reranking.
   Anadir busqueda semantica ademas de FTS5 para mejorar la recuperacion cuando las palabras no coinciden literalmente.

6. Conectores de entrada.
   Telegram, email, importacion de Markdown y Obsidian como fuentes de captura.

7. Panel simple o TUI.
   Interfaz visual para inspeccionar memoria, sesiones, topics y contribuciones sin usar solo CLI.

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

Secuencia concreta, actualizada tras v0.2:

1. ~~Mantener el nucleo actual de July.~~ Completado.
2. ~~Incorporar protocolo de sesion inspirado en Engram.~~ Completado.
3. ~~Incorporar topic_key para agrupar conocimiento.~~ Completado.
4. ~~Anadir recuperacion proactiva.~~ Completado.
5. ~~Anadir trazabilidad de modelos.~~ Completado.
6. ~~Construir el protocolo de comportamiento por proyecto.~~ Completado a nivel documental y validado manualmente con Vocabulario.
7. Anadir onboarding conversacional y registro de avance anti-regresion como comportamiento automatizado.
8. Mejorar la recuperacion con embeddings y reranking.
9. Expandir canales (Telegram, email, Obsidian).
10. Evaluar integraciones mayores (OpenSpec, backends mas sofisticados).

## Backlog posterior

Bloques que quedan para despues:

- embeddings y reranking para recuperacion semantica;
- sugerencias proactivas avanzadas (deteccion de patrones repetidos);
- consolidacion automatica (daily review);
- onboarding conversacional de nuevos proyectos;
- registro estructurado de progreso por proyecto e iteracion;
- reglas de guardado conversacional y confirmacion al usuario;
- relaciones explicitas entre memorias;
- timeline de contexto;
- Telegram como canal de entrada;
- email como canal de entrada;
- importacion desde Obsidian y Markdown;
- exportaciones y backups mas ricos;
- sync multi-dispositivo;
- evaluacion de OpenSpec como capa por proyecto;
- evaluacion de Obsidian como conector, no como fuente de verdad;
- panel simple o TUI;
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
