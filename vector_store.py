"""Local, document-scoped indexing. The legacy collection is never rewritten."""

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.config import Settings
from filelock import FileLock, Timeout

from pdf_reader import Page, Progress, extract_pdf_bytes

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "chroma_db"
DOCUMENT_PATH = BASE_DIR / "documents"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_NAME = "cross-encoder/ms-marco-MiniLM-L6-v2"
COLLECTION_NAME = "pdf_minilm_v1"
UPLOAD_COLLECTION = "pdf_minilm_v2"
INDEX_VERSION = 2
CHUNK_SIZE = 200
CHUNK_OVERLAP = 40


@lru_cache(maxsize=1)
def get_embedding_model():
    """One shared model per process, including Streamlit reruns."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


@lru_cache(maxsize=1)
def get_reranker():
    """Cache both a successful model and an unavailable-model result."""
    try:
        from sentence_transformers import CrossEncoder
        return CrossEncoder(RERANKER_NAME, device="cpu"), None
    except Exception:
        return None, "The optional passage reranker is unavailable. Using local vector search. Check your connection and restart the app to retry its download."


def document_identity(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def chunk_identity(document_id: str, page: int, chunk: int) -> str:
    return hashlib.sha256(f"v{INDEX_VERSION}:{document_id}:{page}:{chunk}".encode()).hexdigest()


def display_filename(name: str) -> str:
    # Display metadata only; it is never used as a storage path.
    return re.sub(r"[\x00-\x1f\x7f]", "", name.replace("\\", "/").split("/")[-1])[:240] or "document.pdf"


def normalize_text(text: str) -> str:
    return "\n".join(re.sub(r"[ \t\u00a0]+", " ", line).strip()
                     for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()).strip()


def clean_pages(pages: list[Page]) -> list[Page]:
    """Remove short, repeated marginal lines only with cross-page evidence."""
    normalized = [Page(p.number, normalize_text(p.text)) for p in pages]
    counts = Counter()
    for page in normalized:
        lines = [line for line in page.text.splitlines() if line]
        counts.update({line.casefold() for line in lines[:3] + lines[-3:] if len(line) <= 160})
    required = max(3, math.ceil(sum(bool(p.text) for p in normalized) * 0.45))
    repeated = {line for line, count in counts.items() if count >= required}
    result = []
    for page in normalized:
        lines = page.text.splitlines()
        nonempty = [i for i, line in enumerate(lines) if line]
        margins = set(nonempty[:3] + nonempty[-3:])
        kept = [line for i, line in enumerate(lines)
                if not (i in margins and line.casefold() in repeated)]
        cleaned = "\n".join(kept).strip()
        # Never erase an entire page solely because its short text repeats.
        result.append(Page(page.number, cleaned if any(c.isalnum() for c in cleaned) else page.text))
    return result


def is_contents(text: str) -> bool:
    lower = text.casefold()
    leaders = len(re.findall(r"(?:\.\s*){3,}\s*\d+", text))
    entries = len(re.findall(r"(?:chapter\s+(?:\d+|[ivxlcdm]+)\b|\b\d{1,3}\s*\n)", lower))
    heading = "table of contents" in lower or bool(re.match(r"^contents\b", lower))
    # Legacy token-decoded chunks can contain only two long dotted entries and
    # lose the page heading, so recognize that distinctive layout as well.
    return (leaders >= 3 or (leaders >= 2 and text.count(".") >= 20)
            or (heading and (entries >= 3 or len(text) < 700)))


def split_spans(text, tokenizer, max_length=None):
    """Use full-page offsets, with final span checks including special tokens.

    verbose=False applies only to these intentionally untruncated calls; it does
    not globally suppress warnings. Fast-tokenizer offsets preserve typography.
    """
    text = normalize_text(text)
    if not text:
        return
    limit = min(max_length or 256, tokenizer.model_max_length)
    special = tokenizer.num_special_tokens_to_add(pair=False)
    budget = min(CHUNK_SIZE, limit - special)
    if budget <= CHUNK_OVERLAP:
        raise ValueError("The embedding model input limit is too small for the configured overlap.")
    options = dict(add_special_tokens=False, truncation=False, verbose=False)
    offsets = None
    try:
        encoded = tokenizer(text, return_offsets_mapping=True, **options)
        tokens, offsets = encoded["input_ids"], encoded["offset_mapping"]
    except (NotImplementedError, TypeError):
        tokens = tokenizer.encode(text, **options)
    start = 0
    while start < len(tokens):
        end = min(start + budget, len(tokens))
        while end > start:
            left, right = (offsets[start][0], offsets[end - 1][1]) if offsets else (-1, -1)
            chunk = (text[left:right] if offsets else tokenizer.decode(tokens[start:end], skip_special_tokens=True)).strip()
            length = len(tokenizer.encode(chunk, add_special_tokens=True, truncation=False, verbose=False))
            if length <= min(limit, budget + special):
                break
            end -= 1
        if end <= start:
            raise ValueError("A text span cannot fit within the embedding model input limit.")
        if chunk and any(c.isalnum() for c in chunk):
            yield {"text": chunk, "char_start": left, "char_end": right}
        if end == len(tokens):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)


def split_text(text, tokenizer):
    """Compatibility wrapper for the existing chunking helper."""
    for span in split_spans(text, tokenizer):
        yield span["text"]


@dataclass
class Document:
    document_id: str
    filename: str
    status: str = "pending"
    chunk_count: int = 0
    page_count: int = 0
    legacy_source: str | None = None
    kind: str = "pdf"
    schema_version: int = INDEX_VERSION
    empty_pages: int = 0
    error: str = ""


class ProcessingBusy(ValueError):
    pass


class VectorStore:
    def __init__(self, database_path=DATABASE_PATH, document_path=None, model=None):
        self.database_path = Path(database_path).resolve()
        self.document_path = Path(document_path) if document_path is not None else (
            DOCUMENT_PATH if self.database_path == DATABASE_PATH else self.database_path.parent / "documents")
        self._model = model
        self.client = chromadb.PersistentClient(path=str(self.database_path), settings=Settings(anonymized_telemetry=False))

    @property
    def model(self):
        if self._model is None:
            self._model = get_embedding_model()
        return self._model

    def collection(self, legacy=False, create=False):
        name = COLLECTION_NAME if legacy else UPLOAD_COLLECTION
        if create:
            return self.client.get_or_create_collection(name=name, embedding_function=None,
                                                        configuration={"hnsw": {"space": "cosine"}})
        from chromadb.errors import NotFoundError
        try:
            return self.client.get_collection(name=name, embedding_function=None)
        except NotFoundError:
            return None

    def directory(self, document_id):
        if not re.fullmatch(r"[0-9a-f]{64}", document_id):
            raise ValueError("Invalid document identity.")
        return self.document_path / document_id

    def read_document(self, document_id):
        path = self.directory(document_id) / "manifest.json"
        if not path.exists():
            return None
        return Document(**json.loads(path.read_text(encoding="utf-8")))

    def _save(self, document):
        directory = self.directory(document.document_id)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / "manifest.json"
        temporary = directory / "manifest.tmp"
        temporary.write_text(json.dumps(asdict(document), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)

    def list_documents(self, include_incomplete=False):
        documents = []
        for path in sorted(self.document_path.glob("*/manifest.json")):
            try:
                document = self.read_document(path.parent.name)
            except (OSError, ValueError, TypeError):
                continue
            if document and (include_incomplete or document.status == "ready"):
                documents.append(document)
        legacy = self.collection(legacy=True)
        if legacy is not None:
            sources = {}
            for offset in range(0, legacy.count(), 1000):
                for metadata in legacy.get(limit=1000, offset=offset, include=["metadatas"])["metadatas"]:
                    if metadata and metadata.get("source"):
                        source = metadata["source"]
                        count, pages = sources.get(source, (0, set()))
                        pages.add(metadata.get("page", 1))
                        sources[source] = (count + 1, pages)
            for source, (count, pages) in sorted(sources.items()):
                documents.append(Document("legacy:" + document_identity(source.encode()), display_filename(source),
                                          "ready", count, len(pages), source, "legacy", 1))
        return documents

    def is_processing(self, document_id):
        directory = self.directory(document_id)
        if not directory.exists():
            return False
        lock = FileLock(str(directory / "index.lock"))
        try:
            with lock.acquire(timeout=0):
                return False
        except Timeout:
            return True

    def process_pdf(self, data, filename, max_upload_mb=25, progress: Progress | None = None):
        if not data or len(data) > max_upload_mb * 1024 * 1024:
            extract_pdf_bytes(data, max_upload_mb)
        document_id = document_identity(data)
        directory = self.directory(document_id)
        directory.mkdir(parents=True, exist_ok=True)
        try:
            with FileLock(str(directory / "index.lock"), timeout=0):
                existing = self.read_document(document_id)
                if existing and existing.status == "ready":
                    return existing
                document = Document(document_id, display_filename(filename), status="processing")
                self._save(document)
                try:
                    extracted = extract_pdf_bytes(data, max_upload_mb, progress)
                    (directory / "original.pdf").write_bytes(data)
                    document.empty_pages = len(extracted.empty_pages)
                    return self._index(extracted.pages, document, progress)
                except Exception:
                    document.status = "failed"
                    document.error = "Processing did not finish. You can safely retry this document."
                    self._save(document)
                    raise
        except Timeout:
            raise ProcessingBusy("This document is already being processed. Wait for it to finish, then refresh.") from None

    def _index(self, pages, document, progress=None):
        directory = self.directory(document.document_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "pages.json").write_text(json.dumps([asdict(p) for p in pages], ensure_ascii=False), encoding="utf-8")
        if progress:
            progress("Preparing local embedding model (first use may download it)", 0)
        model = self.model
        chunks = []
        for index, page in enumerate(clean_pages(pages)):
            for number, span in enumerate(split_spans(page.text, model.tokenizer, model.max_seq_length), start=1):
                chunks.append({**span, "page": page.number, "chunk": number, "is_toc": is_contents(page.text)})
            if progress:
                progress("Cleaning and chunking pages", (index + 1) / len(pages))
        if not chunks:
            raise ValueError("No useful text found. Scanned PDFs require an OCR step before indexing.")
        collection = self.collection(create=True)
        # Replace only this unready v2 document. Legacy and ready indexes stay intact.
        collection.delete(where={"document_id": document.document_id})
        for start in range(0, len(chunks), 64):
            batch = chunks[start:start + 64]
            if progress:
                progress("Embedding passages locally", start / len(chunks))
            embeddings = model.encode([c["text"] for c in batch], batch_size=32,
                                      normalize_embeddings=True, show_progress_bar=False).tolist()
            if progress:
                progress("Storing passages", (start + len(batch)) / len(chunks))
            metadata = [{"document_id": document.document_id, "filename": document.filename,
                         "source": document.filename, "page": c["page"], "chunk": c["chunk"],
                         "embedding_model": MODEL_NAME, "schema_version": INDEX_VERSION,
                         "index_version": INDEX_VERSION, "char_start": c["char_start"],
                         "char_end": c["char_end"], "is_toc": c["is_toc"]} for c in batch]
            collection.upsert(ids=[chunk_identity(document.document_id, c["page"], c["chunk"]) for c in batch],
                              documents=[c["text"] for c in batch], embeddings=embeddings, metadatas=metadata)
        stored = collection.get(where={"document_id": document.document_id}, include=[])
        if len(stored["ids"]) != len(chunks):
            raise ValueError("Not all passages were stored. Please retry processing.")
        document.status, document.chunk_count, document.page_count = "ready", len(chunks), len(pages)
        document.error = ""
        self._save(document)
        if progress:
            progress("Document ready", 1)
        return document

    def original_page(self, document, number):
        if document.kind == "legacy":
            return None  # A legacy filename does not prove which local PDF produced it.
        path = self.directory(document.document_id) / "pages.json"
        if not path.exists():
            return None
        return next((p["text"] for p in json.loads(path.read_text(encoding="utf-8")) if p["number"] == number), None)

    def search(self, question, document, candidates=15):
        if not question.strip():
            return []
        if document.kind != "legacy":
            current = self.read_document(document.document_id)
            if not current or current.status != "ready":
                raise ValueError("This document is not indexed yet. Process it before asking questions.")
            if current.schema_version != INDEX_VERSION:
                raise ValueError("This document uses a different index version.")
        collection = self.collection(legacy=document.kind == "legacy")
        if collection is None:
            return []
        where = {"source": document.legacy_source} if document.kind == "legacy" else {"document_id": document.document_id}
        embeddings = self.model.encode([question], normalize_embeddings=True, show_progress_bar=False).tolist()
        results = collection.query(query_embeddings=embeddings, where=where,
                                   n_results=max(1, min(candidates, document.chunk_count)),
                                   include=["documents", "metadatas", "distances"])
        return [{"id": identity, "text": text, "source": document.filename, "filename": document.filename,
                 "page": metadata.get("page", 1), "chunk": metadata.get("chunk", 0),
                 "distance": distance, "char_start": metadata.get("char_start", -1),
                 "char_end": metadata.get("char_end", -1),
                 "is_toc": metadata.get("is_toc", is_contents(text))}
                for identity, text, metadata, distance in zip(results["ids"][0], results["documents"][0],
                                                              results["metadatas"][0], results["distances"][0])]


def open_store():
    """Compatibility helper returning the cached model and legacy collection."""
    store = VectorStore()
    return store.model, store.collection(legacy=True)


def index_pages(folder, source, *, store=None):
    """Preserve the page-file CLI; new writes use the safer v2 schema."""
    page_files = []
    for path in Path(folder).glob("page_*.txt"):
        match = re.fullmatch(r"page_(\d+)", path.stem)
        if match:
            page_files.append((int(match[1]), path))
    pages = [Page(number, path.read_text(encoding="utf-8")) for number, path in sorted(page_files)]
    if not pages:
        raise FileNotFoundError(f"No page_*.txt files found in: {Path(folder).resolve()}")
    if not any(any(c.isalnum() for c in p.text) for p in pages):
        raise ValueError("No extractable text found. Scanned PDFs may require OCR.")
    store = store or VectorStore()
    # Text files may be edited independently of the PDF. Never claim that their
    # index is the hash of an unrelated PDF merely because its filename matches.
    canonical = json.dumps([asdict(p) for p in pages], ensure_ascii=False, sort_keys=True).encode()
    identity = document_identity(b"page-text-v2\0" + canonical)
    directory = store.directory(identity)
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(directory / "index.lock"), timeout=0):
            document = store.read_document(identity)
            if not document or document.status != "ready":
                document = Document(identity, display_filename(source), "processing", kind="page_text")
                store._save(document)
                try:
                    document = store._index(pages, document)
                except Exception:
                    document.status, document.error = "failed", "Processing failed. Run indexing again to retry."
                    store._save(document)
                    raise
    except Timeout:
        raise ProcessingBusy("This document is already being indexed.") from None
    print(f"\nStored {document.chunk_count} chunks from {document.filename}.")
    print(f"Database: {store.database_path}")
    return document


def search_pages(question, source=None, top_k=5, *, store=None, document_id=None):
    store = store or VectorStore()
    documents = store.list_documents()
    if source:
        documents = [d for d in documents if d.filename == source or d.legacy_source == source]
    if document_id:
        documents = [d for d in documents if d.document_id == document_id]
    matches = [match for document in documents for match in store.search(question, document, top_k)]
    return sorted(matches, key=lambda match: match["distance"])[:top_k]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Index PDF page text and search it with ChromaDB.")
    commands = parser.add_subparsers(dest="command", required=True)
    index_command = commands.add_parser("index")
    index_command.add_argument("--folder", default="output_text")
    index_command.add_argument("--source", required=True)
    search_command = commands.add_parser("search")
    search_command.add_argument("question")
    search_command.add_argument("--source")
    search_command.add_argument("--document-id")
    search_command.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    try:
        if args.command == "index":
            index_pages(args.folder, args.source)
        else:
            if args.top_k < 1:
                parser.error("--top-k must be at least 1")
            matches = search_pages(args.question, args.source, args.top_k, document_id=args.document_id)
            if not matches:
                print("No matching documents found. Run indexing first or check the selected source.")
            for number, match in enumerate(matches, start=1):
                print(f"\n[{number}] {match['source']} — PDF page {match['page']}")
                print(f"Distance: {match['distance']:.4f}")
                print(match["text"])
    except (ValueError, OSError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
