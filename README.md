# git-hc (Hide Comments)

A Git extension that hides comments from source files in any repository, storing the original commented version in Git's own object storage, and uses Git's merge algorithm to restore comments into updated files.

**Requires python to run.**
## Features

- **Hides comments from any file**: `git hc <filename>`
- **Preserves code**: Strips single-line (`//`, `#`), multi-line (`/* ... */`), and inline comments using the open-source Pygments library (500+ languages supported). C/C++ preprocessor directives (`#include`, `#define`) are kept intact.
- **Git object storage**: Stores the commented version directly into Git's object database via `git hash-object -w`.
- **Three-way merge on restore**: When you run `git hc show <filename>`, it restores comments into the file, intelligently merging back any edits you made while comments were hidden.
- **Manifest file**: Supports `.githidecomments` at the repository root. You can manually list files in `.githidecomments`, and `git hc` / `git hc sync` will automatically hide their comments.
- **Status check**: `git hc status` shows all files currently tracked with hidden comments and their blob hashes.
- **Clean separation**: Test suites are completely isolated in `tests/` with real polyglot test fixtures.

## Installation

```bash
# Clone the repository
git clone <repo-url> hc
cd hc

# Install with pip (in editable/user mode)
pip install -e .

# Or using Makefile
make install
```

Ensure `~/.local/bin` is in your `PATH`.

## Usage

```bash
# Hide comments in a file (adds to .githidecomments and stores blob in Git object storage)
git hc src/main.c

# Check status of hidden files
git hc status

# Edit the file with your IDE/editor (no comments visible!)
vim src/main.c

# Restore comments back into the file (merges comments into your updated code)
git hc show src/main.c

# Or manually add files to .githidecomments and sync:
echo "src/utils.py" >> .githidecomments
git hc sync   # or simply: git hc
```

## Running Tests

```bash
# Run all tests (118 tests across unit and integration suites)
python3 -m pytest tests/ -v
```

## Motivation
Personally not a big fan of agents leaving too many comments -- makes everything unreadable.