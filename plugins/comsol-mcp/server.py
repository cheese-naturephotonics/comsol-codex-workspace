"""Local MCP server for driving COMSOL from Codex."""

from __future__ import annotations

from pathlib import Path
import os
import sys

from mcp.server.fastmcp import FastMCP


PLUGIN_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(os.environ.get("COMSOL_MCP_PROJECT_ROOT", PLUGIN_ROOT.parent.parent)).resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.comsol_mcp_session import ComsolMcpSession


session = ComsolMcpSession(PROJECT_ROOT)
mcp = FastMCP(
    name="COMSOL MCP",
    instructions=(
        "Control a local COMSOL 5.3a session. Prefer starting a COMSOL server, "
        "then launch a Desktop client if the user wants to watch the model update live."
    ),
)


@mcp.tool(description="Start a local COMSOL server with graphics enabled for API and Desktop clients.")
def start_comsol_server(port: int = 0) -> dict[str, object]:
    return session.ensure_server(port=port)


@mcp.tool(description="Connect the MCP bridge to an already running COMSOL server.")
def connect_comsol_server(port: int, host: str = "localhost") -> dict[str, object]:
    return session.connect_to_server(port=port, host=host)


@mcp.tool(description="Show the current COMSOL server/client status and loaded models.")
def comsol_server_status() -> dict[str, object]:
    return session.server_status()


@mcp.tool(description="Launch the visible COMSOL Desktop client so the user can watch the session.")
def launch_comsol_desktop() -> dict[str, object]:
    return session.launch_desktop_client()


@mcp.tool(description="Open a COMSOL .mph model file and make it the active model for later tool calls.")
def open_model(path: str) -> dict[str, object]:
    return session.open_model(path)


@mcp.tool(description="List all models currently loaded in the connected COMSOL session.")
def list_loaded_models() -> dict[str, object]:
    return session.list_models()


@mcp.tool(description="Summarize one loaded model, including studies, plots, meshes, and parameters.")
def model_summary(model_name: str | None = None, include_parameters: bool = True) -> dict[str, object]:
    return session.model_summary(model_name=model_name, include_parameters=include_parameters)


@mcp.tool(description="Set a COMSOL model parameter. Pass units inside the value string when needed.")
def set_parameter(name: str, value: str, model_name: str | None = None) -> dict[str, object]:
    return session.set_parameter(name=name, value=value, model_name=model_name)


@mcp.tool(description="Build a named geometry sequence, or all geometries when no name is given.")
def build_geometry(geometry: str | None = None, model_name: str | None = None) -> dict[str, object]:
    return session.build_geometry(geometry=geometry, model_name=model_name)


@mcp.tool(description="Run a named mesh sequence, or all meshes when no name is given.")
def run_mesh(mesh: str | None = None, model_name: str | None = None) -> dict[str, object]:
    return session.run_mesh(mesh=mesh, model_name=model_name)


@mcp.tool(description="Run a named COMSOL study, or all studies when no name is given.")
def run_study(study: str | None = None, model_name: str | None = None) -> dict[str, object]:
    return session.run_study(study=study, model_name=model_name)


@mcp.tool(description="Save the active COMSOL model, optionally to a new path or export format.")
def save_model(
    path: str | None = None,
    model_name: str | None = None,
    format: str | None = None,
) -> dict[str, object]:
    return session.save_model(path=path, model_name=model_name, format=format)


@mcp.tool(description="Export a named plot group to an image file, or run an existing export node by name.")
def export_plot(name: str, out_path: str | None = None, model_name: str | None = None) -> dict[str, object]:
    return session.export_plot(name=name, out_path=out_path, model_name=model_name)


@mcp.tool(description="Capture a screenshot of a visible window whose title matches the given pattern.")
def capture_window(title_pattern: str = "COMSOL", out_path: str | None = None) -> dict[str, object]:
    return session.capture_window(title_pattern=title_pattern, out_path=out_path)


@mcp.tool(description="Disconnect the API client, optionally stopping the COMSOL server started by this MCP bridge.")
def disconnect_comsol(stop_server: bool = False) -> dict[str, object]:
    return session.disconnect(stop_server=stop_server)


if __name__ == "__main__":
    mcp.run()
