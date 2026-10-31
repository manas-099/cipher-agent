# tests/conftest.py
# The uv build installs app/src on sys.path (app.pth). That makes the regular
# package app/src/app shadow the repo-root app.src namespace, so running tests
# from the repo root fails with "ModuleNotFoundError: app.src".
# Drop that entry and make sure the repository root is importable instead.

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_SRC = (REPO_ROOT / "app" / "src").resolve()


def _normalise(path: str) -> Path | None:
    try:
        return Path(path or ".").resolve()
    except OSError:
        return None


sys.path[:] = [
    path for path in sys.path if _normalise(path) != APP_SRC
]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
