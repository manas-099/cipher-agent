# app/src/infrastructure/sandbox/sandbox_factory.py
# Builds a SandboxSession and language adapters, then returns one
# routing SandboxPort (ToolFactory injects a single port).

from __future__ import annotations

from pathlib import Path

from app.src.config.settings import SandboxSettings, get_settings
from app.src.infrastructure.sandbox.bash_sandbox import BashSandbox
from app.src.infrastructure.sandbox.docker_runner import DockerRunner
from app.src.infrastructure.sandbox.node_sandbox import NodeSandbox
from app.src.infrastructure.sandbox.python_sandbox import PythonSandbox
from app.src.infrastructure.sandbox.sandbox_session import SandboxSession
from app.src.logger.logger import get_logger
from app.src.ports.outbound.sandbox_port import (
    ExecutionResult,
    LintResult,
    SandboxLanguage,
    SandboxPort,
    TestResult,
)


class RoutingSandbox(SandboxPort):
    """
    One SandboxPort that dispatches to the right language adapter.

    run_code/run_command carry an explicit language.
    run_tests/lint_code/install_package infer it from framework/linter/manager
    or from the project files at the given path.

    All adapters share one SandboxSession (one container per agent task).
    """

    def __init__(
        self,
        adapters: dict[SandboxLanguage, SandboxPort],
        session: SandboxSession,
        *,
        owns_session: bool = False,
    ) -> None:
        self._adapters = adapters
        self._session = session
        self._owns_session = owns_session
        self._logger = get_logger(__name__)

    # ── SandboxPort ───────────────────────────────────────────────────────────

    def run_code(
        self,
        file_path: str,
        language: SandboxLanguage,
        timeout: int = 30,
        args: list[str] | None = None,
    ) -> ExecutionResult:
        return self._adapter(language).run_code(file_path, language, timeout, args)

    def run_command(
        self,
        command: str,
        language: SandboxLanguage,
        working_dir: str | None = None,
        timeout: int = 30,
    ) -> ExecutionResult:
        return self._adapter(language).run_command(
            command, language, working_dir, timeout
        )

    def run_tests(
        self,
        path: str,
        framework: str = "auto",
        test_file: str | None = None,
        timeout: int = 60,
    ) -> TestResult:
        language = self._language_for_framework(framework, path)
        return self._adapter(language).run_tests(path, framework, test_file, timeout)

    def lint_code(
        self,
        path: str,
        linter: str = "auto",
        fix: bool = False,
    ) -> LintResult:
        language = self._language_for_linter(linter, path)
        return self._adapter(language).lint_code(path, linter, fix)

    def install_package(
        self,
        package: str,
        manager: str = "auto",
        version: str | None = None,
    ) -> ExecutionResult:
        language = self._language_for_manager(manager)
        return self._adapter(language).install_package(package, manager, version)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    @property
    def session(self) -> SandboxSession:
        return self._session

    def close(self) -> None:
        if self._owns_session:
            self._session.stop()

    def __enter__(self) -> "RoutingSandbox":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # ── dispatch helpers ──────────────────────────────────────────────────────

    def _adapter(self, language: SandboxLanguage) -> SandboxPort:
        try:
            return self._adapters[language]
        except KeyError:
            raise ValueError(f"No sandbox adapter for language: {language}")

    def _language_for_framework(self, framework: str, path: str) -> SandboxLanguage:
        if framework == "pytest":
            return SandboxLanguage.PYTHON
        if framework == "jest":
            return SandboxLanguage.NODE
        return self._detect_language(path)

    def _language_for_linter(self, linter: str, path: str) -> SandboxLanguage:
        if linter in ("flake8", "ruff"):
            return SandboxLanguage.PYTHON
        if linter == "eslint":
            return SandboxLanguage.NODE
        return self._detect_language(path)

    def _language_for_manager(self, manager: str) -> SandboxLanguage:
        if manager == "npm":
            return SandboxLanguage.NODE
        if manager in ("apt", "apt-get"):
            return SandboxLanguage.BASH
        return SandboxLanguage.PYTHON

    def _detect_language(self, path: str) -> SandboxLanguage:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = Path(self._session.workspace_root) / candidate
        resolved = candidate.resolve()
        root = resolved if resolved.is_dir() else resolved.parent

        if (root / "package.json").exists():
            return SandboxLanguage.NODE
        if any(
            (root / name).exists()
            for name in ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg")
        ):
            return SandboxLanguage.PYTHON

        suffix_languages = {
            ".py": SandboxLanguage.PYTHON,
            ".js": SandboxLanguage.NODE,
            ".ts": SandboxLanguage.NODE,
            ".sh": SandboxLanguage.BASH,
        }
        for suffix, language in suffix_languages.items():
            if any(root.glob(f"*{suffix}")):
                return language

        return SandboxLanguage.PYTHON


class SandboxFactory:
    """
    Creates sessions and adapters from a shared DockerRunner.

    Per-task usage (recommended):
        factory = SandboxFactory()
        router = factory.create_router(workspace_root="/path/to/project")
        try:
            tool_factory = ToolFactory(fs, router, llm)
            ...
        finally:
            router.close()

    Caller-provided session:
        session = factory.create_session(workspace_root)
        router = factory.create_router(session=session)
        ...
        session.stop()
    """

    _ADAPTERS = {
        SandboxLanguage.PYTHON: PythonSandbox,
        SandboxLanguage.NODE: NodeSandbox,
        SandboxLanguage.BASH: BashSandbox,
    }

    def __init__(
        self,
        runner: DockerRunner | None = None,
        settings: SandboxSettings | None = None,
    ) -> None:
        self._runner = runner or DockerRunner(settings)
        self._settings = settings or get_settings().sandbox
        self._logger = get_logger(__name__)

    def create_session(self, workspace_root: str | None = None) -> SandboxSession:
        root = (
            workspace_root
            or self._settings.WORKSPACE_ROOT
            or str(Path.cwd())
        )
        session = SandboxSession(
            runner=self._runner,
            image=self._settings.IMAGE_SANDBOX,
            workspace_root=root,
            settings=self._settings,
        )
        return session.start()

    def create(
        self,
        language: SandboxLanguage,
        session: SandboxSession,
    ) -> SandboxPort:
        try:
            adapter_class = self._ADAPTERS[language]
        except KeyError:
            raise ValueError(f"Unsupported sandbox language: {language}")
        return adapter_class(session, self._settings)

    def create_all(
        self, session: SandboxSession
    ) -> dict[SandboxLanguage, SandboxPort]:
        return {
            language: self.create(language, session)
            for language in self._ADAPTERS
        }

    def create_router(
        self,
        session: SandboxSession | None = None,
        workspace_root: str | None = None,
    ) -> RoutingSandbox:
        owns_session = session is None
        if session is None:
            session = self.create_session(workspace_root)

        router = RoutingSandbox(
            self.create_all(session),
            session,
            owns_session=owns_session,
        )
        self._logger.info(
            "sandbox_router_created",
            session_id=session.id,
            languages=[language.value for language in self._ADAPTERS],
            owns_session=owns_session,
        )
        return router
