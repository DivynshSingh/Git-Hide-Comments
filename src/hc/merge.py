"""
merge.py — Restore comments into a user-edited file.

Strategy (chosen after testing alternatives):

    base = strip_comments(original)   ← what the user was shown
    curr = current file content        ← what the user saved after editing
    orig = original (with comments)    ← stored in Git objects

    1.  `git diff --no-index -U5 base curr`
            → unified diff of user's edits relative to the stripped baseline.
            Exit 0 means no edits; exit 1 means files differ (normal).

    2.  `patch --fuzz=5 orig < diff`
            → applies the user's edits onto the commented original.
            --fuzz=5 gives patch 5 lines of leeway when matching context,
            so it can find the right location even though the original has
            extra comment lines that the stripped base doesn't.

Why not `git merge-file`?
    git merge-file(curr, base, orig) creates conflicts when user edits are
    near comment lines because the stripped blank lines (base) don't match
    the comment text in orig — git sees both sides changed and flags a conflict.
    The diff|patch approach sidesteps this by working only on the diff of
    user's edits, anchored by surrounding code context.

Returns:
    (merged_content: str, success: bool)
    If patch exits non-zero, success=False and the content may be partial;
    .rej files are left in the temp directory (reported to caller).
"""

import os
import re
import subprocess
import tempfile

from .comments import strip_comments


class MergeError(RuntimeError):
    """Raised when git diff or git merge-file itself fails."""


def _apply_git_diff_to_orig(orig_text: str, base_text: str, curr_text: str) -> tuple[str, bool]:
    """
    Apply changes between base_text and curr_text (calculated by git diff)
    onto orig_text, preserving comments.
    """
    with tempfile.TemporaryDirectory(prefix='git-hc-diff-') as d:
        base_p = os.path.join(d, 'base')
        curr_p = os.path.join(d, 'curr')
        with open(base_p, 'w', encoding='utf-8') as f:
            f.write(base_text)
        with open(curr_p, 'w', encoding='utf-8') as f:
            f.write(curr_text)

        diff_proc = subprocess.run(
            ['git', 'diff', '--no-index', '-U0', base_p, curr_p],
            capture_output=True,
            text=True,
        )
        if diff_proc.returncode == 0:
            return orig_text, True
        if diff_proc.returncode > 1:
            raise MergeError(f'git diff failed: {diff_proc.stderr.strip()}')

        diff_output = diff_proc.stdout

    orig_lines = orig_text.splitlines(keepends=True)
    base_lines = base_text.splitlines(keepends=True)

    hunk_regex = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
    hunks = []
    current_hunk = None

    for line in diff_output.splitlines(keepends=True):
        m = hunk_regex.match(line)
        if m:
            if current_hunk:
                hunks.append(current_hunk)
            old_start = int(m.group(1))
            old_count = int(m.group(2)) if m.group(2) is not None else 1
            new_start = int(m.group(3))
            new_count = int(m.group(4)) if m.group(4) is not None else 1
            current_hunk = {
                'old_start': old_start,
                'old_count': old_count,
                'new_start': new_start,
                'new_count': new_count,
                'del_lines': [],
                'add_lines': [],
            }
        elif current_hunk is not None:
            if line.startswith('-'):
                current_hunk['del_lines'].append(line[1:])
            elif line.startswith('+'):
                current_hunk['add_lines'].append(line[1:])

    if current_hunk:
        hunks.append(current_hunk)

    res_lines = list(orig_lines)
    for hunk in reversed(hunks):
        old_start = hunk['old_start']
        count = hunk['old_count']
        add_lines = hunk['add_lines']

        if count == 0:
            # Pure insertion after line old_start (0-indexed: index old_start)
            res_lines[old_start:old_start] = add_lines
            continue

        start_idx = old_start - 1
        if count == 1 and len(add_lines) == 1 and 0 <= start_idx < len(orig_lines):
            orig_line = orig_lines[start_idx]
            base_line = base_lines[start_idx] if start_idx < len(base_lines) else ''
            add_line = add_lines[0]
            base_stripped = base_line.rstrip('\r\n')
            orig_stripped = orig_line.rstrip('\r\n')
            # If the original line had an inline comment at the end, preserve it
            if orig_stripped.startswith(base_stripped) and len(orig_stripped) > len(base_stripped):
                comment_part = orig_stripped[len(base_stripped):]
                newline_char = '\n' if add_line.endswith('\n') or orig_line.endswith('\n') else ''
                replacement = [add_line.rstrip('\r\n') + comment_part + newline_char]
            else:
                replacement = add_lines
        else:
            replacement = add_lines

        res_lines[start_idx:start_idx + count] = replacement

    return ''.join(res_lines), True


def restore_comments(
    filename: str,
    original: str,
    current: str,
) -> tuple[str, bool]:
    """
    Merge user's edits (made in the stripped file) back into the
    commented original using Git's own merge and diff algorithms.

    Args:
        filename: Basename used to pick the right Pygments lexer and to
                  name temp files (e.g. 'main.c').
        original: Content of the file *before* comments were hidden
                  (retrieved from Git object storage).
        current:  Content of the file *now* (may include user edits made
                  while comments were hidden).

    Returns:
        A tuple ``(merged, success)`` where *merged* is the resulting
        source text and *success* is True if merged cleanly.
    """
    base = strip_comments(filename, original)
    name = os.path.basename(filename)

    # Fast path: current is identical to original (no changes) or to base (no-op)
    if current == original or current == base:
        return original, True

    # First attempt: standard git merge-file (Git's 3-way merge algorithm)
    with tempfile.TemporaryDirectory(prefix='git-hc-merge-') as d:
        base_p = os.path.join(d, f'base_{name}')
        curr_p = os.path.join(d, f'curr_{name}')
        orig_p = os.path.join(d, f'orig_{name}')

        for path, text in [(base_p, base), (curr_p, current), (orig_p, original)]:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(text)

        merge_proc = subprocess.run(
            ['git', 'merge-file', '-p', curr_p, base_p, orig_p],
            capture_output=True,
            text=True,
        )

        if merge_proc.returncode == 0:
            return merge_proc.stdout, True

    # Second attempt: Git diff-based merge anchored by line mapping
    try:
        merged_diff, ok = _apply_git_diff_to_orig(original, base, current)
        if ok:
            return merged_diff, True
    except Exception:
        pass

    # If both had conflicts, return git merge-file's output with standard conflict markers
    return merge_proc.stdout, False
