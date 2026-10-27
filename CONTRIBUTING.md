# Contributing

Thanks for helping improve PassageHarbor. Keep the project small, understandable, and useful for one person running it locally.

## Before changing code

Read the [architecture](docs/architecture.md) and [developer reference](docs/developer-reference.md). Check existing issues for duplicate reports. For a larger change, describe the concrete problem and intended behavior before adding a framework or service. Do not bundle unrelated refactors with a focused fix.

## Local development

```powershell
git clone https://github.com/hammadfarooq-ai/passageharbor.git
Set-Location passageharbor
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/check_docs.py
```

Use the [setup guide](docs/getting-started.md) if activation/dependencies fail. Do not copy your real `.env` into a reproduction or commit. The test suite uses synthetic PDFs, temporary storage, fake embeddings, and mocked provider responses.

## Change guidelines

- Preserve selected-document filters and conversation isolation.
- Never run tests against the user's real Chroma database or upload directory.
- Preserve original extracted page text when changing cleaning or chunking.
- Keep final spans within the actual embedding budget including special tokens.
- Treat document text and filenames as untrusted data, not instructions.
- Keep API errors safe; do not log keys or raw sensitive provider responses.
- Maintain index readiness and safely retryable failure states.
- Document incompatible schema/model changes and keep old collections available.
- Keep code, comments, interface text, and documentation in English.
- Add meaningful regression coverage for behavior changes; documentation-only edits need link/visual checks rather than redundant unit tests.

## Pull requests

Explain the user-visible problem, the resulting behavior, and the validation performed. Include limitations or manual checks that were not run. Update relevant docs and the unreleased changelog. Keep commits reviewable and avoid generated data, caches, PDFs, or secrets.

Run:

```powershell
python -m pytest -q
python -m compileall -q app.py pdf_reader.py vector_store.py rag.py
python scripts/check_docs.py
```

Review Mermaid/SVG rendering when changing diagrams. Do not call live Groq generation in tests or CI. If manually evaluating a provider or model, use synthetic data and explicitly account for usage and the external data boundary.

## Bug reports and security

Use the issue templates with a minimal reproduction, OS/Python versions, and safe error summary. Redact credentials and avoid private source excerpts. Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md), not in a public issue.

Contributions are submitted under the repository's [MIT License](LICENSE). Model weights, dependencies, provider services, and user PDFs retain their separate licenses/terms.
