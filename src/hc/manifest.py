"""
manifest.py — Manage the .githidecomments file.

Format (plain text, one entry per line):
    <repo-relative-path>:<40-char-sha1>

Example:
    src/main.c:a3f8b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9
    lib/util.py:0011223344556677889900aabbccddeeff001122

The file lives at the repo root so it can be committed (or .gitignored)
like any other dotfile.  Entries are kept sorted for determinism.
"""

from pathlib import Path

MANIFEST_NAME = '.githidecomments'


def _path(repo_root: str) -> Path:
    return Path(repo_root) / MANIFEST_NAME


def load(repo_root: str) -> dict[str, str]:
    """
    Parse .githidecomments and return ``{relpath: sha1}``.

    Returns an empty dict if the file doesn't exist.
    Supports both `file:sha` and plain `file` (pending sync).
    """
    p = _path(repo_root)
    if not p.exists():
        return {}
    entries: dict[str, str] = {}
    for raw in p.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            relpath, _, sha = line.partition(':')
            relpath = relpath.strip()
            sha = sha.strip()
            if relpath:
                entries[relpath] = sha
        else:
            relpath = line.strip()
            if relpath:
                entries[relpath] = ''
    return entries


def save(repo_root: str, entries: dict[str, str]) -> None:
    """Write *entries* back to .githidecomments (sorted, one per line)."""
    p = _path(repo_root)
    if entries:
        lines = [
            f'{k}:{v}' if v else k
            for k, v in sorted(entries.items())
        ]
        p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    else:
        # Keep the file but empty rather than deleting it
        p.write_text('', encoding='utf-8')


def add_entry(repo_root: str, relpath: str, sha: str) -> None:
    """Add or update the entry for *relpath* → *sha*."""
    entries = load(repo_root)
    entries[relpath] = sha
    save(repo_root, entries)


def remove_entry(repo_root: str, relpath: str) -> None:
    """Remove the entry for *relpath* (no-op if absent)."""
    entries = load(repo_root)
    entries.pop(relpath, None)
    save(repo_root, entries)


def is_hidden(repo_root: str, relpath: str) -> bool:
    """Return True if *relpath* currently has its comments hidden."""
    return relpath in load(repo_root)


def list_entries(repo_root: str) -> list[tuple[str, str]]:
    """Return a sorted list of ``(relpath, sha)`` pairs."""
    return sorted(load(repo_root).items())
