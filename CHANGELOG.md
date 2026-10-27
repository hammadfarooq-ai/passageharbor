# Changelog

Meaningful project changes are recorded here. Dates use ISO format. No release/tag is implied by an unreleased entry.

## Unreleased

### Application

- Streamlit PDF Knowledge Assistant with uploads, document selection, per-document session chat, streamed Groq answers, and expandable source passages.
- pypdf extraction, preserved original page text, safe hash-based upload identities, duplicate reuse, and PDF validation with explicit no-OCR guidance.
- Local cached MiniLM embeddings, token-bounded original spans, conservative repeated-margin cleaning, and contents-aware passage selection.
- V2 Chroma collection with stable IDs, manifest readiness, batch writes, locks, partial-index recovery, and legacy v1 discovery.
- Optional cached CPU reranking with a nonblocking vector-search fallback.
- Follow-up rewriting, safe provider error messages, incomplete-draft states, and citation-label mapping checks.
- Preserved extraction/index/search CLI workflows and temporary-store/mocked-provider tests.

### Documentation and repository

- PassageHarbor repository identity while retaining the existing application title.
- Designed README, editable SVG visuals, Mermaid component/sequence/state diagrams, and comprehensive user/developer/reference guides.
- MIT license, contribution/security guidance, issue/PR templates, and a cross-platform CI workflow.
- Documentation validation for local links, anchors, fenced blocks, and SVG accessibility metadata.
- Public-source exclusions for credentials, PDFs, extracted text, databases, environments, and generated artifacts.
