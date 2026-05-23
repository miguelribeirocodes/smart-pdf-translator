"""
Teste minimo do extractor.

Roda contra os PDFs reais na pasta do projeto, se existirem.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.extractor import extract_spans, page_count

ROOT = Path(__file__).resolve().parent.parent

PDFS = [
    ROOT / "document_pdf.pdf",
    ROOT / "document_pdf (1).pdf",
]


@pytest.mark.parametrize("pdf", [p for p in PDFS if p.exists()])
def test_extractor_returns_spans(pdf: Path) -> None:
    spans = extract_spans(str(pdf))
    assert spans, f"Esperava pelo menos 1 span em {pdf.name}"

    # Conferir estrutura
    s = spans[0]
    assert isinstance(s.text, str) and s.text.strip()
    assert s.size > 0
    assert len(s.bbox) == 4
    assert all(isinstance(c, (int, float)) for c in s.bbox)
    assert s.page >= 0


@pytest.mark.parametrize("pdf", [p for p in PDFS if p.exists()])
def test_page_count_positive(pdf: Path) -> None:
    n = page_count(str(pdf))
    assert n > 0


def test_supported_languages_has_pt_and_en() -> None:
    from src.translator import SUPPORTED_LANGUAGES
    assert "en" in SUPPORTED_LANGUAGES
    assert "pt" in SUPPORTED_LANGUAGES
