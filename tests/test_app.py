from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import rag
import vector_store
from conftest import make_pdf


@pytest.fixture(autouse=True)
def clear_cached_resources():
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def test_ui_empty_and_document_isolated_passage_mode(store, monkeypatch):
    monkeypatch.setattr(vector_store, "VectorStore", lambda: store)
    monkeypatch.setattr(rag, "load_config", lambda: rag.Config())
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
    app.run(timeout=30)
    assert not app.exception
    assert app.title[0].value == "PDF Knowledge Assistant"
    assert app.chat_input[0].disabled
    first = store.process_pdf(make_pdf(["Persistence requires continued effort."]), "first.pdf")
    second = store.process_pdf(make_pdf(["Astronomy is the study of stars."]), "second.pdf")
    app.run(timeout=30)
    assert not app.exception
    app.selectbox[0].select(first.document_id).run()
    app.chat_input[0].set_value("What is persistence?").run(timeout=30)
    assert not app.exception
    histories = app.session_state["conversations"]
    assert histories[first.document_id][-1]["sources"][0]["filename"] == "first.pdf"
    saved_sources = histories[first.document_id][-1]["sources"]
    app.selectbox[0].select(second.document_id).run()
    assert not app.exception
    assert not app.chat_message
    app.selectbox[0].select(first.document_id).run()
    assert len(app.chat_message) == 2
    assert app.session_state["conversations"][first.document_id][-1]["sources"] == saved_sources
    next(b for b in app.button if b.label == "Clear conversation").click().run()
    assert not app.session_state["conversations"][first.document_id]


def test_ui_marks_stream_failure_and_invalid_citations(store, monkeypatch):
    monkeypatch.setattr(vector_store, "VectorStore", lambda: store)
    monkeypatch.setattr(rag, "load_config", lambda: rag.Config("mock-key", "mock-model"))
    store.process_pdf(make_pdf(), "test.pdf")

    def invalid_stream(*args, **kwargs):
        yield "Unsupported citation [99]."

    monkeypatch.setattr(rag, "stream_answer", invalid_stream)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
    app.run(timeout=30)
    app.chat_input[0].set_value("What does it say?").run(timeout=30)
    assert not app.exception
    document_id = app.selectbox[0].value
    answer = app.session_state["conversations"][document_id][-1]
    assert answer["status"] == "unverified"
    assert "Needs verification" in answer["notice"]

    def broken_stream(*args, **kwargs):
        yield "A partial draft"
        raise rag.GenerationError("Groq timed out. Please try again.")

    monkeypatch.setattr(rag, "stream_answer", broken_stream)
    monkeypatch.setattr(rag, "rewrite_question", lambda question, *args: (question, None))
    app.chat_input[0].set_value("Another question").run(timeout=30)
    assert not app.exception
    answer = app.session_state["conversations"][document_id][-1]
    assert answer["status"] == "failed" and answer["content"] == "A partial draft"
    assert "Incomplete draft" in answer["notice"]
