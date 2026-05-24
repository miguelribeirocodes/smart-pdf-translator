"""
Writer: reescreve spans traduzidos in-place no PDF original.

Fase 0 (CRUA):
- Apaga o texto original cobrindo com retangulo branco e escreve o novo
  texto na mesma bbox usando insert_textbox.
- Usa NotoSans (via pymupdf-fonts) em vez das fontes base14 para garantir
  cobertura Unicode completa -- elimina os "?" que surgiam com helv/hebo.
- Se o texto traduzido nao couber na bbox original, reduz o tamanho da fonte
  progressivamente ate caber ou atingir 6pt (minimo).

Estrategia anti-quebra-de-layout:
- Pintamos um retangulo branco sobre o texto antigo (draw_rect).
- Inserimos o novo texto com insert_textbox, alinhamento esquerdo.
- A bbox de escrita e ligeiramente expandida horizontalmente para absorver
  a expansao tipica de texto traduzido (Problema 1 do briefing, tratamento
  minimo; solucao completa na Fase 1).

Sobre as fontes:
- pymupdf-fonts (pip install pymupdf-fonts) fornece NotoSans com ~3246
  glifos cobrindo Latin, Cirilico, Grego, Hebraico, Arabico, CJK basico, etc.
- Registramos as 4 variantes (regular, bold, italic, bold-italic) uma vez
  por documento para evitar registros duplicados por pagina.

Problema 3:
- Adicionada write_translated_pdf_blocks() que trabalha no nivel de bloco
  (paragrafo) em vez de span. O texto traduzido do bloco inteiro e inserido
  no bbox da uniao de todos os spans do bloco, permitindo que insert_textbox
  faca a quebra de linha naturalmente -- elimina os grandes espacos vazios
  que apareciam na traducao span-a-span.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple, TYPE_CHECKING

import pymupdf

if TYPE_CHECKING:
    from .grouper import TextBlock

try:
    import pymupdf_fonts as _mf
    _FONT_BUFFERS: Dict[str, bytes] = {
        "notos":   _mf.fontbuffers["notos"],    # NotoSans Regular
        "notosbo": _mf.fontbuffers["notosbo"],  # NotoSans Bold
        "notosit": _mf.fontbuffers["notosit"],  # NotoSans Italic
        "notosbi": _mf.fontbuffers["notosbi"],  # NotoSans Bold Italic
    }
    _HAS_NOTO = True
except Exception:  # noqa: BLE001
    _FONT_BUFFERS = {}
    _HAS_NOTO = False

from .extractor import TextSpan

log = logging.getLogger(__name__)

if not _HAS_NOTO:
    log.warning(
        "pymupdf-fonts nao encontrado. Usando fontes base14 (Latin-1 apenas). "
        "Instale com: pip install pymupdf-fonts"
    )

# Nomes internos das fontes Noto registradas no documento
_NOTO_REGULAR     = "notos"
_NOTO_BOLD        = "notosbo"
_NOTO_ITALIC      = "notosit"
_NOTO_BOLD_ITALIC = "notosbi"

# Fallback base14 se pymupdf-fonts nao estiver disponivel
_BASE14 = {
    "regular":     "helv",
    "bold":        "hebo",
    "italic":      "heit",
    "bold_italic": "hebi",
}

_FONT_SIZE_CANDIDATES_RATIOS = [1.0, 0.90, 0.80, 0.70]
_FONT_SIZE_MINIMUM = 6.0
_FONT_SIZE_FINE_STEP = 0.5

# Padding interno aplicado ao lado esquerdo de cada bloco ao reescrever o texto.
# Afasta o texto da borda vertical das celulas de tabela, evitando o artefato
# cosmetico onde a linha divisora parece "cortar" a primeira letra do conteudo.
_CELL_PADDING_LEFT = 2.0


def _detect_variant(flags: int, font: str) -> str:
    """Detecta variante de fonte (regular/bold/italic/bold_italic) a partir de flags e nome."""
    fname = font.lower()
    is_bold   = bool(flags & 16) or "bold"    in fname or "-bd" in fname
    is_italic = bool(flags & 2)  or "italic"  in fname or "oblique" in fname
    if is_bold and is_italic:
        return "bold_italic"
    if is_bold:
        return "bold"
    if is_italic:
        return "italic"
    return "regular"


def _pick_font_variant(span: TextSpan) -> str:
    """Retorna o nome da variante de fonte para um TextSpan."""
    return _detect_variant(span.flags, span.font)


def _variant_to_fontname(variant: str) -> str:
    """Converte variante para o nome de fonte a usar no insert_textbox."""
    if _HAS_NOTO:
        return {
            "regular":     _NOTO_REGULAR,
            "bold":        _NOTO_BOLD,
            "italic":      _NOTO_ITALIC,
            "bold_italic": _NOTO_BOLD_ITALIC,
        }[variant]
    return _BASE14[variant]


def _int_color_to_rgb(c: int) -> Tuple[float, float, float]:
    r = ((c >> 16) & 0xFF) / 255.0
    g = ((c >> 8)  & 0xFF) / 255.0
    b = (c & 0xFF)          / 255.0
    return (r, g, b)


def _register_noto_fonts(doc: pymupdf.Document) -> None:
    """
    Pre-registra as 4 variantes NotoSans no documento uma unica vez.
    PyMuPDF deduplica automaticamente por xref; chamadas extras sao no-op.
    """
    if not _HAS_NOTO:
        return
    if len(doc) == 0:
        return
    page0 = doc[0]
    for fname, buf in _FONT_BUFFERS.items():
        try:
            page0.insert_font(fontname=fname, fontbuffer=buf)
        except Exception as e:  # noqa: BLE001
            log.debug("Nao foi possivel pre-registrar fonte %s: %s", fname, e)


def _ensure_fonts_on_page(page: pymupdf.Page) -> None:
    """Garante que as fontes Noto estao registradas na pagina dada."""
    if not _HAS_NOTO:
        return
    for fname, buf in _FONT_BUFFERS.items():
        try:
            page.insert_font(fontname=fname, fontbuffer=buf)
        except Exception:  # noqa: BLE001
            pass


def _insert_text_with_fallback(
    page: pymupdf.Page,
    draw_rect: pymupdf.Rect,
    text: str,
    fontname: str,
    font_size: float,
    color: Tuple[float, float, float],
    align: int = 0,
) -> None:
    """
    Insere texto na draw_rect reduzindo a fonte se necessario.
    Tenta os candidatos pre-definidos e depois descida fina ate _FONT_SIZE_MINIMUM.
    Sempre insere algo (forcado em _FONT_SIZE_MINIMUM como ultimo recurso).
    """
    candidates = [round(font_size * r, 1) for r in _FONT_SIZE_CANDIDATES_RATIOS]

    inserted = -1
    chosen_size = font_size

    for fs in candidates:
        if fs < _FONT_SIZE_MINIMUM:
            break
        inserted = page.insert_textbox(
            draw_rect, text,
            fontname=fontname, fontsize=fs,
            color=color, align=align, overlay=True,
        )
        if inserted >= 0:
            chosen_size = fs
            break

    # Descida fina se ainda nao coube
    if inserted < 0:
        fs = max(candidates[-1] - _FONT_SIZE_FINE_STEP, _FONT_SIZE_MINIMUM)
        while fs >= _FONT_SIZE_MINIMUM:
            inserted = page.insert_textbox(
                draw_rect, text,
                fontname=fontname, fontsize=fs,
                color=color, align=align, overlay=True,
            )
            if inserted >= 0:
                chosen_size = fs
                break
            fs -= _FONT_SIZE_FINE_STEP

    # Ultimo recurso: forcado em minimo
    if inserted < 0:
        page.insert_textbox(
            draw_rect, text,
            fontname=fontname, fontsize=_FONT_SIZE_MINIMUM,
            color=color, align=align, overlay=True,
        )
        log.warning(
            "Texto nao coube nem em %.1fpt na pagina (rect=%s): %r",
            _FONT_SIZE_MINIMUM, draw_rect, text[:60],
        )


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def write_translated_pdf(
    input_pdf: str,
    output_pdf: str,
    spans: List[TextSpan],
    translations: List[str],
) -> None:
    """
    [Legado - traducao span-a-span]
    Aplica translations[i] no lugar de spans[i].text no PDF de saida.
    Mantido para compatibilidade; prefira write_translated_pdf_blocks().
    """
    if len(spans) != len(translations):
        raise ValueError(
            f"Spans ({len(spans)}) e translations ({len(translations)}) "
            "precisam ter o mesmo tamanho."
        )

    doc = pymupdf.open(input_pdf)

    try:
        _register_noto_fonts(doc)

        by_page: dict[int, list[tuple[TextSpan, str]]] = {}
        for span, translation in zip(spans, translations):
            by_page.setdefault(span.page, []).append((span, translation))

        for page_idx, items in by_page.items():
            page = doc[page_idx]
            _ensure_fonts_on_page(page)

            # 1) Cobrir o texto original com retangulo branco
            for span, translation in items:
                if translation == span.text:
                    continue
                rect = pymupdf.Rect(span.bbox)
                rect = pymupdf.Rect(
                    rect.x0 - 0.5, rect.y0 - 0.5,
                    rect.x1 + 0.5, rect.y1 + 0.5,
                )
                page.draw_rect(rect, color=None, fill=(1, 1, 1), overlay=True)

            # 2) Escrever texto traduzido
            for span, translation in items:
                if translation == span.text:
                    continue

                rect      = pymupdf.Rect(span.bbox)
                variant   = _pick_font_variant(span)
                fontname  = _variant_to_fontname(variant)
                color     = _int_color_to_rgb(span.color)
                font_size = span.size

                page_w    = span.page_w if span.page_w > 0 else page.rect.width
                line_x1   = span.line_x1 if span.line_x1 > rect.x1 else rect.x1
                right_cap = page_w - 30
                draw_right = min(line_x1 + 5, right_cap)
                draw_right = max(draw_right, rect.x1)

                draw_rect = pymupdf.Rect(
                    rect.x0,
                    rect.y0 - 1.0,
                    draw_right,
                    rect.y1 + 2.0,
                )

                _insert_text_with_fallback(page, draw_rect, translation, fontname, font_size, color)

        doc.save(output_pdf, garbage=4, deflate=True)
    finally:
        doc.close()


def write_translated_pdf_blocks(
    input_pdf: str,
    output_pdf: str,
    blocks: "List[TextBlock]",
    translations: List[str],
) -> None:
    """
    [Problema 3] Traducao por bloco (paragrafo).

    Para cada bloco:
    1. Apaga o texto original de cada span individualmente (retangulo branco
       preciso sobre cada span, evitando apagar areas adjacentes).
    2. Escreve o texto traduzido no bbox da uniao do bloco, deixando o
       insert_textbox fazer a quebra de linha naturalmente.

    Vantagens sobre a abordagem span-a-span:
    - Eliminacao dos grandes espacos vazios entre segmentos traduzidos.
    - Traducao coerente de paragrafos inteiros (melhor qualidade linguistica).
    - Reducao de chamadas ao tradutor (um bloco = uma chamada).
    """
    if len(blocks) != len(translations):
        raise ValueError(
            f"Blocks ({len(blocks)}) e translations ({len(translations)}) "
            "precisam ter o mesmo tamanho."
        )

    doc = pymupdf.open(input_pdf)

    try:
        _register_noto_fonts(doc)

        # Agrupar por pagina
        by_page: dict[int, list] = {}
        for block, translation in zip(blocks, translations):
            by_page.setdefault(block.page, []).append((block, translation))

        for page_idx, items in sorted(by_page.items()):
            page = doc[page_idx]
            _ensure_fonts_on_page(page)

            # 1) Apagar texto original span-a-span (precisao maxima)
            for block, translation in items:
                if translation == block.text:
                    continue
                for span in block.spans:
                    rect = pymupdf.Rect(span.bbox)
                    # Pequena margem para cobrir antialiasing da fonte original
                    rect = pymupdf.Rect(
                        rect.x0 - 0.5, rect.y0 - 1.0,
                        rect.x1 + 0.5, rect.y1 + 1.0,
                    )
                    page.draw_rect(rect, color=None, fill=(1, 1, 1), overlay=True)

            # 2) Escrever texto traduzido no bbox do bloco
            for block, translation in items:
                if translation == block.text:
                    continue

                # bbox do bloco com pequena margem vertical
                bx0, by0, bx1, by1 = block.bbox
                page_w = block.page_w if block.page_w > 0 else page.rect.width

                # Cap na margem da pagina (30pt de seguranca)
                right_cap = page_w - 30.0
                bx1_safe = min(bx1, right_cap)
                bx1_safe = max(bx1_safe, bx0 + 10.0)  # largura minima de 10pt

                draw_rect = pymupdf.Rect(bx0 + _CELL_PADDING_LEFT, by0 - 1.0, bx1_safe, by1 + 2.0)

                variant  = _detect_variant(block.flags, block.font)
                fontname = _variant_to_fontname(variant)
                color    = _int_color_to_rgb(block.color)

                _insert_text_with_fallback(page, draw_rect, translation, fontname, block.size, color)

        doc.save(output_pdf, garbage=4, deflate=True)
    finally:
        doc.close()
