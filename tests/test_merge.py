"""
test_merge.py — Unit tests for hc.merge (patch-based comment restoration).

Tests are run inside a git_repo fixture so that `git diff --no-index` works.
"""

import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / 'src'))

from hc.merge import restore_comments, MergeError
from hc.comments import strip_comments


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════

C_WITH_COMMENTS = '''\
// file header comment
#include <stdio.h>

/* This block comment spans
   two lines */
int add(int a, int b) {
    // return the sum
    return a + b; // simple addition
}

int main() {
    int x = 10;
    // call add with 5
    int result = add(x, 5);
    printf("Result: %d\\n", result); // print it
    return 0;
}
'''

PY_WITH_COMMENTS = '''\
# module docstring comment
import os

# helper


def greet(name):
    # say hello
    print(f"Hello, {name}")  # inline


def main():
    greet("world")
    return 0
'''


# ═══════════════════════════════════════════════════════════════════════════
#  No-edit scenarios (user didn't change anything while hidden)
# ═══════════════════════════════════════════════════════════════════════════

class TestRestoreNoEdits:
    def test_c_no_edit_restores_original(self, git_repo):
        current = strip_comments('f.c', C_WITH_COMMENTS)
        merged, ok = restore_comments('f.c', C_WITH_COMMENTS, current)
        assert ok is True
        assert merged.strip() == C_WITH_COMMENTS.strip()

    def test_py_no_edit_restores_original(self, git_repo):
        current = strip_comments('f.py', PY_WITH_COMMENTS)
        merged, ok = restore_comments('f.py', PY_WITH_COMMENTS, current)
        assert ok is True
        assert merged.strip() == PY_WITH_COMMENTS.strip()

    def test_identical_input_returns_original(self, git_repo):
        """When current == original, nothing has changed at all."""
        merged, ok = restore_comments('f.c', C_WITH_COMMENTS, C_WITH_COMMENTS)
        assert ok is True
        assert merged == C_WITH_COMMENTS


# ═══════════════════════════════════════════════════════════════════════════
#  Simple edits (single value change)
# ═══════════════════════════════════════════════════════════════════════════

class TestRestoreSimpleEdits:
    def test_single_value_change(self, git_repo):
        base = strip_comments('f.c', C_WITH_COMMENTS)
        current = base.replace('    int x = 10;', '    int x = 42;')
        merged, ok = restore_comments('f.c', C_WITH_COMMENTS, current)
        assert ok is True
        assert 'int x = 42;' in merged
        assert '// file header comment' in merged
        assert '// return the sum' in merged

    def test_edit_in_function_body(self, git_repo):
        base = strip_comments('f.c', C_WITH_COMMENTS)
        current = base.replace('    return a + b;', '    return a + b + 1;')
        merged, ok = restore_comments('f.c', C_WITH_COMMENTS, current)
        assert ok is True
        assert 'return a + b + 1;' in merged
        # Comments in the function should come back
        assert '// return the sum' in merged

    def test_python_edit(self, git_repo):
        base = strip_comments('f.py', PY_WITH_COMMENTS)
        current = base.replace('    return 0', '    return 99')
        merged, ok = restore_comments('f.py', PY_WITH_COMMENTS, current)
        assert ok is True
        assert 'return 99' in merged
        assert '# module docstring comment' in merged


# ═══════════════════════════════════════════════════════════════════════════
#  Line-insertion edits
# ═══════════════════════════════════════════════════════════════════════════

class TestRestoreInsertions:
    def test_insert_new_line(self, git_repo):
        base = strip_comments('f.c', C_WITH_COMMENTS)
        current = base.replace(
            '    int x = 10;',
            '    int x = 10;\n    int y = 20;',
        )
        merged, ok = restore_comments('f.c', C_WITH_COMMENTS, current)
        assert ok is True
        assert 'int y = 20;' in merged
        assert '// file header comment' in merged

    def test_insert_function(self, git_repo):
        base = strip_comments('f.c', C_WITH_COMMENTS)
        new_fn = '\nint sub(int a, int b) {\n    return a - b;\n}\n'
        current = base.replace('\nint main()', new_fn + '\nint main()')
        merged, ok = restore_comments('f.c', C_WITH_COMMENTS, current)
        assert ok is True
        assert 'sub(int a, int b)' in merged


# ═══════════════════════════════════════════════════════════════════════════
#  Multi-language fixtures
# ═══════════════════════════════════════════════════════════════════════════

class TestRestoreMultiLanguage:
    @pytest.mark.parametrize('fname,code', [
        ('f.js', '// js comment\nconst x = 1;\nconst y = 2;\n'),
        ('f.go', '// go comment\npackage main\nfunc main() {}\n'),
        ('f.rs', '// rust comment\nfn main() {}\n'),
        ('f.java', '// java\nclass Foo { int x = 1; }\n'),
    ])
    def test_restore_no_edit(self, git_repo, fname, code):
        base = strip_comments(fname, code)
        merged, ok = restore_comments(fname, code, base)
        assert ok is True
        assert merged.strip() == code.strip()

    @pytest.mark.parametrize('fname,code,old,new', [
        ('f.js', '// js\nconst x = 1;\nconst y = 2;\n', 'const x = 1;', 'const x = 99;'),
        ('f.go', '// go\npackage main\nfunc main() {}\n', 'func main() {}', 'func main() { return }'),
    ])
    def test_restore_with_edit(self, git_repo, fname, code, old, new):
        base = strip_comments(fname, code)
        current = base.replace(old, new)
        merged, ok = restore_comments(fname, code, current)
        assert ok is True
        assert new in merged
        assert '//' in merged  # comment should be back


# ═══════════════════════════════════════════════════════════════════════════
#  Real fixture files
# ═══════════════════════════════════════════════════════════════════════════

class TestRestoreRealFixtures:
    def test_c_fixture_roundtrip(self, git_repo, polyglot):
        c_dir = polyglot / 'c'
        if not c_dir.exists():
            pytest.skip('No C fixtures')
        files = list(c_dir.glob('*'))
        if not files:
            pytest.skip('No C files in fixture')
        content = files[0].read_text(encoding='utf-8', errors='replace')
        base = strip_comments('f.c', content)
        merged, ok = restore_comments('f.c', content, base)
        assert ok is True
        assert merged.strip() == content.strip()

    def test_python_fixture_roundtrip(self, git_repo, polyglot):
        py_dir = polyglot / 'python'
        if not py_dir.exists():
            pytest.skip('No Python fixtures')
        files = list(py_dir.glob('*'))
        if not files:
            pytest.skip('No Python files in fixture')
        content = files[0].read_text(encoding='utf-8', errors='replace')
        base = strip_comments('f.py', content)
        merged, ok = restore_comments('f.py', content, base)
        assert ok is True
        assert merged.strip() == content.strip()
