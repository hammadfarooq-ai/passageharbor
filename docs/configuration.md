# Configuration reference

[Documentation home](README.md) · [Troubleshooting](troubleshooting.md)

## Application environment variables

`load_config()` loads `.env` next to the Python files using `load_dotenv(..., override=False)`. Existing process variables win. The app strips leading/trailing whitespace from key/model values. Restart the Streamlit process after edits: dotenv does not overwrite values already loaded into that process.

| Variable | Default | Validation and behavior |
| --- | --- | --- |
| `GROQ_API_KEY` | Empty string | Required for answers when a model is configured; never commit a real value. |
| `GROQ_MODEL` | Empty string | Required for answers; passed to the Groq SDK on every request. |
| `MAX_UPLOAD_MB` | `25` | Must parse as a positive integer; measured as `value × 1024 × 1024` bytes. |

Both Groq fields must be nonempty to enable generation and follow-up rewriting. This checks configuration presence, not key validity or model access. Empty/missing values leave passage-only search available. An invalid upload-limit value prevents normal app initialization until corrected.

```dotenv
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=your_available_groq_chat_model_id
MAX_UPLOAD_MB=25
```

`.env.example` intentionally leaves the two Groq values blank. See [Groq's supported models](https://console.groq.com/docs/models) rather than assuming a model identifier will remain available forever. Reasoning models can consume output capacity before producing visible content; see [output-limit troubleshooting](troubleshooting.md#the-answer-is-empty-or-incomplete).

## Streamlit server and presentation

`.streamlit/config.toml` sets:

- `server.address = "127.0.0.1"`: loopback only.
- `server.maxUploadSize = 25`: transport limit in MB.
- `browser.gatherUsageStats = false`: disable Streamlit usage statistics.
- A light theme, green accent, neutral backgrounds, and a sans-serif font.

The app also checks file size before reading uploaded bytes for processing. Newer Streamlit versions receive the app limit through the uploader's `max_upload_size` argument when available. Older versions rely on the server transport limit as well as the application check.

To accept 50 MB, set `MAX_UPLOAD_MB=50` and start with:

```powershell
python -m streamlit run app.py --server.maxUploadSize 50
```

Use `--server.port 8502` for an occupied port. Keep loopback binding unless you separately design authentication, access controls, and deployment hardening. The project does not supply those controls.

## Sidebar retrieval settings

| Control | Default | UI range / effect |
| --- | --- | --- |
| Improve passage ranking | Off | Uses the cached cross-encoder locally on CPU. |
| Candidate passages | `15` | Integer range 10–30; scoped to the selected document. |
| Passages per answer | `5` | Integer range 4–6; filters can retain fewer. |

There is no user-configurable relevance threshold. Distances and reranker scores are not confidence percentages. Validate any future threshold against representative questions before relying on it.

## Code constants and request limits

These are implementation settings, not `.env` variables:

| Location | Setting | Value |
| --- | --- | --- |
| `vector_store.py` | Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| `vector_store.py` | Optional reranker | `cross-encoder/ms-marco-MiniLM-L6-v2` |
| `vector_store.py` | Content chunk target / overlap | `200` / `40` tokens |
| `vector_store.py` | New collection / schema | `pdf_minilm_v2` / `2` |
| `vector_store.py` | Legacy collection | `pdf_minilm_v1` |
| `vector_store.py` | Chroma upsert batch | `64` chunks |
| `vector_store.py` | Encoder batch | `32` texts |
| `rag.py` | SDK timeout / retries | `45.0` seconds / `0` automatic retries |
| `rag.py` | Generation | `stream=True`, temperature `0.1`, `max_completion_tokens=1000` |
| `rag.py` | Follow-up rewriting | Temperature `0`, `max_completion_tokens=160` |
| `rag.py` | Recent history | Up to `6` eligible messages, `1800` characters each |
| `app.py` | User question input | Up to `2000` characters |

Final chunk length is capped by the model/tokenizer limit including special tokens, so 200 is a target rather than permission to exceed the actual input budget. Increasing generation tokens or choosing a different model can affect cost and latency. Changing embedding model, normalization, or chunk identity assumptions requires an explicit index migration, not simply changing a string over an existing collection.

## Paths

`BASE_DIR` is the directory containing `vector_store.py`. The default database is `BASE_DIR / "chroma_db"`, uploads/manifests are under `BASE_DIR / "documents"`, and `.env` is loaded from `BASE_DIR`. There is no `DATABASE_PATH` or upload-directory environment variable implemented.

For tests or scripts, pass `VectorStore(database_path=..., document_path=..., model=...)` explicitly. When a nondefault database is passed without a document path, its sibling `documents` directory is used. Always pass both for isolated tests or nonstandard layouts.

## Library cache and device settings

The embedding model uses Sentence Transformers' default device selection; the reranker explicitly uses CPU. Hugging Face/Sentence Transformers manage disk caching and their own environment settings, such as `HF_HOME` and `SENTENCE_TRANSFORMERS_HOME`. Fully populated local caches can support local retrieval without further downloads when the libraries are configured offline. Groq still needs a connection for generation.

The shared embedding loader and reranker use process caches. `st.cache_resource` also shares the UI's `VectorStore`. The reranker caches a failed initialization result; restart to retry. A new CLI process has a fresh memory cache.
