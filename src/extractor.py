"""
Extractor: le um PDF e devolve uma lista plana de TextSpan.

Fase 0 - traducao CRUA:
- Granularidade = span (PyMuPDF). Cada span tem texto homogeneo (mesma fonte,
  tamanho, cor) e bbox proprio. Isso e o suficiente para traduzir e reescrever
  in-place, ainda que a qualidade da traducao por span seja menor que por
  paragrafo logico. O reagrupamento em paragrafos fica para Fase 1
  (Problema 3 do briefing).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, List, Tuple

import pymupdf  # PyMuPDF


@dataclass
class TextSpan:
    """Unidade minima de texto extraida do PDF."""
    page: int                       # indice da pagina (0-based)
    block: int                      # indice do bloco na pagina
    line: int                       # indice da linha no bloco
    span: int                       # indice do span na linha
    text: str                       # texto original
    bbox: Tuple[float, float, float, float]   # (x0, y0, x1, y1)
    font: str                       # nome da fonte (e.g. 'Calibri-Bold')
    size: float                     # tamanho da fonte em pontos
    color: int                      # cor (int RGB, ex 0 = preto)
    flags: int                      # flags PyMuPDF (bold, italic, etc.)

    def to_dict(self) -> dict:
        return asdict(self)


def extract_spans(pdf_path: str) -> List[TextSpan]:
    """
    Le um PDF e devolve a lista de TextSpan em ordem de leitura.

    Ignora:
    - Spans vazios ou com whitespace puro (nao precisa traduzir).
    - Imagens, vetores, formularios (intocados na reescrita).
    """
    doc = pymupdf.open(pdf_path)
    spans: List[TextSpan] = []

    try:
        for page_idx, page in enumerate(doc):
            data = page.get_text("dict")
            for b_idx, block in enumerate(data.get("blocks", [])):
                if block.get("type", 0) != 0:
                    continue  # 0 = text, 1 = image -> ignorar
                for l_idx, line in enumerate(block.get("lines", [])):
                    for s_idx, span in enumerate(line.get("spans", [])):
                        text = span.get("text", "")
                        if not text or not text.strip():
                            continue
                        spans.append(
                            TextSpan(
                                page=page_idx,
                                block=b_idx,
                                line=l_idx,
                                span=s_idx,
                                text=text,
                                bbox=tuple(span["bbox"]),
                                font=span.get("font", ""),
                                size=float(span.get("size", 10.0)),
                                color=int(span.get("color", 0)),
                                flags=int(span.get("flags", 0)),
                            )
                        )
    finally:
        doc.close()

    return spans


def page_count(pdf_path: str) -> int:
    doc = pymupdf.open(pdf_path)
    try:
        return len(doc)
    finally:
        doc.close()


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Uso: python extractor.py caminho/do/arquivo.pdf")
        sys.exit(1)

    spans = extract_spans(sys.argv[1])
    print(f"Total de spans extraidos: {len(spans)}")
    for s in spans[:5]:
        print(json.dumps(s.to_dict(), ensure_ascii=False))
