PYTHON ?= venv/bin/python3
PIP ?= venv/bin/pip

.PHONY: install-dev format lint test typecheck check

install-dev:
	$(PIP) install -r requirements.txt -r requirements-dev.txt

format:
	$(PYTHON) -m ruff format src tests module2_transcribe.py module3_analyze.py scripts

lint:
	$(PYTHON) -m ruff check src tests module2_transcribe.py module3_analyze.py scripts

test:
	$(PYTHON) -m pytest tests -q

typecheck:
	$(PYTHON) -m mypy --config-file mypy.ini

check:
	$(PYTHON) -m ruff check src tests module2_transcribe.py module3_analyze.py scripts
	$(PYTHON) -m mypy --config-file mypy.ini
	$(PYTHON) -m pytest tests -q