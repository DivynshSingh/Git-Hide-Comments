"""
test_integration.py — End-to-end tests for the git-hc CLI.

Each test:
  1. Runs in an isolated git repo (git_repo fixture).
  2. Copies a real polyglot fixture file into the repo.
  3. Calls git-hc via subprocess (run_hc fixture).
  4. Asserts on filesystem state and exit codes.

These tests cover the full pipeline:
  hide → status → edit → show
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / 'src'))

FIXTURE_ROOT = HERE / 'fixtures' / 'polyglot'

# ─────────────────── inline fixture code (no network needed) ────────────────

C_CODE = '''\
// A simple C program
#include <stdio.h>

/* Entry point */
int main() {
    // Print greeting
    printf("Hello, World!\\n"); // end-of-line comment
    return 0; // success
}
'''

PY_CODE = '''\
# Python hello world
import sys

# Main function


def main():
    # Say hello
    print("Hello, World!")  # print it
    return 0
'''

JS_CODE = '''\
// JavaScript hello world
const msg = "Hello, World!";

/* Log it */
console.log(msg); // output
'''


# ════════════════════════════════════════════════════════════════════════════
#  Basic hide / show / status
# ════════════════════════════════════════════════════════════════════════════

class TestHideCommand:
    def test_hide_removes_comments(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        result = run_hc('hello.c')
        assert result.returncode == 0, result.stderr
        content = f.read_text()
        assert '//' not in content
        assert '/*' not in content

    def test_hide_preserves_code(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        run_hc('hello.c')
        content = f.read_text()
        assert 'printf' in content
        assert 'return 0;' in content
        assert '#include <stdio.h>' in content   # preprocessor kept

    def test_hide_creates_manifest(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        run_hc('hello.c')
        manifest = git_repo / '.githidecomments'
        assert manifest.exists()
        assert 'hello.c' in manifest.read_text()

    def test_hide_subcommand_explicit(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        result = run_hc('hide', 'hello.c')
        assert result.returncode == 0

    def test_hide_nonexistent_file_fails(self, git_repo, run_hc):
        result = run_hc('nonexistent.c')
        assert result.returncode != 0

    def test_double_hide_fails(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        run_hc('hello.c')
        result = run_hc('hello.c')
        assert result.returncode != 0

    def test_hide_file_without_comments(self, git_repo, run_hc):
        f = git_repo / 'bare.c'
        f.write_text('int x = 1;\nreturn 0;\n')
        result = run_hc('bare.c')
        # Should succeed (or exit 0 with no-op message) but not hide
        manifest = git_repo / '.githidecomments'
        if manifest.exists():
            assert 'bare.c' not in manifest.read_text()


class TestStatusCommand:
    def test_status_empty(self, git_repo, run_hc):
        result = run_hc('status')
        assert result.returncode == 0
        assert 'no files' in result.stdout.lower()

    def test_status_shows_hidden_file(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        run_hc('hello.c')
        result = run_hc('status')
        assert result.returncode == 0
        assert 'hello.c' in result.stdout

    def test_status_shows_blob_sha(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        run_hc('hello.c')
        result = run_hc('status')
        # Should show at least 8 hex chars (abbreviated SHA)
        import re
        assert re.search(r'[0-9a-f]{8}', result.stdout), result.stdout

    def test_status_multiple_files(self, git_repo, run_hc):
        for name, code in [('a.c', C_CODE), ('b.py', PY_CODE)]:
            (git_repo / name).write_text(code)
            run_hc(name)
        result = run_hc('status')
        assert 'a.c' in result.stdout
        assert 'b.py' in result.stdout


class TestSyncAndManualManifest:
    def test_manual_githidecomments_sync(self, git_repo, run_hc):
        # User manually adds a file to .githidecomments
        f = git_repo / 'manual.c'
        f.write_text(C_CODE)
        manifest = git_repo / '.githidecomments'
        manifest.write_text('manual.c\n')

        # Run git hc (no args) or git hc sync
        res = run_hc('sync')
        assert res.returncode == 0
        content = f.read_text()
        assert '//' not in content
        assert 'manual.c' in manifest.read_text()
        assert ':' in manifest.read_text()  # now has blob sha

    def test_no_args_triggers_sync_on_existing_manifest(self, git_repo, run_hc):
        f = git_repo / 'auto.py'
        f.write_text(PY_CODE)
        manifest = git_repo / '.githidecomments'
        manifest.write_text('auto.py\n')

        res = run_hc()
        assert res.returncode == 0
        content = f.read_text()
        assert '#' not in content


class TestShowCommand:
    def test_show_restores_comments(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        run_hc('hello.c')
        result = run_hc('show', 'hello.c')
        assert result.returncode == 0, result.stderr
        content = f.read_text()
        assert '//' in content

    def test_show_exact_roundtrip(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        run_hc('hello.c')
        run_hc('show', 'hello.c')
        assert f.read_text().strip() == C_CODE.strip()

    def test_show_removes_manifest_entry(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        run_hc('hello.c')
        run_hc('show', 'hello.c')
        manifest = (git_repo / '.githidecomments').read_text()
        assert 'hello.c' not in manifest

    def test_show_unknown_file_fails(self, git_repo, run_hc):
        result = run_hc('show', 'not-hidden.c')
        assert result.returncode != 0

    def test_show_disappears_from_status(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        run_hc('hello.c')
        run_hc('show', 'hello.c')
        result = run_hc('status')
        assert 'hello.c' not in result.stdout

    def test_show_python(self, git_repo, run_hc):
        f = git_repo / 'hello.py'
        f.write_text(PY_CODE)
        run_hc('hello.py')
        run_hc('show', 'hello.py')
        assert f.read_text().strip() == PY_CODE.strip()

    def test_show_javascript(self, git_repo, run_hc):
        f = git_repo / 'hello.js'
        f.write_text(JS_CODE)
        run_hc('hello.js')
        run_hc('show', 'hello.js')
        assert f.read_text().strip() == JS_CODE.strip()


# ════════════════════════════════════════════════════════════════════════════
#  Hide → Edit → Show (the core workflow)
# ════════════════════════════════════════════════════════════════════════════

class TestHideEditShow:
    def test_simple_value_change_preserved(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        run_hc('hello.c')

        # User changes return value while comments are hidden
        content = f.read_text()
        f.write_text(content.replace('return 0;', 'return 42;'))

        result = run_hc('show', 'hello.c')
        assert result.returncode == 0, result.stderr

        final = f.read_text()
        assert 'return 42;' in final           # user's edit preserved
        assert '// A simple C program' in final  # top comment back
        assert '/* Entry point */' in final      # block comment back

    def test_added_line_preserved(self, git_repo, run_hc):
        f = git_repo / 'hello.c'
        f.write_text(C_CODE)
        run_hc('hello.c')

        content = f.read_text()
        f.write_text(content.replace(
            'return 0;',
            'int y = 99;\n    return 0;'
        ))

        result = run_hc('show', 'hello.c')
        assert result.returncode == 0, result.stderr

        final = f.read_text()
        assert 'int y = 99;' in final
        assert '//' in final  # at least one comment back

    def test_python_edit_preserved(self, git_repo, run_hc):
        f = git_repo / 'hello.py'
        f.write_text(PY_CODE)
        run_hc('hello.py')

        content = f.read_text()
        f.write_text(content.replace('print("Hello, World!")', 'print("Hi!")'))

        result = run_hc('show', 'hello.py')
        assert result.returncode == 0, result.stderr

        final = f.read_text()
        assert 'print("Hi!")' in final
        assert '# Python hello world' in final

    def test_multiple_files_independent(self, git_repo, run_hc):
        fc = git_repo / 'hello.c'
        fp = git_repo / 'hello.py'
        fc.write_text(C_CODE)
        fp.write_text(PY_CODE)

        run_hc('hello.c')
        run_hc('hello.py')

        # Edit both while hidden
        fc.write_text(fc.read_text().replace('return 0;', 'return 1;'))
        fp.write_text(fp.read_text().replace('return 0', 'return 2'))

        run_hc('show', 'hello.c')
        run_hc('show', 'hello.py')

        assert 'return 1;' in fc.read_text()
        assert '//' in fc.read_text()

        assert 'return 2' in fp.read_text()
        assert '#' in fp.read_text()


# ════════════════════════════════════════════════════════════════════════════
#  Real polyglot fixture files
# ════════════════════════════════════════════════════════════════════════════

class TestRealPolyglotFixtures:
    @pytest.mark.parametrize('lang_dir,ext', [
        ('c', 'c'),
        ('python', 'py'),
        ('javascript', 'js'),
        ('go', 'go'),
    ])
    def test_hide_show_roundtrip(self, git_repo, run_hc, polyglot, lang_dir, ext):
        src_dir = polyglot / lang_dir
        if not src_dir.exists():
            pytest.skip(f'No {lang_dir} fixture directory')
        candidates = list(src_dir.glob('hello_commented.*')) or list(src_dir.glob('*'))
        if not candidates:
            pytest.skip(f'No files in {src_dir}')

        src = candidates[0]
        dest = git_repo / f'hello.{ext}'
        shutil.copy(src, dest)

        original = dest.read_text(encoding='utf-8', errors='replace')

        result = run_hc(f'hello.{ext}')
        assert result.returncode == 0, f'hide failed: {result.stderr}'

        result = run_hc('show', f'hello.{ext}')
        assert result.returncode == 0, f'show failed: {result.stderr}'

        restored = dest.read_text(encoding='utf-8', errors='replace')
        assert restored.strip() == original.strip(), (
            f'{src.name}: round-trip failed — restored content differs from original'
        )
