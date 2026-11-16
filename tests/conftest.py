"""
conftest.py — Shared pytest fixtures.

Provides:
  git_repo   — a fresh git repo in a tmp directory; CWD is changed into it.
  polyglot   — the path to tests/fixtures/polyglot/ (cloned real code).
  hc_script  — absolute path to the git-hc entry-point script.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
FIXTURE_ROOT = HERE / 'fixtures' / 'polyglot'


# ── git_repo fixture ─────────────────────────────────────────────────────────

@pytest.fixture()
def git_repo(tmp_path):
    """
    Yield a Path pointing to a freshly initialised bare-minimum git repo.
    Changes the working directory into the repo while the test runs, then
    restores it afterwards.
    """
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'hc-test@example.com'],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'HC Test'],
        cwd=tmp_path, check=True, capture_output=True,
    )
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old_cwd)


# ── polyglot fixture ─────────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def polyglot():
    """
    Return the path to the polyglot fixture directory.
    Skips the whole test module if the fixtures haven't been fetched yet.
    Prefers files named hello_commented.* over other files for tests
    that assert on comments being present.
    """
    if not FIXTURE_ROOT.exists() or not any(FIXTURE_ROOT.iterdir()):
        pytest.skip(
            'Polyglot fixtures not found. Run `make fixtures` first.'
        )
    return FIXTURE_ROOT


# ── hc_script fixture ────────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def hc_script():
    """Return the absolute path to git-hc."""
    script = REPO_ROOT / 'git-hc'
    assert script.exists(), f'git-hc not found at {script}'
    return str(script)


# ── run_hc helper (available as fixture) ─────────────────────────────────────

@pytest.fixture()
def run_hc(hc_script):
    """
    Return a callable ``run_hc(*args)`` that invokes git-hc and returns
    a CompletedProcess.  CWD is whatever the test has set (usually git_repo).
    """
    def _run(*args):
        return subprocess.run(
            [sys.executable, hc_script] + list(args),
            capture_output=True,
            text=True,
        )
    return _run
