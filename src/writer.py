"""
Writer: reescreve spans traduzidos in-place no PDF original.

Fase 0 (CRUA):
- Apaga o texto original com redact_annot (cor de fundo branca por default)
  e escreve o novo texto na mesma bbox usando insert_textbox.
- Sem ajuste fino de fonte/tamanho. Se o texto traduzido nao couber, sera
  truncado ou ficara sobre o limite da bbox -> esse e o "Problema 1" do
  briefing, tratado em fases posteriores.
- Sem substituicao inteligente de fonte. Usamos uma fonte segura (helv) com
  suporte a Latin-1 para garantir que acentos rendem -> "Problema 2" tratado
  parcialmente aqui usando fallback, mas sem manter a fonte original.

Estrategia anti-quebra-de-layout:
- Pintamos um retangulo branco sobre o texto antigo (em vez de redact_annot,
  que pode remover imagens proximas).
- Inserimos o novo texto com PyMuPDF insert_textbox, alinhamento esquerdo,
  font_size = min(original_size, ajuste se nao couber).
"""
from __future__ import annotations

import logging
from typing import Iterable, List, Tuple

import pymupdf

from .extractor import TextSpan

log = logging.getLogger(__name__)


# Mapa de fontes do PDF original para fontes "seguras" do PyMuPDF
# (base14, sempre disponiveis e com Latin-1).
FONT_MAP = {
    # Calibri / Arial families -> Helvetica
    "default": "helv",
    "bold": "hebo",
    "italic": "heit",
    "bold_italic": "hebi",
}


def _pick_safe_font(span: TextSpan) -> str:
    """Mapeia a fonte original para uma fonte segura do PyMuPDF."""
    flags = span.flags
    is_bold = bool(flags & 16) or "bold" in span.font.lower() or "-bd" in span.font.lower()
    is_italic = bool(flags & 2) or "italic" in span.font.lower() or "oblique" in span.font.lower()
    if is_bold and is_italic:
        return FONT_MAP["bold_italic"]
    if is_bold:
        return FONT_MAP["bold"]
    if is_italic:
        return FONT_MAP["italic"]
    return FONT_MAP["default"]


def _int_color_to_rgb(c: int) -> Tuple[float, float, float]:
    r = ((c >> 16) & 0xFF) / 255.0
    g = ((c >> 8) & 0xFF) / 255.0
    b = (c & 0xFF) / 255.0
    return (r, g, b)


def write_translated_pdf(
    input_pdf: str,
    output_pdf: str,
    spans: List[TextSpan],
    translations: List[str],
) -> None:
    """
    Aplica `translations[i]` no lugar de `spans[i].text` no PDF de saida.

    Args:
        input_pdf: caminho do PDF original.
        output_pdf: caminho onde salvar o PDF traduzido.
        spans: lista produzida por extractor.extract_spans().
        translations: lista paralela com o texto traduzido de cada span.
    """
    if len(spans) != len(translations):
        raise ValueError(
            f"Spans ({len(spans)}) e translations ({len(translations)}) "
            f"precisam ter o mesmo tamanho."
        )

    doc = pymupdf.open(input_pdf)

    try:
        # Agrupa spans por pagina para minimizar acesso a paginas
        by_page: dict[int, list[tuple[TextSpan, str]]] = {}
        for span, translation in zip(spans, translations):
            by_page.setdefault(span.page, []).append((span, translation))

        for page_idx, items in by_page.items():
            page = doc[page_idx]

            # 1) Apagar o texto original cobrindo cada bbox com retangulo branco.
            #    (redact_annot e mais limpo, mas pode afetar imagens proximas)
            for span, translation in items:
                if translation == span.text:
                    continue  # nada a fazer
                rect = pymupdf.Rect(span.bbox)
                # Pequeno padding para evitar artefatos de borda
                rect = pymupdf.Rect(
                    rect.x0 - 0.5, rect.y0 - 0.5, rect.x1 + 0.5, rect.y1 + 0.5
                )
                page.draw_rect(rect, color=None, fill=(1, 1, 1), overlay=True)

            # 2) Escrever texto traduzido sobre o retangulo branco
            for span, translation in items:
                if translation == span.text:
                    continue
                rect = pymupdf.Rect(span.bbox)
                fontname = _pick_safe_font(span)
                color = _int_color_to_rgb(span.color)

                # Tenta usar o tamanho original; se nao couber, reduz
                # progressivamente ate caber ou atingir tamanho minimo.
                font_size = span.size
                inserted = -1
                # Aumenta a largura util ligeiramente para acomodar expansao
                # de texto (Problema 1 do briefing, tratamento minimo).
                draw_rect = pymupdf.Rect(
                    rect.x0,
                    rect.y0 - 1.0,
                    rect.x1 + max(60, (rect.x1 - rect.x0) * 0.4),
                    rect.y1 + 2.0,
                )

                while font_size >= 4.0:
                    inserted = page.insert_textbox(
                        draw_rect,
                        translation,
                        fontname=fontname,
                        fontsize=font_size,
                        color=color,
                        align=0,  # left
                        overlay=True,
                    )
                    if inserted >= 0:
                        break
                    font_size -= 0.5

                if inserted < 0:
                    # Ainda nao coube: forca insercao com 4pt
                    page.insert_textbox(
                        draw_rect,
                        translation,
                        fontname=fontname,
                        fontsize=4.0,
                        color=color,
                        align=0,
                        overlay=True,
                    )
                    log.warning(
                        "Span pagina %s nao coube nem em 4pt: %r",
                        page_idx,
                        translation[:60],
                    )

        # Salva com garbage=4 (limpa objetos nao usados) e deflate=True
        doc.save(output_pdf, garbage=4, deflate=True)
    finally:
        doc.close()
