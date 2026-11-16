"""
test_comments.py — Unit tests for hc.comments (Pygments-based stripping).

Tests are grouped by:
  - Core invariants (line-count preservation, code survival)
  - Per-language comment patterns (C, Python, JS, Go, Rust, Java)
  - Real fixture files from leachim6/hello-world
  - has_comments() detection
  - Edge cases (empty files, files with no comments, strings vs comments)
"""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / 'src'))

from hc.comments import strip_comments, has_comments


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _count_lines(text: str) -> int:
    return text.count('\n')


def _has_no_comment_markers(text: str) -> bool:
    """Rough check: no // or /* or # (Python) remain as comments.
    Won't work perfectly for all cases but good enough for unit tests
    where the remaining code is known."""
    return '//' not in text and '/*' not in text


# ═══════════════════════════════════════════════════════════════════════════
#  Core invariants
# ═══════════════════════════════════════════════════════════════════════════

class TestLineCountInvariant:
    """The stripped output MUST have the same number of newlines as input."""

    def test_single_line_comment(self):
        code = '// file header\nint x = 1;\n'
        assert _count_lines(strip_comments('f.c', code)) == _count_lines(code)

    def test_multiline_block_comment(self):
        code = '/* line 1\n   line 2\n   line 3 */\nint x = 1;\n'
        assert _count_lines(strip_comments('f.c', code)) == _count_lines(code)

    def test_inline_comment(self):
        code = 'int x = 1; // end-of-line\nreturn x;\n'
        assert _count_lines(strip_comments('f.c', code)) == _count_lines(code)

    def test_mixed_comments(self):
        code = (
            '// header\n'
            '#include <stdio.h>\n'
            '/* block\n   comment */\n'
            'int main() {\n'
            '    int x = 10; // inline\n'
            '    return 0;\n'
            '}\n'
        )
        assert _count_lines(strip_comments('f.c', code)) == _count_lines(code)

    def test_empty_file(self):
        code = ''
        assert _count_lines(strip_comments('f.c', code)) == _count_lines(code)

    def test_no_comments(self):
        code = 'int x = 1;\nreturn x;\n'
        stripped = strip_comments('f.c', code)
        assert _count_lines(stripped) == _count_lines(code)
        assert stripped.strip() == code.strip()

    def test_python_line_comment(self):
        code = '# header\ndef foo():\n    # body\n    pass\n'
        assert _count_lines(strip_comments('f.py', code)) == _count_lines(code)


class TestCodeSurvival:
    """Code (non-comment) tokens must survive stripping intact."""

    def test_function_body_preserved(self):
        code = '// comment\nint add(int a, int b) {\n    return a + b;\n}\n'
        stripped = strip_comments('f.c', code)
        assert 'int add(int a, int b)' in stripped
        assert 'return a + b;' in stripped

    def test_string_literal_not_stripped(self):
        # Comments inside string literals must NOT be stripped
        # Use a 2-line snippet so CLexer has enough context to tokenize properly
        code = 'char *url = "http://example.com";\nint x = 1; // real comment\n'
        stripped = strip_comments('f.c', code)
        assert 'http://example.com' in stripped
        assert '// real comment' not in stripped

    def test_preprocessor_preserved(self):
        code = '#include <stdio.h>\n#define MAX 100\nint x;\n'
        stripped = strip_comments('f.c', code)
        assert '#include <stdio.h>' in stripped
        assert '#define MAX 100' in stripped

    def test_imports_preserved_python(self):
        code = '# comment\nimport os\nimport sys\n'
        stripped = strip_comments('f.py', code)
        assert 'import os' in stripped
        assert 'import sys' in stripped


# ═══════════════════════════════════════════════════════════════════════════
#  Per-language comment patterns
# ═══════════════════════════════════════════════════════════════════════════

class TestCComments:
    def test_single_line(self):
        stripped = strip_comments('f.c', '// comment\nint x;\n')
        assert '//' not in stripped
        assert 'int x;' in stripped

    def test_multiline_block(self):
        stripped = strip_comments('f.c', '/* block\n comment */\nint x;\n')
        assert '/*' not in stripped
        assert '*/' not in stripped
        assert 'int x;' in stripped

    def test_inline(self):
        # strip_comments preserves line count; inline comment is on same line as code
        # so code line stays, only the comment part is blanked
        stripped = strip_comments('f.c', 'int x = 1; // inline\nint y = 2;\n')
        assert '// inline' not in stripped
        assert 'int x = 1;' in stripped

    def test_preprocessor_kept(self):
        code = '#include <stdio.h>\n#define X 1\nint x;\n'
        stripped = strip_comments('f.c', code)
        assert '#include <stdio.h>' in stripped
        assert '#define X 1' in stripped


class TestPythonComments:
    def test_hash_comment(self):
        stripped = strip_comments('f.py', '# comment\nx = 1\n')
        assert '#' not in stripped
        assert 'x = 1' in stripped

    def test_inline_hash(self):
        stripped = strip_comments('f.py', 'x = 1  # inline\n')
        assert '# inline' not in stripped
        assert 'x = 1' in stripped

    def test_string_not_comment(self):
        # Regular string with hash inside is not a comment
        code = 'x = "not # a comment"\n'
        stripped = strip_comments('f.py', code)
        assert '"not # a comment"' in stripped


class TestJavaScriptComments:
    def test_single_line(self):
        stripped = strip_comments('f.js', '// js comment\nconst x = 1;\n')
        assert '//' not in stripped
        assert 'const x = 1;' in stripped

    def test_block_comment(self):
        stripped = strip_comments('f.js', '/* block */\nconst x = 1;\n')
        assert '/*' not in stripped
        assert 'const x = 1;' in stripped


class TestGoComments:
    def test_single_line(self):
        stripped = strip_comments('f.go', '// go comment\npackage main\n')
        assert '//' not in stripped
        assert 'package main' in stripped

    def test_block_comment(self):
        stripped = strip_comments('f.go', '/* block */\npackage main\n')
        assert '/*' not in stripped
        assert 'package main' in stripped


class TestRustComments:
    def test_single_line(self):
        stripped = strip_comments('f.rs', '// rust comment\nfn main() {}\n')
        assert '//' not in stripped
        assert 'fn main()' in stripped


class TestJavaComments:
    def test_single_line(self):
        stripped = strip_comments('f.java', '// java comment\nclass Foo {}\n')
        assert '//' not in stripped
        assert 'class Foo' in stripped

    def test_javadoc(self):
        code = '/** javadoc */\npublic void foo() {}\n'
        stripped = strip_comments('f.java', code)
        assert '/**' not in stripped
        assert 'public void foo()' in stripped


# ═══════════════════════════════════════════════════════════════════════════
#  Real fixture files
# ═══════════════════════════════════════════════════════════════════════════

class TestRealFixtures:
    """Test against actual source files cloned from leachim6/hello-world."""

    @pytest.mark.parametrize('lang,glob,fname', [
        ('c',          'c',          'f.c'),
        ('python',     'python',     'f.py'),
        ('javascript', 'javascript', 'f.js'),
        ('go',         'go',         'f.go'),
    ])
    def test_fixture_line_count_preserved(self, polyglot, lang, glob, fname):
        lang_dir = polyglot / glob
        if not lang_dir.exists():
            pytest.skip(f'No {lang} fixtures found')
        # Prefer the hello_commented file (has real comments); fall back to any file
        candidates = list(lang_dir.glob('hello_commented.*')) or list(lang_dir.glob('*'))
        if not candidates:
            pytest.skip(f'No files in {lang_dir}')
        source_file = candidates[0]
        content = source_file.read_text(encoding='utf-8', errors='replace')
        stripped = strip_comments(fname, content)
        assert _count_lines(stripped) == _count_lines(content), (
            f'{source_file.name}: line count changed after stripping'
        )

    def test_c_fixture_has_comments(self, polyglot):
        c_dir = polyglot / 'c'
        if not c_dir.exists():
            pytest.skip('No C fixtures')
        # Use the commented fixture explicitly
        candidates = list(c_dir.glob('hello_commented.*'))
        if not candidates:
            pytest.skip('No hello_commented C file')
        content = candidates[0].read_text(encoding='utf-8', errors='replace')
        # Our hello_commented.c always has comments
        assert has_comments('f.c', content)


# ═══════════════════════════════════════════════════════════════════════════
#  has_comments()
# ═══════════════════════════════════════════════════════════════════════════

class TestHasComments:
    def test_detects_single_line(self):
        assert has_comments('f.c', '// comment\nint x;') is True

    def test_detects_multiline(self):
        assert has_comments('f.c', '/* block */\nint x;') is True

    def test_detects_python(self):
        assert has_comments('f.py', '# comment\nx = 1') is True

    def test_no_comments_c(self):
        assert has_comments('f.c', 'int x = 1;\nreturn x;\n') is False

    def test_no_comments_py(self):
        assert has_comments('f.py', 'x = 1\ny = 2\n') is False

    def test_preproc_not_counted(self):
        # #include is a preprocessor directive, not a comment
        assert has_comments('f.c', '#include <stdio.h>\nint x;\n') is False

    def test_string_not_comment(self):
        assert has_comments('f.c', 'char *s = "// not a comment";\n') is False
