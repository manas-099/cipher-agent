# tests/unit/infrastructure/test_local_fs_adapter.py

from __future__ import annotations

from pathlib import Path

import pytest

from app.src.exception.exceptions import (
    ConflictError,
    FileAlreadyExistsError,
    FilesystemError,
    InvalidRequestError,
    PathNotFoundError,
    PathOutsideWorkspaceError,
)
from app.src.infrastructure.filesystem.local_fs_adapter import LocalFSAdapter


@pytest.fixture()
def workspace(tmp_path: Path) -> LocalFSAdapter:
    return LocalFSAdapter(str(tmp_path))


@pytest.fixture()
def populated(workspace: LocalFSAdapter, tmp_path: Path) -> LocalFSAdapter:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text(
        "print('one')\nprint('two')\nprint('three')\n", encoding="utf-8"
    )
    (tmp_path / "src" / "util.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# Title\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("x\n", encoding="utf-8")
    return workspace


# ── construction ──────────────────────────────────────────────────────────────

def test_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        LocalFSAdapter(str(tmp_path / "nope"))


def test_file_root_raises(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(Exception):
        LocalFSAdapter(str(file_path))


# ── read_file ────────────────────────────────────────────────────────────────

def test_read_file_full(populated: LocalFSAdapter) -> None:
    result = populated.read_file("src/main.py")
    assert result.path == "src/main.py"
    assert result.total_lines == 3
    assert result.has_more is False
    assert result.content == "print('one')\nprint('two')\nprint('three')"
    assert result.size_bytes > 0


def test_read_file_offset_and_limit(populated: LocalFSAdapter) -> None:
    result = populated.read_file("src/main.py", offset=1, limit=1)
    assert result.content == "print('two')"
    assert result.has_more is True


def test_read_file_offset_past_end(populated: LocalFSAdapter) -> None:
    result = populated.read_file("src/main.py", offset=99)
    assert result.content == ""
    assert result.has_more is False


def test_read_file_invalid_offset(populated: LocalFSAdapter) -> None:
    with pytest.raises(InvalidRequestError):
        populated.read_file("src/main.py", offset=-1)


def test_read_file_missing(populated: LocalFSAdapter) -> None:
    with pytest.raises(PathNotFoundError):
        populated.read_file("src/nope.py")


def test_read_file_rejects_binary(populated: LocalFSAdapter, tmp_path: Path) -> None:
    (tmp_path / "bin.dat").write_bytes(b"abc\x00def")
    with pytest.raises(FilesystemError):
        populated.read_file("bin.dat")


# ── get_file_info ────────────────────────────────────────────────────────────

def test_get_file_info(populated: LocalFSAdapter) -> None:
    info = populated.get_file_info("src/main.py")
    assert info.exists is True
    assert info.line_count == 3
    assert info.extension == ".py"
    assert info.size_kb > 0
    assert info.last_modified


def test_get_file_info_missing_is_not_error(populated: LocalFSAdapter) -> None:
    info = populated.get_file_info("missing.txt")
    assert info.exists is False
    assert info.size_bytes == 0
    assert info.line_count == 0


# ── list_files ───────────────────────────────────────────────────────────────

def test_list_files_non_recursive(populated: LocalFSAdapter) -> None:
    assert populated.list_files(".") == ["README.md"]


def test_list_files_recursive_skips_noise(populated: LocalFSAdapter) -> None:
    files = populated.list_files(".", recursive=True)
    assert "src/main.py" in files
    assert "README.md" in files
    assert all(".git/" not in item for item in files)
    assert all("node_modules/" not in item for item in files)


def test_list_files_missing(populated: LocalFSAdapter) -> None:
    with pytest.raises(PathNotFoundError):
        populated.list_files("nope")


# ── file_tree ────────────────────────────────────────────────────────────────

def test_file_tree(populated: LocalFSAdapter) -> None:
    tree = populated.file_tree(".")
    assert "." in tree
    assert "src/" in tree
    assert "main.py" in tree
    assert "node_modules" not in tree


def test_file_tree_max_depth(populated: LocalFSAdapter) -> None:
    tree = populated.file_tree(".", max_depth=1)
    assert "src/" in tree
    assert "main.py" not in tree


def test_file_tree_invalid_depth(populated: LocalFSAdapter) -> None:
    with pytest.raises(InvalidRequestError):
        populated.file_tree(".", max_depth=-1)


# ── grep_search ──────────────────────────────────────────────────────────────

def test_grep_search(populated: LocalFSAdapter) -> None:
    matches = populated.grep_search(".", "print")
    assert len(matches) == 3
    assert all(match.file == "src/main.py" for match in matches)
    assert matches[0].line_number == 1


def test_grep_case_insensitive(populated: LocalFSAdapter) -> None:
    assert populated.grep_search(".", "PRINT", case_sensitive=True) == []
    assert len(populated.grep_search(".", "PRINT", case_sensitive=False)) == 3


def test_grep_file_pattern(populated: LocalFSAdapter) -> None:
    matches = populated.grep_search(".", "VALUE", file_pattern="*.py")
    assert len(matches) == 1
    assert matches[0].file == "src/util.py"


def test_grep_max_results(populated: LocalFSAdapter) -> None:
    matches = populated.grep_search(".", "print", max_results=2)
    assert len(matches) == 2


def test_grep_invalid_pattern(populated: LocalFSAdapter) -> None:
    with pytest.raises(InvalidRequestError):
        populated.grep_search(".", "")


def test_grep_missing(populated: LocalFSAdapter) -> None:
    with pytest.raises(PathNotFoundError):
        populated.grep_search("nope", "x")


# ── create_file ──────────────────────────────────────────────────────────────

def test_create_file(workspace: LocalFSAdapter, tmp_path: Path) -> None:
    workspace.create_file("a/b/new.txt", "hello")
    assert (tmp_path / "a" / "b" / "new.txt").read_text(encoding="utf-8") == "hello"


def test_create_file_conflict(populated: LocalFSAdapter) -> None:
    with pytest.raises(FileAlreadyExistsError):
        populated.create_file("README.md", "x")


def test_create_file_overwrite(populated: LocalFSAdapter, tmp_path: Path) -> None:
    populated.create_file("README.md", "new", overwrite=True)
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "new"


# ── edit_file ────────────────────────────────────────────────────────────────

def test_edit_file_one_indexed(populated: LocalFSAdapter, tmp_path: Path) -> None:
    populated.edit_file("src/main.py", 2, 2, "print('TWO')")
    lines = (tmp_path / "src" / "main.py").read_text(encoding="utf-8").splitlines()
    assert lines == ["print('one')", "print('TWO')", "print('three')"]


def test_edit_file_multiline(populated: LocalFSAdapter, tmp_path: Path) -> None:
    populated.edit_file("src/main.py", 1, 2, "a\nb\nc")
    lines = (tmp_path / "src" / "main.py").read_text(encoding="utf-8").splitlines()
    assert lines == ["a", "b", "c", "print('three')"]


def test_edit_file_out_of_range(populated: LocalFSAdapter) -> None:
    with pytest.raises(InvalidRequestError):
        populated.edit_file("src/main.py", 5, 6, "x")


def test_edit_file_bad_range(populated: LocalFSAdapter) -> None:
    with pytest.raises(InvalidRequestError):
        populated.edit_file("src/main.py", 3, 1, "x")


# ── replace_in_file ──────────────────────────────────────────────────────────

def test_replace_single(populated: LocalFSAdapter, tmp_path: Path) -> None:
    populated.replace_in_file("src/util.py", "1", "2")
    assert (tmp_path / "src" / "util.py").read_text(encoding="utf-8") == "VALUE = 2\n"


def test_replace_conflict(populated: LocalFSAdapter) -> None:
    with pytest.raises(ConflictError):
        populated.replace_in_file("src/main.py", "print", "echo")


def test_replace_all(populated: LocalFSAdapter, tmp_path: Path) -> None:
    populated.replace_in_file("src/main.py", "print", "echo", replace_all=True)
    text = (tmp_path / "src" / "main.py").read_text(encoding="utf-8")
    assert "print" not in text
    assert text.count("echo") == 3


def test_replace_not_found(populated: LocalFSAdapter) -> None:
    with pytest.raises(InvalidRequestError):
        populated.replace_in_file("src/util.py", "zzz", "y")


# ── find_and_replace_all ─────────────────────────────────────────────────────

def test_find_and_replace_all(populated: LocalFSAdapter, tmp_path: Path) -> None:
    changed = populated.find_and_replace_all(".", "print", "echo")
    assert changed == {"src/main.py": 3}
    assert "echo" in (tmp_path / "src" / "main.py").read_text(encoding="utf-8")


def test_find_and_replace_dry_run(populated: LocalFSAdapter, tmp_path: Path) -> None:
    changed = populated.find_and_replace_all(".", "print", "echo", dry_run=True)
    assert changed == {"src/main.py": 3}
    assert "print" in (tmp_path / "src" / "main.py").read_text(encoding="utf-8")


def test_find_and_replace_pattern(populated: LocalFSAdapter) -> None:
    changed = populated.find_and_replace_all(".", "VALUE", "OTHER", file_pattern="*.py")
    assert changed == {"src/util.py": 1}


# ── move / copy ──────────────────────────────────────────────────────────────

def test_move_file(populated: LocalFSAdapter, tmp_path: Path) -> None:
    populated.move_file("README.md", "docs/README.md")
    assert not (tmp_path / "README.md").exists()
    assert (tmp_path / "docs" / "README.md").exists()


def test_move_conflict(populated: LocalFSAdapter) -> None:
    with pytest.raises(FileAlreadyExistsError):
        populated.move_file("README.md", "src/main.py")


def test_move_overwrite(populated: LocalFSAdapter, tmp_path: Path) -> None:
    populated.move_file("README.md", "src/main.py", overwrite=True)
    assert (tmp_path / "src" / "main.py").read_text(encoding="utf-8") == "# Title\n"


def test_move_missing(populated: LocalFSAdapter) -> None:
    with pytest.raises(PathNotFoundError):
        populated.move_file("nope.txt", "x.txt")


def test_copy_file(populated: LocalFSAdapter, tmp_path: Path) -> None:
    populated.copy_file("README.md", "docs/README.md")
    assert (tmp_path / "README.md").exists()
    assert (tmp_path / "docs" / "README.md").exists()


def test_copy_same_file(populated: LocalFSAdapter) -> None:
    with pytest.raises(InvalidRequestError):
        populated.copy_file("README.md", "README.md")


# ── folders ──────────────────────────────────────────────────────────────────

def test_create_folder(workspace: LocalFSAdapter, tmp_path: Path) -> None:
    workspace.create_folder("a/b/c")
    assert (tmp_path / "a" / "b" / "c").is_dir()


def test_create_folder_existing_ok(workspace: LocalFSAdapter) -> None:
    workspace.create_folder("a/b")
    workspace.create_folder("a/b")


def test_create_folder_existing_not_ok(workspace: LocalFSAdapter) -> None:
    workspace.create_folder("a/b")
    with pytest.raises(FileAlreadyExistsError):
        workspace.create_folder("a/b", exist_ok=False)


def test_delete_folder(populated: LocalFSAdapter, tmp_path: Path) -> None:
    populated.delete_folder("src")
    assert not (tmp_path / "src").exists()


def test_delete_folder_missing(populated: LocalFSAdapter) -> None:
    with pytest.raises(PathNotFoundError):
        populated.delete_folder("nope")


def test_delete_file(populated: LocalFSAdapter, tmp_path: Path) -> None:
    populated.delete_file("README.md")
    assert not (tmp_path / "README.md").exists()


def test_delete_file_missing(populated: LocalFSAdapter) -> None:
    with pytest.raises(PathNotFoundError):
        populated.delete_file("nope.txt")


def test_delete_file_missing_allowed(populated: LocalFSAdapter) -> None:
    populated.delete_file("nope.txt", must_exist=False)


# ── path confinement ─────────────────────────────────────────────────────────

def test_relative_escape_rejected(populated: LocalFSAdapter) -> None:
    with pytest.raises(PathOutsideWorkspaceError):
        populated.read_file("../outside.txt")


def test_absolute_outside_rejected(populated: LocalFSAdapter, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(PathOutsideWorkspaceError):
        populated.read_file(str(outside))


def test_absolute_inside_allowed(populated: LocalFSAdapter, tmp_path: Path) -> None:
    result = populated.read_file(str(tmp_path / "README.md"))
    assert result.path == "README.md"


def test_empty_path_rejected(populated: LocalFSAdapter) -> None:
    with pytest.raises(InvalidRequestError):
        populated.read_file("")


def test_delete_root_rejected(populated: LocalFSAdapter) -> None:
    with pytest.raises(InvalidRequestError):
        populated.delete_folder(".")


def test_move_root_rejected(populated: LocalFSAdapter) -> None:
    with pytest.raises(InvalidRequestError):
        populated.move_file(".", "x")


def test_symlink_escape_rejected(
    populated: LocalFSAdapter, tmp_path: Path
) -> None:
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")

    with pytest.raises(PathOutsideWorkspaceError):
        populated.read_file("link.txt")
