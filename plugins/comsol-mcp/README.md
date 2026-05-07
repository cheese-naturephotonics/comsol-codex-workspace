# COMSOL MCP

This repo-local plugin exposes a local MCP server for COMSOL on Windows.

## What it does

- starts a local `comsolmphserver`;
- connects a Python `mph` client that Codex can drive;
- opens `.mph` files and edits parameters;
- runs geometry, mesh, and study steps;
- exports plot groups to image files;
- launches a visible `comsolmphclient` window;
- captures screenshots of visible COMSOL windows;
- supports the browser workspace in this repository.

## Manual launch

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_comsol_mcp_server.ps1
```

## Notes

- The plugin is repo-local on purpose, so opening this repository in Codex is enough to expose it.
- The Python environment is expected at `./.venv-comsol311` and can be created by `scripts/setup_comsol_mph_env.ps1`.
- For a visible GUI session, start the COMSOL server first, then launch the Desktop client and connect it to the reported host and port if needed.
