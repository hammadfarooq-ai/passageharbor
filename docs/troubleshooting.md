# Troubleshooting

[Documentation home](README.md) · [Configuration reference](configuration.md)

## The app will not start

Run from the project directory and use the interpreter from the intended virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

For a missing command/module, check which Python you are running before reinstalling into a different environment. If activation is blocked, use the explicit interpreter path instead of changing execution policy. If the port is occupied, add `--server.port 8502` and open that URL.

## The app says configuration or storage cannot be opened

Check that `MAX_UPLOAD_MB` is a positive integer, the `.env` filename is correct, and project storage is writable. Confirm sufficient free disk space. Stop other scripts using incompatible Chroma versions before retrying. Back up data before dependency upgrades. Do not delete `chroma_db` as a routine fix.

## Groq settings are still missing after editing .env

Save the file as `.env` alongside `app.py`, not `.env.txt`. Both `GROQ_API_KEY` and `GROQ_MODEL` must be nonempty. Stop Streamlit with Ctrl+C and restart it. Existing process environment variables take precedence; dotenv does not overwrite them or previously loaded values. Do not print the full `.env` to diagnose this.

A local presence-only check that does not expose the values or make API calls:

```powershell
python -c "from rag import load_config; c=load_config(); print('Key present:', bool(c.api_key)); print('Model present:', bool(c.model))"
```

Presence is not authentication validation.

## Authentication or permission error

Check the key in the [Groq console](https://console.groq.com/keys), account access, and any model permissions. Avoid trailing copied whitespace, stale process values, or a revoked key. Update locally and restart. Do not paste the key into a public issue or chat transcript.

## Configured model is unavailable

Choose an exact current chat model ID from [Groq's supported models](https://console.groq.com/docs/models) that your account can access. The application intentionally has no permanent fallback model. Some errors also mean the selected model cannot accept the request/context settings. Review the model's documented limits and try a narrower question or fewer passages.

## Rate limit, connection failure, or timeout

Wait after a rate limit and check account quotas. Check network/firewall access to Groq after connection errors. The client uses a 45-second timeout and zero automatic retries, so the UI avoids silently submitting repeated billable requests. Retrieved passages remain available when generation fails. Follow-up rewriting may have its own failure notice and fall back to the original wording.

## The answer is empty or incomplete

An empty visible response is treated as an error. The generation cap is 1,000 completion tokens; a length-limited response remains an incomplete draft. Some reasoning models can consume completion capacity before producing visible answer text. Try a narrower question or another available chat model. Maintainers can deliberately adjust the generation/rewrite token limits in `rag.py`, considering provider compatibility, latency, and cost.

The follow-up rewrite has a separate 160-token budget. If it fails or yields empty/overlong text, the original question is used for retrieval.

## Citation warning

An answer marked **Needs verification** has missing/malformed labels or labels outside the supplied source list. Inspect the sources and ask a more specific question. The application does not silently delete bad labels and present the result as verified. Even a valid mapping does not guarantee that every claim is entailed by a cited passage.

## No useful PDF text

Scanned-only PDFs require OCR before upload. This application does not provide OCR. Unlock encrypted files and save a readable copy first. Corrupt, zero-page, and empty inputs cannot be indexed. A mixed PDF can index its text while images, handwriting, diagrams, and some tables remain unavailable to retrieval.

If extracted text is in an unexpected order, inspect original page text and the actual PDF. Multi-column layout and complex tables can exceed the extractor's reading-order fidelity.

## The upload limit looks inconsistent

The app checks `MAX_UPLOAD_MB`; Streamlit also has a transport limit. Set both when increasing the default:

```powershell
# Save MAX_UPLOAD_MB=50 in .env and restart with:
python -m streamlit run app.py --server.maxUploadSize 50
```

On older Streamlit versions the uploader label follows the transport setting. On newer versions the app passes a per-uploader size limit when supported. The application check still applies before indexing.

## First search is slow or model download fails

The first indexing/search operation loads MiniLM and can require Hugging Face access, dependency initialization, and disk reads. Even a partial cache can trigger metadata checks or additional downloads. Subsequent questions share the process model. Each CLI invocation is a new process.

Check network access, cache permissions, and available disk space. For intentionally offline use, populate the complete cache first and use the libraries' offline settings. Do not globally suppress warnings to hide a failed load. The intentional whole-page tokenization path already suppresses only its own misleading sequence-length warning; unrelated warnings remain visible.

## Optional reranker is unavailable

Leave **Improve passage ranking** off for the simplest CPU workflow. If enabled but download/initialization fails, the app uses vector ordering and displays a notice. Its failed initialization is cached to avoid repeat downloads; restart the app after correcting connectivity. Prediction failure also falls back for that request. This does not affect the stored MiniLM vectors.

## Wrong or weak passages

Confirm the correct document is selected. Ask a more specific question, increase candidates, or try optional reranking. Broad word matches can still be semantically weak; no unvalidated universal relevance cutoff is applied. Contents filtering and deduplication are heuristics, not a quality guarantee.

For legacy indexes, old token-decoded formatting and promotional text can remain. Process the original PDF as a new upload to use the new cleaning/span logic. A new PDF entry remains separate from the legacy entry because matching filenames do not prove matching bytes.

## Processing was interrupted

Upload exactly the same PDF bytes and process again after any active indexer finishes. A stale processing manifest is retryable once its OS file lock is released. A leftover lock file alone is harmless. Partial new chunks remain hidden from normal retrieval until readiness is recorded. Do not remove the whole database or unrelated document directories.

## CLI includes unexpected pages or versions

Use a fresh, dedicated extraction folder for each PDF: the extractor does not remove stale page files from earlier runs. CLI search without filters searches all ready documents. `--source` can match multiple versions sharing a name; use the full `--document-id` to select one precisely. See the [CLI reference](cli-reference.md).

## Report a reproducible issue

Include Python/package versions, OS, command, safe error summary, and a small synthetic reproduction when possible. State whether the problem involves a new upload, legacy index, or generation. Exclude `.env`, keys, raw private PDFs, database files, and confidential excerpts. Read [Contributing](../CONTRIBUTING.md) and use [private reporting](../SECURITY.md) for vulnerabilities.
