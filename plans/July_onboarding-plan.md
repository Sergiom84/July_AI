# Plan: Integración Fácil de July en Proyectos

## Objetivo

Este plan responde a una pregunta práctica:

- cómo integrar July de forma simple en varios proyectos;
- sin meter July dentro del código de cada app;
- empezando por `Dashboard_AV`.

## Principio clave

July no debe integrarse como un plugin embebido dentro de cada proyecto.

La integración correcta y más simple es esta:

- July vive como servidor MCP externo compartido;
- cada cliente compatible se conecta a ese servidor;
- los proyectos solo aportan contexto, no una dependencia técnica nueva.

Consecuencia práctica:

- no hace falta añadir July a `package.json` ni al backend de cada app;
- no hace falta tocar React, Express o SQLite del proyecto objetivo;
- basta con conectar el cliente MCP a July y hacer onboarding del proyecto.

## Modelo de integración recomendado

### Nivel 1: integración global por cliente

Se configura July una sola vez por cliente:

- Roo Code
- Claude Desktop
- Codex
- Z.Ai
- cualquier otro cliente MCP compatible

Después de eso, todos los proyectos abiertos en ese cliente pueden usar July.

Esta es la vía más fácil y la que debe ser el default.

### Nivel 2: integración ligera por proyecto

Solo si hace falta portabilidad o aislamiento por repo:

- añadir una configuración local MCP del cliente en ese proyecto;
- usar una `project_key` estable;
- hacer onboarding inicial del repo.

Esta integración sigue siendo externa.
No convierte July en parte del runtime del proyecto.

## Qué significa “integrar un proyecto”

Para July, integrar un proyecto significa:

1. poder invocarlo desde el cliente que usas en ese repo;
2. asignar una clave estable al proyecto;
3. guardar una primera foto útil del repositorio;
4. reutilizar ese contexto en sesiones futuras y entre modelos.

No significa:

- instalar July dentro del proyecto;
- modificar el código de la app para “llamar” a July;
- generar documentación invasiva en el repo por defecto.

## Configuración más simple por cliente

La configuración base ya existe y debe reutilizarse desde `MCP_SETUP.md`.

### Windows

Usar:

```json
{
  "mcpServers": {
    "july": {
      "command": "cmd",
      "args": ["/c", "C:\\Users\\sergi\\Desktop\\Aplicaciones\\July\\start-july-mcp.cmd"],
      "cwd": "C:\\Users\\sergi\\Desktop\\Aplicaciones\\July"
    }
  }
}
```

### WSL / Linux / macOS

Usar:

```json
{
  "mcpServers": {
    "july": {
      "command": "bash",
      "args": ["/mnt/c/Users/sergi/Desktop/Aplicaciones/July/start-july-mcp.sh"],
      "cwd": "/mnt/c/Users/sergi/Desktop/Aplicaciones/July"
    }
  }
}
```

## Estrategia operativa recomendada

### Opción A: una vez por cliente

Es la recomendada.

- Configuras July en Roo una vez.
- Configuras July en Claude una vez.
- Configuras July en Codex una vez.
- A partir de ahí, cualquier repo abierto en ese cliente puede usar July.

Ventajas:

- cero cambios en los proyectos;
- misma memoria para todos los repos;
- menos mantenimiento;
- más fácil para flujo multi-modelo.

### Opción B: por proyecto

Solo usar si quieres que un proyecto cargue su propia config MCP local.

Ejemplo típico en Roo:

```json
{
  "mcpServers": {
    "july": {
      "command": "cmd",
      "args": ["/c", "C:\\Users\\sergi\\Desktop\\Aplicaciones\\July\\start-july-mcp.cmd"],
      "cwd": "C:\\Users\\sergi\\Desktop\\Aplicaciones\\July"
    }
  }
}
```

Ruta sugerida:

```text
<proyecto>/.roo/mcp.json
```

Esto sigue siendo una referencia al servidor MCP de July.
No es una instalación de July dentro del proyecto.

## Patrón canónico por proyecto

Para cualquier proyecto nuevo, el patrón debe ser:

1. elegir una `project_key` canónica y estable;
2. consultar `project_context` y `session_context`;
3. decidir si el proyecto es nuevo o conocido;
4. si es nuevo, hacer onboarding;
5. abrir sesión real con `session_start`;
6. cerrar siempre con `session_summary` y `session_end`.

Claves recomendadas:

- usar minúsculas y guiones;
- no mezclar `Dashboard_AV`, `dashboard-av` y variantes;
- usar la misma clave en todos los clientes.

## Primera integración: Dashboard_AV

### Clave recomendada

Usar:

- `project_key: "dashboard-av"`
- `topic_key: "dashboard-av"`

No usar mezclas como:

- `Dashboard_AV`
- `dashav`
- `dashboardAV`

## Qué debe guardar el onboarding de Dashboard_AV

La primera captura no debe ser una nota mínima.
Debe dejar una foto útil para el siguiente agente.

Contenido recomendado:

- ruta del repo;
- objetivo del proyecto;
- stack real;
- módulos visibles;
- persistencia y fuentes de datos;
- endpoints principales;
- comandos de desarrollo;
- estado funcional actual;
- dudas abiertas o riesgos.

## Onboarding recomendado para Dashboard_AV

### Paso 0: comprobar si ya existe contexto

```text
project_context
  project_key: "dashboard-av"

session_context
  project_key: "dashboard-av"
```

Si no hay contexto útil, tratarlo como proyecto nuevo.

### Paso 1: abrir sesión con clave única

```text
session_start
  session_key: "dashboard-av-onboarding-2026-03-18"
  project_key: "dashboard-av"
  goal: "Onboarding inicial y primera foto útil del repo"
```

### Paso 2: crear topic estable

```text
topic_create
  topic_key: "dashboard-av"
  label: "Dashboard AV"
  domain: "Soporte Técnico"
```

### Paso 3: enlazar la sesión al topic

Usar el `session_id` devuelto por `session_start`.

```text
topic_link
  session_id: <session_id_devuelto>
  topic_key: "dashboard-av"
```

### Paso 4: capturar perfil inicial útil

Texto recomendado para `capture_input`:

```text
Dashboard_AV es un dashboard interno de soporte técnico ubicado en C:\Users\sergi\Desktop\Aplicaciones\Dashboard_AV.
Stack actual: React 19 + Vite 7 + Express 4 + @libsql/client/Turso + shadcn/ui + xlsx.
Módulos actuales: Tendencias, Dashboard AV, Informática y Renove.
Tendencias usa fichero plano 2026 como fuente principal, fichero crudo opcional para validación visible e histórico, y exporta presentación Weekly PPT.
Dashboard AV e Informática usan carga tabular independiente.
Persistencia backend: tablas soportes, informatica, tendencias y renove.
Comandos principales: npm run dev, npm run check, npm run build.
Objetivo operativo: visualizar métricas de soporte, validar cargas Excel y generar salidas ejecutivas semanales.
```

### Paso 5: cerrar con resumen útil

```text
session_summary
  session_key: "dashboard-av-onboarding-2026-03-18"
  summary: "Onboarding inicial completado para Dashboard_AV con perfil de arquitectura, módulos y fuentes de datos."
  discoveries: "El proyecto tiene cuatro áreas funcionales: Tendencias, Dashboard AV, Informática y Renove. Tendencias ya usa flujo plano + crudo + validación + exportación PPT."
  next_steps: "Usar project_context antes de cada nueva tarea y registrar decisiones técnicas y errores resueltos durante la iteración."
  relevant_files: "client/src/pages, server/routes.ts, server/db.ts, shared/"
```

### Paso 6: cerrar sesión

```text
session_end
  session_key: "dashboard-av-onboarding-2026-03-18"
```

### Paso 7: verificar

```text
project_context
  project_key: "dashboard-av"
```

El resultado debería permitir a otro cliente entender:

- qué es el proyecto;
- cómo está montado;
- qué módulos tiene;
- cuál es el siguiente paso razonable.

## Flujo de uso diario después del onboarding

Una vez integrado el proyecto, el patrón de trabajo debería ser:

1. abrir el repo;
2. consultar `project_context dashboard-av`;
3. consultar `session_context dashboard-av`;
4. empezar la nueva tarea;
5. registrar decisiones, hallazgos y errores resueltos;
6. cerrar con `session_summary` y `session_end`.

## Escalado a otros proyectos

Para incorporar July a otros proyectos, repetir el mismo patrón:

1. configurar July en el cliente una vez;
2. elegir `project_key` estable;
3. hacer onboarding inicial;
4. reutilizar `project_context` y `session_context` antes de cada iteración.

Checklist por proyecto:

- [ ] `project_key` definida y estable
- [ ] July visible desde el cliente MCP
- [ ] `project_context` revisado antes del onboarding
- [ ] `session_start` ejecutado
- [ ] perfil inicial capturado con suficiente detalle
- [ ] `topic_create` y `topic_link` ejecutados
- [ ] `session_summary` y `session_end` ejecutados
- [ ] verificado con `project_context`

## Regla práctica final

La forma más fácil de integrar July no es “meterlo” en cada proyecto.

La forma más fácil es:

- configurar July una vez por cliente;
- tratar cada repo como un proyecto con `project_key`;
- hacer onboarding de contexto, no instalación de código.
