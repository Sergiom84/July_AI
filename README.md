# July

July es un orquestador local-first con memoria persistente. Su funcion no es solo guardar entradas libres, sino capturarlas, clasificarlas, convertirlas en tareas o memoria util, relacionarlas entre proyectos y servir contexto reutilizable a distintos agentes y clientes.

## Lectura obligatoria para agentes

Antes de actuar sobre este proyecto, cualquier agente, CLI o modelo debe leer en este orden:

1. `README.md`
2. `ROADMAP.md`
3. `AGENTS.md`
4. Los archivos especificos del area que vaya a tocar

Ningun agente debe asumir que el chat actual sustituye a estos documentos.

## Mantenimiento documental obligatorio

Si un cambio modifica comandos, arquitectura, flujo MCP, proveedor LLM, prioridades, roadmap o la forma de trabajar del proyecto, ese mismo cambio debe actualizar `README.md` y `ROADMAP.md`.

La regla es simple:

- `README.md` mantiene la vision y la guia operativa corta.
- `ROADMAP.md` mantiene el estado vivo del proyecto.
- `AGENTS.md` obliga a leer y mantener ambos.

## Que implementa este primer corte

- Captura de entrada libre desde CLI o stdin.
- Clasificacion heuristica de intencion.
- Soporte para inputs sin formulario fijo.
- Almacenamiento local en SQLite.
- FTS5 para buscar inbox y memoria.
- Creacion de tareas y memoria candidata cuando tiene sentido.
- Deteccion de dudas y generacion de preguntas de aclaracion.
- Resolucion de aclaraciones sobre un inbox item existente.
- Promocion de memoria candidata a memoria estable.
- Capa LLM opcional y desacoplada para refinar clasificacion y destilado.
- Primer MCP server por stdio para exponer July a clientes externos.

## Modelo operativo

Pipeline actual:

`input libre -> extraer urls/rutas/proyecto -> clasificar -> guardar inbox -> crear tarea/memoria candidata -> recuperar`

Tipos de intencion iniciales:

- `repository_onboarding`
- `resource_watch_later`
- `resource_apply_to_project`
- `memory_query`
- `repository_audit_with_memory`
- `external_analysis_import`
- `architecture_collaboration`
- `general_note`

## Uso rapido

### 1. Capturar una entrada libre

```powershell
python -m july capture "Quiero que me recuerdes ver este link: https://youtu.be/91BGGKlQrho?is=cl4QJLJSMw4gl_Yh"
```

```powershell
python -m july capture "He visto un curso que quiero aplicar en Lucy3000 = https://www.youtube.com/live/V-eiE0M-mWM?si=ltpvWp8xfhi2SH1W"
```

```powershell
python -m july capture "Accede a C:\Users\sergi\Desktop\Aplicaciones\Vocabulario, comprueba que los acceso a Supabase y Render son correctos. Si tienes dudas, tira de la memoria."
```

### 2. Ver el inbox

```powershell
python -m july inbox
```

### 3. Resolver una aclaracion

```powershell
python -m july clarify 3 "Quiero una auditoria tecnica completa apoyandote en lo que ya aprendimos en otros proyectos"
```

### 4. Ver tareas pendientes

```powershell
python -m july tasks
```

### 5. Ver memoria candidata o lista

```powershell
python -m july memory
```

### 6. Promover una memoria candidata

```powershell
python -m july promote-memory 1
```

### 7. Ver contexto agrupado por proyecto

```powershell
python -m july project-context Vocabulario
```

### 8. Buscar contexto

```powershell
python -m july search skill
python -m july search MCP
python -m july search Lucy3000
```

### 9. Probar una clasificacion sin guardar

```powershell
python -m july capture "Accede a C:\Users\sergi\Desktop\Aplicaciones\Voice_Clon, revisa el markdown y vamos a proceder con la arquitectura." --dry-run
```

### 10. Lanzar el servidor MCP

```powershell
python -m july mcp
```

Herramientas MCP expuestas actualmente:

- `capture_input`
- `search_context`
- `project_context`
- `list_inbox`
- `clarify_input`
- `promote_memory`

Ejemplo de configuracion MCP por stdio:

```json
{
  "mcpServers": {
    "july": {
      "command": "python",
      "args": ["-m", "july", "mcp"],
      "cwd": "C:\\Users\\sergi\\Desktop\\Aplicaciones\\July"
    }
  }
}
```

## Donde guarda los datos

Por defecto la base vive en:

`./data/july.db`

Se puede cambiar con:

`JULY_DB_PATH`

July carga automaticamente un archivo `.env` en la raiz del proyecto si existe, asi que `JULY_DB_PATH` tambien puede vivir ahi.

## Capa LLM opcional

July puede pedir ayuda a un proveedor LLM para:

- refinar clasificaciones ambiguas;
- mejorar resumenes;
- destilar memoria candidata.

OpenAI es la configuracion principal documentada ahora mismo:

```powershell
$env:JULY_LLM_PROVIDER="openai_compatible"
$env:JULY_LLM_MODEL="gpt-4.1-mini"
$env:JULY_LLM_API_KEY="tu-api-key"
$env:JULY_LLM_BASE_URL="https://api.openai.com/v1"
```

Variables soportadas:

- `JULY_LLM_PROVIDER`
- `JULY_LLM_MODEL`
- `JULY_LLM_API_KEY`
- `JULY_LLM_BASE_URL`
- `JULY_LLM_TIMEOUT`

Estas variables pueden definirse en `.env` o en el entorno del sistema.

July mantiene una arquitectura compatible con otros proveedores `OpenAI-compatible`. Z.ai sigue siendo una alternativa compatible, pero ya no es el ejemplo principal del proyecto.

Ejemplos:

```powershell
python -m july capture "Estoy utilizando Codex en local..." --use-llm
python -m july clarify 3 "Solo quiero arquitectura" --use-llm
python -m july promote-memory 1 --use-llm
```

## Mesa redonda de modelos

Uno de los puntos fuertes de July es que todas las opiniones cuentan. Claude, Codex, Z.ai, Perplexity y otros modelos pueden aportar ideas validas.

La intencion no es seguir ciegamente a un unico modelo, sino montar una mesa redonda:

- cada modelo puede aportar un planteamiento;
- cada aportacion debe poder registrarse;
- las aportaciones deben compararse;
- la decision final debe sintetizar lo mejor de todas.

July no esta pensado para una unica voz. Esta pensado para aprovechar el contraste entre varias IAs y convertirlo en conocimiento util y trazable.

## Como interpretar este MVP

- No todo lo que entra se convierte en memoria.
- Todo lo que entra puede quedar en inbox.
- Los links pendientes suelen generar tarea, no memoria estable.
- Las revisiones de repo, arquitectura o planteamientos externos pueden generar memoria candidata o util directamente.
- Si la clasificacion no es suficientemente segura, July marca la entrada como `needs_clarification`.
- Una aclaracion actualiza el mismo `inbox_item`; no crea otro distinto.

## Contrato publico del proyecto

- `README.md` es la vision y la guia operativa corta.
- `ROADMAP.md` es el estado vivo y la direccion del proyecto.
- `AGENTS.md` es la instruccion obligatoria para cualquier agente o CLI que contribuya.

Estos tres archivos deben mantenerse alineados.
