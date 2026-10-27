# Privacy and security

[Documentation home](README.md) · [Security reporting](../SECURITY.md)

## Data boundary

PDF bytes and original extracted pages are stored locally under generated identity paths. Cleaning, chunking, embeddings, Chroma vector search, and optional reranking execute locally. Dependency and first-use model downloads contact their package/model hosts.

When generation is configured and a question is submitted, the app can send the following to Groq:

- The user's original question.
- Selected source excerpts, sanitized display filenames, and PDF page labels.
- Up to six eligible recent conversation messages, capped by characters.

For follow-ups, a separate rewriting request contains the latest question and bounded recent conversation. Its returned standalone question is then used for local retrieval. Generation retains the original user wording.

The application does not upload the entire PDF file to Groq. However, selected excerpts can still contain sensitive material, and their filenames can reveal information. Several questions can cumulatively send multiple parts of a document. Review the provider's [data policies](https://console.groq.com/docs/your-data) and your own requirements before using confidential PDFs.

When Groq configuration is missing, local passage mode skips answer generation and rewriting. With a valid local model cache and appropriate library offline settings, retrieval can run without a provider connection. That is different from promising every first-run library load is offline.

## Secrets

Keep `GROQ_API_KEY` in the root `.env` or the process environment. The repository ignores `.env` and other `.env.*` files while explicitly allowing `.env.example`. The example contains no key. Application errors use safe messages rather than raw provider bodies. Never post a real key, full environment dump, or private passage in an issue.

If a key is exposed, revoke/rotate it in Groq and update the local configuration. Removing it from the latest commit does not remove it from Git history. Review public history and hosting logs as well. This project has no automatic secret vault or key-rotation service.

## Local storage protection

Uploaded PDFs are stored as `documents/<sha256>/original.pdf`; filenames are display metadata rather than path inputs. Chunks, manifests, and raw page text remain readable to anyone with filesystem access. The application does **not** encrypt the local data directories or provide a retention/deletion schedule.

Back up `chroma_db/` and `documents/` together while the application is stopped. Keep backups private. The UI's **Clear conversation** resets only current-session messages; it is not a document deletion or secure erasure action.

## Local service exposure

The checked-in Streamlit configuration binds to `127.0.0.1`. There is no authentication, authorization system, multi-user data partition, or public-deployment hardening. Document-scoped retrieval prevents normal question mixing inside this workflow; it is not a tenant security model.

Changing the bind address or placing the app behind a public tunnel changes the risk materially. Add access controls, storage isolation, upload protections, and operational review before deployment beyond one local user. This repository does not include those features.

## Uploaded content and prompt injection

Documents and their filenames are untrusted reference data. System instructions require the model to ignore embedded instructions, use only supplied passages, and avoid invented sources/pages/quotes. The generation client is not given document-triggered tool execution capabilities.

Prompt instructions and numeric label validation are defenses with limits. They cannot guarantee that a model ignores all malicious content, cites the best excerpt, or supports every statement. Numeric citations are checked for mapping rather than entailment. Responses stream as drafts and are marked for verification if labels are missing/invalid or generation is incomplete. Review sensitive answers against the original document.

The interface uses Streamlit's normal Markdown renderer for assistant text without enabling raw HTML for that text. This does not make generated text inherently trustworthy. Do not execute commands or follow instructions merely because they appear in a PDF answer.

## Operational boundaries

There is no OCR, virus scanner, adversarial PDF sandbox, rate-limit service, resource quota beyond upload size, or untrusted multi-user hosting layer. A PDF can have a small compressed file size and still be expensive to parse. Use the local single-user scope and handle only documents you are authorized to process.

Chroma anonymized telemetry is disabled in the client settings and Streamlit usage statistics are disabled in the project config. Third-party libraries and providers have their own behavior and terms. The project does not claim a formal security audit or regulatory compliance certification.
