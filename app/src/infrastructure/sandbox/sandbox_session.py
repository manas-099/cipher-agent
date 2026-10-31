# app/src/infrastructure/sandbox/sandbox_session.py
# One persistent Docker container per agent task.
# Creates a Python venv at /opt/cipher-venv, installs project dependencies
# with the network on, then locks the network down for execution.

from __future__ import annotations

import os
import shlex
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.src.config.settings import SandboxSettings, get_settings
from app.src.infrastructure.sandbox.docker_runner import (
    CONTAINER_WORKSPACE,
    DockerRunner,
)
from app.src.logger.logger import get_logger
from app.src.ports.outbound.sandbox_port import ExecutionResult

VENV_PATH = "/opt/cipher-venv"
PYTHON_BIN = f"{VENV_PATH}/bin/python"

_IGNORED_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    ".git",
    "__pycache__",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


class SandboxSession:
    """
    A persistent sandbox for a single agent task.

    Lifecycle:
        session = SandboxSession(runner, image, workspace_root)
        session.start()          # create container + bootstrap env
        session.exec("pytest")   # run commands inside it
        session.stop()           # remove container

    Use as a context manager to guarantee cleanup:
        with SandboxSession(...) as session:
            session.exec("python app.py")
    """

    def __init__(
        self,
        runner: DockerRunner,
        image: str,
        workspace_root: str,
        *,
        settings: SandboxSettings | None = None,
    ) -> None:
        self.id = uuid.uuid4().hex
        self._runner = runner
        self._image = image
        self._settings = settings or get_settings().sandbox
        self._workspace_root = str(Path(workspace_root).resolve())
        self._logger = get_logger(__name__)

        self._container = None
        self._locked_down = False
        self.has_venv = False

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> "SandboxSession":
        if self._container is not None:
            return self

        self._container = self._runner.create_container(
            image=self._image,
            workspace_root=self._workspace_root,
            session_id=self.id,
            network_disabled=False,
        )

        try:
            self._bootstrap()
        except Exception:
            self.stop()
            raise
        else:
            if self._settings.NETWORK_DISABLED:
                self.disable_network()

        return self

    def stop(self) -> None:
        if self._container is not None:
            self._runner.remove(self._container)
            self._container = None
            self._logger.info("sandbox_session_stopped", session_id=self.id)

    def __enter__(self) -> "SandboxSession":
        return self.start()

    def __exit__(self, *_exc) -> None:
        self.stop()

    # ── execution ─────────────────────────────────────────────────────────────

    @property
    def workspace_root(self) -> str:
        return self._workspace_root

    @property
    def python_executable(self) -> str:
        return PYTHON_BIN if self.has_venv else "python3"

    def exec(
        self,
        command: str,
        *,
        timeout: int | None = None,
        workdir: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> ExecutionResult:
        if self._container is None:
            raise RuntimeError("Sandbox session is not started.")

        environment = self._environment()
        if extra_env:
            environment.update(extra_env)

        return self._runner.exec(
            self._container,
            command,
            workdir=self._container_workdir(workdir),
            environment=environment,
            timeout=timeout,
        )

    def relative_path(self, path: str) -> str:
        root = Path(self._workspace_root).resolve()
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(root)
        except ValueError as e:
            raise ValueError(
                f"Path '{path}' is outside the sandbox workspace '{root}'"
            ) from e
        posix = relative.as_posix()
        return "." if posix in ("", ".") else posix

    # ── networking ────────────────────────────────────────────────────────────

    def disable_network(self) -> None:
        if self._container is None or self._locked_down:
            return
        if not self._settings.NETWORK_DISABLED:
            return
        self._runner.disconnect_all(self._container)
        self._locked_down = True

    def enable_network(self) -> None:
        if self._container is None or not self._locked_down:
            return
        if self._runner.connect(self._container, self._settings.NETWORK_NAME):
            self._locked_down = False

    @contextmanager
    def network(self) -> Iterator[None]:
        if not self._locked_down:
            yield
            return

        self.enable_network()
        try:
            yield
        finally:
            self.disable_network()

    # ── bootstrap ─────────────────────────────────────────────────────────────

    def _bootstrap(self) -> None:
        self._logger.info("sandbox_session_bootstrap_started", session_id=self.id)

        venv_result = self._exec_raw(
            f"python3 -m venv {VENV_PATH}",
            timeout=180,
        )
        check = self._exec_raw(f"test -x {PYTHON_BIN}", timeout=10)
        self.has_venv = check.success

        if not self.has_venv:
            self._logger.warning(
                "sandbox_venv_unavailable",
                output=venv_result.output[:500],
            )
        else:
            self._exec_raw(
                f"{PYTHON_BIN} -m pip install --no-cache-dir "
                "pytest pytest-asyncio pytest-cov ruff flake8",
                timeout=600,
            )

        self._bootstrap_python_projects()
        self._bootstrap_node_projects()

        self._logger.info(
            "sandbox_session_bootstrap_finished",
            session_id=self.id,
            has_venv=self.has_venv,
        )

    def _bootstrap_python_projects(self) -> None:
        if not self.has_venv:
            return

        requirement_files = list(self._find_manifests("requirements.txt"))
        for requirement_file in requirement_files:
            relative = requirement_file.relative_to(self._workspace_root).as_posix()
            self._logger.info("sandbox_install_requirements", path=relative)
            self._exec_raw(
                f"{PYTHON_BIN} -m pip install --no-cache-dir "
                f"-r {shlex.quote(f'{CONTAINER_WORKSPACE}/{relative}')}",
                timeout=900,
            )

        project_dirs = {p.parent for p in requirement_files}
        for pyproject in self._find_manifests("pyproject.toml"):
            if pyproject.parent in project_dirs:
                continue
            relative = pyproject.parent.relative_to(self._workspace_root).as_posix()
            target = f"{CONTAINER_WORKSPACE}/{relative}" if relative else CONTAINER_WORKSPACE
            self._logger.info("sandbox_install_project", path=relative or ".")
            self._exec_raw(
                f"{PYTHON_BIN} -m pip install --no-cache-dir -e {shlex.quote(target)}",
                timeout=900,
            )

    def _bootstrap_node_projects(self) -> None:
        package_files = list(self._find_manifests("package.json"))
        for package_file in package_files:
            relative = package_file.parent.relative_to(self._workspace_root).as_posix()
            self._logger.info("sandbox_npm_install", path=relative or ".")
            self._exec_raw(
                "npm install --no-audit --no-fund",
                timeout=900,
                workdir=relative or None,
            )

    def _find_manifests(self, name: str, max_depth: int = 3):
        root = Path(self._workspace_root)
        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath)
            depth = len(current.relative_to(root).parts)
            if depth >= max_depth:
                dirnames[:] = []
            else:
                dirnames[:] = [
                    entry for entry in dirnames if entry not in _IGNORED_DIRS
                ]
            if name in filenames:
                yield current / name

    # ── helpers ───────────────────────────────────────────────────────────────

    def _exec_raw(
        self,
        command: str,
        *,
        timeout: int,
        workdir: str | None = None,
    ) -> ExecutionResult:
        return self._runner.exec(
            self._container,
            command,
            workdir=self._container_workdir(workdir),
            environment={
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "DEBIAN_FRONTEND": "noninteractive",
            },
            timeout=timeout,
        )

    def _environment(self) -> dict[str, str]:
        path_parts = ["/workspace/node_modules/.bin"]
        environment = {
            "PYTHONPATH": CONTAINER_WORKSPACE,
            "PYTHONUNBUFFERED": "1",
        }
        if self.has_venv:
            path_parts.insert(0, f"{VENV_PATH}/bin")
            environment["VIRTUAL_ENV"] = VENV_PATH
        path_parts.extend(
            ["/usr/local/sbin", "/usr/local/bin", "/usr/sbin", "/usr/bin", "/sbin", "/bin"]
        )
        environment["PATH"] = ":".join(path_parts)
        return environment

    @staticmethod
    def _container_workdir(workdir: str | None) -> str:
        if not workdir or workdir == ".":
            return CONTAINER_WORKSPACE
        if workdir.startswith("/"):
            return workdir
        return f"{CONTAINER_WORKSPACE}/{workdir}"
