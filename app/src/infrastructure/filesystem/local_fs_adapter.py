# app/src/infrastructure/filesystem/local_fs_adapter.py
# Local filesystem implementation of FilesystemPort.
# Every path is resolved and confined to the configured workspace root.
# Domain tools never import os/pathlib directly — they call this adapter.

from __future__ import annotations

import fnmatch
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.src.exception.exceptions import (
    ConfigurationError,
    ConflictError,
    FileAlreadyExistsError,
    FilesystemError,
    InvalidRequestError,
    PathNotFoundError,
    PathOutsideWorkspaceError,
)
from app.src.logger.logger import get_logger
from app.src.ports.outbound.filesystem_port import (
    FileContent,
    FileInfo,
    FilesystemPort,
    SearchMatch,
)

__all__ = ["LocalFSAdapter"]

_IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
}

_BINARY_SNIFF_BYTES = 8192


class LocalFSAdapter(FilesystemPort):
    """
    FilesystemPort backed by the local disk.

    The adapter is always scoped to one workspace root. Relative paths are
    resolved from that root; absolute paths are accepted only when they stay
    inside it. Symlinks are resolved, so links pointing outside are rejected.

    Recursive listings, trees, and searches skip common noise directories
    (.git, .venv, node_modules, caches, build output).
    """

    def __init__(self, workspace_root: str) -> None:
        root = Path(workspace_root).expanduser().resolve()

        if not root.exists():
            raise ConfigurationError(
                f"Workspace root does not exist: {root}"
            )
        if not root.is_dir():
            raise ConfigurationError(
                f"Workspace root is not a directory: {root}"
            )

        self._root = root
        self._logger = get_logger(__name__)

    @property
    def workspace_root(self) -> str:
        return str(self._root)

    # ── read operations ───────────────────────────────────────────────────────

    def read_file(
        self,
        path: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> FileContent:
        if offset < 0:
            raise InvalidRequestError("offset must be >= 0")
        if limit is not None and limit < 0:
            raise InvalidRequestError("limit must be >= 0")

        target = self._resolve(path)
        self._require_file(target)
        self._require_text(target)

        text = self._read_text(target)
        lines = text.splitlines()
        total = len(lines)

        start = min(offset, total)
        end = total if limit is None else min(start + limit, total)
        selected = lines[start:end]

        return FileContent(
            path=self._display(target),
            content="\n".join(selected),
            total_lines=total,
            has_more=end < total,
            size_bytes=target.stat().st_size,
        )

    def get_file_info(self, path: str) -> FileInfo:
        target = self._resolve(path)
        display = self._display(target)

        if not target.exists():
            return FileInfo(
                path=display,
                exists=False,
                size_bytes=0,
                size_kb=0.0,
                line_count=0,
                extension=target.suffix,
                last_modified="",
            )

        try:
            stat = target.stat()
        except OSError as exc:
            raise FilesystemError(
                f"Could not stat '{display}': {exc}"
            ) from exc

        if target.is_file():
            size_bytes = stat.st_size
            line_count = (
                0
                if self._is_binary(target)
                else len(self._read_text(target).splitlines())
            )
            extension = target.suffix
        else:
            size_bytes = 0
            line_count = 0
            extension = ""

        return FileInfo(
            path=display,
            exists=True,
            size_bytes=size_bytes,
            size_kb=size_bytes / 1024,
            line_count=line_count,
            extension=extension,
            last_modified=datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat(),
        )

    def list_files(
        self,
        path: str,
        recursive: bool = False,
    ) -> list[str]:
        target = self._resolve(path)
        self._require_dir(target)

        files = [
            self._display(file_path)
            for file_path in self._iter_files(
                target,
                recursive=recursive,
                file_pattern="*",
            )
        ]
        return sorted(files)

    def file_tree(
        self,
        path: str,
        max_depth: int = 3,
        show_hidden: bool = False,
        ignore: list[str] | None = None,
    ) -> str:
        if max_depth < 0:
            raise InvalidRequestError("max_depth must be >= 0")

        target = self._resolve(path)
        self._require_dir(target)

        ignore_patterns = [pattern for pattern in (ignore or []) if pattern]
        lines = [self._display(target)]
        self._tree_children(
            directory=target,
            prefix="",
            depth=0,
            max_depth=max_depth,
            show_hidden=show_hidden,
            ignore=ignore_patterns,
            lines=lines,
        )
        return "\n".join(lines)

    def grep_search(
        self,
        path: str,
        pattern: str,
        file_pattern: str = "*",
        recursive: bool = True,
        case_sensitive: bool = True,
        max_results: int = 100,
    ) -> list[SearchMatch]:
        if not pattern:
            raise InvalidRequestError("pattern must not be empty")
        if max_results < 0:
            raise InvalidRequestError("max_results must be >= 0")

        target = self._resolve(path)
        if not target.exists():
            raise PathNotFoundError(
                f"Path not found: {self._display(target)}"
            )

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error:
            regex = re.compile(re.escape(pattern), flags)

        matches: list[SearchMatch] = []
        if max_results == 0:
            return matches

        for file_path in self._iter_files(
            target,
            recursive=recursive,
            file_pattern=file_pattern,
        ):
            if self._is_binary(file_path):
                continue

            text = self._read_text(file_path)
            for line_number, line in enumerate(text.splitlines(), start=1):
                if not regex.search(line):
                    continue
                matches.append(
                    SearchMatch(
                        file=self._display(file_path),
                        line_number=line_number,
                        line_content=line,
                    )
                )
                if len(matches) >= max_results:
                    return matches

        return matches

    # ── write operations ──────────────────────────────────────────────────────

    def create_file(
        self,
        path: str,
        content: str,
        overwrite: bool = False,
    ) -> None:
        self._require_str(content, "content")

        target = self._resolve(path)
        if target.exists():
            if target.is_dir():
                raise FilesystemError(
                    f"Cannot create file; directory exists: {self._display(target)}"
                )
            if not overwrite:
                raise FileAlreadyExistsError(
                    f"File already exists: {self._display(target)}"
                )

        self._write_text(target, content)
        self._logger.info(
            "fs_file_created",
            path=self._display(target),
            bytes=len(content.encode("utf-8")),
            overwrite=overwrite,
        )

    def edit_file(
        self,
        path: str,
        start_line: int,
        end_line: int,
        new_content: str,
    ) -> None:
        self._require_str(new_content, "new_content")
        if start_line < 1 or end_line < start_line:
            raise InvalidRequestError(
                "start_line and end_line are 1-indexed; "
                "start_line must be >= 1 and <= end_line"
            )

        target = self._resolve(path)
        self._require_file(target)
        self._require_text(target)

        text = self._read_text(target)
        lines = text.splitlines()
        total = len(lines)

        if start_line > total or end_line > total:
            raise InvalidRequestError(
                f"Line range {start_line}-{end_line} is outside "
                f"'{self._display(target)}' (1-{total})"
            )

        replacement = new_content.splitlines()
        updated = (
            lines[: start_line - 1]
            + replacement
            + lines[end_line:]
        )

        new_text = "\n".join(updated)
        if text.endswith("\n") and updated:
            new_text += "\n"

        self._write_text(target, new_text)
        self._logger.info(
            "fs_file_edited",
            path=self._display(target),
            start_line=start_line,
            end_line=end_line,
        )

    def replace_in_file(
        self,
        path: str,
        old_str: str,
        new_str: str,
        replace_all: bool = False,
    ) -> None:
        self._require_str(old_str, "old_str")
        self._require_str(new_str, "new_str")
        if not old_str:
            raise InvalidRequestError("old_str must not be empty")

        target = self._resolve(path)
        self._require_file(target)
        self._require_text(target)

        text = self._read_text(target)
        count = text.count(old_str)
        display = self._display(target)

        if count == 0:
            raise InvalidRequestError(
                f"String not found in '{display}': {old_str!r}"
            )
        if count > 1 and not replace_all:
            raise ConflictError(
                f"String appears {count} times in '{display}'; "
                "pass replace_all=True to replace every occurrence"
            )

        new_text = text.replace(
            old_str,
            new_str,
            -1 if replace_all else 1,
        )
        self._write_text(target, new_text)
        self._logger.info(
            "fs_string_replaced",
            path=display,
            replacements=count if replace_all else 1,
        )

    def find_and_replace_all(
        self,
        path: str,
        old_str: str,
        new_str: str,
        file_pattern: str = "*",
        recursive: bool = True,
        dry_run: bool = False,
    ) -> dict[str, int]:
        self._require_str(old_str, "old_str")
        self._require_str(new_str, "new_str")
        if not old_str:
            raise InvalidRequestError("old_str must not be empty")

        target = self._resolve(path)
        if not target.exists():
            raise PathNotFoundError(
                f"Path not found: {self._display(target)}"
            )

        changed: dict[str, int] = {}

        for file_path in self._iter_files(
            target,
            recursive=recursive,
            file_pattern=file_pattern,
        ):
            if self._is_binary(file_path):
                continue

            text = self._read_text(file_path)
            count = text.count(old_str)
            if count == 0:
                continue

            display = self._display(file_path)
            changed[display] = count

            if not dry_run:
                self._write_text(file_path, text.replace(old_str, new_str))

        if changed:
            self._logger.info(
                "fs_replace_all_finished",
                files=len(changed),
                replacements=sum(changed.values()),
                dry_run=dry_run,
            )

        return changed

    def delete_file(
        self,
        path: str,
        must_exist: bool = True,
    ) -> None:
        target = self._resolve(path)
        self._require_not_root(target, "delete")

        if not target.exists():
            if must_exist:
                raise PathNotFoundError(
                    f"File not found: {self._display(target)}"
                )
            return

        if not target.is_file():
            raise FilesystemError(
                f"Not a file: {self._display(target)}; use delete_folder"
            )

        try:
            target.unlink()
        except OSError as exc:
            raise FilesystemError(
                f"Could not delete '{self._display(target)}': {exc}"
            ) from exc

        self._logger.info("fs_file_deleted", path=self._display(target))

    def move_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False,
    ) -> None:
        source_path = self._resolve(source)
        destination_path = self._resolve(destination)
        self._require_not_root(source_path, "move")

        if not source_path.exists():
            raise PathNotFoundError(
                f"Source not found: {self._display(source_path)}"
            )
        if not source_path.is_file():
            raise FilesystemError(
                f"Source is not a file: {self._display(source_path)}"
            )
        if source_path == destination_path:
            return

        self._check_destination(destination_path, overwrite)

        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            if destination_path.exists():
                destination_path.unlink()
            source_path.replace(destination_path)
        except OSError as exc:
            raise FilesystemError(
                f"Could not move '{self._display(source_path)}' to "
                f"'{self._display(destination_path)}': {exc}"
            ) from exc

        self._logger.info(
            "fs_file_moved",
            source=self._display(source_path),
            destination=self._display(destination_path),
        )

    def copy_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False,
    ) -> None:
        source_path = self._resolve(source)
        destination_path = self._resolve(destination)

        if not source_path.exists():
            raise PathNotFoundError(
                f"Source not found: {self._display(source_path)}"
            )
        if not source_path.is_file():
            raise FilesystemError(
                f"Source is not a file: {self._display(source_path)}"
            )
        if source_path == destination_path:
            raise InvalidRequestError(
                "Source and destination are the same file"
            )

        self._check_destination(destination_path, overwrite)

        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination_path)
        except OSError as exc:
            raise FilesystemError(
                f"Could not copy '{self._display(source_path)}' to "
                f"'{self._display(destination_path)}': {exc}"
            ) from exc

        self._logger.info(
            "fs_file_copied",
            source=self._display(source_path),
            destination=self._display(destination_path),
        )

    def create_folder(
        self,
        path: str,
        exist_ok: bool = True,
    ) -> None:
        target = self._resolve(path)

        if target.exists():
            if target.is_dir() and exist_ok:
                return
            raise FileAlreadyExistsError(
                f"Path already exists: {self._display(target)}"
            )

        try:
            target.mkdir(parents=True, exist_ok=exist_ok)
        except OSError as exc:
            raise FilesystemError(
                f"Could not create folder '{self._display(target)}': {exc}"
            ) from exc

        self._logger.info("fs_folder_created", path=self._display(target))

    def delete_folder(
        self,
        path: str,
        must_exist: bool = True,
    ) -> None:
        target = self._resolve(path)
        self._require_not_root(target, "delete")

        if not target.exists():
            if must_exist:
                raise PathNotFoundError(
                    f"Folder not found: {self._display(target)}"
                )
            return

        if not target.is_dir():
            raise FilesystemError(
                f"Not a directory: {self._display(target)}; use delete_file"
            )

        try:
            shutil.rmtree(target)
        except OSError as exc:
            raise FilesystemError(
                f"Could not delete folder '{self._display(target)}': {exc}"
            ) from exc

        self._logger.info("fs_folder_deleted", path=self._display(target))

    # ── path helpers ──────────────────────────────────────────────────────────

    def _resolve(self, path: str) -> Path:
        if not isinstance(path, str):
            raise InvalidRequestError("Path must be a string")

        raw = path.strip()
        if not raw:
            raise InvalidRequestError("Path must not be empty")

        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = self._root / candidate

        try:
            resolved = candidate.resolve()
        except OSError as exc:
            raise FilesystemError(f"Could not resolve '{path}': {exc}") from exc

        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            raise PathOutsideWorkspaceError(
                f"Path '{path}' is outside the workspace '{self._root}'"
            ) from exc

        return resolved

    def _display(self, path: Path) -> str:
        return path.relative_to(self._root).as_posix()

    def _is_within_root(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self._root)
            return True
        except (OSError, ValueError):
            return False

    def _require_not_root(self, path: Path, action: str) -> None:
        if path == self._root:
            raise InvalidRequestError(
                f"Cannot {action} the workspace root"
            )

    def _require_file(self, path: Path) -> None:
        if not path.exists():
            raise PathNotFoundError(f"File not found: {self._display(path)}")
        if not path.is_file():
            raise FilesystemError(f"Not a file: {self._display(path)}")

    def _require_dir(self, path: Path) -> None:
        if not path.exists():
            raise PathNotFoundError(f"Folder not found: {self._display(path)}")
        if not path.is_dir():
            raise FilesystemError(f"Not a directory: {self._display(path)}")

    @staticmethod
    def _require_str(value: str, name: str) -> None:
        if not isinstance(value, str):
            raise InvalidRequestError(f"{name} must be a string")

    def _check_destination(self, path: Path, overwrite: bool) -> None:
        if not path.exists():
            return
        if path.is_dir():
            raise FilesystemError(
                f"Destination is a directory: {self._display(path)}"
            )
        if not overwrite:
            raise FileAlreadyExistsError(
                f"Destination already exists: {self._display(path)}"
            )

    # ── file iteration / tree ─────────────────────────────────────────────────

    def _iter_files(
        self,
        root: Path,
        *,
        recursive: bool,
        file_pattern: str,
    ) -> Iterator[Path]:
        if root.is_file():
            if fnmatch.fnmatch(root.name, file_pattern):
                yield root
            return

        if not recursive:
            for entry in self._sorted_entries(root):
                if not entry.is_file():
                    continue
                if not fnmatch.fnmatch(entry.name, file_pattern):
                    continue
                if self._is_within_root(entry):
                    yield entry
            return

        for dirpath, dirnames, filenames in os.walk(root):
            directory = Path(dirpath)
            dirnames[:] = sorted(
                (
                    name
                    for name in dirnames
                    if name not in _IGNORED_DIRS
                    and not (directory / name).is_symlink()
                ),
                key=str.lower,
            )
            for name in sorted(filenames, key=str.lower):
                if not fnmatch.fnmatch(name, file_pattern):
                    continue
                candidate = directory / name
                if self._is_within_root(candidate):
                    yield candidate

    def _tree_children(
        self,
        *,
        directory: Path,
        prefix: str,
        depth: int,
        max_depth: int,
        show_hidden: bool,
        ignore: list[str],
        lines: list[str],
    ) -> None:
        if depth >= max_depth:
            return

        entries = []
        for entry in self._sorted_entries(directory):
            if not show_hidden and entry.name.startswith("."):
                continue
            if entry.is_dir() and entry.name in _IGNORED_DIRS:
                continue
            if self._matches_ignore(entry.name, ignore):
                continue
            if entry.is_symlink() or not self._is_within_root(entry):
                continue
            entries.append(entry)

        entries.sort(key=lambda entry: (not entry.is_dir(), entry.name.lower()))

        for index, entry in enumerate(entries):
            last = index == len(entries) - 1
            connector = "└── " if last else "├── "
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{prefix}{connector}{entry.name}{suffix}")

            if entry.is_dir():
                self._tree_children(
                    directory=entry,
                    prefix=prefix + ("    " if last else "│   "),
                    depth=depth + 1,
                    max_depth=max_depth,
                    show_hidden=show_hidden,
                    ignore=ignore,
                    lines=lines,
                )

    @staticmethod
    def _sorted_entries(directory: Path) -> list[Path]:
        try:
            return sorted(directory.iterdir(), key=lambda entry: entry.name.lower())
        except OSError as exc:
            raise FilesystemError(
                f"Could not list directory '{directory}': {exc}"
            ) from exc

    @staticmethod
    def _matches_ignore(name: str, patterns: list[str]) -> bool:
        return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)

    # ── text helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise FilesystemError(f"Could not read '{path}': {exc}") from exc

    @staticmethod
    def _write_text(path: Path, text: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        except OSError as exc:
            raise FilesystemError(f"Could not write '{path}': {exc}") from exc

    @staticmethod
    def _is_binary(path: Path) -> bool:
        try:
            with path.open("rb") as handle:
                return b"\x00" in handle.read(_BINARY_SNIFF_BYTES)
        except OSError as exc:
            raise FilesystemError(f"Could not read '{path}': {exc}") from exc

    def _require_text(self, path: Path) -> None:
        if self._is_binary(path):
            raise FilesystemError(
                f"Binary file cannot be read or edited as text: "
                f"{self._display(path)}"
            )
