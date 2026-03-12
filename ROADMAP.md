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
- 19 herramientas MCP (antes 6).
- 28 comandos CLI (antes 11).
- 12 tablas en la base de datos (antes 6).

Estado resumido:

- Implementado: nucleo local-first del orquestador + protocolo de sesion + topic keys + proactive recall + URL metadata + model traceability + external references.
- Parcial: uso de LLM para refinado de clasificacion y memoria (funcional pero requiere API key).
- Pendiente: conectores externos, embeddings, sugerencias proactivas avanzadas.

## Siguiente bloque logico

1. Embeddings y reranking.
   Anadir busqueda semantica ademas de FTS5 para mejorar la recuperacion cuando las palabras no coinciden literalmente.

2. Sugerencias proactivas avanzadas.
   Que July no solo encuentre memorias por keywords, sino que detecte patrones: "llevas 3 proyectos usando el mismo stack, quieres convertirlo en una plantilla?"

3. Consolidacion automatica.
   Un comando `daily-review` o `consolidate` que revise el inbox, promueva memorias candidatas y sugiera cerrar sesiones abiertas.

4. Conectores de entrada.
   Telegram, email, importacion de Markdown y Obsidian como fuentes de captura.

5. Panel simple o TUI.
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
- Memoria como infraestructura reusable entre herramientas -> implementado via MCP con 19 herramientas.

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

## Aporte de Genspark (sesion v0.2)

En la sesion de implementacion de v0.2, Genspark aporto:

- implementacion completa del protocolo de sesion inspirado en Engram;
- sistema de topic keys para hilos tematicos;
- recuperacion proactiva automatica al capturar;
- extraccion de metadatos de URLs con manejo especial de YouTube;
- trazabilidad de contribuciones de modelos;
- integracion de referencias externas (skills.sh, agents.md) como puntos de apoyo;
- ampliacion del MCP server de 6 a 19 herramientas;
- ampliacion de la CLI de 11 a 28 comandos.

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
6. Mejorar la recuperacion con embeddings y reranking.
7. Anadir consolidacion automatica y daily review.
8. Expandir canales (Telegram, email, Obsidian).
9. Evaluar integraciones mayores (OpenSpec, backends mas sofisticados).

## Backlog posterior

Bloques que quedan para despues:

- embeddings y reranking para recuperacion semantica;
- sugerencias proactivas avanzadas (deteccion de patrones repetidos);
- consolidacion automatica (daily review);
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
