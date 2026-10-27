# Getting started

[Documentation home](README.md) · [Next: user guide](user-guide.md)

## Prerequisites

Install Python 3.11 or newer and Git if cloning the repository. Python 3.11 or 3.12 is a practical fresh-environment choice; local development also used Windows/Python 3.13. A CPU is sufficient. A GPU is optional, and the reranker is explicitly configured for CPU. There is no minimum RAM benchmark in this repository; model loading, PDF length, and library versions affect memory use. Allow room for Python dependencies, model caches, and the local document database.

Internet access is required to install dependencies and download models the first time. Groq answer generation requires internet access and a configured Groq account/model. A Groq key is unnecessary for local passage search.

## Install on Windows

```powershell
git clone https://github.com/hammadfarooq-ai/passageharbor.git
Set-Location passageharbor
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

For an existing checkout at `D:\rag-app`, use `Set-Location D:\rag-app` and skip cloning. Do not move or delete an existing database just to start the UI.

If `python` is unavailable but the Windows launcher is installed, choose an installed interpreter, for example `py -3.12 -m venv .venv`. If activation is blocked, run commands through `.\.venv\Scripts\python.exe` directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

This avoids changing PowerShell's execution policy. Avoid mixing packages from different Python installations. Use `python -m pip` so installation targets the interpreter that runs the app.

## Configure Groq

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Enter your own values:

```dotenv
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=your_available_groq_chat_model_id
MAX_UPLOAD_MB=25
```

Create the key in the [Groq API Keys console](https://console.groq.com/keys). Select an available text chat model using [Groq's model list](https://console.groq.com/docs/models); model IDs and account access can change. The repository deliberately leaves the model placeholder empty instead of promising permanent availability of one model.

Save the file in the project root, alongside `app.py`, as `.env` rather than `.env.txt`. Do not paste a real key into source code, public issues, screenshots, or documentation. A process environment variable overrides the same name in `.env`. Restart Streamlit after edits so previously loaded values do not persist.

## Run and stop

```powershell
python -m streamlit run app.py
```

Open the address printed by Streamlit, normally `http://127.0.0.1:8501`. Stop it with **Ctrl+C** in the terminal that launched it. Restart with the same command. If port 8501 is busy:

```powershell
python -m streamlit run app.py --server.port 8502
```

Use the new printed URL. The checked-in `.streamlit/config.toml` binds to `127.0.0.1`, uses a light neutral theme, sets the transport upload limit to 25 MB, and disables Streamlit usage statistics. Run from the project folder to load that configuration. Database, document, and `.env` paths use the source-file location, so changing working directories does not create a second database.

## First run and downloads

The UI can list indexed documents before loading the embedding model. First processing or search loads `sentence-transformers/all-MiniLM-L6-v2`. The library may contact Hugging Face to resolve/download assets even when some files are cached. After loading, the process shares the model across questions and reruns. A separate CLI process must load its own model.

Turning on **Improve passage ranking** loads `cross-encoder/ms-marco-MiniLM-L6-v2` separately. It can increase CPU latency and storage use. If loading fails, retrieval continues with a nonblocking notice. An unavailable-reranker result is cached; restart the app to retry the load.

Model cache locations are managed by Hugging Face and Sentence Transformers. `HF_HOME` and `SENTENCE_TRANSFORMERS_HOME` are library settings, not extra app-specific variables. If working offline after downloading all needed assets, consult the libraries' offline configuration; do not expect an uncached model to load without a download.

## Verify the first document

1. Upload a small text PDF.
2. Select **Process document** and wait for **Ready**.
3. Select the document and ask a question about a specific part.
4. Inspect the passages and PDF page numbers before relying on the answer.

With blank Groq settings, the same workflow displays passages only. With valid settings, it streams an answer and checks citation labels when complete. Asking a question can invoke Groq and incur usage under your account; the automated test suite uses mocks instead.

## Update an existing installation

Stop the app. Back up `chroma_db/` and `documents/` together before dependency/schema upgrades. Review the [changelog](../CHANGELOG.md), pull the code, and reinstall dependencies in the intended environment. The provided requirements use compatibility ranges rather than a fully locked environment, so newly resolved dependency versions can differ between installations.

The application recognizes the compatible legacy collection without migration. Never delete its database as an installation step. See [storage and migration](storage-and-migration.md).
