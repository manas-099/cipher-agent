# app/src/infrastructure/sandbox/python_sandbox.py
# Python command builder. Runs inside the shared session's venv.

from __future__ import annotations

import shlex

from app.src.infrastructure.sandbox.base_sandbox_adapter import BaseSandboxAdapter
from app.src.ports.outbound.sandbox_port import SandboxLanguage


class PythonSandbox(BaseSandboxAdapter):
    language = SandboxLanguage.PYTHON

    @property
    def _python(self) -> str:
        return self._session.python_executable

    def _code_command(self, file_name: str, args: list[str] | None) -> str:
        return f"{self._python} {shlex.quote(file_name)}{self._quote_args(args)}"

    def _test_command(self, target: str | None, framework: str) -> str:
        return f"{self._python} -m pytest {shlex.quote(target or '.')} -q"

    def _lint_command(self, target: str | None, linter: str, fix: bool) -> str:
        target = shlex.quote(target or ".")

        if linter == "ruff":
            command = f"{self._python} -m ruff check {target}"
            if fix:
                command += " --fix"
            return command

        return f"{self._python} -m flake8 {target}"

    def _install_command(
        self, package: str, manager: str, version: str | None
    ) -> str:
        spec = f"{package}=={version}" if version else package
        return f"{self._python} -m pip install {shlex.quote(spec)}"
