# Setup, running and testing

The full install and operation guide. For an overview of the project, see the [README](../README.md).

## Hardware and software

| | Minimum | Used for development and measurements |
|---|---|---|
| CPU | 4 cores, x86-64 (no GPU needed) | Ryzen 7 PRO 5850U, 16 threads |
| RAM | 8 GB (Mistral Q4 ≈ 4.1 GB + other models ≈ 1 GB) | 15 GiB |
| Disk | ~8 GB (Ollama model 4.4 GB, Hugging Face models 1.1 GB, Python env, indexes) | |
| OS | Linux (tested). Windows: installer built by CI; `scripts/run.ps1` provided, untested | Linux |
| Software | Python 3.11, Node.js 20+ with npm (to build the UI), [Ollama](https://ollama.com) | Python 3.11, Node 26, Ollama 0.33.3 |

Expect retrieval in about 1 s and a full answer in 1–3 minutes on CPU. The first answer after start-up is the slowest (see
[Troubleshooting](#troubleshooting)).

## Offline setup (once, with internet)

The parsed corpus, `data/processed/chunks.json`, is in the repository, so the statute PDFs are not needed to run HakiAI.
To rebuild the corpus, put the 25 PDFs named in [data/sources.yaml](../data/sources.yaml) into `data/raw_pdfs/` (`file:`
gives each name) and delete `chunks.json` before the setup. Then:

```bash
python3.11 -m venv .venv && source .venv/bin/activate      # Windows: py -3.11 -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r backend/requirements-dev.txt                 # runtime + test tools; torch comes from the CPU wheel index
(cd frontend && npm ci && npm run build)                    # builds the UI into frontend/dist
ollama serve &                                              # skip if Ollama already runs as a service
python scripts/setup_offline.py                             # see below
```

`setup_offline.py` does four things:
1. Caches the four Hugging Face models (embedder, cross-encoder, sw→en and en→sw translators) in the Hugging Face cache
   (`~/.cache/huggingface`, or `$HF_HOME`).
2. Runs `ollama pull mistral:7b-instruct-q4_K_M`.
3. Builds `data/processed/chunks.json` if it is missing (about 4 minutes), then the indexes (about 1 minute).
4. Reloads everything in a fresh process with `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`.

Every line must print `OK`; a `FAIL` line names its fix.
- Flags: `--skip-ollama`, `--skip-index`, `--verify-only`.
- Settings: copy `.env.example` to `.env` to change any of them (prefix `HAKI_`). The defaults live in
  `backend/app/config.py`.

After this, no internet connection is needed.

## Run

```bash
./scripts/run.sh            # Windows: powershell -ExecutionPolicy Bypass -File scripts\run.ps1
```

The script:
1. Builds the frontend if `frontend/dist` is missing.
2. Checks Ollama, the model, the indexes and the build (`python -m backend.app.preflight`). If Ollama is installed but not
   running, it starts it.
3. Serves the API and the UI on <http://127.0.0.1:8000>. Change the address with `HAKI_API_HOST` / `HAKI_API_PORT`.

`GET /api/health` returns 200 when everything is ready; otherwise it returns 503 and names each fix.

Other ways to run:

| Command | What it does |
|---|---|
| `make api` | `uvicorn backend.app.main:app --reload` (real stack) |
| `make api-fake` + `cd frontend && npm run dev` | Synthetic corpus and fake models (no indexes, models or Ollama), with the Vite dev server on :5173. For UI work |
| `make smoke` | One real question end to end against a running API (`scripts/smoke.py`) |

### Docker (optional)

```bash
docker compose build
docker compose up -d ollama
docker compose exec ollama ollama pull mistral:7b-instruct-q4_K_M
docker compose run --rm -e HF_HUB_OFFLINE=0 -e TRANSFORMERS_OFFLINE=0 api python scripts/setup_offline.py --skip-ollama
docker compose up -d api                                    # http://127.0.0.1:8000
```

- **Nothing large is baked into the image.** `./data` (PDFs, chunks, indexes, feedback) is bind-mounted, the Hugging Face
  models live in the `hf-models` volume and the Ollama model in the `ollama` volume.
- **Re-use host indexes.** Indexes built on the host work in the container (same paths under `/app/data`), so the
  `setup_offline.py` step can add `--skip-index`.
- **Status.** The files validate with `docker compose config` but were not built on the development machine (no Docker
  daemon access there).

## Installers and releases

The Windows installer and the Linux archive package the same app with PyInstaller (`desktop/hakiai.spec`): Python, the
backend, the built UI, `chunks.json` and the indexes in one folder. Models are not bundled.

The packaged app starts `backend/app/desktop/launcher.py` (also `python -m backend.app.desktop` from source). It:
1. Opens the browser at an already running HakiAI, if there is one on the configured port.
2. Starts Ollama if it is installed but not running, or explains where to get it. Laws can be read without it.
3. On the first start, downloads the four Hugging Face models and pulls the Ollama model (`--setup` does only this).
4. Serves on 127.0.0.1 (the configured port, or a free one) and opens the browser. Closing the window quits.

Accounts (`app.db`), feedback and the Ollama log go to the per-user data folder: `%LOCALAPPDATA%\HakiAI` on Windows,
`~/.local/share/HakiAI` on Linux. Models stay in the Hugging Face cache and in Ollama, shared with a source install.

| Task | Command |
|---|---|
| Build for Linux (`dist/HakiAI-linux-x86_64.tar.gz`) | `pip install -r desktop/requirements-build.txt && ./scripts/build_desktop.sh` |
| Build for Windows (`dist\HakiAI-Setup-x64.exe`, needs [Inno Setup 6](https://jrsoftware.org/isinfo.php)) | `pip install -r desktop\requirements-build.txt; .\scripts\build_desktop.ps1 -Version 2.0.0` |
| Check a build (bundled corpus, indexes, UI, and one answer on built-in test data) | `dist/HakiAI/HakiAI --self-test` |
| Install a local Linux build | `HAKI_TARBALL=dist/HakiAI-linux-x86_64.tar.gz ./scripts/install.sh` |
| Publish a release (both builds, self-tested, with `.sha256` files) | `git tag v2.0.0 && git push origin v2.0.0` |

The release workflow (`.github/workflows/release.yml`) builds on ubuntu-22.04 and windows-2022. The Linux build therefore
needs glibc 2.35 or newer. The README's download link and `scripts/install.sh` always fetch the latest release. Builds
are not code-signed, so Windows SmartScreen warns on first run.

## Tests and checks

```bash
./scripts/check.sh                                          # ruff, ruff format, mypy --strict, pytest + coverage (≥ 85%)
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
cd frontend && npm run e2e                                  # Playwright against the fake-backend API (needs Chromium)
python scripts/check_links.py                               # every relative link in the Markdown docs resolves
```

Default tests:
- need no models, no Ollama and no network (sockets are disabled);
- never write into `data/` (`backend/tests/conftest.py`).

Tests marked `real` use the cached models, the built indexes and a running Ollama with the model pulled:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 pytest -m real -q
```

Expected result: 5 passed, 1 skipped (the OCR test needs the optional `pytesseract`). The offline variables are required:
without them the Hugging Face libraries try the network, which the test socket guard blocks.

## Evaluate

The harness is in `eval/` (logic in `backend/app/evaluation/`); details and file formats are in
[eval/README.md](../eval/README.md).

```bash
python eval/validate_ground_truth.py   # needs eval/ground_truth.json, written by a human
python eval/run_retrieval.py           # P@5, Recall@20, MRR for FAISS vs BM25 vs hybrid vs hybrid+rerank, bootstrap CIs
python eval/tune_threshold.py          # null-response threshold sweep (in-corpus vs eval/out_of_corpus.json)
python eval/run_functional.py          # 20 questions (5 Kiswahili) through the running API
python eval/grounding_check.py         # citation and structure checks on the functional answers
python eval/bench_latency.py -n 4      # per-stage latency on the running API
python eval/report.py                  # assemble eval/results into one report
```

`python eval/run_eval.py` runs the offline steps in order. Human inputs still outstanding are listed in
[docs/HUMAN_TODO.md](HUMAN_TODO.md): ground truth, rater sheets and the usability survey.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Preflight or `/api/health`: "Ollama is not reachable"; answers end with `llm_unavailable` | Ollama is not running | `ollama serve` (or start the Ollama service). `run.sh` does this automatically if `ollama` is installed |
| "the model is not in Ollama"; stream error `model_not_loaded` | Model not pulled | `ollama pull mistral:7b-instruct-q4_K_M` |
| Startup stops with "index … is stale" or "no readable … index" | `chunks.json` or the embedding model changed after the indexes were built, or they were never built | `python -m backend.app.ingestion.build_index` |
| Startup stops with "a model could not be loaded from the local cache" | The Hugging Face models were never downloaded, or `HF_HOME` points elsewhere | `python scripts/setup_offline.py --skip-ollama --skip-index` (online, once) |
| "chunks.json is missing" / missing PDF error | No corpus built, or a PDF from `data/sources.yaml` is not in `data/raw_pdfs/` | Add the PDF, then `python -m backend.app.ingestion.build_corpus` |
| "the frontend is not built" / blank page at `/` | `frontend/dist` missing | `cd frontend && npm ci && npm run build` |
| Answers wait at "you are number N in line"; 503 `busy` | One answer is generated at a time (CPU); the queue holds 8 | Wait; this is by design for one CPU |
| Port 8000 in use | Another server | `HAKI_API_PORT=8001 ./scripts/run.sh` |
| `pytest -m real` fails with "A test tried to use socket" | The Hugging Face hub tries the network | Prefix with `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` |

**Slow CPU tips:**
- **The first answer after start-up is slow.** Ollama loads the 4.1 GB model, then evaluates the ~2,300-token prompt.
  Measured cold: 78–219 s to the first token, 151–304 s in total. Later answers reuse the loaded model for `HAKI_OLLAMA_KEEP_ALIVE`
  (default `30m`); raise it, e.g. `2h`, to keep the model in memory between sessions.
- **Free memory.** Close other heavy applications; with 8 GB RAM the system swaps otherwise.
- **Shorter answers.** `HAKI_NUM_PREDICT=800` ends answers sooner; the formal letter may then be cut short.
- **Do not lower `HAKI_NUM_CTX`** to save time. It shrinks the room for the five sections, which are then truncated and
  can lose the provision that matters.
- **Stop generating early.** Closing the browser tab stops generation at once and frees the CPU for the next question.

