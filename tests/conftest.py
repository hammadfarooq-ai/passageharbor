"""All stores are temporary; no network or real embedding downloads in tests."""

import hashlib
import io
import re
import sys
from pathlib import Path

import numpy as np
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vector_store import VectorStore


class FakeTokenizer:
    model_max_length = 256

    def num_special_tokens_to_add(self, pair=False):
        return 2

    def __call__(self, text, **kwargs):
        assert kwargs.get("truncation") is False
        assert kwargs.get("verbose") is False
        matches = list(re.finditer(r"\w+|[^\w\s]", text))
        return {"input_ids": list(range(len(matches))),
                "offset_mapping": [(m.start(), m.end()) for m in matches]}

    def encode(self, text, add_special_tokens=True, **kwargs):
        tokens = self(text, **kwargs)["input_ids"]
        return [0] + tokens + [0] if add_special_tokens else tokens


class FakeModel:
    tokenizer = FakeTokenizer()
    max_seq_length = 256

    def __init__(self):
        self.calls = 0
        self.fail_after = None

    def encode(self, texts, normalize_embeddings=True, **kwargs):
        assert normalize_embeddings is True
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise RuntimeError("Simulated embedding failure")
        vectors = []
        for text in texts:
            vector = np.zeros(16, dtype=np.float32)
            for token in re.findall(r"\w+", text.lower()):
                vector[hashlib.sha256(token.encode()).digest()[0] % 16] += 1
            norm = np.linalg.norm(vector)
            vectors.append(vector / (norm or 1))
        return np.array(vectors)


def make_pdf(texts=("Persistence requires sustained effort.",), password=None):
    writer = PdfWriter()
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    font_reference = writer._add_object(font)
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})})
        if text:
            safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 40 750 Td ({safe}) Tj ET".encode("ascii"))
            page[NameObject("/Contents")] = writer._add_object(stream)
    if password:
        writer.encrypt(password)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def model():
    return FakeModel()


@pytest.fixture
def store(tmp_path, model):
    return VectorStore(tmp_path / "chroma", tmp_path / "documents", model=model)
