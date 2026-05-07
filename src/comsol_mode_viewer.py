"""Generic local browser workspace for COMSOL Desktop and model sessions."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
import argparse
import atexit
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time

import numpy as np

from src.comsol_mph_helper import COMSOL_BIN, COMSOL_MPHCLIENT_EXE, connect_client, start_server


FIELD_SPECS: dict[str, dict[str, str]] = {
    "normE": {
        "expression": "ewfd.normE",
        "label": "|E|",
        "mode": "magnitude",
    },
    "reEx": {
        "expression": "real(ewfd.Ex)",
        "label": "Re(Ex)",
        "mode": "signed",
    },
    "reEy": {
        "expression": "real(ewfd.Ey)",
        "label": "Re(Ey)",
        "mode": "signed",
    },
    "reEz": {
        "expression": "real(ewfd.Ez)",
        "label": "Re(Ez)",
        "mode": "signed",
    },
}

DEFAULT_PLOT_NAMES = (
    "Electric Field (ewfd)",
    "Transverse Electric Field",
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "item"


def is_ascii_path(path: Path) -> bool:
    return all(ord(char) < 128 for char in str(path))


def as_float_list(values: np.ndarray) -> list[float]:
    array = np.asarray(values, dtype=float)
    array = np.nan_to_num(array, nan=0.0, posinf=0.0, neginf=0.0)
    return array.tolist()


def summarize_values(values: np.ndarray) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    array = np.nan_to_num(array, nan=0.0, posinf=0.0, neginf=0.0)
    if array.size == 0:
        return {"min": 0.0, "max": 0.0}
    return {
        "min": float(array.min()),
        "max": float(array.max()),
    }


@dataclass
class ViewerConfig:
    model_path: Path | None
    host: str
    port: int
    workspace_root: Path
    web_root: Path


class ComsolModeViewerService:
    """Manage one COMSOL server/client session for the browser workspace."""

    def __init__(self, config: ViewerConfig):
        self.config = config
        self.stage_dir = self.config.workspace_root / "results" / "comsol_mode_viewer" / "staged_models"
        self.output_dir = self.config.workspace_root / "results" / "comsol_mode_viewer"
        self.desktop_image_path = self.output_dir / "comsol_desktop_live.png"
        self.desktop_capture_script = self.config.workspace_root / "scripts" / "capture_comsol_window.ps1"
        self.desktop_open_script = self.config.workspace_root / "scripts" / "open_comsol_model_in_desktop.ps1"
        self.stage_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.server = None
        self.client = None
        self.lock = threading.Lock()
        self.latest_payload: dict[str, Any] | None = None
        self.latest_desktop_payload: dict[str, Any] | None = None
        self.active_model_name: str | None = None
        self.model_source_paths: dict[str, str] = {}
        self.model_loaded_paths: dict[str, str] = {}
        self.default_model_loaded = False

    def shutdown(self) -> None:
        with self.lock:
            try:
                if self.client and self.client.port:
                    self.client.disconnect()
            except Exception:
                pass
            finally:
                self.client = None
            try:
                if self.server and self.server.running():
                    self.server.stop()
            except Exception:
                pass
            finally:
                self.server = None

    def payload(self) -> dict[str, Any]:
        with self.lock:
            self.latest_payload = self._refresh_payload(solve=False, parameter_overrides={})
            return self.latest_payload

    def rerun(self, parameter_overrides: dict[str, str] | None, solve: bool) -> dict[str, Any]:
        with self.lock:
            self.latest_payload = self._refresh_payload(
                solve=solve,
                parameter_overrides=parameter_overrides or {},
            )
            return self.latest_payload

    def open_model(self, path: str) -> dict[str, Any]:
        with self.lock:
            model_path = self._resolve_existing_path(path)
            self._ensure_client()
            self._load_model_path(model_path)
            self._sync_desktop_to_model(model_path)
            self.latest_payload = self._refresh_payload(solve=False, parameter_overrides={})
            return self.latest_payload

    def activate_model(self, model_name: str) -> dict[str, Any]:
        with self.lock:
            model = self._resolve_model(model_name)
            self.active_model_name = model.name()
            source_path = self.model_source_paths.get(model.name())
            if source_path:
                self._sync_desktop_to_model(Path(source_path))
            self.latest_payload = self._refresh_payload(solve=False, parameter_overrides={})
            return self.latest_payload

    def desktop_status(self, refresh: bool = True) -> dict[str, Any]:
        with self.lock:
            if refresh or self.latest_desktop_payload is None:
                self.latest_desktop_payload = self._capture_desktop_window()
            return self.latest_desktop_payload

    def _refresh_payload(self, solve: bool, parameter_overrides: dict[str, str]) -> dict[str, Any]:
        self._ensure_client()
        self._maybe_load_default_model()
        model = self._resolve_model(allow_none=True)
        if model is not None:
            changed = self._apply_parameters(model, parameter_overrides)
            if changed:
                model.build()
                model.mesh()
            if solve or changed:
                model.solve()
        payload = self._build_payload(model)
        payload_path = self.output_dir / "latest_payload.json"
        payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def _ensure_client(self) -> None:
        if self.client is not None and self.client.port:
            return
        if self.server is None or not self.server.running():
            self.server = start_server(port=0, multi="on")
        self.client = connect_client(self.server.port, "localhost")
        self.client.caching(True)

    def _maybe_load_default_model(self) -> None:
        if self.default_model_loaded:
            return
        self.default_model_loaded = True
        if self.config.model_path is None:
            return
        if not self.config.model_path.exists():
            return
        if self.client is None:
            return
        if self.client.models():
            return
        self._load_model_path(self.config.model_path)

    def _loaded_models(self) -> list[dict[str, str]]:
        if self.client is None or not self.client.port:
            return []
        models: list[dict[str, str]] = []
        for model in self.client.models():
            file_path = str(model.file())
            models.append(
                {
                    "name": model.name(),
                    "file": file_path,
                    "sourcePath": self.model_source_paths.get(model.name(), file_path),
                }
            )
        return models

    def _resolve_model(self, model_name: str | None = None, allow_none: bool = False):
        if self.client is None or not self.client.port:
            if allow_none:
                return None
            raise LookupError("COMSOL client is not connected.")
        if model_name:
            if model_name in self.client.names():
                self.active_model_name = model_name
                return self.client / model_name
            for model in self.client.models():
                if str(model.file()) == model_name or Path(str(model.file())).stem == model_name:
                    self.active_model_name = model.name()
                    return model
            if allow_none:
                return None
            raise LookupError(f'No loaded model matches "{model_name}".')
        if self.active_model_name and self.active_model_name in self.client.names():
            return self.client / self.active_model_name
        models = self.client.models()
        if not models:
            if allow_none:
                return None
            raise LookupError("No COMSOL model is loaded yet.")
        self.active_model_name = models[0].name()
        return models[0]

    def _resolve_existing_path(self, path: str) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.config.workspace_root / candidate
        candidate = candidate.resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"Path does not exist: {candidate}")
        return candidate

    def _stage_model(self, source_path: Path) -> Path:
        source_path = source_path.resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Model path does not exist: {source_path}")
        if is_ascii_path(source_path):
            return source_path
        digest = hashlib.sha1(str(source_path).encode("utf-8")).hexdigest()[:10]
        target_name = f"{slugify(source_path.stem)}_{digest}{source_path.suffix}"
        target_path = self.stage_dir / target_name
        if (
            not target_path.exists()
            or source_path.stat().st_mtime_ns > target_path.stat().st_mtime_ns
            or source_path.stat().st_size != target_path.stat().st_size
        ):
            shutil.copy2(source_path, target_path)
        return target_path

    def _load_model_path(self, source_path: Path):
        if self.client is None:
            raise RuntimeError("COMSOL client is not ready.")
        staged_path = self._stage_model(source_path)
        model = self.client.load(staged_path)
        self.active_model_name = model.name()
        self.model_source_paths[model.name()] = str(source_path)
        self.model_loaded_paths[model.name()] = str(staged_path)
        return model

    def _apply_parameters(self, model, parameter_overrides: dict[str, str]) -> bool:
        if not parameter_overrides:
            return False
        current_parameters = model.parameters()
        changed = False
        for name, raw_value in parameter_overrides.items():
            if name not in current_parameters:
                continue
            value = str(raw_value).strip()
            if not value or current_parameters[name] == value:
                continue
            model.parameter(name, value)
            changed = True
        return changed

    def _build_payload(self, model) -> dict[str, Any]:
        loaded_models = self._loaded_models()
        active_model = model.name() if model is not None else None
        preview = self._build_preview_payload(model)
        return {
            "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
            "server": {
                "host": "localhost",
                "port": self.server.port if self.server is not None else None,
            },
            "session": {
                "desktopClientExecutable": str(COMSOL_MPHCLIENT_EXE),
                "desktopRunning": self._desktop_client_running(),
                "loadedModels": loaded_models,
                "activeModel": active_model,
            },
            "model": self._build_model_summary(model) if model is not None else None,
            "preview": preview,
        }

    def _build_model_summary(self, model) -> dict[str, Any]:
        return {
            "name": model.name(),
            "file": self.model_source_paths.get(model.name(), str(model.file())),
            "loadedPath": self.model_loaded_paths.get(model.name(), str(model.file())),
            "version": model.version(),
            "modules": model.modules(),
            "datasets": model.datasets(),
            "plots": model.plots(),
            "studies": model.studies(),
            "geometries": model.geometries(),
            "meshes": model.meshes(),
            "exports": model.exports(),
            "parameters": model.parameters(),
            "problems": self._safe_problems(model),
        }

    def _build_preview_payload(self, model) -> dict[str, Any]:
        if model is None:
            return {
                "available": False,
                "reason": "No model is loaded yet. Open any .mph file to start.",
            }
        try:
            datasets = model.datasets()
            dataset_name = next((name for name in datasets if "Solution 1" in name), datasets[0])
            inner_indices, inner_values = model.inner(dataset_name)
            expressions = ["x", "y"] + [spec["expression"] for spec in FIELD_SPECS.values()]
            units = ["um", "um"] + [None] * len(FIELD_SPECS)
            values = model.evaluate(expressions, unit=units, dataset=dataset_name)
            x_values = np.asarray(values[0], dtype=float)
            y_values = np.asarray(values[1], dtype=float)
            field_values = {
                key: np.asarray(values[index + 2], dtype=float)
                for index, key in enumerate(FIELD_SPECS)
            }
            if x_values.ndim == 1:
                x_values = x_values[np.newaxis, :]
                y_values = y_values[np.newaxis, :]
                field_values = {key: array[np.newaxis, :] for key, array in field_values.items()}

            x_um = np.asarray(x_values[0], dtype=float)
            y_um = np.asarray(y_values[0], dtype=float)
            solutions: list[dict[str, Any]] = []
            for mode_index in range(x_values.shape[0]):
                mode_fields: dict[str, Any] = {}
                for key, array in field_values.items():
                    mode_array = np.asarray(array[mode_index], dtype=float)
                    mode_fields[key] = {
                        "values": as_float_list(mode_array),
                        "stats": summarize_values(mode_array),
                    }
                solutions.append(
                    {
                        "modeIndex": int(inner_indices[mode_index]) if mode_index < len(inner_indices) else mode_index + 1,
                        "modeValue": float(inner_values[mode_index]) if mode_index < len(inner_values) else 0.0,
                        "fields": mode_fields,
                    }
                )

            return {
                "available": True,
                "fieldSpecs": {
                    key: {
                        "label": spec["label"],
                        "mode": spec["mode"],
                    }
                    for key, spec in FIELD_SPECS.items()
                },
                "geometry": {
                    "xUm": as_float_list(x_um),
                    "yUm": as_float_list(y_um),
                    "boundsUm": {
                        "xMin": float(x_um.min()) if x_um.size else 0.0,
                        "xMax": float(x_um.max()) if x_um.size else 0.0,
                        "yMin": float(y_um.min()) if y_um.size else 0.0,
                        "yMax": float(y_um.max()) if y_um.size else 0.0,
                    },
                },
                "solutions": solutions,
                "plots": self._export_plots(model),
            }
        except Exception as exc:
            return {
                "available": False,
                "reason": (
                    "The current model does not match the built-in field preview adapter yet. "
                    f"Use Desktop view for full COMSOL GUI access. Details: {exc}"
                ),
            }

    def _export_plots(self, model) -> list[dict[str, str]]:
        exported: list[dict[str, str]] = []
        for plot_name in DEFAULT_PLOT_NAMES:
            if plot_name not in model.plots():
                continue
            out_path = self.output_dir / f"{slugify(plot_name)}.txt"
            self._export_plot_group_data(model, plot_name, out_path)
            exported.append(
                {
                    "name": plot_name,
                    "dataPath": f"/artifacts/{out_path.name}",
                }
            )
        return exported

    def _find_named_child(self, group: Any, name: str):
        exact = [child for child in group.children() if child.name() == name]
        if exact:
            return exact[0]
        folded = name.casefold()
        for child in group.children():
            if child.name().casefold() == folded:
                return child
        return None

    def _export_plot_group_data(self, model, plot_name: str, out_path: Path) -> None:
        plot_node = self._find_named_child(model / "plots", plot_name)
        if plot_node is None:
            raise LookupError(f'No plot named "{plot_name}" was found.')
        export_list = model.java.result().export()
        tag = f"viewerplot_{int(time.time() * 1000)}"
        export_list.create(tag, "Plot")
        export_node = next(child for child in (model / "exports").children() if child.tag() == tag)
        export_node.property("plotgroup", plot_node.tag())
        export_node.property("filename", str(out_path))
        export_node.run()
        export_list.remove(tag)

    def _simplify_problems(self, problems: list[dict[str, Any]]) -> list[dict[str, object]]:
        simplified: list[dict[str, object]] = []
        for problem in problems:
            simplified.append({key: str(value) if key == "node" else value for key, value in problem.items()})
        return simplified

    def _safe_problems(self, model) -> list[dict[str, object]]:
        try:
            return self._simplify_problems(model.problems())
        except Exception as exc:
            return [{"message": f"Problem scan unavailable in this COMSOL session: {exc}"}]

    def _desktop_client_running(self) -> bool:
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            (
                "Get-Process | "
                "Where-Object { ($_.ProcessName -eq 'comsolmphclient' -or $_.ProcessName -eq 'comsol') -and $_.MainWindowHandle -ne 0 } | "
                "Select-Object -First 1 -ExpandProperty Id"
            ),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        return bool(result.stdout.strip())

    def _ensure_desktop_client(self, timeout: int = 45) -> None:
        self._ensure_client()
        if self._desktop_client_running():
            return
        if not COMSOL_MPHCLIENT_EXE.exists():
            raise FileNotFoundError(f"COMSOL Desktop executable was not found: {COMSOL_MPHCLIENT_EXE}")
        subprocess.Popen(
            [
                str(COMSOL_MPHCLIENT_EXE),
                "-server",
                "localhost",
                "-port",
                str(self.server.port),
            ],
            cwd=str(COMSOL_BIN),
        )
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            if self._desktop_client_running():
                return
            time.sleep(1.0)
        raise TimeoutError("COMSOL Desktop did not expose a visible window within the time limit.")

    def _capture_desktop_window(self) -> dict[str, Any]:
        self._ensure_desktop_client()
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.desktop_capture_script),
            "-OutPath",
            str(self.desktop_image_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "Unknown desktop capture error."
            raise RuntimeError(message)
        payload = json.loads(result.stdout)
        payload["imagePath"] = f"/artifacts/{self.desktop_image_path.name}"
        payload["available"] = True
        return payload

    def _sync_desktop_to_model(self, model_path: Path) -> None:
        self._ensure_desktop_client()
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.desktop_open_script),
            "-ModelPath",
            str(model_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "Unknown COMSOL Desktop open-model error."
            raise RuntimeError(message)


class ViewerRequestHandler(SimpleHTTPRequestHandler):
    """Serve the generic COMSOL workspace plus JSON endpoints."""

    service: ComsolModeViewerService
    static_root: Path
    artifact_root: Path

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.static_root), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self._send_json(HTTPStatus.OK, self.service.payload())
            return
        if parsed.path == "/api/desktop/status":
            refresh = parse_qs(parsed.query).get("refresh", ["1"])[0] != "0"
            try:
                payload = self.service.desktop_status(refresh=refresh)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"available": False, "error": str(exc)})
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        if parsed.path.startswith("/artifacts/"):
            self._serve_artifact(parsed.path.removeprefix("/artifacts/"))
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("content-length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Invalid JSON body: {exc}"})
            return

        try:
            if parsed.path == "/api/run":
                result = self.service.rerun(
                    parameter_overrides=payload.get("parameters") or {},
                    solve=bool(payload.get("solve", False)),
                )
            elif parsed.path == "/api/model/open":
                result = self.service.open_model(str(payload.get("path", "")).strip())
            elif parsed.path == "/api/model/activate":
                result = self.service.activate_model(str(payload.get("model", "")).strip())
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.OK, result)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_artifact(self, relative_name: str) -> None:
        safe_name = os.path.basename(relative_name)
        target = (self.artifact_root / safe_name).resolve()
        if not target.exists() or self.artifact_root.resolve() not in target.parents:
            self.send_error(HTTPStatus.NOT_FOUND, "Artifact not found")
            return
        self.path = "/" + safe_name
        original = self.directory
        try:
            self.directory = str(self.artifact_root)
            super().do_GET()
        finally:
            self.directory = original


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local COMSOL workspace.")
    parser.add_argument("--model", default=None, help="Optional .mph file to load on startup.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind the viewer server to.")
    parser.add_argument("--port", default=8765, type=int, help="Port to bind the viewer server to.")
    return parser


def run_server(config: ViewerConfig) -> None:
    service = ComsolModeViewerService(config)
    atexit.register(service.shutdown)

    class BoundHandler(ViewerRequestHandler):
        pass

    BoundHandler.service = service
    BoundHandler.static_root = config.web_root
    BoundHandler.artifact_root = service.output_dir

    httpd = ThreadingHTTPServer((config.host, config.port), BoundHandler)
    print(f"COMSOL workspace listening on http://{config.host}:{config.port}")
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        service.shutdown()


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = ViewerConfig(
        model_path=Path(args.model).resolve() if args.model else None,
        host=args.host,
        port=args.port,
        workspace_root=root,
        web_root=root / "webviewer",
    )
    run_server(config)


if __name__ == "__main__":
    main()
