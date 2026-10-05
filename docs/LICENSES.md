# Third-party licences

Collected on 2026-10-05. Python licences were read from installed package metadata (`License-Expression` or the licence
classifiers), npm licences from each package's `package.json`, and model licences from the Hugging Face model cards or
`ollama show`. The project's own terms are in [LICENSE](../LICENSE): an academic project, all rights reserved by the author.

**Summary:** every dependency and model is under a permissive licence (MIT, BSD, 0BSD, Apache-2.0, ISC, PSF, MIT-CMU);
the bundled fonts are under the SIL Open Font License 1.1. The only
weak-copyleft licence is MPL-2.0, used by certifi and tqdm (and, as a test-only tool, axe-core). It is file-level and applies only if those files are modified,
which this project does not do. No GPL or AGPL code is bundled.

## Models (downloaded once by `scripts/setup_offline.py`, never redistributed with the code)

| Model | Used for | Licence | Source of the licence |
|---|---|---|---|
| sentence-transformers/all-MiniLM-L6-v2 | dense embeddings | Apache-2.0 | model card |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | reranking | Apache-2.0 | model card |
| Helsinki-NLP/opus-mt-swc-en | Kiswahili → English | Apache-2.0 | model card |
| Helsinki-NLP/opus-mt-en-sw | English → Kiswahili | Apache-2.0 | model card |
| mistral:7b-instruct-q4_K_M (Ollama) | answer generation | Apache-2.0 | `ollama show` |

## Corpus

The statute PDFs in `data/raw_pdfs/` come from kenyalaw.org (see `data/sources.yaml`). They are git-ignored and not
redistributed with this repository. Their redistribution terms were not checked.

## Python runtime (`backend/requirements.txt` and everything it pulls in)

Direct dependencies are marked ●.

| Package | Version | Licence |
|---|---|---|
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| argon2-cffi ● | 25.1.0 | MIT |
| argon2-cffi-bindings | 26.1.0 | MIT |
| certifi | 2026.7.22 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| cloudpickle | 3.1.2 | BSD |
| cryptography ● | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| faiss-cpu ● | 1.15.1 | MIT |
| fastapi ● | 0.142.2 | MIT |
| filelock | 4.0.9 | MIT |
| fsspec | 2026.9.0 | BSD-3-Clause |
| h11 | 0.16.0 | MIT |
| hf-xet | 1.6.0 | Apache-2.0 |
| httpcore | 1.0.9 | BSD-3-Clause |
| httptools (uvicorn[standard]) | 0.8.0 | MIT |
| httpx ● | 0.28.1 | BSD |
| huggingface_hub | 1.33.0 | Apache-2.0 |
| idna | 3.20 | BSD-3-Clause |
| Jinja2 | 3.1.6 | BSD |
| joblib | 1.6.0 | BSD-3-Clause |
| langdetect ● | 1.0.9 | Apache-2.0 |
| lxml | 6.1.3 | BSD-3-Clause |
| markdown-it-py | 4.2.0 | MIT |
| MarkupSafe | 3.0.3 | BSD-3-Clause |
| mdurl | 0.1.2 | MIT |
| mpmath | 1.3.0 | BSD |
| narwhals | 2.26.0 | MIT |
| networkx | 3.6.1 | BSD-3-Clause |
| numpy ● | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| opentelemetry-api | 1.45.0 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pdfminer.six | 20260107 | MIT |
| pdfplumber ● | 0.11.10 | MIT |
| pillow | 12.3.0 | MIT-CMU |
| pycparser | 3.0 | BSD-3-Clause |
| pydantic ● | 2.13.5 | MIT |
| pydantic_core | 2.46.5 | MIT |
| pydantic-settings ● | 2.15.0 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| pypdfium2 | 5.13.0 | BSD-3-Clause, Apache-2.0 (plus PDFium's dependency licences) |
| python-docx ● | 1.2.0 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| PyYAML ● | 6.0.3 | MIT |
| regex | 2026.9.29 | Apache-2.0 AND CNRI-Python |
| requests ● | 2.34.2 | Apache-2.0 |
| rich | 15.0.0 | MIT |
| sacremoses ● | 0.2.0 | MIT |
| safetensors | 0.8.0 | Apache-2.0 |
| scikit-learn | 1.9.1 | BSD-3-Clause |
| scipy | 1.17.1 | BSD |
| sentence-transformers ● | 6.1.0 | Apache-2.0 |
| sentencepiece ● | 0.2.2 | Apache-2.0 |
| setuptools | 84.0.0 | MIT |
| shellingham | 1.5.4 | ISC |
| six | 1.17.0 | MIT |
| sse-starlette ● | 3.5.0 | BSD-3-Clause |
| starlette | 1.7.0 | BSD-3-Clause |
| sympy | 1.14.0 | BSD |
| threadpoolctl | 3.7.0 | BSD-3-Clause |
| tokenizers | 0.23.2 | Apache-2.0 |
| torch ● | 2.14.1+cpu | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT |
| tqdm | 4.70.1 | MPL-2.0 AND MIT |
| transformers ● | 5.18.0 | Apache-2.0 |
| typer | 0.27.2 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.4 | MIT |
| urllib3 | 2.8.0 | MIT |
| uvicorn ● | 0.54.0 | BSD-3-Clause |
| uvloop (uvicorn[standard]) | 0.23.0 | Apache-2.0 OR MIT |
| watchfiles (uvicorn[standard]) | 1.3.0 | MIT |
| websockets (uvicorn[standard]) | 17.1 | BSD-3-Clause |
| Whoosh ● | 2.7.4 | BSD |

## Python development tools (`backend/requirements-dev.txt`, not shipped)

| Package | Version | Licence |
|---|---|---|
| pytest | 9.1.1 | MIT |
| pytest-cov | 5.0.0 | MIT |
| pytest-socket | 0.8.1 | MIT |
| coverage | 7.16.2 | Apache-2.0 |
| ruff | 0.16.10 | MIT |
| mypy | 1.20.2 | MIT |
| reportlab | 4.5.1 | BSD |
| types-PyYAML | 6.0.12.20260906 | Apache-2.0 |
| types-requests | 2.33.0.20260906 | Apache-2.0 |
| pip-audit (audit only, not pinned) | 2.10.1 | Apache-2.0 |

## Frontend (production dependencies: 144 packages, updated in M12)

| Licence | Packages |
|---|---|
| MIT | 139, including react 19.3.0, react-dom 19.3.0, react-router 8.4.0, react-markdown 10.1.0, scheduler, the unified/remark/rehype/mdast/hast utilities and the @radix-ui/* primitives (dialog 1.1.23, dropdown-menu 2.1.24, tabs 1.1.21, tooltip 1.2.16, popover 1.1.23, toast 1.2.23, toggle-group 1.1.19, scroll-area 1.2.18, with their internal packages) |
| ISC | 2 (lucide-react 1.52.0, @ungap/structured-clone 1.4.0) |
| 0BSD | 1 (tslib 2.8.1, pulled in by Radix) |
| OFL-1.1 | 3 font packages, all 5.3.0: @fontsource-variable/archivo, @fontsource-variable/source-serif-4 and @fontsource/ibm-plex-mono |

The fonts are bundled with the app (offline). OFL-1.1 allows bundling and redistribution with software; it only forbids
selling the fonts on their own and reusing their reserved names for modified versions. The four fonts of the two directions
not chosen at the M11 gate were removed in M12.

The development dependencies (Vite, Tailwind, ESLint, Vitest, Playwright, TypeScript, and @axe-core/playwright 4.13.0 with
axe-core, MPL-2.0, for accessibility checks in e2e) are build and test tools only and are not part of the bundle. Regenerate this table with `npm ls --omit=dev --all --json` and each package's `license` field.

## Dependency audit (2026-10-05)

| Tool | Scope | Result |
|---|---|---|
| `pip-audit -r backend/requirements.txt -r backend/requirements-dev.txt` | pinned requirements, resolved | No known vulnerabilities. torch 2.14.1+cpu was not audited: the `+cpu` local version is not on PyPI. |
| `pip-audit` (installed .venv) | 122 installed packages | No known vulnerabilities. torch (+cpu) and the local hakiai-backend package were not audited. |
| `npm audit` (frontend) | 376 packages (89 prod, 288 dev) | 0 vulnerabilities. |
| `npm audit --omit=dev` (frontend, M11, after adding Radix, lucide and fonts) | 145 prod packages | 0 vulnerabilities. |
| `npm audit` (frontend, M12, after adding react-router and @axe-core/playwright, removing 4 fonts) | all packages | 0 vulnerabilities. |

Nothing was upgraded. Rerun both audits before each release, and upgrade a pin only when a finding applies to how this
project uses the package.
