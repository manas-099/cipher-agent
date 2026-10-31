# app/src/infrastructure/sandbox/docker_runner.py
# Low-level Docker engine for the persistent sandbox session.
# Owns container lifecycle, exec, network lockdown, output capture, cleanup.
# Knows nothing about Python/Node/Bash — adapters build the command strings.

from __future__ import annotations

import time
from pathlib import Path

# pyrefly: ignore[missing-import]
import docker
from docker.errors import DockerException, ImageNotFound

from app.src.config.settings import SandboxSettings, get_settings
from app.src.logger.logger import get_logger
from app.src.ports.outbound.sandbox_port import ExecutionResult

CONTAINER_WORKSPACE = "/workspace"


class DockerRunner:
    """
    Docker operations shared by every sandbox session.

    One container is created per agent task (managed by SandboxSession).
    This class only creates/execs/removes that container and enforces limits.
    """

    def __init__(self, settings: SandboxSettings | None = None) -> None:
        self._settings = settings or get_settings().sandbox
        self._logger = get_logger(__name__)
        self._client = self._connect()

    def _connect(self):
        try:
            client = docker.from_env()
            client.ping()
            self._logger.info("docker_runner_connected")
            return client
        except DockerException as e:
            self._logger.error("docker_runner_unavailable", error=str(e))
            return None

    @property
    def available(self) -> bool:
        return self._client is not None

    # ── container lifecycle ───────────────────────────────────────────────────

    def create_container(
        self,
        image: str,
        workspace_root: str,
        session_id: str,
        *,
        network_disabled: bool = False,
    ) -> "docker.models.containers.Container":
        if self._client is None:
            raise RuntimeError("Docker daemon is not available.")

        create_kwargs: dict = {
            "image": image,
            "command": ["sleep", "infinity"],
            "detach": True,
            "working_dir": CONTAINER_WORKSPACE,
            "network_disabled": network_disabled,
            "mem_limit": f"{self._settings.MEMORY_LIMIT_MB}m",
            "nano_cpus": int(self._settings.CPU_LIMIT * 1_000_000_000),
            "pids_limit": self._settings.PIDS_LIMIT,
            "security_opt": ["no-new-privileges"],
            "volumes": {
                str(Path(workspace_root).resolve()): {
                    "bind": CONTAINER_WORKSPACE,
                    "mode": "rw",
                }
            },
            "labels": {"cipher.session": session_id},
        }
        if self._settings.DROP_CAPABILITIES:
            create_kwargs["cap_drop"] = ["ALL"]
            create_kwargs["cap_add"] = [
                "CHOWN",
                "DAC_OVERRIDE",
                "FOWNER",
                "SETUID",
                "SETGID",
            ]

        try:
            container = self._client.containers.create(**create_kwargs)
            container.start()
        except ImageNotFound:
            self._logger.error("sandbox_image_not_found", image=image)
            raise
        except DockerException as e:
            self._logger.error("sandbox_container_create_failed", image=image, error=str(e))
            raise

        self._logger.info(
            "sandbox_session_container_started",
            session_id=session_id,
            image=image,
            workspace_root=workspace_root,
        )
        return container

    def remove(self, container) -> None:
        try:
            container.stop(timeout=2)
        except Exception:
            pass
        try:
            container.remove(force=True)
        except Exception:
            pass

    # ── command execution ─────────────────────────────────────────────────────

    def exec(
        self,
        container,
        command: str,
        *,
        workdir: str | None = None,
        environment: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        start = time.monotonic()
        timeout = max(int(timeout or self._settings.TIMEOUT_SECONDS), 1)

        cmd = [
            "timeout",
            "--signal=KILL",
            f"{timeout}s",
            "bash",
            "-c",
            command,
        ]

        try:
            result = container.exec_run(
                cmd=cmd,
                workdir=workdir or CONTAINER_WORKSPACE,
                environment=environment or {},
                demux=False,
            )
            exit_code = int(result.exit_code) if result.exit_code is not None else -1
            raw = result.output

            if isinstance(raw, bytes):
                stdout, stderr = self._demux(raw)
            elif isinstance(raw, tuple):
                stdout = self._to_text(raw[0])
                stderr = self._to_text(raw[1])
            else:
                stdout = self._to_text(raw)
                stderr = ""

            timed_out = exit_code in (124, 137)
            if timed_out:
                stderr = f"{stderr}\nExecution timed out after {timeout}s".strip()

            stdout = self._truncate(stdout)
            stderr = self._truncate(stderr)

            duration = time.monotonic() - start
            self._logger.info(
                "sandbox_exec_finished",
                exit_code=exit_code,
                timed_out=timed_out,
                duration_seconds=round(duration, 3),
                workdir=workdir,
            )
            return ExecutionResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                timed_out=timed_out,
                duration_seconds=duration,
            )

        except DockerException as e:
            self._logger.error("sandbox_exec_failed", error=str(e))
            return self._error(f"Docker exec failed: {e}", start)
        except Exception as e:
            self._logger.error("sandbox_exec_unexpected_error", error=str(e))
            return self._error(f"Sandbox exec error: {e}", start)

    # ── networking ────────────────────────────────────────────────────────────

    def network_names(self, container) -> list[str]:
        try:
            container.reload()
        except Exception:
            pass
        networks = (
            container.attrs.get("NetworkSettings", {}).get("Networks", {}) or {}
        )
        return list(networks.keys())

    def disconnect_all(self, container) -> list[str]:
        if self._client is None:
            return []
        names = self.network_names(container)
        disconnected: list[str] = []
        for name in names:
            try:
                network = self._client.networks.get(name)
                network.disconnect(container, force=True)
                disconnected.append(name)
            except DockerException as e:
                self._logger.warning(
                    "sandbox_network_disconnect_failed",
                    network=name,
                    error=str(e),
                )
        if disconnected:
            self._logger.info("sandbox_network_locked_down", networks=disconnected)
        return disconnected

    def connect(self, container, network_name: str) -> bool:
        if self._client is None:
            return False
        try:
            network = self._client.networks.get(network_name)
            network.connect(container)
            self._logger.info("sandbox_network_enabled", network=network_name)
            return True
        except DockerException as e:
            self._logger.warning(
                "sandbox_network_enable_failed",
                network=network_name,
                error=str(e),
            )
            return False

    # ── output helpers ────────────────────────────────────────────────────────

    def _truncate(self, text: str) -> str:
        limit = self._settings.MAX_OUTPUT_CHARS
        if limit <= 0 or len(text) <= limit:
            return text
        removed = len(text) - limit
        return f"{text[:limit]}\n... [truncated {removed} chars]"

    @staticmethod
    def _to_text(value) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    @staticmethod
    def _demux(raw: bytes) -> tuple[str, str]:
        """
        Non-TTY Docker streams are framed:
        [stream_type:1][0:3][size:4 big-endian][payload:size]
        stream_type 1 = stdout, 2 = stderr.
        Falls back to all-stdout if the data is not framed.
        """
        if not raw:
            return "", ""

        stdout: list[bytes] = []
        stderr: list[bytes] = []
        offset = 0
        parsed_any = False

        while offset + 8 <= len(raw):
            stream_type = raw[offset]
            size = int.from_bytes(raw[offset + 4:offset + 8], "big")
            if stream_type not in (0, 1, 2) or offset + 8 + size > len(raw):
                break
            payload = raw[offset + 8:offset + 8 + size]
            offset += 8 + size
            parsed_any = True
            if stream_type == 2:
                stderr.append(payload)
            else:
                stdout.append(payload)

        if not parsed_any:
            return raw.decode("utf-8", errors="replace"), ""

        return (
            b"".join(stdout).decode("utf-8", errors="replace"),
            b"".join(stderr).decode("utf-8", errors="replace"),
        )

    def _error(self, message: str, start: float) -> ExecutionResult:
        return ExecutionResult(
            stdout="",
            stderr=message,
            exit_code=-1,
            timed_out=False,
            duration_seconds=time.monotonic() - start,
        )
