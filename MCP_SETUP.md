# July MCP - Configuración Multi-Entorno

July MCP puede ejecutarse desde **cmd**, **PowerShell** o **WSL**. Este documento explica cómo configurarlo según tu entorno.

## Scripts disponibles

| Entorno | Script de entrada | Uso |
|---------|------------------|-----|
| Windows (cmd/PowerShell) | `start-july-mcp.cmd` | Llama a `scripts\mcp.ps1` |
| WSL / Linux / macOS | `start-july-mcp.sh` | Llama a `scripts/mcp.sh` |

## Configuración para Roo Code

### Opción 1: Windows (cmd / PowerShell)

Usa esta configuración cuando trabajes desde Windows nativo:

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

**Funciona desde:**
- VS Code en Windows
- Terminal cmd
- Terminal PowerShell

### Opción 2: WSL (Windows Subsystem for Linux)

Usa esta configuración cuando trabajes desde WSL:

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

**Funciona desde:**
- VS Code Remote - WSL
- Terminal WSL (bash)

**Nota:** Asegúrate de haber creado el entorno virtual en WSL:
```bash
cd /mnt/c/Users/sergi/Desktop/Aplicaciones/July
python3 -m venv .venv
.venv/bin/pip install -e .
```

### Opción 3: Linux / macOS nativo

Usa esta configuración en sistemas Unix nativos:

```json
{
  "mcpServers": {
    "july": {
      "command": "bash",
      "args": ["/ruta/a/July/start-july-mcp.sh"],
      "cwd": "/ruta/a/July"
    }
  }
}
```

## Dónde configurar

### Configuración Global (todos los proyectos)

**Windows:**
```
%APPDATA%\Code\User\globalStorage\rooveterinaryinc.roo-cline\settings\mcp_settings.json
```

**WSL:**
```
\\wsl$\<distro>\home\<user>\.config\Code\User\globalStorage\rooveterinaryinc.roo-cline\settings\mcp_settings.json
```

### Configuración Local (proyecto específico)

```
<proyecto>/.roo/mcp.json
```

## Cambiar entre entornos

Si trabajas indistintamente en Windows y WSL, tienes dos opciones:

1. **Configuración global diferente por entorno**: Cada entorno (Windows/WSL) tiene su propio `mcp_settings.json` con la configuración apropiada.

2. **Configuración local por proyecto**: Cada proyecto puede tener su propio `.roo/mcp.json` con la configuración del entorno donde se trabaja.

## Verificar que funciona

### Windows (PowerShell):
```powershell
.\start-july-mcp.cmd
```

### WSL (bash):
```bash
./start-july-mcp.sh
```

Si el MCP inicia correctamente, verás la salida del servidor MCP en formato JSON-RPC.

## Estructura de scripts

```
July/
├── start-july-mcp.cmd      # Entrada Windows → scripts\mcp.ps1
├── start-july-mcp.sh       # Entrada WSL/Linux → scripts/mcp.sh
└── scripts/
    ├── mcp.ps1             # MCP Windows → july.ps1 mcp
    ├── mcp.sh              # MCP WSL/Linux → july.sh mcp
    ├── july.ps1            # July Windows → .venv\Scripts\python.exe -m july
    └── july.sh             # July WSL/Linux → .venv/bin/python -m july
```

## Requisitos por entorno

| Entorno | Python | venv | Comando de setup |
|---------|--------|------|------------------|
| Windows | 3.11+ | `.venv\Scripts\python.exe` | `.\scripts\bootstrap.ps1` |
| WSL | 3.11+ | `.venv/bin/python` | `python3 -m venv .venv && .venv/bin/pip install -e .` |
