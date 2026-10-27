# Storage, identities, and migration

[Documentation home](README.md) · [Architecture](architecture.md)

## Filesystem layout

```text
project/
├── chroma_db/                     # Persistent Chroma files
└── documents/
    └── <64-character-sha256>/
        ├── original.pdf           # Present for PDF-upload indexes
        ├── pages.json             # Original extracted page text
        ├── manifest.json          # Identity, state, counts, display metadata
        └── index.lock             # File-lock coordination
```

`manifest.tmp` can briefly exist during atomic manifest replacement. `original.pdf` is not created by page-text CLI indexing. Generated CLI `output_text/page_*.txt` files are an independent workflow, not the UI's storage directory.

All these data directories are ignored by Git. A public clone contains no uploaded PDF, Chroma database, extracted book text, or local `.env`. Ignoring them does not remove the original files from a working machine.

## Document identity

For uploaded PDFs:

```text
document_id = sha256(uploaded_pdf_bytes).hexdigest()
```

Identity is based on exact bytes, not the filename, extracted text, or a similarity comparison. Identical bytes reuse the first ready manifest. Different bytes remain distinct even when their visible contents or filenames match. Sanitized original filenames are display metadata, never directory names.

For page-text CLI indexing, the application serializes the sorted `Page` records using JSON with `ensure_ascii=False` and sorted keys, encodes the result as UTF-8, prefixes `b"page-text-v2\0"`, and hashes those bytes. That namespace avoids pretending independently edited text files have the hash of a matching PDF. Display-name changes do not create a new page-text index when the page content is identical.

Legacy selector identities are `"legacy:" + sha256(source.encode()).hexdigest()`. They are selection keys derived from legacy metadata, not claims about original PDF bytes.

## Stable chunk identity

```text
sha256(f"v2:{document_id}:{pdf_page}:{chunk_number}".encode()).hexdigest()
```

PDF pages and chunk numbers are one-based. Chunk numbers restart for each page. The schema prefix changes the identity namespace when an intentional schema revision is introduced. Stability assumes the same extraction/cleaning/chunking behavior; dependency or algorithm changes can produce different spans and must be treated deliberately.

## Original page format

`pages.json` is an array of records such as:

```json
[
  {"number": 1, "text": "Example handbook text before cleaning.\n"},
  {"number": 2, "text": ""}
]
```

The empty record preserves the PDF page numbering. Source excerpts are sliced from normalized/cleaned text, while this file preserves the extractor's original output. It is not OCR output or a rendered PDF page.

## Manifest format

Illustrative ready manifest; the repeated `a` identity below is a placeholder:

```json
{
  "document_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "filename": "example-handbook.pdf",
  "status": "ready",
  "chunk_count": 12,
  "page_count": 4,
  "legacy_source": null,
  "kind": "pdf",
  "schema_version": 2,
  "empty_pages": 0,
  "error": ""
}
```

`kind` is `pdf` for uploads or `page_text` for CLI extraction indexes. Legacy `Document` objects are discovered at runtime with `kind="legacy"`, schema 1, their exact `legacy_source`, and no corresponding v2 manifest. Failure manifests contain a safe generic error string rather than a provider response or secret.

## V2 chunk metadata

Every new record includes:

- `document_id`: content identity.
- `filename`: sanitized original display filename.
- `source`: the same display filename for compatibility with helper result fields.
- `page`, `chunk`: one-based PDF page and page-local chunk number.
- `embedding_model`: `sentence-transformers/all-MiniLM-L6-v2`.
- `schema_version`, `index_version`: both `2` in this implementation.
- `char_start`, `char_end`: offsets in cleaned normalized page text, or `-1` when unavailable.
- `is_toc`: contents-layout heuristic for the originating cleaned page.

The Chroma record's document field contains passage text. Embeddings are explicitly supplied, normalized, and stored in a cosine-space collection. The default library embedding function is not used.

## Readiness, locking, and retry

The process takes a per-identity `FileLock`, writes a processing manifest, preserves extracted pages, builds spans, and writes batches. It then checks that the number of records returned for that `document_id` equals the chunk count before atomically replacing the manifest with ready state.

If processing fails, a failed manifest remains. Partial Chroma batches can remain, but the UI's normal catalog and retrieval exclude unready documents. Retrying clears only that identity's incomplete v2 records before writing them again. The application does not delete the database, other documents, or the legacy collection.

A leftover `index.lock` file does not itself mean processing is active. An active OS-level lock does. Process termination releases the lock; an interrupted processing manifest can then be retried. Do not run competing indexers for the same document identity.

## Legacy compatibility

Existing `pdf_minilm_v1` records are discovered by paging through their metadata and grouping exact `source` values. Legacy retrieval uses `where={"source": legacy_source}` in that collection. New retrieval uses `where={"document_id": document_id}` in `pdf_minilm_v2` after checking the manifest.

The legacy integration assumes the original compatible MiniLM embedding setup. It does not infer or convert arbitrary unrelated embedding collections. Legacy excerpts retain their old formatting/boilerplate, and original pages cannot be reconstructed reliably just from a source filename.

Uploading the same-named book creates a new PDF-byte identity alongside the legacy entry. This is deliberate: a filename is not evidence that two files are identical. No migration is required to search the existing compatible index.

## Backup and restore

1. Stop Streamlit and any CLI writer.
2. Copy `chroma_db/` and `documents/` together to your chosen local backup location.
3. Store `.env` separately if needed, using appropriate secret-handling practices.
4. Restore both data directories into a compatible checkout before starting the app.
5. Verify the catalog and representative questions before relying on restored results.

Do not copy only a subset of Chroma's internal files or only manifests while writes are active. There is no automatic cloud backup, versioned data migration utility, or storage repair command in this project.

## Future migrations

Changing embedding dimensions, model, normalization, or schema requires a new collection/schema path alongside existing records. Keep existing data available until a new index is verified. Record the migration in the changelog and update query filters and ready-state handling together. The current app rejects a new-document manifest whose schema does not match the current version rather than silently mixing it into search.
