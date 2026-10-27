# User guide

[Documentation home](README.md) · [Configuration reference](configuration.md)

## Upload and process

Use **Upload a PDF** in the sidebar. The default limit is 25 MB. The application validates emptiness, size, readability, and password protection before indexing. It accepts text-based PDFs; it does not run OCR.

**Process document** shows extraction, preparation of the local embedding model, cleaning/chunking, embedding, and storage phases. The progress indicator describes the current phase, not a single estimated completion time. First model loading can be slower than later questions.

Duplicate processing is guarded in the UI and by a file lock. The same PDF byte hash reuses its completed index, even if uploaded under a different filename. Different bytes produce separate documents, including files with identical names. Updating only PDF metadata also changes the byte hash.

Blank pages are preserved in original page text and counted in the processing result, but produce no useful text chunks. A scanned-only PDF with no extractable alphanumeric text is rejected with OCR guidance. Mixed PDFs can appear ready while their images remain unsearchable.

## Document selection and state

Choose **Selected document** to control the evidence used by the next question. New entries show a short identity suffix to distinguish identical filenames. Legacy entries show **existing index**.

- **Ready:** search and chat are available.
- **Processing:** another indexer may still be active; refresh to check it.
- **Failed or interrupted:** upload the same PDF and choose **Process document** to retry. Partial records stay out of normal retrieval.
- **No documents:** upload and process a PDF before entering questions.

Changing documents changes both retrieval scope and the conversation supplied to the answer pipeline. Clearing the conversation affects only the current selection. It does not delete uploaded files, page text, or vectors.

## Ask useful questions

Start with a concrete question whose answer is likely to fit in a few source passages. The example buttons offer broad entry points, but specific questions usually give you more relevant evidence.

For example, “Which three actions are recommended in the preparation section?” is easier to inspect than “Explain everything in this book.” The app searches passages and is not an exhaustive document summarizer.

Follow-ups such as “How can I apply that?” use up to six recent eligible messages to rewrite the question into a standalone search query. If clarification fails, the original question is searched. Generation still receives the original user wording. Previous assistant text is conversational context, not source evidence.

Chat input is limited to 2,000 characters in the UI. Each document's history remains within the Streamlit session. Reloading or reconnecting can preserve a live session in some circumstances, but session history is not a durable chat archive and should not be relied on after the session ends.

## Read the answer and sources

During streaming, the response is marked as a **draft**. On completion, numeric citation labels are checked against that answer's selected passages. A warning marks missing, malformed, or unmapped labels as needing verification. An interrupted or output-limited response is kept as an incomplete draft.

Expand **Source passages** below an answer to inspect its labels, filename, PDF page, and full excerpt. Labels are local to that answer. A later answer's `[1]` can refer to a different passage. The saved history retains the original mapping across reruns.

For new indexes, **Inspect original page text** shows the extracted page before cleaning. This is extracted text rather than a rendered image of the PDF. Legacy records do not prove which local PDF produced them, so the app does not guess a PDF path from a filename or offer original-page inspection for them.

PDF page labels count from the first page of the actual file. A printed title page, Roman numeral section, or offset book numbering can make the printed number different.

> Valid labels show which retrieved passages the answer refers to. They do not verify every claim, establish quotation accuracy, or guarantee the absence of hallucinations. Read the excerpts and the original PDF when accuracy matters.

## Search settings

Open the sidebar's **Search settings** expander:

- **Improve passage ranking:** off by default; uses a local CPU cross-encoder when available. Failures fall back to vector retrieval.
- **Candidate passages:** 10–30, default 15. More candidates can expose more useful text to reranking but do not expand the model's actual source corpus beyond the selected document.
- **Passages per answer:** 4–6, default 5. Deduplication and contents filtering can produce fewer.

Contents-like chunks are avoided when useful prose is available, unless the question explicitly asks for a table of contents or contents page. Duplicate and heavily overlapping excerpts are removed after ranking. These are heuristics; they can miss relevant text or occasionally classify a passage incorrectly.

Scores are not displayed as confidence percentages. The app does not impose an unvalidated universal relevance threshold.

## Work without Groq configuration

If either Groq setting is empty, the application explains what to configure and returns local passages for questions. It makes no Groq request in this mode. Follow-up rewriting is skipped, so rephrase references such as “that” explicitly for better local search.

If credentials are present but invalid, generation can fail after retrieval. Sources remain visible. Configuration presence is not authentication validation, and the application does not make a paid test request simply because it starts.

## Practical limits

There is no OCR, image understanding, multi-document question answering in the UI, account system, or public-hosting security layer. Multi-column text and complex tables can be extracted in an unexpected order. Use shorter, more specific questions when the document is large or the source evidence is incomplete. See [Troubleshooting](troubleshooting.md) for recovery steps.
