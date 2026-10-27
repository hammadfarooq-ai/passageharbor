# Testing and verification

[Documentation home](README.md) · [Contributing](../CONTRIBUTING.md)

## Run the checks

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q app.py pdf_reader.py vector_store.py rag.py
python scripts/check_docs.py
```

Use the same virtual environment as the app. The automated suite does not make paid Groq requests or download embedding/reranker models. Dependency installation itself requires package downloads.

If a restricted environment denies pytest's normal temporary directory, choose a **new, disposable** directory inside the workspace:

```powershell
New-Item -ItemType Directory -Path .validation -Force | Out-Null
python -m pytest -q --basetemp .validation/pytest-run-new
```

Pytest can remove/recreate its basetemp path. Never point it at `chroma_db`, `documents`, the project root, or any directory containing user data. Use a fresh name if a previous run still holds files open.

## What the automated suite covers

### Extraction and chunking

- Empty, corrupt, unreadable, encrypted, zero-page, and textless PDFs.
- Mixed blank/text pages, size limits, and preserved page numbering.
- Bounded chunk tokens including special tokens, overlap, full-page coverage, original offsets/case/punctuation, and empty text.
- Conservative repetition-backed cleaning and legacy contents-fragment detection.

### Persistence and identity

- PDF-byte SHA-256 identities and deterministic chunk IDs.
- Duplicate upload reuse without additional embedding work.
- Distinct PDFs with identical filenames.
- Original PDF/page preservation and safe generated directories.
- Selected-document query isolation and exact legacy source filtering.
- Partial writes, hidden incomplete indexes, lock contention, and retry completion.
- Original extraction/index/search CLI compatibility and empty-folder errors.

### Retrieval and generation

- Optional reranker ordering and graceful fallback.
- Duplicate/heavy-overlap removal and contents filtering.
- Citation mapping, missing labels, malformed numeric groups, and the exact insufficient-information response.
- Configuration presence, invalid upload limits, safe API status errors, connection/timeouts, empty responses, and truncated streams.
- Follow-up rewrite behavior and fallback, bounded recent history, and exclusion of failed assistant entries.
- Installed Groq SDK streaming types through `httpx.MockTransport`, without opening a provider socket.

### Streamlit behavior

- Empty-state controls and passage-only mode.
- Per-document conversation isolation, clear conversation, and persisted source mappings.
- Visible unverified-citation and incomplete-stream states.

## How tests stay isolated

`tests/conftest.py` creates temporary Chroma and document directories and injects deterministic fake embeddings and tokenization. Test PDFs are synthetic, generated with `pypdf`; no user PDF is needed. Groq tests inject mocked clients or a mock HTTP transport. Streamlit tests replace its store/configuration and clear cached resources between cases.

Real `.env` values must not be used for automated generation. New tests should pass explicit temporary paths and mocked clients rather than rely on the default `VectorStore()` or live provider credentials. Keep model-quality experiments separate from the unit suite.

## CI workflow

`.github/workflows/ci.yml` targets Linux/Python 3.11 and Windows/Python 3.13, installs CPU PyTorch and project development dependencies, runs tests, compiles application modules, and validates documentation. It receives no Groq secret. Third-party actions are pinned to immutable revisions with their verified release versions documented in comments.

The README badge reports the live GitHub workflow result. A configured matrix is not a claim that every future dependency resolution will pass. Inspect failed-job logs before broadening compatibility claims. Requirements are ranged, not a reproducible lockfile.

## Manual smoke checks

### Server startup

```powershell
python -m streamlit run app.py --server.headless true --server.port 8502
```

In another terminal:

```powershell
Invoke-WebRequest http://127.0.0.1:8502/_stcore/health
```

A healthy response confirms server startup, not successful execution of every UI interaction. Open the app to verify the selected-document view and empty states. Stop the smoke server with Ctrl+C.

### Real local models

Use a small synthetic PDF and a temporary `VectorStore` with explicit paths. Load the real cached/downloaded MiniLM, check every final chunk's length with the actual tokenizer, index, and search within one document. Never run destructive model/index experiments against the original database. A model loaded from cache is not evidence that fresh model downloads work.

### Legacy compatibility

Stop writers and copy the entire database to a disposable location. Open the copy with explicit document paths, discover the legacy entries, and verify representative queries. Read-only inspection or source-file hashes can confirm the original files were not altered. Do not run tests against the production/local working database merely because they are intended to be read-only: libraries may initialize or migrate files.

### Groq generation

A live answer or rewrite request can incur provider usage and transmit its question/context. Only run it when explicitly intended. A startup configuration-presence check is not credential authentication. To verify streaming manually, ask a synthetic question, observe deltas, then inspect the completed labels and passages. Never publish a real key or private excerpt as test evidence.

## Evidence boundaries

The unit suite checks implementation mechanics, not semantic retrieval quality, model factuality, OCR, all browser layouts, or guaranteed hallucination prevention. Source inspection and representative question evaluation remain necessary. Local development previously verified actual MiniLM spans across a 253-page local PDF and retrieval against a copied 875-chunk legacy index; those user data and generated files are intentionally not part of the public test corpus. Live Groq generation and fresh reranker downloads are not implied by that verification.

`scripts/check_docs.py` checks local documentation references, heading anchors, fenced-code balance, and SVG structure/accessibility metadata. It does not make HTTP requests to validate remote URLs or execute a Mermaid rendering engine. Rendered diagrams should also be reviewed on GitHub after publishing.
