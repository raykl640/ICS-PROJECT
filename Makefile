PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python)

.PHONY: install check test lint fmt api api-fake smoke index eval

install:  ## install runtime + dev dependencies
	$(PY) -m pip install -r backend/requirements-dev.txt

check:    ## ruff + format check + mypy + pytest with coverage
	./scripts/check.sh

test:     ## fast test run
	$(PY) -m pytest -q -x

lint:     ## lint and type-check only
	$(PY) -m ruff check backend && $(PY) -m mypy

fmt:      ## auto-format and fix lint
	$(PY) -m ruff format backend && $(PY) -m ruff check --fix backend

api:      ## run the API with reload
	$(PY) -m uvicorn backend.app.main:app --reload

api-fake: ## run the API on the synthetic corpus with fake models (frontend development)
	HAKI_FAKE_BACKENDS=1 HAKI_DEV_MODE=true $(PY) -m uvicorn backend.app.main:app --reload

smoke:    ## end-to-end check of a running real API
	$(PY) scripts/smoke.py

index:    ## build chunks.json and indexes
	$(PY) -m backend.app.ingestion.build_index

eval:     ## run the evaluation suite
	$(PY) eval/run_eval.py
