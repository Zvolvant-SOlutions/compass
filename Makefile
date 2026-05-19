.PHONY: install demo test lint fmt clean seed help

PY := .venv/bin/python
STREAMLIT := .venv/bin/streamlit
UV := $(shell command -v uv 2>/dev/null)

help:
	@echo "Compass — build targets"
	@echo ""
	@echo "  make install   Create .venv and install dependencies"
	@echo "  make seed      Build local SQLite database with seed data"
	@echo "  make demo      Launch the Streamlit app"
	@echo "  make test      Run pytest suite"
	@echo "  make lint      Run ruff check + format check"
	@echo "  make fmt       Apply ruff fixes + format"
	@echo "  make clean     Remove .venv, caches, and local DB"

.venv/bin/python:
ifeq ($(UV),)
	python3.12 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install ruff pytest
else
	$(UV) venv --python 3.12 .venv
	$(UV) pip install --python .venv/bin/python -r requirements.txt
	$(UV) pip install --python .venv/bin/python ruff pytest
endif

install: .venv/bin/python
	@echo "Environment ready. Run 'make seed' then 'make demo'."

seed: .venv/bin/python
	PYTHONPATH=src $(PY) scripts/seed_db.py

demo: .venv/bin/python
	PYTHONPATH=src $(STREAMLIT) run streamlit_app.py \
		--server.headless false --browser.gatherUsageStats false

test: .venv/bin/python
	PYTHONPATH=src .venv/bin/pytest tests -q

lint: .venv/bin/python
	.venv/bin/ruff check src streamlit_app.py tests scripts
	.venv/bin/ruff format --check src streamlit_app.py tests scripts

fmt: .venv/bin/python
	.venv/bin/ruff check --fix src streamlit_app.py tests scripts
	.venv/bin/ruff format src streamlit_app.py tests scripts

clean:
	rm -rf .venv .pytest_cache .ruff_cache *.db
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
