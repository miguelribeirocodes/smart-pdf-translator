"""
Testes da deteccao de celulas por bordas verticais (Sessao #10).

Valida que _split_by_columns separa spans em sub-blocos quando ha uma borda
vertical entre eles, mesmo quando o gap horizontal e pequeno demais para o
threshold tradicional.

Genericidade: os casos abaixo simulam layouts arbitrarios via spans sinteticos.
Se algum quebrar, qualquer PDF real com layout similar vai quebrar tambem.
"""
from __future__ import annotations

from src.extractor import TextSpan
from src.grouper import _split_by_columns, group_into_blocks, _COLUMN_GAP_RATIO


def _span(text: str, x0: float, x1: float, y0: float = 100.0, y1: float = 110.0,
          page: int = 0, block: int = 0, line: int = 0, span: int = 0,
          size: float = 9.0) -> TextSpan:
    """Constroi um TextSpan sintetico para testes."""
    return TextSpan(
        page=page, block=block, line=line, span=span,
        text=text, bbox=(x0, y0, x1, y1),
        font="Arial", size=size, color=0, flags=0,
    )


# =============================================================================
# Compatibilidade legacy (sem v_lines)
# =============================================================================

def test_legacy_no_v_lines_preserves_behavior() -> None:
    """Sem v_lines, comportamento atual: split so por gap horizontal."""
    spans = [
        _span("A", 50, 100),
        _span("B", 105, 150),  # gap 5pt, muito pequeno
    ]
    # Sem v_lines -> nao divide
    groups = _split_by_columns(spans)
    assert len(groups) == 1


def test_legacy_large_gap_still_splits() -> None:
    """Gap grande continua dividindo mesmo sem v_lines."""
    spans = [
        _span("A", 50, 100, size=10),    # gap_threshold = 15
        _span("B", 120, 200, size=10),   # gap 20 > 15
    ]
    groups = _split_by_columns(spans)
    assert len(groups) == 2


# =============================================================================
# Sessao #10 - sinal por borda vertical
# =============================================================================

def test_border_in_small_gap_triggers_split() -> None:
    """Borda no meio do gap pequeno -> split."""
    spans = [
        _span("A", 50, 100, size=9),    # gap_threshold = 13.5
        _span("B", 110, 200, size=9),   # gap 10pt < threshold
    ]
    # Sem v_lines: nao divide
    assert len(_split_by_columns(spans)) == 1
    # Com v_lines contendo borda em 105 (entre 100 e 110): DIVIDE
    assert len(_split_by_columns(spans, v_lines=[105.0])) == 2


def test_border_outside_gap_does_not_trigger_split() -> None:
    """Borda fora do gap (a esquerda do prev ou a direita do curr) nao conta."""
    spans = [
        _span("A", 50, 100, size=9),
        _span("B", 110, 200, size=9),
    ]
    # Borda em 50 (na esquerda do A) -> nao divide
    assert len(_split_by_columns(spans, v_lines=[50.0])) == 1
    # Borda em 200 (no fim do B) -> nao divide
    assert len(_split_by_columns(spans, v_lines=[200.0])) == 1
    # Borda em 300 (depois de tudo) -> nao divide
    assert len(_split_by_columns(spans, v_lines=[300.0])) == 1


def test_border_at_gap_edge_is_strict() -> None:
    """Bordas exatamente em prev.x1 ou curr.x0 nao contam (estritamente entre)."""
    spans = [
        _span("A", 50, 100, size=9),
        _span("B", 110, 200, size=9),
    ]
    # Borda em 100 (= prev.x1): nao conta (estritamente >)
    assert len(_split_by_columns(spans, v_lines=[100.0])) == 1
    # Borda em 110 (= curr.x0): nao conta (estritamente <)
    assert len(_split_by_columns(spans, v_lines=[110.0])) == 1
    # Borda em 100.1: conta
    assert len(_split_by_columns(spans, v_lines=[100.1])) == 2


def test_afry_distribution_case_reproduces() -> None:
    """Caso real do RFQ Novo Nordisk (Bloco 32 da capa, document_pdf (1).pdf).

    Spans: 'Distribution:' x=[151.3, 199.1], 'Novo Nordisk - E' x=[211.6, 274.4],
    'AFRY BR - E' x=[284.8, 328.5]. Gaps: 12.5 e 10.4 < threshold 13.5.
    Bordas detectadas em 206.5, 277.4 (entre os spans). Esperado: 3 sub-blocos.
    """
    spans = [
        _span("Distribution: ", 151.3, 199.1, size=9),
        _span("Novo Nordisk - E ", 211.6, 274.4, size=9, line=1),
        _span("AFRY BR - E ", 284.8, 328.5, size=9, line=2),
    ]
    v_lines = [206.5, 277.4, 334.1]
    # Sem v_lines: 1 bloco (problema reportado)
    assert len(_split_by_columns(spans)) == 1
    # Com v_lines: 3 sub-blocos
    groups = _split_by_columns(spans, v_lines=v_lines)
    assert len(groups) == 3
    assert groups[0][0].text.strip() == "Distribution:"
    assert groups[1][0].text.strip() == "Novo Nordisk - E"
    assert groups[2][0].text.strip() == "AFRY BR - E"


def test_paragraph_with_borders_not_split() -> None:
    """Spans em y distintos (paragrafo multi-linha) nao sao divididos mesmo
    com bordas na pagina."""
    spans = [
        _span("Linha 1", 50, 200, y0=100, y1=110),
        _span("Linha 2", 50, 200, y0=115, y1=125),  # y distinta
    ]
    # Mesmo com borda em 100 (entre 50 e 200), nao divide porque y e diferente
    assert len(_split_by_columns(spans, v_lines=[100.0])) == 1


def test_group_into_blocks_propagates_v_lines() -> None:
    """group_into_blocks repassa v_lines_by_page corretamente."""
    spans = [
        _span("A", 50, 100, page=0, block=5, size=9),
        _span("B", 110, 200, page=0, block=5, line=1, size=9),
    ]
    # Sem v_lines_by_page: 1 bloco
    blocks = group_into_blocks(spans)
    assert len(blocks) == 1
    # Com v_lines_by_page contendo borda na pagina 0: 2 blocos
    blocks = group_into_blocks(spans, v_lines_by_page={0: [105.0]})
    assert len(blocks) == 2


def test_group_into_blocks_v_lines_per_page_isolated() -> None:
    """Bordas de uma pagina nao afetam outra."""
    spans = [
        _span("A1", 50, 100, page=0, block=1, size=9),
        _span("A2", 110, 200, page=0, block=1, line=1, size=9),
        _span("B1", 50, 100, page=1, block=1, size=9),
        _span("B2", 110, 200, page=1, block=1, line=1, size=9),
    ]
    # Borda so na pagina 0: pagina 1 nao deve dividir
    blocks = group_into_blocks(spans, v_lines_by_page={0: [105.0]})
    by_page = {}
    for b in blocks:
        by_page.setdefault(b.page, []).append(b)
    assert len(by_page[0]) == 2  # pagina 0 dividida
    assert len(by_page[1]) == 1  # pagina 1 nao dividida
