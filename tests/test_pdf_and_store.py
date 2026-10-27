import hashlib
import sys

import pytest
from filelock import FileLock

import vector_store
from conftest import FakeTokenizer, make_pdf
from pdf_reader import PDFError, Page, extract_pdf_bytes, extract_pdf_to_txt
from vector_store import (COLLECTION_NAME, MODEL_NAME, ProcessingBusy, chunk_identity,
                          clean_pages, document_identity, index_pages, normalize_text,
                          search_pages, split_spans, split_text)


@pytest.mark.parametrize("data, expected", [(b"", "empty"), (b"not a PDF", "valid PDF"),
    (b"%PDF-corrupt", "could not be read"), (make_pdf([""]), "OCR"),
    (make_pdf([]), "no pages"), (make_pdf(password="secret"), "password protected")])
def test_invalid_pdfs(data, expected):
    with pytest.raises(PDFError, match=expected):
        extract_pdf_bytes(data)


def test_size_and_empty_pages():
    with pytest.raises(PDFError, match="upload limit"):
        extract_pdf_bytes(b"x" * (1024 * 1024 + 1), max_upload_mb=1)
    extraction = extract_pdf_bytes(make_pdf(["", "Case and punctuation, preserved!"]))
    assert extraction.empty_pages == [1]
    assert extraction.pages[1].number == 2
    assert "Case and punctuation, preserved!" in extraction.pages[1].text


def test_chunk_limits_offsets_overlap_and_no_truncation():
    tokenizer = FakeTokenizer()
    text = "Introduction: " + " ".join(f"OriginalWord{i}," for i in range(900)) + " FinalWord!"
    spans = list(split_spans(text, tokenizer, max_length=128))
    assert len(spans) > 10
    for span in spans:
        assert len(tokenizer.encode(span["text"], truncation=False, verbose=False)) <= 128
        assert normalize_text(text)[span["char_start"]:span["char_end"]] == span["text"]
    assert spans[1]["char_start"] < spans[0]["char_end"]
    assert spans[0]["text"].startswith("Introduction:")
    assert spans[-1]["text"].endswith("FinalWord!")
    assert list(split_text(" \n ", tokenizer)) == []


def test_conservative_cleaning():
    pages = [Page(i, f"Repeated header\nUnique useful paragraph number {i}.\nRepeated promotional footer") for i in range(1, 6)]
    cleaned = clean_pages(pages)
    assert all("Repeated" not in p.text for p in cleaned)
    assert all(f"number {p.number}" in p.text for p in cleaned)
    assert pages[0].text.startswith("Repeated")
    assert clean_pages([Page(1, "One useful line")])[0].text == "One useful line"
    assert all(p.text for p in clean_pages([Page(i, "Repeated but only content") for i in range(4)]))


def test_hashes_duplicate_and_same_filename(store, model):
    data = make_pdf(["One source about persistence."])
    document = store.process_pdf(data, "../../same.pdf")
    assert document.document_id == hashlib.sha256(data).hexdigest()
    assert document.filename == "same.pdf"
    assert document.status == "ready"
    calls = model.calls
    again = store.process_pdf(data, "renamed.pdf")
    assert again == document
    assert model.calls == calls
    other = store.process_pdf(make_pdf(["A separate source about astronomy."]), "same.pdf")
    assert other.document_id != document.document_id
    collection = store.collection()
    records = collection.get(where={"document_id": document.document_id}, include=["metadatas"])
    assert records["ids"] == [chunk_identity(document.document_id, 1, 1)]
    assert collection.count() == 2
    assert records["metadatas"][0]["embedding_model"] == MODEL_NAME
    assert records["metadatas"][0]["schema_version"] == 2
    assert store.original_page(document, 1).startswith("One source")
    assert (store.directory(document.document_id) / "original.pdf").read_bytes() == data
    with pytest.raises(ValueError, match="identity"):
        store.directory("../../escape")


def test_selected_document_isolation(store):
    first = store.process_pdf(make_pdf(["First document says persistence is sustained effort."]), "same.pdf")
    second = store.process_pdf(make_pdf(["Second document says astronomy studies stars."]), "same.pdf")
    assert "First document" in store.search("stars", first)[0]["text"]
    assert "Second document" in store.search("persistence", second)[0]["text"]
    assert store.search(" ", first) == []


def test_legacy_discovery_and_filtering(store):
    legacy = store.client.create_collection(COLLECTION_NAME, embedding_function=None,
                                           configuration={"hnsw": {"space": "cosine"}})
    legacy.add(ids=["old-a", "old-b"], documents=["Legacy apple", "Legacy orange"],
               embeddings=store.model.encode(["apple", "orange"]).tolist(),
               metadatas=[{"source": "old.pdf", "page": 12}, {"source": "other.pdf", "page": 8}])
    docs = store.list_documents()
    old = next(d for d in docs if d.legacy_source == "old.pdf")
    assert old.chunk_count == 1 and old.kind == "legacy"
    assert store.search("orange", old)[0]["text"] == "Legacy apple"
    assert store.search("orange", old)[0]["page"] == 12
    store.process_pdf(make_pdf(), "old.pdf")
    assert legacy.count() == 2
    assert store.original_page(old, 12) is None


def test_partial_index_hidden_retry_and_lock(store, model):
    data = make_pdf([" ".join(f"word{i}" for i in range(11000))])
    identity = document_identity(data)
    model.fail_after = 1  # Leave the first batch in Chroma, fail the second.
    with pytest.raises(RuntimeError, match="embedding failure"):
        store.process_pdf(data, "partial.pdf")
    assert store.collection().count() == 64
    assert store.list_documents() == []
    failed = store.read_document(identity)
    assert failed.status == "failed"
    with pytest.raises(ValueError, match="not indexed"):
        store.search("word", failed)
    model.fail_after = None
    ready = store.process_pdf(data, "partial.pdf")
    assert ready.status == "ready"
    assert store.collection().count() == ready.chunk_count
    with FileLock(str(store.directory(identity) / "index.lock")):
        assert store.is_processing(identity)
        with pytest.raises(ProcessingBusy):
            store.process_pdf(data, "partial.pdf")
    assert not store.is_processing(identity)


def test_existing_cli_workflow(store, tmp_path, monkeypatch, capsys):
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(make_pdf(["Persistence takes effort.", "Keep working despite setbacks."]))
    output = tmp_path / "pages"
    extract_pdf_to_txt(str(pdf), str(output))
    monkeypatch.setattr(vector_store, "VectorStore", lambda: store)
    monkeypatch.setattr(sys, "argv", ["vector_store.py", "index", "--folder", str(output), "--source", "source.pdf"])
    vector_store.main()
    assert "Stored 2 chunks" in capsys.readouterr().out
    count = store.collection().count()
    index_pages(output, "source.pdf", store=store)
    assert store.collection().count() == count
    monkeypatch.setattr(sys, "argv", ["vector_store.py", "search", "persistence", "--source", "source.pdf", "--top-k", "1"])
    vector_store.main()
    assert "PDF page" in capsys.readouterr().out
    assert len(search_pages("effort", store=store)) == 2
    assert not search_pages("effort", source="missing.pdf", store=store)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        index_pages(empty, "empty.pdf", store=store)
    (empty / "page_1.txt").write_text(" \n")
    with pytest.raises(ValueError, match="No extractable text"):
        index_pages(empty, "empty.pdf", store=store)
