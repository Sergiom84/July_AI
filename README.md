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

## Que implementa este corte

### Nucleo original (v0.1)

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

### Nuevo en v0.2

- Protocolo de sesion completo: `session-start`, `session-summary`, `session-end`, `session-context`.
- Hilos tematicos con `topic_key`: crear temas, enlazar items/memorias/sesiones, consultar contexto por tema.
- Recuperacion proactiva: al capturar un input, July busca automaticamente en memoria y sugiere reutilizar conocimiento previo.
- Extraccion de metadatos de URLs: titulo, descripcion, tipo de contenido. Manejo especial de YouTube (video id, canal, duracion).
- Trazabilidad de modelos: registrar contribuciones de Claude, GPT, Z.AI, Codex, Perplexity, Genspark u otros. Marcar como adoptadas o no.
- Referencias externas: July sugiere consultar skills.sh y agents.md cuando detecta que un input podria beneficiarse de una skill o un patron de agente.
- 19 herramientas MCP expuestas (antes 6).
- 28 comandos CLI (antes 11).

## Modelo operativo

Pipeline actual:

`input libre -> extraer urls/rutas/proyecto -> clasificar -> recall proactivo -> guardar inbox -> crear tarea/memoria candidata -> fetch URL metadata -> sugerir referencias externas -> recuperar`

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
python -m july capture "Quiero que me recuerdes ver este link: https://youtu.be/91BGGKlQrho"
```

```powershell
python -m july capture "He visto un curso que quiero aplicar en Lucy3000 = https://www.youtube.com/live/V-eiE0M-mWM" --fetch-urls
```

```powershell
python -m july capture "Accede a C:\Users\sergi\Desktop\Aplicaciones\Vocabulario, comprueba los accesos" --model-name claude
```

### 2. Ver el inbox

```powershell
python -m july inbox
```

### 3. Resolver una aclaracion

```powershell
python -m july clarify 3 "Quiero una auditoria tecnica completa"
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
python -m july capture "Quiero montar JWT en Vocabulario" --dry-run
```

### 10. Protocolo de sesion

```powershell
# Iniciar sesion
python -m july session-start "ses-001" --project Lucy3000 --agent claude --goal "Implementar JWT"

# Guardar resumen antes de cerrar
python -m july session-summary "ses-001" "Implementamos JWT con refresh tokens" --discoveries "httpOnly cookie obligatoria" --next-steps "Proteger rutas privadas"

# Cerrar sesion
python -m july session-end "ses-001"

# Recuperar contexto de sesiones recientes
python -m july session-context --project Lucy3000

# Listar sesiones
python -m july sessions
```

### 11. Hilos tematicos (topic keys)

```powershell
# Crear un tema
python -m july topic-create "auth/jwt-flow" "Autenticacion JWT" --domain Programacion --description "Todo sobre JWT y refresh tokens"

# Enlazar items al tema
python -m july topic-link "auth/jwt-flow" --memory-item-id 1
python -m july topic-link "auth/jwt-flow" --session-id 1

# Ver todo lo vinculado a un tema
python -m july topic-context "auth/jwt-flow"

# Listar temas
python -m july topics
```

### 12. Trazabilidad de modelos

```powershell
# Registrar una contribucion
python -m july model-contribution "claude" "architecture" "Propuesta JWT" "Usar refresh tokens en httpOnly cookies" --project Vocabulario

# Listar contribuciones
python -m july model-contributions --project Vocabulario

# Marcar como adoptada
python -m july adopt-contribution 1 --notes "Adoptada por experiencia previa en Lucy3000"
```

### 13. Fetch de URLs

```powershell
python -m july fetch-url "https://github.com/Gentleman-Programming/engram"
```

### 14. Referencias externas

```powershell
# Consultar una fuente de referencia conocida
python -m july fetch-reference skills.sh
python -m july fetch-reference agents.md

# Ver referencias almacenadas
python -m july external-references
```

### 15. Lanzar el servidor MCP

```powershell
python -m july mcp
```

Herramientas MCP expuestas actualmente:

- `capture_input` (con proactive recall, fetch URLs, model traceability)
- `search_context`
- `project_context`
- `list_inbox`
- `clarify_input`
- `promote_memory`
- `session_start`
- `session_summary`
- `session_end`
- `session_context`
- `topic_create`
- `topic_link`
- `topic_context`
- `save_model_contribution`
- `fetch_url`
- `fetch_reference`
- `proactive_recall`

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

## Esquema de base de datos

Tablas principales:

| Tabla | Funcion |
|---|---|
| `inbox_items` | Entradas brutas capturadas |
| `tasks` | Tareas derivadas de inputs |
| `memory_items` | Memoria candidata y estable |
| `artifacts` | URLs y rutas detectadas |
| `project_links` | Relaciones entre items y proyectos |
| `clarification_events` | Historial de aclaraciones |
| `sessions` | Sesiones de trabajo con inicio, resumen y cierre |
| `topic_keys` | Temas estables para agrupar conocimiento |
| `topic_links` | Enlaces entre temas y items/memorias/sesiones |
| `model_contributions` | Contribuciones trazables de modelos IA |
| `url_metadata` | Metadatos extraidos de URLs (titulo, descripcion, YouTube) |
| `external_references` | Referencias a fuentes externas (skills.sh, agents.md) |

Indices FTS5: `inbox_items_fts`, `memory_items_fts`.

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

## Mesa redonda de modelos

Uno de los puntos fuertes de July es que todas las opiniones cuentan. Claude, Codex, Z.ai, Perplexity, Genspark y otros modelos pueden aportar ideas validas.

La intencion no es seguir ciegamente a un unico modelo, sino montar una mesa redonda:

- cada modelo puede aportar un planteamiento;
- cada aportacion se registra con `model-contribution` y queda trazable;
- las aportaciones pueden compararse con `model-contributions`;
- la decision final se marca como adoptada con `adopt-contribution`;
- las no adoptadas quedan como registro historico, no se borran.

July no esta pensado para una unica voz. Esta pensado para aprovechar el contraste entre varias IAs y convertirlo en conocimiento util y trazable.

## Recuperacion proactiva

Cada vez que se captura una nueva entrada, July busca automaticamente en su memoria y sesiones previas:

- Si encuentra memorias globales reutilizables, sugiere reutilizarlas.
- Si encuentra memorias de otros proyectos con contenido similar, avisa con `cross_project`.
- Si hay sesiones recientes del mismo proyecto, las incluye como contexto.

Esto convierte a July en un sistema que **recuerda por ti y te avisa cuando algo es relevante**, no solo un almacen pasivo.

## Referencias externas como punto de apoyo

July puede sugerir consultar fuentes externas cuando detecta que un input se beneficiaria de ellas:

- **skills.sh**: Cuando el input implica crear patrones reutilizables, plantillas, workflows o scaffolding.
- **agents.md**: Cuando el input implica crear agentes, sub-agentes, orquestacion o automatizacion.

Estas sugerencias son puntos de referencia. July toma la idea, la revisa, y crea su propia implementacion. No depende de ellas ni las copia literalmente.

## Como interpretar este MVP

- No todo lo que entra se convierte en memoria.
- Todo lo que entra puede quedar en inbox.
- Los links pendientes suelen generar tarea, no memoria estable.
- Las revisiones de repo, arquitectura o planteamientos externos pueden generar memoria candidata o util directamente.
- Si la clasificacion no es suficientemente segura, July marca la entrada como `needs_clarification`.
- Una aclaracion actualiza el mismo `inbox_item`; no crea otro distinto.
- Al capturar, July busca proactivamente en memoria y sugiere reutilizar conocimiento previo.
- Las sesiones permiten consolidar el conocimiento de un bloque de trabajo.
- Los topic keys permiten agrupar conocimiento disperso bajo un mismo hilo.

## Contrato publico del proyecto

- `README.md` es la vision y la guia operativa corta.
- `ROADMAP.md` es el estado vivo y la direccion del proyecto.
- `AGENTS.md` es la instruccion obligatoria para cualquier agente o CLI que contribuya.

Estos tres archivos deben mantenerse alineados.
