# app/src/infrastructure/sandbox/lazy_sandbox.py
# SandboxPort wrapper that defers container creation until the first
# execution call. Lets the API start (and serve file-only tasks) without
# requiring Docker to be reachable at startup.

from __future__ import annotations

import threading

from app.src.infrastructure.sandbox.sandbox_factory import (
    RoutingSandbox,
    SandboxFactory,
)
from app.src.ports.outbound.sandbox_port import (
    ExecutionResult,
    LintResult,
    SandboxLanguage,
    SandboxPort,
    TestResult,
)

__all__ = ["LazySandbox"]


class LazySandbox(SandboxPort):
    """Creates one RoutingSandbox on first use, then reuses it."""

    def __init__(
        self,
        factory: SandboxFactory,
        *,
        workspace_root: str | None = None,
    ) -> None:
        self._factory = factory
        self._workspace_root = workspace_root
        self._router: RoutingSandbox | None = None
        self._lock = threading.Lock()

    def _get_router(self) -> RoutingSandbox:
        with self._lock:
            if self._router is None:
                self._router = self._factory.create_router(
                    workspace_root=self._workspace_root
                )
            return self._router

    def run_code(
        self,
        file_path: str,
        language: SandboxLanguage,
        timeout: int = 30,
        args: list[str] | None = None,
    ) -> ExecutionResult:
        return self._get_router().run_code(file_path, language, timeout, args)

    def run_command(
        self,
        command: str,
        language: SandboxLanguage,
        working_dir: str | None = None,
        timeout: int = 30,
    ) -> ExecutionResult:
        return self._get_router().run_command(
            command, language, working_dir, timeout
        )

    def run_tests(
        self,
        path: str,
        framework: str = "auto",
        test_file: str | None = None,
        timeout: int = 60,
    ) -> TestResult:
        return self._get_router().run_tests(path, framework, test_file, timeout)

    def lint_code(
        self,
        path: str,
        linter: str = "auto",
        fix: bool = False,
    ) -> LintResult:
        return self._get_router().lint_code(path, linter, fix)

    def install_package(
        self,
        package: str,
        manager: str = "auto",
        version: str | None = None,
    ) -> ExecutionResult:
        return self._get_router().install_package(package, manager, version)

    @property
    def started(self) -> bool:
        return self._router is not None

    def close(self) -> None:
        with self._lock:
            router, self._router = self._router, None
        if router is not None:
            router.close()
