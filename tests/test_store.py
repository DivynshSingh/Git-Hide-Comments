"""
test_store.py — Unit tests for hc.store (Git object storage).

Each test runs in an isolated git repo (git_repo fixture).
"""

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / 'src'))

from hc.store import store_blob, read_blob, git_root, GitError


# ═══════════════════════════════════════════════════════════════════════════
#  store_blob / read_blob
# ═══════════════════════════════════════════════════════════════════════════

class TestStoreBlob:
    def test_returns_40_char_hex(self, git_repo):
        sha = store_blob('hello world')
        assert len(sha) == 40
        assert all(c in '0123456789abcdef' for c in sha)

    def test_roundtrip(self, git_repo):
        content = '// original content\nint x = 1;\n'
        sha = store_blob(content)
        retrieved = read_blob(sha)
        assert retrieved == content

    def test_roundtrip_multiline(self, git_repo):
        content = 'line 1\nline 2\nline 3\n'
        sha = store_blob(content)
        assert read_blob(sha) == content

    def test_sha_is_deterministic(self, git_repo):
        sha1 = store_blob('same content')
        sha2 = store_blob('same content')
        assert sha1 == sha2

    def test_different_content_different_sha(self, git_repo):
        sha1 = store_blob('content A')
        sha2 = store_blob('content B')
        assert sha1 != sha2

    def test_empty_string(self, git_repo):
        sha = store_blob('')
        assert len(sha) == 40
        assert read_blob(sha) == ''

    def test_unicode_content(self, git_repo):
        content = '// こんにちは\nint x = 1;\n'
        sha = store_blob(content)
        assert read_blob(sha) == content

    def test_binary_data_roundtrip(self, git_repo):
        # Store a string with unusual whitespace
        content = '\t\t\n    spaces   \n\r\n'
        sha = store_blob(content)
        assert read_blob(sha) == content


class TestReadBlob:
    def test_bad_sha_raises_git_error(self, git_repo):
        with pytest.raises(GitError):
            read_blob('0' * 40)

    def test_abbreviated_sha_works(self, git_repo):
        content = 'short sha test'
        sha = store_blob(content)
        # Git accepts abbreviated SHAs (first 7 chars usually unique in small repos)
        assert read_blob(sha[:7]) == content


# ═══════════════════════════════════════════════════════════════════════════
#  git_root
# ═══════════════════════════════════════════════════════════════════════════

class TestGitRoot:
    def test_returns_string(self, git_repo):
        root = git_root()
        assert isinstance(root, str)

    def test_root_is_valid_dir(self, git_repo):
        root = git_root()
        assert Path(root).is_dir()

    def test_root_contains_dot_git(self, git_repo):
        root = git_root()
        assert (Path(root) / '.git').exists()

    def test_root_matches_tmp_path(self, git_repo):
        root = git_root()
        assert Path(root).resolve() == git_repo.resolve()
