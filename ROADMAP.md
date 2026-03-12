# ROADMAP

## Estado actual implementado

Lo que ya existe hoy en el codigo:

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

Estado resumido:

- Implementado: nucleo local-first del orquestador.
- Parcial: uso de LLM para refinado de clasificacion y memoria.
- Pendiente: protocolo de memoria avanzado y trazabilidad rica entre sesiones.

## Siguiente bloque logico

Los siguientes pasos deben inspirarse en Engram, pero adaptados al enfoque de July:

1. Protocolo de memoria para agentes.
   July necesita reglas claras de cuando guardar, cuando buscar, cuando resumir y como actuar tras compaction.

2. Ciclo de sesion.
   Incorporar `session_start`, `session_summary`, cierre de sesion y recuperacion de contexto reciente.

3. Tema evolutivo o `topic_key`.
   Introducir una forma estable de agrupar decisiones, aprendizajes y problemas repetidos bajo un mismo hilo.

4. Recuperacion de contexto mas rica.
   Añadir timeline, mejores relaciones entre items y contexto incremental por proyecto o tema.

5. Trazabilidad de opiniones de modelos.
   Guardar y contrastar aportes de Claude, Codex, Z.ai, Perplexity y otros como parte del sistema, no como notas sueltas.

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

Lo mas valioso de Engram para July no es copiarlo entero, sino absorber:

- Memory Protocol;
- session summary;
- context recovery;
- topic hygiene;
- idea de memoria como infraestructura reusable entre herramientas.

## Aporte de Genspark

`July_Genspark.txt` plantea una vision muy apoyada en Engram como motor principal y lo combina con:

- Gentle AI como capa de orquestacion;
- Obsidian como memoria personal;
- OpenSpec para estructura por proyecto;
- sincronizacion entre dispositivos o equipo;
- stack pensado mas cerca de un ecosistema completo que de un MVP personal.

Lo que aporta de valor:

- una arquitectura por capas facil de visualizar;
- importancia de MCP como interfaz universal;
- utilidad de una estructura por proyecto;
- idea de separar memoria tecnica y memoria personal.

Lo que no encaja como punto de partida de July:

- enfoque de equipo;
- sincronizacion cloud como prioridad;
- Engram como nucleo obligatorio en v1;
- Obsidian como base principal;
- stack externo demasiado pesado para el arranque.

Genspark se usara como referencia analizada, no como documento rector del proyecto.

## Aporte de Z.AI

`July_Z.AI.txt` empuja una postura muy clara y pragmatica:

- Engram es la referencia principal y mas alineada;
- Google Docs no debe ser el nucleo;
- SQLite + FTS5 + MCP es la base correcta;
- la memoria debe registrarse de forma curada, no guardar todo sin filtro;
- una parte importante del valor esta en enchufar la misma memoria a varios agentes.

Lo que aporta de valor:

- insistencia en un arranque sencillo y util;
- validacion fuerte del enfoque MCP + SQLite;
- idea de curacion de memoria por parte del agente;
- recomendacion de usar Engram como base o referencia antes de sobre-ingenierizar.

Lo que no se adopta literalmente:

- arrancar usando Engram como solucion casi cerrada;
- desplazar demasiado pronto el nucleo propio de July;
- limitar el sistema a memoria para programacion sin ampliar el rol de orquestador.

Z.AI se toma como una referencia muy buena para el bloque de memoria, pero no como definicion completa del producto.

## Aporte de GPT

`July_GPT.txt` aporta una lectura mas amplia y mas cercana a la vision actual de July:

- el sistema debe dividirse en captura, memoria y orquestacion;
- no hay que guardar solo conversaciones, sino activos de conocimiento;
- la memoria debe separarse por tipos y por clases;
- OpenSpec puede servir por proyecto, no como memoria global;
- Engram es una referencia fuerte para memoria, no necesariamente el producto entero.

Lo que aporta de valor:

- una arquitectura de capas muy alineada con July;
- distincion entre memoria episodica, semantica y procedimental;
- distincion entre memoria global, por proyecto, de sesion y destilada;
- idea de destilar conocimiento reutilizable en vez de acumular chats brutos.

Lo que no se toma como mandato literal:

- introducir demasiadas capas avanzadas del segundo cerebro antes de consolidar el MVP;
- abrir demasiados conectores e integraciones al mismo tiempo;
- pasar demasiado pronto a una arquitectura amplia antes de fijar bien el protocolo base.

GPT se toma como la referencia externa que mas refuerza la direccion de July como orquestador y memoria viva.

## Coincidencias

Las visiones de Engram, Genspark, Z.AI y GPT coinciden en un nucleo comun:

- local-first;
- memoria persistente;
- SQLite y FTS como cimiento razonable;
- MCP como interfaz universal;
- contexto entre sesiones y proyectos;
- recuperacion proactiva del conocimiento ya aprendido;
- necesidad de que varios agentes puedan usar la misma base.

Ademas, GPT y Z.AI coinciden en algo especialmente util para July:

- Google Docs no debe ser la fuente de verdad;
- el sistema necesita una base propia;
- el valor esta en reutilizar conocimiento, no en acumular historial sin procesar.

## Diferencias clave

Engram y la propuesta de Genspark priorizan:

- motor de memoria para coding agents;
- flujo muy centrado en agentes de desarrollo;
- protocolo de memoria y sesiones como centro del sistema.

Z.AI prioriza:

- un arranque pragmatico usando Engram casi como solucion base;
- memoria muy orientada a programacion y reutilizacion tecnica;
- configuracion minima antes que capas amplias de producto.

GPT prioriza:

- arquitectura por capas;
- memoria como sistema mas amplio que un chat o un motor de coding;
- conocimiento destilado, tipado y organizado por clases y alcance.

July prioriza:

- orquestador amplio;
- inbox universal;
- tareas, links, ideas y recursos ademas de memoria;
- varias IAs como mesa redonda;
- sintesis entre opiniones;
- soporte para proyectos, notas, recursos y decisiones, no solo coding memory.

Tambien queda claro que para July:

- Obsidian no es obligatorio en v1;
- sync de equipo no es prioridad;
- Gentle AI y OpenSpec son inspiraciones posibles, no dependencias de arranque.

## Propuesta unificada para July

Secuencia concreta recomendada:

1. Mantener el nucleo actual de July.
   No sustituirlo por Engram ni por Obsidian, pero seguir absorbiendo lo mejor de ambos.

2. Incorporar el primer bloque semantico inspirado en Engram.
   Añadir protocolo de memoria, resumen de sesion y recuperacion tras compaction.

3. Incorporar el modelo de conocimiento que GPT empuja.
   Pasar de guardar inputs y memoria basica a diferenciar mejor memoria episodica, semantica y procedimental, junto con alcance global, proyecto y sesion.

4. Añadir `topic_key` o equivalente.
   Resolver el problema de "esto ya lo he vivido antes con otro nombre o en otro contexto".

5. Añadir trazabilidad de modelos.
   Registrar que propuestas vienen de Claude, Codex, Z.ai, Perplexity u otros, y permitir compararlas.

6. Mejorar la recuperacion.
   Timeline, relaciones entre items, busqueda mejorada por proyecto y tema.

7. Expandir canales.
   Cuando el nucleo este estable, integrar Telegram, email y otros inputs externos.

8. Evaluar integraciones mayores.
   Solo despues de consolidar el nucleo, valorar OpenSpec, Obsidian o un backend de memoria mas sofisticado.

## Backlog posterior

Bloques que quedan para despues del siguiente bloque logico:

- relaciones explicitas entre memorias;
- sugerencias proactivas;
- timeline de contexto;
- importacion estructurada de opiniones de modelos;
- Telegram;
- email;
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
