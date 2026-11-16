# ──────────────────────────────────────────────────────────────
#  git hc — Makefile
# ──────────────────────────────────────────────────────────────
SHELL       := /bin/bash
PYTHON      := python3
PIP         := $(PYTHON) -m pip
INSTALL_DIR := $(HOME)/.local/bin
FIXTURE_DIR := tests/fixtures/polyglot

.PHONY: all install uninstall test fixtures clean help

all: help

# ── install ───────────────────────────────────────────────────
install: fixtures
	@echo "→ Installing git-hc to $(INSTALL_DIR)/"
	@mkdir -p $(INSTALL_DIR)
	@cp git-hc $(INSTALL_DIR)/git-hc
	@chmod +x $(INSTALL_DIR)/git-hc
	@echo "   Done.  Make sure $(INSTALL_DIR) is in your PATH."
	@echo "   Test with: git hc --help"

uninstall:
	@rm -f $(INSTALL_DIR)/git-hc
	@echo "→ Removed $(INSTALL_DIR)/git-hc"

# ── dev dependencies ──────────────────────────────────────────
deps:
	$(PIP) install -r requirements.txt

# ── test fixtures (clone real polyglot code) ─────────────────
fixtures: $(FIXTURE_DIR)/.done

$(FIXTURE_DIR)/.done:
	@echo "→ Fetching polyglot fixtures from leachim6/hello-world …"
	@mkdir -p $(FIXTURE_DIR)
	@TMP=$$(mktemp -d) && \
	  git clone --depth=1 --filter=blob:none --sparse \
	    https://github.com/leachim6/hello-world "$$TMP" 2>&1 | tail -3 && \
	  cd "$$TMP" && \
	  git sparse-checkout set c python javascript go rust java 2>/dev/null; \
	  cp -r c python javascript go rust java "$(CURDIR)/$(FIXTURE_DIR)/" 2>/dev/null || true; \
	  rm -rf "$$TMP"
	@touch $(FIXTURE_DIR)/.done
	@echo "   Fixtures ready in $(FIXTURE_DIR)/"

# ── tests ─────────────────────────────────────────────────────
test: fixtures
	$(PYTHON) -m pytest tests/ -v --tb=short

test-unit:
	$(PYTHON) -m pytest tests/test_comments.py tests/test_store.py \
	                    tests/test_manifest.py tests/test_merge.py -v --tb=short

test-integration: fixtures
	$(PYTHON) -m pytest tests/test_integration.py -v --tb=short

# ── clean ─────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true
	rm -rf .pytest_cache dist build *.egg-info src/*.egg-info

clean-fixtures:
	rm -rf $(FIXTURE_DIR)

# ── help ──────────────────────────────────────────────────────
help:
	@echo "git hc — hide / restore source-code comments"
	@echo ""
	@echo "Targets:"
	@echo "  make install          Install git-hc to ~/.local/bin"
	@echo "  make uninstall        Remove git-hc from ~/.local/bin"
	@echo "  make fixtures         Download polyglot test fixtures"
	@echo "  make test             Run the full test suite"
	@echo "  make test-unit        Run only unit tests (no network needed)"
	@echo "  make test-integration Run only integration tests"
	@echo "  make deps             Install Python dependencies"
	@echo "  make clean            Remove build artifacts"
	@echo "  make clean-fixtures   Remove downloaded fixtures"
