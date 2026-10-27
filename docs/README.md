# Documentation

PassageHarbor is the repository name. **PDF Knowledge Assistant** is the title displayed in the Streamlit application. These guides describe the implementation in this repository rather than a separate hosted service.

## Choose a reading path

### I want to use the app

Read [Getting started](getting-started.md), then the [User guide](user-guide.md). Keep [Troubleshooting](troubleshooting.md) nearby if setup, downloads, or generation fail.

### I want to understand or extend the code

Read [Architecture](architecture.md), [Developer reference](developer-reference.md), and [Testing](testing.md). Consult [Contributing](../CONTRIBUTING.md) before submitting a change.

### I already have a local index

Read [Storage and migration](storage-and-migration.md) before moving data, changing model settings, or upgrading Chroma. The [CLI reference](cli-reference.md) explains how the original commands continue to work.

### I need to understand the data boundary

Read [Privacy and security](privacy-and-security.md) and [Configuration](configuration.md). Local embeddings do not make answer generation local: selected evidence and conversational context can be sent to Groq.

## Reference map

- [Getting started](getting-started.md): prerequisites, PowerShell setup, first downloads, start/stop.
- [User guide](user-guide.md): upload, selection, follow-ups, passage inspection, and settings.
- [Architecture](architecture.md): module responsibilities, indexing flow, QA sequence, failure states.
- [Configuration](configuration.md): environment variables, Streamlit options, model/cache settings.
- [Storage and migration](storage-and-migration.md): data layout, manifests, metadata, and compatibility.
- [CLI reference](cli-reference.md): extraction, indexing, search, and filter behavior.
- [Developer reference](developer-reference.md): public helpers and their inputs/outputs.
- [Testing](testing.md): test mechanics, verification scope, and manual smoke checks.
- [Privacy and security](privacy-and-security.md): local/external data, credentials, and limitations.
- [Troubleshooting](troubleshooting.md): actionable diagnosis and recovery.
- [Design archive](design/README.md): original editable diagram, retained as historical context.

## Terminology

**Document identity** is the SHA-256 hash of uploaded PDF bytes. **Page** means a one-based PDF page. A **chunk** is a token-bounded span from one page. A **candidate** is a vector-search result before optional reranking and deduplication. A **passage** is a selected chunk supplied as evidence. A **citation label** such as `[2]` refers to one passage in one answer, not a permanent database record number.

**Legacy** means records in `pdf_minilm_v1` using source metadata. **Ready** means a new document's chunks were written, counted, and recorded in a ready manifest. **Grounded** describes the intended use of supplied passages; it is not a guarantee that every generated statement is supported.

## Documentation conventions

Commands assume an activated virtual environment and the project directory unless stated otherwise. Values such as `my-document.pdf` and `your_available_groq_chat_model_id` are examples to replace. Synthetic examples are not user documents or measured retrieval-quality results. Diagrams have editable sources; SVG assets include accessibility titles and descriptions.
