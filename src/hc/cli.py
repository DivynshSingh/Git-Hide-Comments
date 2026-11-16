"""
cli.py — CLI implementation for git-hc.
"""

import sys
import os
import argparse
from pathlib import Path

from .store import store_blob, read_blob, git_root, GitError
from .manifest import load, add_entry, remove_entry, is_hidden, list_entries
from .comments import strip_comments, has_comments
from .merge import restore_comments, MergeError


def _resolve_relpath(filepath: str, root: str) -> tuple[Path, str]:
    """Return (absolute Path, repo-relative POSIX string)."""
    abs_path = Path(filepath).resolve()
    try:
        relpath = abs_path.relative_to(root).as_posix()
    except ValueError:
        _die(f"'{filepath}' is outside the git repository root '{root}'")
    return abs_path, relpath


def _die(msg: str, code: int = 1) -> None:
    print(f'git hc: error: {msg}', file=sys.stderr)
    sys.exit(code)


def cmd_hide(args: argparse.Namespace) -> None:
    """Hide comments in a file."""
    try:
        root = git_root()
    except GitError as exc:
        _die(str(exc))

    abs_path, relpath = _resolve_relpath(args.file, root)

    if not abs_path.exists():
        _die(f"'{args.file}' does not exist")

    if is_hidden(root, relpath):
        _die(f"'{relpath}' already has its comments hidden")

    content = abs_path.read_text(encoding='utf-8')

    if not has_comments(abs_path.name, content):
        print(f"git hc: no detectable comments in '{relpath}' — nothing to do")
        return

    sha = store_blob(content)
    stripped = strip_comments(abs_path.name, content)
    abs_path.write_text(stripped, encoding='utf-8')
    add_entry(root, relpath, sha)

    print(f"git hc: comments hidden in '{relpath}'  (blob {sha[:8]})")


def cmd_show(args: argparse.Namespace) -> None:
    """Restore comments into a file, merging any user edits made while hidden."""
    try:
        root = git_root()
    except GitError as exc:
        _die(str(exc))

    abs_path, relpath = _resolve_relpath(args.file, root)

    entries = load(root)
    if relpath not in entries:
        _die(f"'{relpath}' is not listed in .githidecomments")

    sha = entries[relpath]

    try:
        original = read_blob(sha)
    except GitError as exc:
        _die(
            f"Cannot read stored blob {sha[:8]} for '{relpath}'.\n"
            f"  The blob may have been pruned from Git object storage.\n"
            f"  Details: {exc}"
        )

    if not abs_path.exists():
        _die(f"'{args.file}' does not exist on disk")

    current = abs_path.read_text(encoding='utf-8')

    try:
        merged, success = restore_comments(abs_path.name, original, current)
    except MergeError as exc:
        _die(str(exc))

    abs_path.write_text(merged, encoding='utf-8')

    if success:
        remove_entry(root, relpath)
        print(f"git hc: comments restored in '{relpath}'")
    else:
        print(
            f'git hc: WARNING — conflicts occurred when restoring comments in\n'
            f"  '{relpath}'\n"
            f'  Conflict markers have been inserted into the file.\n'
            f"  '{relpath}' has NOT been removed from .githidecomments.\n"
            f'  Fix the conflicts, then run `git hc show {args.file}` again.',
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_status(args: argparse.Namespace) -> None:  # noqa: ARG001
    """List all files with currently hidden comments."""
    try:
        root = git_root()
    except GitError as exc:
        _die(str(exc))

    entries = list_entries(root)

    if not entries:
        print('git hc: no files with hidden comments')
        return

    col = max(len(r) for r, _ in entries)
    col = max(col, 4)  # minimum column width for header
    print(f"{'File':<{col}}  Blob SHA")
    print('─' * (col + 10))
    for relpath, sha in entries:
        display_sha = sha[:8] if sha else '(pending)'
        print(f'{relpath:<{col}}  {display_sha}')


def cmd_sync(args: argparse.Namespace) -> None:
    """Sync all files mentioned in .githidecomments (hide comments for pending entries)."""
    try:
        root = git_root()
    except GitError as exc:
        _die(str(exc))

    entries = load(root)
    if not entries:
        print('git hc: no files listed in .githidecomments')
        return

    updated_any = False
    for relpath, sha in list(entries.items()):
        abs_path = Path(root) / relpath
        if not abs_path.exists():
            print(f"git hc: warning: '{relpath}' does not exist on disk", file=sys.stderr)
            continue

        content = abs_path.read_text(encoding='utf-8')
        if not sha:
            if has_comments(abs_path.name, content):
                blob_sha = store_blob(content)
                stripped = strip_comments(abs_path.name, content)
                abs_path.write_text(stripped, encoding='utf-8')
                add_entry(root, relpath, blob_sha)
                print(f"git hc: comments hidden in '{relpath}'  (blob {blob_sha[:8]})")
            else:
                blob_sha = store_blob(content)
                add_entry(root, relpath, blob_sha)
                print(f"git hc: registered '{relpath}'  (blob {blob_sha[:8]})")
            updated_any = True

    if not updated_any:
        cmd_status(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='git hc',
        description='Hide / restore source-code comments using Git object storage.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Examples:\n'
            '  git hc src/main.c          # hide comments\n'
            '  git hc hide src/main.c     # same\n'
            '  git hc status              # list hidden files\n'
            '  git hc show src/main.c     # restore comments\n'
            '  git hc sync                # hide comments for files in .githidecomments\n'
        ),
    )
    sub = parser.add_subparsers(dest='cmd', metavar='COMMAND')

    p_hide = sub.add_parser('hide', help='Hide comments in <file>')
    p_hide.add_argument('file', metavar='FILE')

    p_show = sub.add_parser('show', help='Restore comments in <file>')
    p_show.add_argument('file', metavar='FILE')

    sub.add_parser('status', help='List files with hidden comments')
    sub.add_parser('sync', help='Sync files listed in .githidecomments')

    return parser


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    known_cmds = {'hide', 'show', 'status', 'sync', '--help', '-h'}
    if argv and argv[0] not in known_cmds:
        argv = ['hide'] + argv

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd is None:
        try:
            root = git_root()
            manifest_file = Path(root) / '.githidecomments'
            if manifest_file.exists() and manifest_file.read_text().strip():
                cmd_sync(args)
                return
        except Exception:
            pass
        parser.print_help()
        sys.exit(0)

    dispatch = {
        'hide': cmd_hide,
        'show': cmd_show,
        'status': cmd_status,
        'sync': cmd_sync,
    }
    dispatch[args.cmd](args)
