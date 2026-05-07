"""Stateful helpers for the local COMSOL MCP server."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import time
from typing import Any

from PIL import ImageGrab
import win32gui

from mph.client import Client
from mph.model import Model
from mph.server import Server

from src.comsol_mph_helper import COMSOL_MPHCLIENT_EXE, connect_client, start_server


class ComsolMcpSession:
    """Hold onto one COMSOL server/client session for MCP tool calls."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()
        self.results_dir = self.workspace_root / "results" / "comsol_mcp"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.server: Server | None = None
        self.client: Client | None = None
        self.server_host = "localhost"
        self.server_port: int | None = None
        self.active_model_name: str | None = None

    def ensure_server(self, port: int = 0, multi: bool = True) -> dict[str, object]:
        if self.server and self.server.running():
            return self.server_status()
        self.server = start_server(port=port, multi=multi)
        self.server_host = "localhost"
        self.server_port = self.server.port
        return self.server_status()

    def connect_to_server(self, port: int | None = None, host: str = "localhost") -> dict[str, object]:
        target_port = port if port is not None else self.server_port
        if target_port is None:
            raise ValueError("No COMSOL server port is known yet. Start or specify a server first.")

        if self.client and self.client.port:
            if self.client.port == target_port and self.client.host == host:
                return self.server_status()
            self.client.disconnect()

        if self.client is None:
            self.client = connect_client(target_port, host)
            self.client.caching(True)
        else:
            self.client.connect(target_port, host)

        self.server_host = host
        self.server_port = target_port
        return self.server_status()

    def disconnect(self, stop_server: bool = False) -> dict[str, object]:
        if self.client and self.client.port:
            self.client.disconnect()
        if stop_server and self.server and self.server.running():
            self.server.stop()
            self.server = None
            self.server_port = None
        return self.server_status()

    def launch_desktop_client(self) -> dict[str, object]:
        self.ensure_server()
        if not COMSOL_MPHCLIENT_EXE.exists():
            raise FileNotFoundError(f"Missing COMSOL Desktop client executable: {COMSOL_MPHCLIENT_EXE}")
        command = [str(COMSOL_MPHCLIENT_EXE)]
        if self.server_host:
            command += ["-server", self.server_host]
        if self.server_port is not None:
            command += ["-port", str(self.server_port)]
        process = subprocess.Popen(
            command,
            cwd=str(COMSOL_MPHCLIENT_EXE.parent),
        )
        return {
            "pid": process.pid,
            "server_host": self.server_host,
            "server_port": self.server_port,
            "note": (
                "If COMSOL Desktop does not auto-connect, use its server-connection dialog "
                f"and enter host '{self.server_host}' with port {self.server_port}."
            ),
        }

    def open_model(self, path: str) -> dict[str, object]:
        model_path = self._resolve_existing_path(path)
        client = self._ensure_connected_client()
        model = client.load(model_path)
        self.active_model_name = model.name()
        return self._model_summary(model)

    def list_models(self) -> dict[str, object]:
        client = self._ensure_connected_client()
        models = [{"name": model.name(), "file": str(model.file())} for model in client.models()]
        return {"models": models, "active_model": self.active_model_name}

    def model_summary(self, model_name: str | None = None, include_parameters: bool = True) -> dict[str, object]:
        model = self._resolve_model(model_name)
        return self._model_summary(model, include_parameters=include_parameters)

    def set_parameter(self, name: str, value: str, model_name: str | None = None) -> dict[str, object]:
        model = self._resolve_model(model_name)
        model.parameter(name, value)
        return {
            "model": model.name(),
            "parameter": name,
            "value": model.parameter(name),
        }

    def build_geometry(self, geometry: str | None = None, model_name: str | None = None) -> dict[str, object]:
        model = self._resolve_model(model_name)
        model.build(geometry)
        return {
            "model": model.name(),
            "geometry": geometry or "all",
            "geometries": model.geometries(),
        }

    def run_mesh(self, mesh: str | None = None, model_name: str | None = None) -> dict[str, object]:
        model = self._resolve_model(model_name)
        model.mesh(mesh)
        return {
            "model": model.name(),
            "mesh": mesh or "all",
            "meshes": model.meshes(),
        }

    def run_study(self, study: str | None = None, model_name: str | None = None) -> dict[str, object]:
        model = self._resolve_model(model_name)
        model.solve(study)
        return {
            "model": model.name(),
            "study": study or "all",
            "problems": self._safe_problems(model),
        }

    def save_model(
        self,
        path: str | None = None,
        model_name: str | None = None,
        format: str | None = None,
    ) -> dict[str, object]:
        model = self._resolve_model(model_name)
        target = self._resolve_output_path(path, default_stem=model.name(), default_suffix=".mph") if path else None
        model.save(target, format=format)
        return {
            "model": model.name(),
            "saved_to": str(target if target is not None else model.file()),
            "format": format or "Comsol",
        }

    def export_plot(self, name: str, out_path: str | None = None, model_name: str | None = None) -> dict[str, object]:
        model = self._resolve_model(model_name)
        target = self._resolve_output_path(out_path, default_stem=self._slugify(name), default_suffix=".png")

        export_node = self._find_named_child(model / "exports", name)
        if export_node is not None:
            model.export(export_node.name(), target)
        else:
            plot_node = self._find_named_child(model / "plots", name)
            if plot_node is None:
                available = model.plots()
                raise LookupError(f'No plot or export named "{name}" was found. Available plots: {available}')
            self._export_plot_group_image(model, plot_node, target)

        return {
            "model": model.name(),
            "name": name,
            "output_path": str(target),
            "bytes": target.stat().st_size if target.exists() else 0,
        }

    def capture_window(self, title_pattern: str = "COMSOL", out_path: str | None = None) -> dict[str, object]:
        target = self._resolve_output_path(out_path, default_stem="comsol_window", default_suffix=".png")
        pattern = re.compile(title_pattern, re.IGNORECASE)
        matches: list[tuple[int, str, tuple[int, int, int, int]]] = []

        def _collect(hwnd: int, _: object) -> None:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd).strip()
            if not title or not pattern.search(title):
                return
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            if right <= left or bottom <= top:
                return
            matches.append((hwnd, title, (left, top, right, bottom)))

        win32gui.EnumWindows(_collect, None)
        if not matches:
            raise LookupError(f'No visible window matched "{title_pattern}".')

        hwnd, title, rect = max(matches, key=lambda item: (item[2][2] - item[2][0]) * (item[2][3] - item[2][1]))
        image = ImageGrab.grab(bbox=rect, all_screens=True)
        image.save(target)
        return {
            "hwnd": hwnd,
            "title": title,
            "output_path": str(target),
            "width": image.width,
            "height": image.height,
        }

    def server_status(self) -> dict[str, object]:
        loaded_models: list[dict[str, str]] = []
        if self.client and self.client.port:
            loaded_models = [{"name": model.name(), "file": str(model.file())} for model in self.client.models()]
        return {
            "server_process_running": bool(self.server and self.server.running()),
            "server_host": self.server_host,
            "server_port": self.server_port,
            "client_connected": bool(self.client and self.client.port),
            "loaded_models": loaded_models,
            "active_model": self.active_model_name,
            "desktop_client_executable": str(COMSOL_MPHCLIENT_EXE),
        }

    def _ensure_connected_client(self) -> Client:
        if self.client and self.client.port:
            return self.client
        if self.server_port is None:
            self.ensure_server()
        self.connect_to_server(self.server_port, self.server_host)
        assert self.client is not None
        return self.client

    def _resolve_model(self, model_name: str | None = None) -> Model:
        client = self._ensure_connected_client()
        if model_name:
            if model_name in client.names():
                self.active_model_name = model_name
                return client / model_name
            for model in client.models():
                if str(model.file()) == model_name or model.file().stem == model_name:
                    self.active_model_name = model.name()
                    return model
            raise LookupError(f'No loaded model matches "{model_name}".')

        if self.active_model_name and self.active_model_name in client.names():
            return client / self.active_model_name

        models = client.models()
        if len(models) == 1:
            self.active_model_name = models[0].name()
            return models[0]
        if not models:
            raise LookupError("No COMSOL model is loaded yet. Open a model first.")
        raise LookupError(f"Multiple models are loaded. Choose one: {client.names()}")

    def _model_summary(self, model: Model, include_parameters: bool = True) -> dict[str, object]:
        parameters = model.parameters() if include_parameters else {}
        return {
            "name": model.name(),
            "file": str(model.file()),
            "version": model.version(),
            "modules": model.modules(),
            "geometries": model.geometries(),
            "meshes": model.meshes(),
            "studies": model.studies(),
            "datasets": model.datasets(),
            "plots": model.plots(),
            "exports": model.exports(),
            "parameters": parameters,
            "problems": self._safe_problems(model),
        }

    def _simplify_problems(self, problems: list[dict[str, Any]]) -> list[dict[str, object]]:
        simplified: list[dict[str, object]] = []
        for problem in problems:
            simplified.append({key: str(value) if key == "node" else value for key, value in problem.items()})
        return simplified

    def _safe_problems(self, model: Model) -> list[dict[str, object]]:
        try:
            return self._simplify_problems(model.problems())
        except Exception as exc:
            return [{"message": f"Problem scan unavailable in this COMSOL session: {exc}"}]

    def _resolve_existing_path(self, path: str) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.workspace_root / candidate
        candidate = candidate.resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"Path does not exist: {candidate}")
        return candidate

    def _resolve_output_path(self, path: str | None, default_stem: str, default_suffix: str) -> Path:
        if path:
            candidate = Path(path).expanduser()
            if not candidate.is_absolute():
                candidate = self.workspace_root / candidate
        else:
            stamp = time.strftime("%Y%m%d_%H%M%S")
            candidate = self.results_dir / f"{default_stem}_{stamp}{default_suffix}"
        if candidate.suffix == "":
            candidate = candidate.with_suffix(default_suffix)
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate.resolve()

    def _find_named_child(self, group: Any, name: str):
        exact = [child for child in group.children() if child.name() == name]
        if exact:
            return exact[0]
        folded = name.casefold()
        for child in group.children():
            if child.name().casefold() == folded:
                return child
        return None

    def _export_plot_group_image(self, model: Model, plot_node: Any, out_path: Path) -> None:
        export_type = self._image_export_type_for_plot(plot_node.type())
        export_list = model.java.result().export()
        tag = f"codeximg_{int(time.time() * 1000)}"
        export_list.create(tag, export_type)
        export_node = next(child for child in (model / "exports").children() if child.tag() == tag)
        export_node.property("plotgroup", plot_node.tag())

        suffix = out_path.suffix.lower()
        filename_prop, image_type = self._image_file_property_for_suffix(suffix)
        export_node.property(filename_prop, str(out_path))
        export_node.property("imagetype", image_type)
        export_node.run()
        export_list.remove(tag)

    def _image_export_type_for_plot(self, plot_type: str) -> str:
        if "3D" in plot_type:
            return "Image3D"
        if "2D" in plot_type:
            return "Image2D"
        return "Image1D"

    def _image_file_property_for_suffix(self, suffix: str) -> tuple[str, str]:
        mapping = {
            ".png": ("pngfilename", "png"),
            ".jpg": ("jpegfilename", "jpeg"),
            ".jpeg": ("jpegfilename", "jpeg"),
            ".bmp": ("bmpfilename", "bmp"),
            ".gif": ("giffilename", "gif"),
            ".tif": ("tifffilename", "tiff"),
            ".tiff": ("tifffilename", "tiff"),
            ".eps": ("epsfilename", "eps"),
        }
        if suffix not in mapping:
            raise ValueError("Unsupported image suffix. Use one of: .png, .jpg, .jpeg, .bmp, .gif, .tif, .tiff, .eps")
        return mapping[suffix]

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
        return slug or "plot"
