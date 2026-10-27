"""Run with: python -m streamlit run app.py"""

import inspect

import streamlit as st

from pdf_reader import PDFError
from rag import (GenerationError, INSUFFICIENT, load_config, retrieve,
                 rewrite_question, stream_answer, validate_citations)
from vector_store import ProcessingBusy, VectorStore, document_identity

st.set_page_config(page_title="PDF Knowledge Assistant", page_icon="📖", layout="centered")


@st.cache_resource
def get_store():
    return VectorStore()


def render_sources(sources, document, store):
    if not sources:
        return
    with st.expander(f"Source passages · {len(sources)}"):
        st.caption("Numbers refer to PDF pages and may differ from printed book page numbers. Passage labels link the answer to these excerpts; they do not verify every claim.")
        for source in sources:
            st.text(f"[{source['label']}] {source['filename']} · PDF page {source['page']}")
            st.text(source["text"])
            st.divider()
    if document.kind != "legacy":
        with st.expander("Inspect original page text"):
            for number in sorted({source["page"] for source in sources}):
                original = store.original_page(document, number)
                if original is not None:
                    st.caption(f"PDF page {number} · before cleaning")
                    st.text(original or "No extractable text on this page.")


def main():
    st.markdown("""<style>
    .stApp {background: #fafaf9;}
    [data-testid="stSidebar"] {background: #f1f2f0;}
    .block-container {max-width: 880px; padding-top: 2.5rem;}
    h1 {letter-spacing: -0.035em;}
    [data-testid="stChatMessage"] {border: 1px solid #e7e8e5; border-radius: 12px;}
    </style>""", unsafe_allow_html=True)
    st.title("PDF Knowledge Assistant")
    st.write("Ask your document a question. Explore its ideas and see the passages behind each answer.")
    try:
        config = load_config()
        store = get_store()
        documents = store.list_documents(include_incomplete=True)
    except Exception:
        st.error("The local configuration or document store could not be opened. Check .env values and that the project storage folder is writable. See README.md for troubleshooting.")
        st.stop()

    st.session_state.setdefault("conversations", {})
    st.session_state.setdefault("processing", False)
    with st.sidebar:
        st.header("Your documents")
        uploader_options = {}
        if "max_upload_size" in inspect.signature(st.file_uploader).parameters:
            uploader_options["max_upload_size"] = config.max_upload_mb
        upload = st.file_uploader("Upload a PDF", type=["pdf"], disabled=st.session_state.processing,
                                  help=f"Text-based PDFs, up to {config.max_upload_mb} MB. Scanned PDFs require OCR first.",
                                  **uploader_options)
        uploaded_data, uploaded_id, existing, upload_error = None, None, None, None
        busy = False
        if upload is not None:
            if upload.size == 0:
                upload_error = "This file is empty. Choose a PDF containing text."
            elif upload.size > config.max_upload_mb * 1024 * 1024:
                upload_error = f"Choose a PDF smaller than {config.max_upload_mb} MB."
            else:
                uploaded_data = upload.getvalue()
                uploaded_id = document_identity(uploaded_data)
                existing = next((d for d in documents if d.document_id == uploaded_id), None)
                busy = store.is_processing(uploaded_id)
            if upload_error:
                st.error(upload_error)
            elif existing and existing.status == "ready":
                st.success("Already indexed. Select it below to start chatting.")
            elif busy:
                st.info("Processing this document. Refresh to check its status.")
            elif existing and existing.status in ("failed", "processing"):
                st.warning("Processing was interrupted or failed. Use Process document to retry.")
            else:
                st.caption("Ready to process. This PDF is not indexed yet.")
        process = st.button("Process document", type="primary", use_container_width=True,
                            disabled=uploaded_data is None or busy or st.session_state.processing
                            or bool(existing and existing.status == "ready"))
        if process:
            st.session_state.processing = True
            try:
                with st.status("Processing your document…", expanded=True) as status:
                    phase = st.empty()
                    progress_bar = st.progress(0.0)

                    def progress(stage, fraction):
                        phase.text(stage)
                        progress_bar.progress(min(1.0, max(0.0, fraction)))

                    result = store.process_pdf(uploaded_data, upload.name, config.max_upload_mb, progress)
                    status.update(label="Document ready", state="complete", expanded=False)
                st.session_state.document_selector = result.document_id
                st.session_state.processing_note = f"Ready · {result.page_count} PDF pages. {result.empty_pages} pages had no extractable text."
            except (PDFError, ProcessingBusy) as error:
                st.error(str(error))
            except Exception:
                st.error("Processing did not finish. Check free disk space and the connection needed for the first model download, then retry. Your existing documents are still available.")
            finally:
                st.session_state.processing = False
            if "processing_note" in st.session_state:
                st.rerun()
        if note := st.session_state.pop("processing_note", None):
            st.success(note)

        by_id = {d.document_id: d for d in documents}
        options = list(by_id)

        def label(identity):
            item = by_id[identity]
            suffix = "existing index" if item.kind == "legacy" else identity[:8]
            state = "" if item.status == "ready" else f" · {item.status}"
            return f"{item.filename} · {suffix}{state}"

        if st.session_state.get("document_selector") not in options:
            st.session_state.document_selector = next((d.document_id for d in documents if d.status == "ready"), None)
        selected = st.selectbox("Selected document", options, format_func=label,
                                key="document_selector", placeholder="Process your first PDF", disabled=not options)
        document = by_id.get(selected)
        ready = bool(document and document.status == "ready")
        if ready:
            st.caption(f"Ready · {document.page_count} PDF pages · {document.chunk_count} passages")
        elif document:
            st.warning("This document is not indexed. Upload the same PDF and process it to retry.")
        with st.expander("Search settings"):
            rerank = st.checkbox("Improve passage ranking", value=False,
                                 help="Optional local model. Downloads on first use and adds CPU processing time.")
            candidates = st.slider("Candidate passages", 10, 30, 15)
            passage_count = st.slider("Passages per answer", 4, 6, 5)
            st.caption("Ranking scores are not confidence percentages. No universal relevance cutoff is applied.")
        if st.button("Clear conversation", use_container_width=True, disabled=not document):
            st.session_state.conversations[selected] = []
            st.rerun()
        st.caption("Extraction and search run locally. Answers send your question and selected passages to Groq. Follow-ups may also send a short recent conversation.")

    if config.issue:
        st.info(config.issue)
    if not ready:
        st.info("Upload a text-based PDF and select Process document to begin." if not document
                else "Process this document to make its passages searchable.")
        st.chat_input("Ask about your PDF…", disabled=True)
        return
    st.caption(f"Chatting with: {document.filename}")
    if document.kind == "legacy":
        st.caption("This existing index is ready to search. Original page text is available for newly processed documents.")
    history = st.session_state.conversations.setdefault(selected, [])
    prompt = None
    if not history:
        st.write("Start with a question")
        for column, example in zip(st.columns(3), ["What are the main ideas?", "What does it say about persistence?", "What practical steps does it suggest?"]):
            if column.button(example, use_container_width=True):
                prompt = example
    for message in history:
        with st.chat_message(message["role"]):
            if message.get("notice"):
                st.warning(message["notice"])
            st.markdown(message["content"])
            if message["role"] == "assistant":
                render_sources(message.get("sources", []), document, store)
    question = st.chat_input("Ask about your PDF…", max_chars=2000) or prompt
    if not question or not question.strip():
        return
    question = question.strip()
    previous = list(history)
    history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)
    sources, answer, notice, status = [], "", None, "complete"
    provisional, output = None, None
    with st.chat_message("assistant"):
        try:
            with st.spinner("Finding supporting passages…"):
                retrieval_question, rewrite_notice = rewrite_question(question, previous, config)
                sources, ranking_notice = retrieve(store, document, retrieval_question, candidates, passage_count, rerank)
            for informational in (rewrite_notice, ranking_notice):
                if informational:
                    st.info(informational)
            if config.issue:
                answer = "Here are the closest passages I found. Configure Groq to generate an answer with citations." if sources else INSUFFICIENT
                status = "retrieval_only"
                st.write(answer)
            else:
                provisional = st.empty()
                provisional.caption("Draft streaming · citations will be checked when the answer finishes.")
                output = st.empty()
                for token in stream_answer(question, sources, previous, config):
                    answer += token
                    output.markdown(answer + " ▌")
                output.markdown(answer)
                valid, notice = validate_citations(answer, sources)
                provisional.empty()
                if not valid:
                    status = "unverified"
                    st.warning(notice)
        except GenerationError as error:
            notice = str(error)
            status = "failed"
            if provisional is not None:
                provisional.empty()
            if answer.strip():
                if output is not None:
                    output.markdown(answer)
                notice = f"Incomplete draft — needs verification. {notice}"
            else:
                answer = "An answer could not be generated. You can inspect the retrieved passages below."
                if output is not None:
                    output.markdown(answer)
                else:
                    st.write(answer)
            st.warning(notice)
        except Exception:
            answer = "The document could not be searched. Check the local model files and document storage, then try again."
            status = "failed"
            st.error(answer)
        render_sources(sources, document, store)
    history.append({"role": "assistant", "content": answer, "sources": sources,
                    "notice": notice, "status": status})


if __name__ == "__main__":
    main()
