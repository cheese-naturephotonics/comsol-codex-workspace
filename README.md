# Codex COMSOL Workspace

Use Codex to control a local COMSOL session, keep the native COMSOL Desktop visible, and mirror that desktop into a browser workspace.

## What this repository includes

- a repo-local Codex plugin at `plugins/comsol-mcp`
- a local MCP server for COMSOL control
- a browser workspace that mirrors the visible COMSOL Desktop
- helper scripts for Python environment setup and desktop capture

## What users can do

- start and connect to a local COMSOL server
- open any local `.mph` model
- inspect loaded models and active parameters
- run studies from Codex
- export plots from Codex
- keep the native COMSOL Desktop visible while Codex works
- open `http://127.0.0.1:8765/` to watch a browser mirror of the COMSOL GUI

## Current platform target

- Windows
- COMSOL 5.3a installed locally
- Python 3.11 available through `py -3.11`
- Codex desktop app

## Quick start

1. Clone this repository.
2. Open the repository folder in Codex.
3. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_comsol_mph_env.ps1
```

4. Restart Codex after setup if the plugin list does not refresh automatically.
5. In Codex, use the repo-local plugin `COMSOL MCP`, or start the browser workspace with:

```powershell
.\.venv-comsol311\Scripts\python.exe .\scripts\start_comsol_workspace.py --host 127.0.0.1 --port 8765
```

6. Open:

```text
http://127.0.0.1:8765/
```

## How Codex discovers the plugin

This repository ships:

- `.agents/plugins/marketplace.json`
- `plugins/comsol-mcp/.codex-plugin/plugin.json`

That means if another user opens this repository in Codex, the plugin can be discovered as a repo-local plugin without copying files into a global plugin directory.

## Optional: install as a home-local plugin

If a user wants `COMSOL MCP` available outside this repository too:

1. copy `plugins/comsol-mcp` into `~/plugins/comsol-mcp`
2. add a matching entry to `~/.agents/plugins/marketplace.json`
3. restart Codex

The plugin bootstrap script supports:

- `COMSOL_MCP_PROJECT_ROOT` to point at a separate workspace
- `COMSOL_MCP_PYTHON` to point at an already prepared Python executable

## Repository layout

```text
.agents/plugins/marketplace.json
plugins/comsol-mcp/
scripts/
src/
webviewer/
```

## Important notes

- The browser workspace is a generic COMSOL workspace first. The `Desktop` view is the universal path for arbitrary models.
- The `Preview` view is a lightweight adapter for models that match the built-in field preview assumptions. It is optional and may not appear for every model.
- COMSOL command-line behavior varies across versions. The Desktop mirror is robust, but opening the exact same model tab inside native GUI still depends on COMSOL desktop automation details.

## Local validation used here

- Python backend import and compile checks
- local HTTP workspace at `127.0.0.1:8765`
- COMSOL Desktop mirror capture through PowerShell window capture
- browser rendering checks with Playwright

## License

MIT
