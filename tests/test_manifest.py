"""
test_manifest.py — Unit tests for hc.manifest (.githidecomments management).

Each test uses an isolated temp directory (no git repo required; the manifest
module only does file I/O, it doesn't call git).
"""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / 'src'))

from hc.manifest import (
    load,
    save,
    add_entry,
    remove_entry,
    is_hidden,
    list_entries,
    MANIFEST_NAME,
)


@pytest.fixture()
def repo(tmp_path):
    """Return a tmp_path that acts as a mock repo root (no .git needed)."""
    return str(tmp_path)


# ═══════════════════════════════════════════════════════════════════════════
#  load()
# ═══════════════════════════════════════════════════════════════════════════

class TestLoad:
    def test_missing_file_returns_empty(self, repo):
        assert load(repo) == {}

    def test_single_entry(self, repo):
        Path(repo, MANIFEST_NAME).write_text('src/main.c:abc123\n')
        assert load(repo) == {'src/main.c': 'abc123'}

    def test_multiple_entries(self, repo):
        content = 'a.c:sha1\nb.py:sha2\nc.js:sha3\n'
        Path(repo, MANIFEST_NAME).write_text(content)
        entries = load(repo)
        assert entries == {'a.c': 'sha1', 'b.py': 'sha2', 'c.js': 'sha3'}

    def test_ignores_blank_lines(self, repo):
        Path(repo, MANIFEST_NAME).write_text('\na.c:sha1\n\n')
        assert load(repo) == {'a.c': 'sha1'}

    def test_ignores_empty_and_comments(self, repo):
        Path(repo, MANIFEST_NAME).write_text('valid:sha1\n# comment line\n:emptypath\n')
        entries = load(repo)
        assert 'valid' in entries
        assert '# comment line' not in entries
        assert '' not in entries

    def test_plain_path_entry_has_empty_sha(self, repo):
        Path(repo, MANIFEST_NAME).write_text('file_without_sha.c\n')
        entries = load(repo)
        assert 'file_without_sha.c' in entries
        assert entries['file_without_sha.c'] == ''

    def test_whitespace_trimmed(self, repo):
        Path(repo, MANIFEST_NAME).write_text('  src/main.c : abc123  \n')
        assert load(repo) == {'src/main.c': 'abc123'}


# ═══════════════════════════════════════════════════════════════════════════
#  save()
# ═══════════════════════════════════════════════════════════════════════════

class TestSave:
    def test_creates_file(self, repo):
        save(repo, {'a.c': 'sha1'})
        assert Path(repo, MANIFEST_NAME).exists()

    def test_sorted_output(self, repo):
        save(repo, {'z.c': 'sha3', 'a.c': 'sha1', 'm.py': 'sha2'})
        lines = Path(repo, MANIFEST_NAME).read_text().strip().splitlines()
        assert lines == ['a.c:sha1', 'm.py:sha2', 'z.c:sha3']

    def test_empty_dict_writes_empty_file(self, repo):
        save(repo, {})
        assert Path(repo, MANIFEST_NAME).read_text() == ''

    def test_roundtrip(self, repo):
        original = {'src/main.c': 'aaa', 'lib/util.py': 'bbb'}
        save(repo, original)
        assert load(repo) == original


# ═══════════════════════════════════════════════════════════════════════════
#  add_entry() / remove_entry()
# ═══════════════════════════════════════════════════════════════════════════

class TestAddRemove:
    def test_add_creates_entry(self, repo):
        add_entry(repo, 'main.c', 'sha1')
        assert load(repo) == {'main.c': 'sha1'}

    def test_add_multiple(self, repo):
        add_entry(repo, 'a.c', 'sha1')
        add_entry(repo, 'b.py', 'sha2')
        assert load(repo) == {'a.c': 'sha1', 'b.py': 'sha2'}

    def test_add_overwrites_existing(self, repo):
        add_entry(repo, 'main.c', 'oldsha')
        add_entry(repo, 'main.c', 'newsha')
        assert load(repo)['main.c'] == 'newsha'

    def test_remove_existing(self, repo):
        add_entry(repo, 'main.c', 'sha1')
        remove_entry(repo, 'main.c')
        assert 'main.c' not in load(repo)

    def test_remove_nonexistent_no_error(self, repo):
        # Should not raise
        remove_entry(repo, 'does-not-exist.c')

    def test_remove_leaves_others(self, repo):
        add_entry(repo, 'a.c', 'sha1')
        add_entry(repo, 'b.py', 'sha2')
        remove_entry(repo, 'a.c')
        assert load(repo) == {'b.py': 'sha2'}


# ═══════════════════════════════════════════════════════════════════════════
#  is_hidden()
# ═══════════════════════════════════════════════════════════════════════════

class TestIsHidden:
    def test_true_when_present(self, repo):
        add_entry(repo, 'main.c', 'sha')
        assert is_hidden(repo, 'main.c') is True

    def test_false_when_absent(self, repo):
        assert is_hidden(repo, 'main.c') is False

    def test_false_after_removal(self, repo):
        add_entry(repo, 'main.c', 'sha')
        remove_entry(repo, 'main.c')
        assert is_hidden(repo, 'main.c') is False


# ═══════════════════════════════════════════════════════════════════════════
#  list_entries()
# ═══════════════════════════════════════════════════════════════════════════

class TestListEntries:
    def test_empty(self, repo):
        assert list_entries(repo) == []

    def test_sorted_by_path(self, repo):
        add_entry(repo, 'z.c', 'sha3')
        add_entry(repo, 'a.c', 'sha1')
        entries = list_entries(repo)
        assert [r for r, _ in entries] == ['a.c', 'z.c']

    def test_returns_tuples(self, repo):
        add_entry(repo, 'main.c', 'sha1')
        entries = list_entries(repo)
        assert entries == [('main.c', 'sha1')]
