"""
store.py — Thin wrappers around Git's own object storage.

Uses only standard Git plumbing commands:
  - `git hash-object -w --stdin`  to write a blob
  - `git cat-file blob <sha>`     to read a blob
  - `git rev-parse --show-toplevel` to find the repo root

No custom binary format or external database is used.
"""

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    """Raised when a Git plumbing command fails."""


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, **kwargs)
    if result.returncode != 0:
        err = result.stderr.decode(errors='replace') if isinstance(result.stderr, bytes) else result.stderr
        raise GitError(f"Command {cmd} failed (exit {result.returncode}): {err.strip()}")
    return result


def git_root() -> str:
    """Return the absolute path of the nearest Git repository root."""
    result = _run(['git', 'rev-parse', '--show-toplevel'])
    return result.stdout.decode().strip()


def store_blob(content: str, encoding: str = 'utf-8') -> str:
    """
    Store *content* as a loose Git blob object and return its SHA-1 hex string.

    The object is written into the current repo's .git/objects store.
    Running `git gc` will pack it; `git prune` will eventually clean it
    if it's not reachable — but while the SHA is recorded in .githidecomments
    the user is responsible for keeping it.

    Args:
        content:  Text to store.
        encoding: Encoding used when converting str → bytes.

    Returns:
        40-character lowercase hex SHA-1 string.
    """
    result = _run(
        ['git', 'hash-object', '-w', '--stdin'],
        input=content.encode(encoding),
    )
    return result.stdout.decode().strip()


def read_blob(sha: str, encoding: str = 'utf-8') -> str:
    """
    Read a Git blob by its SHA-1 hash and return its contents as a string.

    Args:
        sha:      40-char (or abbreviated) hex SHA-1.
        encoding: Encoding used when converting bytes → str.

    Returns:
        Text content of the blob.

    Raises:
        GitError: If the SHA is unknown or the object is not a blob.
    """
    result = _run(['git', 'cat-file', 'blob', sha])
    return result.stdout.decode(encoding)
