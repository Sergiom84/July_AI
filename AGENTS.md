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

Esto aplica a aportes de:

- Claude
- Codex
- Z.ai
- Perplexity
- cualquier otra IA o agente

## Regla de reconciliacion

No se debe sobrescribir la vision de July con propuestas externas tipo Engram, Genspark, Gentle AI u otras sin reconciliarlas antes con el enfoque principal del proyecto:

- July es un orquestador amplio;
- July tiene inbox universal;
- July combina memoria, tareas, contexto y comparacion entre modelos;
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
