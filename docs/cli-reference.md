# CLI reference

[Documentation home](README.md) · [Storage and migration](storage-and-migration.md)

Run commands from the project directory using the same virtual environment as the UI. These tools use local extraction/embeddings/search and do not call Groq.

## Extract a PDF to page files

```powershell
python pdf_reader.py "my-document.pdf" --output-dir "output_text/my-document"
```

```text
python pdf_reader.py [pdf] [--output-dir OUTPUT_DIR]
```

- `pdf`: path to a text-based PDF. When omitted, the historical example filename is used; that PDF is not included in a fresh clone.
- `--output-dir`: destination for `page_1.txt`, `page_2.txt`, and so on; default `output_text`.
- Extraction applies a default 25 MB limit through the Python helper. `MAX_UPLOAD_MB` configures the UI; the extraction CLI does not load it or expose a size flag.

Blank pages receive empty text files to preserve numbering. Password-protected PDFs that cannot open with an empty password must be unlocked first. No OCR is performed. The output folder is created as needed.

Use a dedicated folder for each extraction. The helper writes extracted pages but does not remove stale page files from an earlier, longer document. Indexing a reused folder can therefore include pages that no longer belong to the intended PDF.

## Index extracted pages

```powershell
python vector_store.py index --folder "output_text/my-document" --source "my-document.pdf"
```

```text
python vector_store.py index [--folder FOLDER] --source SOURCE
```

- `--folder`: directory containing files matching `page_<number>.txt`; default `output_text`.
- `--source`: required original display filename or source label.

Files are sorted by numeric page number. Empty text is skipped during chunking. If no matching files or no useful text exists, the command reports an error. No PDF is guessed or opened from `--source`.

New writes use v2 storage and a content identity for ordered page text in a separate namespace. Repeating an unchanged page-text index reuses it. It does not replace or delete legacy records merely because `source` matches. Failed indexing is retryable for the same identity.

The command prints the number of stored chunks and the resolved database path. It retains the original command shape while using the safer document-state workflow internally.

## Search

```powershell
python vector_store.py search "What does the document recommend?"
python vector_store.py search "What does it say about persistence?" --source "my-document.pdf" --top-k 5
```

```text
python vector_store.py search QUESTION [--source SOURCE] [--document-id DOCUMENT_ID] [--top-k TOP_K]
```

- `QUESTION`: required query string; quote it when it contains spaces.
- `--source`: optional exact display filename or exact legacy source value.
- `--document-id`: optional full identity to select one document precisely.
- `--top-k`: positive integer, default 5.

Without filters, this compatibility command searches **all ready documents** and returns the nearest results across them. In contrast, the UI always scopes search to one selected document. `--source` can match multiple distinct versions sharing a filename. When both filters are present, both must match.

Example using a new document's full identity from `documents/<identity>/manifest.json`:

```powershell
python vector_store.py search "What are the recommended steps?" --document-id "<full-64-character-document-id>" --top-k 3
```

Legacy identities have the form `legacy:<sha256-of-source>` and are returned by `VectorStore.list_documents()`. They are not PDF hashes. The internal selector catalog can be inspected without loading the embedding model:

```python
from vector_store import VectorStore

for document in VectorStore().list_documents():
    print(document.document_id, document.filename, document.kind)
```

CLI search prints the filename, PDF page, raw vector distance, and passage text. Smaller cosine distances indicate nearer vectors within this setup; they are not confidence percentages. This command does not perform the optional reranking, final passage deduplication, follow-up rewriting, or answer generation provided by `rag.py` and the UI.

## Help and errors

```powershell
python pdf_reader.py --help
python vector_store.py --help
python vector_store.py index --help
python vector_store.py search --help
```

Argument errors are handled by argparse. Handled PDF/value/filesystem errors report a nonzero exit with a message. Dependency/model/database failures may require the troubleshooting guide and can still produce a Python traceback. An empty search result prints a no-matches message rather than generating an answer.

A separate invocation creates a new Python process and therefore reloads the model from disk. Repeated searches within the Streamlit process share its loaded model.
