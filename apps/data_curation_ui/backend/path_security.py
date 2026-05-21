from __future__ import annotations

from pathlib import Path


class PathSecurityError(ValueError):
    pass


def repo_root_from_backend() -> Path:
    return Path(__file__).resolve().parents[3]


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_under_repo(raw_path: str, repo_root: Path, *, must_exist: bool = False) -> Path:
    if not raw_path or not raw_path.strip():
        raise PathSecurityError("Path must be non-empty.")
    candidate = Path(raw_path.strip())
    if ".." in candidate.parts:
        raise PathSecurityError("Path traversal using '..' is not allowed.")
    resolved = (candidate if candidate.is_absolute() else repo_root / candidate).resolve()
    root = repo_root.resolve()
    if not _is_relative_to(resolved, root):
        raise PathSecurityError(f"Path must resolve inside repository root: {raw_path}")
    quarantine = (root / "data" / "source_quarantine").resolve()
    if resolved == quarantine or _is_relative_to(resolved, quarantine):
        raise PathSecurityError("Reading or writing data/source_quarantine is not allowed.")
    if must_exist and not resolved.exists():
        raise PathSecurityError(f"Path does not exist: {raw_path}")
    return resolved


def display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def safe_output_path(
    output_directory: str,
    output_filename: str,
    repo_root: Path,
    *,
    create_dir: bool = False,
) -> Path:
    if not output_filename.endswith(".jsonl"):
        raise PathSecurityError("Output filename must end with .jsonl.")
    if Path(output_filename).name != output_filename:
        raise PathSecurityError("Output filename must not contain path separators.")
    directory = resolve_under_repo(output_directory, repo_root)
    if not directory.exists():
        if create_dir:
            directory.mkdir(parents=True, exist_ok=True)
        else:
            raise PathSecurityError(
                f"Output directory does not exist: {output_directory}. Set create_dir=true to create it."
            )
    if not directory.is_dir():
        raise PathSecurityError(f"Output directory is not a directory: {output_directory}")
    return resolve_under_repo(str(directory / output_filename), repo_root)


def safe_existing_or_new_jsonl(raw_path: str, repo_root: Path) -> Path:
    path = resolve_under_repo(raw_path, repo_root)
    if path.suffix != ".jsonl":
        raise PathSecurityError("Output path must end with .jsonl.")
    if not path.parent.exists():
        raise PathSecurityError(f"Output directory does not exist: {display_path(path.parent, repo_root)}")
    return path

