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

# Margem aplicada apos uma borda vertical detectada (via get_drawings).
# Garante que o texto comece apos a linha divisora da tabela, nao sobre ela.
_CELL_BORDER_MARGIN = 4.0   # pt apos a borda detectada
_CELL_PADDING_LEFT  = 1.0   # fallback quando nenhuma borda e detectada nas proximidades

# Distancia maxima (pt) para associar uma borda vertical ao bloco de texto.
# Bordas dentro desse raio a esquerda de bx0 sao consideradas divisoras de celula.
_BORDER_SEARCH_LEFT  = 15.0
# Altura minima (pt) de uma linha para ser considerada borda de tabela.
_BORDER_MIN_HEIGHT   = 8.0

# Margem direita da pagina: distancia entre o final do texto traduzido e a
# borda direita da pagina. Centraliza o valor usado por todos os helpers.
_PAGE_RIGHT_MARGIN    = 30.0
# Gap visual minimo (pt) entre o texto expandido e o bloco vizinho a direita.
# Evita que o texto traduzido encoste na borda da celula vizinha em layouts
# tabulares.
_NEIGHBOR_SAFETY      = 3.0
# Sobreposicao vertical minima (pt) para considerar dois blocos "na mesma faixa
# de linha". Valores baixos podem pegar ruido de antialiasing; valores altos
# perdem linhas reais de tabela em fontes pequenas. 2pt e seguro para fontes
# 8-14pt comuns em documentos tecnicos.
_MIN_VERTICAL_OVERLAP = 2.0
# Distancia minima (pt) entre o texto traduzido e a proxima borda vertical
# detectada a direita do bloco. Usado como cap quando a celula adjacente esta
# vazia (sem TextBlock vizinho). 1pt e o suficiente para nao encostar.
_BORDER_RIGHT_MARGIN  = 1.0


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


def _get_page_vertical_lines(page: pymupdf.Page) -> list[float]:
    """
    Retorna coordenadas x de todas as linhas verticais significativas da pagina.

    Detecta dois tipos de elemento grafico:
    - Segmentos de linha ('l'): quase-verticais (|dx| < 2pt) e altos (dy >= 8pt).
    - Retangulos finos ('re'): largura < 2pt e altura >= 8pt (bordas de tabela
      frequentemente sao rects finos em vez de linhas puras).

    O resultado e uma lista ordenada de x-coords unicas (arredondadas a 0.1pt).
    Chamada uma vez por pagina durante a escrita; custo negligivel vs I/O do PDF.
    """
    v_lines: list[float] = []
    for d in page.get_drawings():
        for item in d.get("items", []):
            if item[0] == "l":                    # segmento de linha
                p1, p2 = item[1], item[2]
                if abs(p1.x - p2.x) < 2.0 and abs(p1.y - p2.y) >= _BORDER_MIN_HEIGHT:
                    v_lines.append(round((p1.x + p2.x) / 2.0, 1))
            elif item[0] == "re":                 # retangulo
                r = item[1]
                if r.width < 2.0 and r.height >= _BORDER_MIN_HEIGHT:
                    v_lines.append(round((r.x0 + r.x1) / 2.0, 1))
    return sorted(set(v_lines))


def _left_boundary(bx0: float, v_lines: list[float]) -> float:
    """
    Calcula o x de inicio de texto para um bloco, respeitando bordas verticais.

    Procura a linha vertical mais proxima A ESQUERDA de bx0 (dentro de
    _BORDER_SEARCH_LEFT pt). Se encontrada, usa border_x + _CELL_BORDER_MARGIN
    como ponto de inicio, garantindo que o texto nao sobreponha a borda.
    Se nenhuma borda for encontrada, usa bx0 + _CELL_PADDING_LEFT (minimo).

    Genericidade: funciona com qualquer PDF que use linhas ou rects finos como
    bordas de tabela — independente de tamanho de fonte, padding ou estilo.
    """
    # Candidatas: linhas dentro da janela de busca a esquerda de bx0
    # (+1pt de tolerancia a direita para pegar bordas exatamente em bx0)
    candidates = [x for x in v_lines
                  if bx0 - _BORDER_SEARCH_LEFT <= x <= bx0 + 1.0]
    if candidates:
        border_x = max(candidates)   # a mais proxima a esquerda
        return border_x + _CELL_BORDER_MARGIN
    return bx0 + _CELL_PADDING_LEFT


def _vertical_overlap(
    bbox_a: Tuple[float, float, float, float],
    bbox_b: Tuple[float, float, float, float],
) -> float:
    """
    Retorna a sobreposicao vertical entre dois bboxes em pontos.
    Zero se nao ha sobreposicao. Usado por _compute_right_cap.
    """
    overlap = min(bbox_a[3], bbox_b[3]) - max(bbox_a[1], bbox_b[1])
    return max(0.0, overlap)


def _compute_right_cap(
    block_bbox: Tuple[float, float, float, float],
    all_page_bboxes: List[Tuple[float, float, float, float]],
    page_w: float,
    v_lines: list[float] | None = None,
) -> float:
    """
    Calcula o limite direito de escrita para um bloco.

    Regra universal: nenhum bloco pode invadir (a) o espaco horizontal de outro
    bloco que esteja na mesma faixa vertical, nem (b) uma borda vertical
    detectada (linha divisora de celula de tabela). Esta heuristica NAO detecta
    'tabela', 'rodape' ou qualquer estrutura especifica do PDF — aplica-se a
    qualquer documento nativo de texto: layouts tabulares, jornais multi-coluna,
    formularios, RFQs, etc.

    Tres fontes de cap:
    1. **Vizinho TextBlock a direita** com sobreposicao vertical >=
       _MIN_VERTICAL_OVERLAP pt. Cap = neighbor.x0 - _NEIGHBOR_SAFETY.
    2. **Proxima borda vertical** detectada via _get_page_vertical_lines.
       Cap = primeira v_line > bx1, menos _BORDER_RIGHT_MARGIN. Importante
       para celulas de tabela com vizinhos VAZIOS (sem TextBlock), onde a
       borda visivel da celula e a unica pista de limite.
    3. **Margem direita da pagina**: page_w - _PAGE_RIGHT_MARGIN.

    O cap retornado e o minimo entre as fontes aplicaveis.

    Genericidade garantida:
    - Sem dependencia do conteudo dos blocos.
    - Sem hardcoding de posicao/proporcao especifica.
    - Comportamento bem definido tanto para textos corridos (sem vizinho/borda
      a direita -> margem da pagina) quanto para layouts densos.

    Args:
        block_bbox: (x0, y0, x1, y1) do bloco a escrever.
        all_page_bboxes: bboxes de TODOS os blocos da pagina. O proprio bloco
                         pode estar incluido; o helper filtra-o automaticamente
                         via condicao ox0 > bx1.
        page_w: largura total da pagina em pt.
        v_lines: lista ORDENADA de x-coords de bordas verticais da pagina,
                 como retornada por _get_page_vertical_lines. Se None ou
                 vazia, o cap por borda nao se aplica (comportamento legacy).

    Returns:
        x-coord do limite direito de escrita, sempre limitado pela margem da
        pagina.

    Custo: O(N + V) por chamada, onde N = blocos e V = bordas verticais na
    pagina. Chamado uma vez por bloco -> O(N*(N+V)) por pagina, rapido para
    PDFs reais (N tipicamente < 200, V tipicamente < 100).
    """
    bx0, by0, bx1, by1 = block_bbox
    page_right_cap = page_w - _PAGE_RIGHT_MARGIN

    # Fonte 1: vizinhos TextBlock a direita com sobreposicao vertical
    neighbor_caps: list[float] = []
    for ox0, oy0, ox1, oy1 in all_page_bboxes:
        if ox0 <= bx1:
            continue  # nao esta estritamente a direita (inclui o proprio bloco)
        overlap = min(by1, oy1) - max(by0, oy0)
        if overlap >= _MIN_VERTICAL_OVERLAP:
            neighbor_caps.append(ox0 - _NEIGHBOR_SAFETY)

    # Fonte 2: proxima borda vertical detectada a direita.
    # v_lines vem ORDENADA de _get_page_vertical_lines, entao paramos no primeiro
    # v > bx1 (o mais proximo a direita). Cobre o caso de celulas vizinhas vazias
    # (sem TextBlock) onde so a borda visivel sinaliza o limite.
    border_cap: float | None = None
    if v_lines:
        for v in v_lines:
            if v > bx1:
                border_cap = v - _BORDER_RIGHT_MARGIN
                break

    # Cap final = min entre todas as fontes aplicaveis
    candidates = [page_right_cap]
    if neighbor_caps:
        candidates.append(min(neighbor_caps))
    if border_cap is not None:
        candidates.append(border_cap)
    return min(candidates)


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
                right_cap = page_w - _PAGE_RIGHT_MARGIN
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

    [Problema 4] Right-cap dinamico por vizinhos:
    O bbox de escrita expande horizontalmente apenas ate _NEIGHBOR_SAFETY pt
    antes do bloco vizinho a direita que compartilhe faixa vertical. Sem
    detectar 'tabela' especificamente -- aplica-se a qualquer PDF nativo:
    layouts tabulares, multi-coluna, formularios, RFQs.
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

            # Pre-calcular linhas verticais da pagina (bordas de tabela)
            v_lines = _get_page_vertical_lines(page)

            # 1) Apagar texto original span-a-span (precisao maxima)
            for block, translation in items:
                if translation == block.text:
                    continue
                for span in block.spans:
                    rect = pymupdf.Rect(span.bbox)
                    rect = pymupdf.Rect(
                        rect.x0 - 0.5, rect.y0 - 1.0,
                        rect.x1 + 0.5, rect.y1 + 1.0,
                    )
                    page.draw_rect(rect, color=None, fill=(1, 1, 1), overlay=True)

            # 2) Escrever texto traduzido no bbox do bloco
            # Pre-calcular bboxes de todos os blocos da pagina (uma unica vez)
            # para o calculo de right_cap. Evita recomputar lista em cada
            # iteracao do loop interno.
            page_block_bboxes = [b.bbox for b, _ in items]

            for block, translation in items:
                if translation == block.text:
                    continue

                bx0, by0, bx1, by1 = block.bbox
                page_w = block.page_w if block.page_w > 0 else page.rect.width

                # Limite direito generico: respeita (a) vizinhos TextBlock no
                # mesmo y e (b) a proxima borda vertical detectada a direita
                # (cobre celulas de tabela com vizinhos vazios). Aplica-se a
                # qualquer PDF nativo.
                right_cap = _compute_right_cap(
                    block.bbox, page_block_bboxes, page_w, v_lines
                )

                # Politica: nunca reduzir abaixo do bx1 original (preserva
                # layouts onde o bloco original ja era largo). Permite
                # expansao ate o cap calculado, respeitando margem da pagina.
                bx1_safe = bx1
                if right_cap > bx1:
                    bx1_safe = min(right_cap, page_w - _PAGE_RIGHT_MARGIN)
                bx1_safe = max(bx1_safe, bx0 + 10.0)  # largura minima de 10pt

                # Posicionamento horizontal: respeita bordas de tabela detectadas
                left_start = _left_boundary(bx0, v_lines)
                draw_rect = pymupdf.Rect(left_start, by0 - 1.0, bx1_safe, by1 + 2.0)

                variant  = _detect_variant(block.flags, block.font)
                fontname = _variant_to_fontname(variant)
                color    = _int_color_to_rgb(block.color)

                _insert_text_with_fallback(page, draw_rect, translation, fontname, block.size, color)

        doc.save(output_pdf, garbage=4, deflate=True)
    finally:
        doc.close()
