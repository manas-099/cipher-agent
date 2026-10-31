# app/src/ports/outbound/filesystem_port.py
# Contract for all filesystem operations.
# Domain tools call this — never open(), os, pathlib directly.
# LocalFSAdapter implements this for the local machine.

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


# ── return types ──────────────────────────────────────────────────────────────

@dataclass
class FileContent:
    """Result of reading a file."""
    path        : str
    content     : str
    total_lines : int
    has_more    : bool     # True if offset+limit did not reach end of file
    size_bytes  : int


@dataclass
class FileInfo:
    """Metadata about a file without reading its content."""
    path          : str
    exists        : bool
    size_bytes    : int
    size_kb       : float
    line_count    : int
    extension     : str
    last_modified : str    # ISO 8601 timestamp


@dataclass
class SearchMatch:
    """Single result from a grep search."""
    file        : str
    line_number : int
    line_content: str


# ── the port ──────────────────────────────────────────────────────────────────

class FilesystemPort(ABC):
    """
    Contract for filesystem access.
    All file and folder operations the agent needs go through here.
    """

    # ── file read operations ──────────────────────────────────────────────────

    @abstractmethod
    def read_file(
        self,
        path   : str,
        offset : int = 0,
        limit  : int | None = None,
    ) -> FileContent:
        """
        Read file contents, optionally with chunking.
        offset: line number to start from (0-indexed)
        limit:  max lines to return (None = all)
        """
        ...

    @abstractmethod
    def get_file_info(self, path: str) -> FileInfo:
        """Return file metadata without reading content."""
        ...

    @abstractmethod
    def list_files(
        self,
        path      : str,
        recursive : bool = False,
    ) -> list[str]:
        """List all files in a directory."""
        ...

    @abstractmethod
    def file_tree(
        self,
        path        : str,
        max_depth   : int = 3,
        show_hidden : bool = False,
        ignore      : list[str] | None = None,
    ) -> str:
        """
        Return directory structure as a formatted tree string.
        No file content — structure only.
        """
        ...

    @abstractmethod
    def grep_search(
        self,
        path           : str,
        pattern        : str,
        file_pattern   : str = "*",
        recursive      : bool = True,
        case_sensitive : bool = True,
        max_results    : int = 100,
    ) -> list[SearchMatch]:
        """Search for pattern across files. Returns filename + line + content."""
        ...

    # ── file write operations ─────────────────────────────────────────────────

    @abstractmethod
    def create_file(
        self,
        path      : str,
        content   : str,
        overwrite : bool = False,
    ) -> None:
        """Create a new file. Raises if exists and overwrite=False."""
        ...

    @abstractmethod
    def edit_file(
        self,
        path        : str,
        start_line  : int,
        end_line    : int,
        new_content : str,
    ) -> None:
        """Replace a block of lines in a file."""
        ...

    @abstractmethod
    def replace_in_file(
        self,
        path        : str,
        old_str     : str,
        new_str     : str,
        replace_all : bool = False,
    ) -> None:
        """
        Find exact string and replace it.
        Raises if old_str not found or found more than once
        and replace_all=False.
        """
        ...

    @abstractmethod
    def find_and_replace_all(
        self,
        path         : str,
        old_str      : str,
        new_str      : str,
        file_pattern : str = "*",
        recursive    : bool = True,
        dry_run      : bool = False,
    ) -> dict[str, int]:
        """
        Replace string across multiple files.
        Returns {filename: replacement_count} for every file changed.
        """
        ...

    @abstractmethod
    def delete_file(
        self,
        path       : str,
        must_exist : bool = True,
    ) -> None:
        """Delete a file. Raises if not found and must_exist=True."""
        ...

    @abstractmethod
    def move_file(
        self,
        source      : str,
        destination : str,
        overwrite   : bool = False,
    ) -> None:
        """Move or rename a file."""
        ...

    @abstractmethod
    def copy_file(
        self,
        source      : str,
        destination : str,
        overwrite   : bool = False,
    ) -> None:
        """Copy a file to a new path."""
        ...

    # ── folder operations ─────────────────────────────────────────────────────

    @abstractmethod
    def create_folder(
        self,
        path     : str,
        exist_ok : bool = True,
    ) -> None:
        """Create directory and all intermediate dirs."""
        ...

    @abstractmethod
    def delete_folder(
        self,
        path       : str,
        must_exist : bool = True,
    ) -> None:
        """Delete directory and all contents recursively."""
        ...