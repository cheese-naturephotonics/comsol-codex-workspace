"""Helpers to make the third-party `mph` package work with this local COMSOL.

The installed COMSOL 5.3a launcher does not expose the Java VM path in a form
that `mph.discovery.find_backends()` can parse automatically, so we register
the backend explicitly.
"""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator
import faulthandler
import os
import re
import shutil
import subprocess
import time

import jpype
import mph
from mph import discovery
from mph.client import Client


COMSOL_ROOT_ENV_VARS = ("COMSOL_MCP_COMSOL_ROOT", "COMSOL_ROOT")


def _installation_from_executable(executable: str | None) -> Path | None:
    if not executable:
        return None
    path = Path(executable).resolve()
    if path.name.lower() not in {"comsol.exe", "comsolmphserver.exe", "comsolmphclient.exe"}:
        return None
    parents = path.parents
    if len(parents) < 3:
        return None
    root = parents[2]
    return root if root.name == "Multiphysics" else None


def _common_install_roots() -> list[Path]:
    roots: list[Path] = []
    for base_env in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        base = os.environ.get(base_env)
        if not base:
            continue
        comsol_dir = Path(base) / "COMSOL"
        if not comsol_dir.exists():
            continue
        roots.extend(sorted(comsol_dir.glob("COMSOL*/Multiphysics"), reverse=True))
    return roots


@lru_cache(maxsize=1)
def _resolve_comsol_root() -> Path:
    for env_var in COMSOL_ROOT_ENV_VARS:
        configured = os.environ.get(env_var)
        if configured:
            candidate = Path(configured).expanduser()
            if candidate.exists():
                return candidate

    for command in ("comsolmphserver.exe", "comsol.exe", "comsolmphclient.exe"):
        candidate = _installation_from_executable(shutil.which(command))
        if candidate and candidate.exists():
            return candidate

    for candidate in _common_install_roots():
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Unable to locate a local COMSOL installation. Set COMSOL_MCP_COMSOL_ROOT "
        "or COMSOL_ROOT to the COMSOL Multiphysics installation directory."
    )


@lru_cache(maxsize=1)
def _comsol_paths() -> dict[str, Path]:
    root = _resolve_comsol_root()
    bin_dir = root / "bin" / "win64"
    return {
        "root": root,
        "bin": bin_dir,
        "comsol": bin_dir / "comsol.exe",
        "server": bin_dir / "comsolmphserver.exe",
        "client": bin_dir / "comsolmphclient.exe",
        "jvm": root / "java" / "win64" / "jre" / "bin" / "server" / "jvm.dll",
    }


class LocalServer:
    """Minimal server handle compatible with the subset used by this repo."""

    def __init__(self, process: subprocess.Popen[str], port: int, cores: int | None = None):
        self.process = process
        self.port = port
        self.cores = cores
        self.version = "5.3a"

    def running(self) -> bool:
        return self.process.poll() is None

    def stop(self, timeout: int = 20) -> None:
        if not self.running():
            return
        try:
            self.process.communicate(input="close", timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()


def _parse_server_port(line: str) -> int | None:
    match = re.match(r"^COMSOL.* \(.*\) .*?(\d{4,5}).*$", line)
    return int(match.group(1)) if match else None


def local_backend() -> discovery.Backend:
    paths = _comsol_paths()
    missing = [path for path in (paths["root"], paths["comsol"], paths["server"], paths["jvm"]) if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing COMSOL components: {missing}")
    return {
        "name": "5.3a",
        "major": 5,
        "minor": 3,
        "patch": 1,
        "build": 0,
        "root": paths["root"],
        "jvm": paths["jvm"],
        "server": [paths["server"]],
    }


def configure_environment() -> None:
    """Prepend COMSOL executables to PATH for this process."""
    paths = _comsol_paths()
    parts = [str(paths["bin"]), str(paths["jvm"].parent.parent)]
    current = os.environ.get("PATH", "")
    prefix = os.pathsep.join(parts)
    if prefix not in current:
        os.environ["PATH"] = prefix + os.pathsep + current


def _prepare_jvm_environment(backend: discovery.Backend) -> None:
    """Mirror the environment fixes that `mph` normally applies on Windows."""
    configure_environment()
    if discovery.system == "Windows" and faulthandler.is_enabled():
        faulthandler.disable()
    if discovery.system == "Windows":
        jre = Path(backend["jvm"]).parent.parent
        current = os.environ.get("PATH", "")
        prefix = str(jre)
        if prefix not in current:
            os.environ["PATH"] = prefix + os.pathsep + current


@contextmanager
def patched_mph_backend() -> Iterator[None]:
    """Temporarily override `mph.discovery.find_backends()` with a local backend."""
    configure_environment()
    backend = local_backend()
    original = discovery.find_backends

    def _find_backends():
        return [backend]

    discovery.find_backends = _find_backends
    try:
        yield
    finally:
        discovery.find_backends = original


def start_client(
    cores: int | None = None,
    session: str = "stand-alone",
):
    """Start `mph` with the local COMSOL backend patched in."""
    with patched_mph_backend():
        mph.option("session", session)
        return mph.start(cores=cores, version="5.3a")


def start_server(
    cores: int | None = None,
    port: int = 0,
    multi: bool | str = True,
    timeout: int = 60,
    arguments: list[str] | None = None,
) -> LocalServer:
    """Start a local COMSOL server process using the patched 5.3a backend."""
    configure_environment()
    extra_arguments = list(arguments) if arguments else []
    server_multi: bool | str
    if multi is True:
        server_multi = "on"
    elif multi is False:
        server_multi = "off"
    else:
        server_multi = multi
    command = [
        str(_comsol_paths()["server"]),
        "-login",
        "never",
        "-autosave",
        "off",
    ]
    if cores:
        command += ["-np", str(cores)]
    if port is not None:
        command += ["-port", str(port)]
    if server_multi:
        command += ["-multi", "on" if server_multi in (True, "on") else "off"]
    command += extra_arguments

    process = subprocess.Popen(
        command,
        cwd=str(_comsol_paths()["bin"]),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="ignore",
    )

    requested = port
    lines: list[str] = []
    detected_port: int | None = None
    start_time = time.monotonic()

    while process.poll() is None:
        assert process.stdout is not None
        line = process.stdout.readline().strip()
        if line:
            lines.append(line)
        detected_port = _parse_server_port(line)
        if detected_port is not None:
            break
        if time.monotonic() - start_time > timeout:
            raise TimeoutError("Server failed to start within time-out period.")

    if detected_port is None:
        last_line = lines[-1] if lines else "no server output"
        raise RuntimeError(f"Starting server failed: {last_line}")
    if requested and detected_port != requested:
        raise RuntimeError(f"Server port is {detected_port}, but {requested} was requested.")
    return LocalServer(process=process, port=detected_port, cores=cores)


def connect_client(port: int, host: str = "localhost") -> Client:
    """Connect an `mph.Client` to a running COMSOL server.

    COMSOL 5.3a on this machine ships the Java API jars under `plugins/`
    instead of the `apiplugins/` directory that newer `mph` releases assume
    for remote sessions, so we bootstrap the JVM manually and then wrap
    `ModelUtil` in a lightweight `mph.Client` instance.
    """
    backend = local_backend()
    _prepare_jvm_environment(backend)
    if not jpype.isJVMStarted():
        jpype.startJVM(
            str(backend["jvm"]),
            classpath=str(Path(backend["root"]) / "plugins" / "*"),
        )
    from com.comsol.model.util import ModelUtil as java

    client = object.__new__(Client)
    client.version = backend["name"]
    client.standalone = False
    client.port = None
    client.host = None
    client.java = java
    client.connect(port, host)
    return client
