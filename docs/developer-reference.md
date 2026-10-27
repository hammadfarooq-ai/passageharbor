# Developer reference

[Documentation home](README.md) · [Architecture](architecture.md) · [Testing](testing.md)

The application modules are ordinary Python files, not a versioned SDK or HTTP API. The helpers below describe the current source contracts. Prefer explicit temporary storage and injected models/clients for programmatic checks.

## PDF extraction: `pdf_reader.py`

### Records and errors

`Page(number: int, text: str)` is a frozen dataclass with a one-based PDF page number and original extracted text. `Extraction(pages: list[Page], empty_pages: list[int])` retains every page and separately lists pages without alphanumeric text. `PDFError` is a `ValueError` with a user-facing message.

### Functions

`extract_pdf_bytes(data, max_upload_mb=25, progress=None) -> Extraction` validates size/header/readability, tries an empty password for encrypted files, and extracts pages with `pypdf`. It rejects empty, invalid, unreadable, zero-page, locked, and entirely textless inputs. A progress callback receives `(stage: str, fraction: float)` during extraction.

`extract_pdf_to_txt(pdf_path, output_dir="output_text", max_upload_mb=25)` reads bytes, extracts pages, writes `page_<number>.txt` as UTF-8, prints destinations, and returns the `Extraction`. It does not clear old files from the destination.

## Index and search: `vector_store.py`

### Identity and text helpers

- `document_identity(data) -> str`: SHA-256 hexadecimal byte hash.
- `chunk_identity(document_id, page, chunk) -> str`: schema-prefixed deterministic chunk hash.
- `display_filename(name) -> str`: sanitizes metadata by removing path components/control characters and limiting display length; it is never a storage path.
- `normalize_text(text) -> str`: conservative line-ending/horizontal-whitespace normalization.
- `clean_pages(pages) -> list[Page]`: repetition-backed marginal-line removal without mutating original records.
- `is_contents(text) -> bool`: a contents-layout heuristic, including legacy dotted-entry fragments.
- `split_spans(text, tokenizer, max_length=None)`: yields dictionaries with `text`, `char_start`, and `char_end` after checking token budgets.
- `split_text(text, tokenizer)`: compatibility wrapper yielding only passage strings.

`get_embedding_model()` is a single-entry process cache for MiniLM. `get_reranker()` caches either `(model, None)` or `(None, safe_notice)`, so a failed initialization is not retried on every rerun.

### `Document`

The dataclass fields are `document_id`, `filename`, `status`, `chunk_count`, `page_count`, `legacy_source`, `kind`, `schema_version`, `empty_pages`, and `error`. Defaults include `status="pending"`, `kind="pdf"`, current schema, zero counts, and empty error. See the [manifest format](storage-and-migration.md#manifest-format) for an example.

### `VectorStore`

```python
from pathlib import Path
from vector_store import VectorStore

store = VectorStore(
    database_path=Path("temporary-workspace/chroma"),
    document_path=Path("temporary-workspace/documents"),
    model=my_local_model,
)
```

The optional injected model must expose `.tokenizer`, `.max_seq_length`, and `.encode(...)` with NumPy-like `.tolist()` results. Indexing/query encoding always requests normalized embeddings. Production uses the cached Sentence Transformer when `model` is omitted.

- `list_documents(include_incomplete=False) -> list[Document]`: reads new manifests and discovers legacy sources. Does not load the embedding model. Invalid/unreadable manifest records are skipped.
- `process_pdf(data, filename, max_upload_mb=25, progress=None) -> Document`: locks the identity, reuses ready documents, preserves source data, indexes, and marks ready. A conflicting lock raises `ProcessingBusy`.
- `search(question, document, candidates=15) -> list[dict]`: validates readiness for new documents, embeds the query, and applies the correct selected-document filter. Blank questions return an empty list.
- `original_page(document, number) -> str | None`: retrieves original extracted text for new indexes. Returns `None` for legacy records or unavailable pages.
- `read_document(document_id) -> Document | None`: reads one new manifest. IDs must be 64 lowercase hexadecimal characters.
- `is_processing(document_id) -> bool`: checks whether the document file lock is currently held.
- `collection(legacy=False, create=False)`: resolves a Chroma collection without automatic embedding; returns `None` when a requested existing collection is absent.

`_index()` and `_save()` are internal state-writing helpers. Do not bypass the upload/CLI wrappers for production writes: those wrappers handle locks and failed-state persistence.

### Search result shape

Results contain `id`, `text`, `source`, `filename`, `page`, `chunk`, `distance`, `char_start`, `char_end`, and `is_toc`. `source` is retained for compatibility. `rag.retrieve()` adds a one-based `label` for the answer context. Neither IDs nor labels are semantic confidence measures.

### Compatibility helpers

`index_pages(folder, source, *, store=None)` writes ordered page text through the v2 workflow and returns a `Document`. `search_pages(question, source=None, top_k=5, *, store=None, document_id=None)` searches matching ready catalog entries and returns the nearest matches globally. `open_store()` returns the cached embedding model and the existing legacy collection (which can be `None` if absent); new code should use `VectorStore` directly. `main()` retains argparse-based `index` and `search` commands.

## Retrieval and generation: `rag.py`

### Configuration and errors

`Config(api_key="", model="", max_upload_mb=25)` stores generation settings. Its `.issue` property returns guidance if either Groq field is empty. `load_config()` reads the root `.env` without overriding process variables and validates the upload limit. `GenerationError` carries safe user-facing generation errors.

`create_client(config)` constructs `Groq(api_key=..., timeout=45.0, max_retries=0)`. It does not make a generation call by itself. `groq_error_message(error)` maps SDK/status failures without returning provider bodies.

### Retrieval helpers

`recent_history(history)` returns at most six eligible messages with bounded content. Entries use `role`, `content`, and optionally `status`. Only `user` and `assistant` roles with complete/default status are eligible.

`rewrite_question(question, history, config, client=None) -> (question, notice)` performs a bounded nonstreaming rewrite when useful/configured. It falls back to original wording on failure. Empty or overlong rewrites are rejected. No documentary claims are accepted from prior assistant answers.

`retrieve(store, document, question, candidates=15, passage_count=5, rerank=False) -> (sources, notice)` scopes search, optionally reranks, filters contents-like material, removes duplicates/heavy overlap, and assigns labels. `heavily_overlaps(a, b)` implements the duplication heuristic.

`build_context(sources) -> str` produces the numbered evidence format:

```text
[1] example-handbook.pdf, PDF page 12
Example supporting passage.
```

### Streaming and citation checks

`stream_answer(question, sources, history, config, client=None) -> Iterator[str]` yields content deltas. With no sources it yields the insufficient-information sentence without calling Groq. Missing configuration raises `GenerationError`. When the helper creates a client, it owns/closes it; injected clients remain caller-owned. Streams are closed when supported. Empty and length-limited responses are failures rather than completed answers.

`validate_citations(answer, sources) -> (valid, notice)` accepts the exact insufficient-information response or checks that numeric labels are present and mapped. Missing labels, unknown labels, or malformed numeric groups are flagged. This is a label validator, not a factual-support evaluator.

## UI session contract

`get_store()` is a Streamlit resource cache. The app's conversation dictionary is keyed by selected `document_id`. A stored assistant entry includes:

```python
{
    "role": "assistant",
    "content": "Example answer [1].",
    "sources": [{"label": 1, "filename": "example.pdf", "page": 2, "text": "Example."}],
    "notice": None,
    "status": "complete",
}
```

Other statuses are `retrieval_only`, `unverified`, and `failed`. These retain their sources for display but their assistant text is excluded from subsequent eligible history. User messages remain in the selected conversation.

## Extension guidance

Keep document filters at the store boundary, preserve originals when altering cleaning, and bump schema/collection identity assumptions for incompatible indexing changes. Add a representative failing test before changing retry/citation/session behavior. Optional provider features belong in `rag.py`; avoid turning the app into an unnecessary API service. The [testing guide](testing.md) explains model/client injection and the boundary between mocked mechanics and real retrieval quality.
