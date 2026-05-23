"""
Extractor: le um PDF e devolve uma lista plana de TextSpan.
Problema 1 (Fase 1): adicionado line_x1 e page_w ao TextSpan para
calcular draw_rect sem ultrapassar a margem da pagina.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Tuple
import pymupdf


@dataclass
class TextSpan:
    """Unidade minima de texto extraida do PDF."""
    page: int
    block: int
    line: int
    span: int
    text: str
    bbox: Tuple[float, float, float, float]
    font: str
    size: float
    color: int
    flags: int
    line_x1: float = 0.0   # borda direita da linha (para draw_rect)
    page_w: float = 0.0    # largura da pagina (para cap de margem)

    def to_dict(self) -> dict:
        return asdict(self)


def extract_spans(pdf_path: str) -> List[TextSpan]:
    """
    Le um PDF e devolve a lista de TextSpan em ordem de leitura.
    Ignora spans vazios e blocos de imagem.
    """
    doc = pymupdf.open(pdf_path)
    spans: List[TextSpan] = []
    try:
        for page_idx, page in enumerate(doc):
            pw = page.rect.width
            data = page.get_text("dict")
            for b_idx, block in enumerate(data.get("blocks", [])):
                if block.get("type", 0) != 0:
                    continue
                for l_idx, line in enumerate(block.get("lines", [])):
                    lx1 = float(line["bbox"][2])
                    for s_idx, span in enumerate(line.get("spans", [])):
                        text = span.get("text", "")
                        if not text or not text.strip():
                            continue
                        spans.append(TextSpan(
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
                            line_x1=lx1,
                            page_w=pw,
                        ))
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
    import sys, json
    if len(sys.argv) < 2:
        print("Uso: python extractor.py arquivo.pdf")
        sys.exit(1)
    spans = extract_spans(sys.argv[1])
    print(f"Total de spans extraidos: {len(spans)}")
    for s in spans[:5]:
        print(json.dumps(s.to_dict(), ensure_ascii=False))
