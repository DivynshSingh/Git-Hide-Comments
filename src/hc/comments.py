"""
comments.py — Strip source-code comments using Pygments.

Design decisions:
  - Uses Pygments lexer engine (MIT-licensed, 500+ languages).
  - NO custom comment-detection regex or hand-written parsers.
  - Preserves C/C++ preprocessor directives (#include, #define, #pragma)
    because Pygments classifies them as Comment.Preproc, not real comments.
  - Preserves exact line count between original and stripped output.
    This is critical: it makes the patch-based merge in merge.py reliable.
  - Each comment character is replaced with a space, then trailing
    whitespace per line is trimmed, so comment-only lines become empty lines.
"""

from pygments.lexers import get_lexer_for_filename, guess_lexer
from pygments.token import Comment
from pygments.util import ClassNotFound


def _get_lexer(filename: str, content: str, ensurenl: bool = True):
    """Resolve the best Pygments lexer for the given file."""
    try:
        return get_lexer_for_filename(filename, ensurenl=ensurenl)
    except ClassNotFound:
        return guess_lexer(content, ensurenl=ensurenl)


def _is_real_comment(ttype) -> bool:
    """
    Return True if the token type is a strippable comment.
    Excludes preprocessor tokens (#include, #define, etc.).
    """
    return (
        ttype in Comment
        and ttype not in Comment.Preproc
        and ttype not in Comment.PreprocFile
    )


def strip_comments(filename: str, content: str) -> str:
    """
    Strip comments from *content* (source code for *filename*).

    Returns a new string where every comment character is replaced by a space
    and trailing whitespace on each line is trimmed.  The number of newlines
    in the returned string is guaranteed to equal the number of newlines in
    *content* (line-count invariant).

    Args:
        filename: Used only to pick the correct Pygments lexer (e.g. 'main.c').
        content:  Full source text.

    Returns:
        Stripped source text with same line count as *content*.
    """
    # ensurenl=True (default) ensures Pygments always produces a trailing
    # newline token, which is what we rely on for the line-count invariant.
    lexer = _get_lexer(filename, content, ensurenl=True)
    tokens = list(lexer.get_tokens(content))

    result_chars: list[str] = []
    for ttype, val in tokens:
        if _is_real_comment(ttype):
            # Replace every non-newline character with a space so that
            # multi-line block comments don't collapse their embedded newlines.
            for ch in val:
                result_chars.append('\n' if ch == '\n' else ' ')
        else:
            result_chars.append(val)

    raw = ''.join(result_chars)
    # Rstrip each line.  Whitespace-only lines (from comment-only lines)
    # become empty strings, preserving the newline structure.
    lines = raw.split('\n')
    cleaned = '\n'.join(line.rstrip() for line in lines)

    # Pygments' ensurenl=True appends a trailing \n when the input doesn't
    # have one.  We must undo that so the output matches the input exactly.
    if not content.endswith('\n') and cleaned.endswith('\n'):
        cleaned = cleaned[:-1]

    return cleaned


def has_comments(filename: str, content: str) -> bool:
    """
    Return True if *content* contains at least one strippable comment.

    Args:
        filename: Used to pick the Pygments lexer.
        content:  Full source text.
    """
    lexer = _get_lexer(filename, content, ensurenl=False)
    for ttype, _ in lexer.get_tokens(content):
        if _is_real_comment(ttype):
            return True
    return False
