"""
Testes do right-cap dinamico em writer.py (Problema 4).

Valida que _compute_right_cap aplica a regra universal:
"nenhum bloco invade o espaco horizontal de outro bloco no mesmo y".

Genericidade: os casos abaixo simulam layouts arbitrarios via bboxes -- nao
dependem de PDFs especificos. Se algum desses casos quebrar, qualquer PDF
real com layout similar vai quebrar tambem.
"""
from __future__ import annotations

from src.writer import (
    _compute_right_cap,
    _vertical_overlap,
    _NEIGHBOR_SAFETY,
    _PAGE_RIGHT_MARGIN,
    _MIN_VERTICAL_OVERLAP,
)


PAGE_W = 595.0   # A4 em pt
EXPECTED_PAGE_CAP = PAGE_W - _PAGE_RIGHT_MARGIN  # 565.0


def test_vertical_overlap_zero_when_disjoint() -> None:
    assert _vertical_overlap((0, 0, 100, 50), (0, 60, 100, 100)) == 0.0


def test_vertical_overlap_positive_when_intersecting() -> None:
    ov = _vertical_overlap((0, 100, 100, 200), (0, 150, 100, 250))
    assert ov == 50.0


def test_isolated_block_uses_page_margin() -> None:
    """Sem vizinhos a direita -> cap e a margem da pagina."""
    block = (50.0, 100.0, 200.0, 120.0)
    cap = _compute_right_cap(block, [block], PAGE_W)
    assert cap == EXPECTED_PAGE_CAP


def test_right_neighbor_same_y_restricts_cap() -> None:
    """Tabela com 2 colunas no mesmo y: cap do esquerdo = neighbor.x0 - safety."""
    left  = (50.0, 100.0, 200.0, 120.0)
    right = (250.0, 100.0, 400.0, 120.0)
    cap = _compute_right_cap(left, [left, right], PAGE_W)
    assert cap == 250.0 - _NEIGHBOR_SAFETY


def test_right_neighbor_different_y_does_not_restrict() -> None:
    """Bloco abaixo (sem sobreposicao vertical) nao restringe cap."""
    block_top    = (50.0,  100.0, 200.0, 120.0)
    block_bottom = (250.0, 200.0, 400.0, 220.0)
    cap = _compute_right_cap(block_top, [block_top, block_bottom], PAGE_W)
    assert cap == EXPECTED_PAGE_CAP


def test_block_to_the_left_does_not_restrict() -> None:
    """Vizinho a esquerda nao limita cap (so vizinhos a direita)."""
    left   = (50.0,  100.0, 200.0, 120.0)
    middle = (250.0, 100.0, 400.0, 120.0)
    cap = _compute_right_cap(middle, [left, middle], PAGE_W)
    assert cap == EXPECTED_PAGE_CAP


def test_multiple_right_neighbors_picks_closest() -> None:
    """Com varios vizinhos a direita, o cap e o do mais proximo."""
    block  = (50.0,  100.0, 200.0, 120.0)
    near   = (220.0, 100.0, 300.0, 120.0)   # mais proximo
    far    = (450.0, 100.0, 550.0, 120.0)
    cap = _compute_right_cap(block, [block, near, far], PAGE_W)
    assert cap == 220.0 - _NEIGHBOR_SAFETY


def test_partial_vertical_overlap_above_threshold_restricts() -> None:
    """Sobreposicao parcial maior que threshold -> vizinho conta."""
    block = (50.0, 100.0, 200.0, 130.0)            # altura 30
    other = (250.0, 120.0, 400.0, 145.0)           # sobreposicao 10pt (> 2pt)
    cap = _compute_right_cap(block, [block, other], PAGE_W)
    assert cap == 250.0 - _NEIGHBOR_SAFETY


def test_negligible_vertical_overlap_does_not_restrict() -> None:
    """Sobreposicao < _MIN_VERTICAL_OVERLAP -> ignorada como ruido."""
    # Bloco vai ate y=120; outro comeca em y=119 (sobreposicao 1pt < 2pt)
    block = (50.0,  100.0, 200.0, 120.0)
    other = (250.0, 119.0, 400.0, 140.0)
    cap = _compute_right_cap(block, [block, other], PAGE_W)
    assert cap == EXPECTED_PAGE_CAP


def test_neighbor_cap_capped_by_page_margin() -> None:
    """Se vizinho esta alem da margem da pagina, cap usa a margem."""
    block = (50.0,  100.0, 200.0, 120.0)
    # Vizinho impossivelmente longe -> cap nao deve exceder margem da pagina
    far_neighbor = (580.0, 100.0, 590.0, 120.0)
    cap = _compute_right_cap(block, [block, far_neighbor], PAGE_W)
    # 580 - 3 = 577, mas margem da pagina = 565 -> deve ficar em 565
    assert cap == EXPECTED_PAGE_CAP


def test_table_row_three_columns_each_capped_correctly() -> None:
    """Linha de tabela com 3 colunas: cada bloco respeita o vizinho seguinte."""
    col1 = (50.0,  100.0, 150.0, 120.0)
    col2 = (170.0, 100.0, 300.0, 120.0)
    col3 = (320.0, 100.0, 500.0, 120.0)
    all_blocks = [col1, col2, col3]

    cap1 = _compute_right_cap(col1, all_blocks, PAGE_W)
    cap2 = _compute_right_cap(col2, all_blocks, PAGE_W)
    cap3 = _compute_right_cap(col3, all_blocks, PAGE_W)

    assert cap1 == 170.0 - _NEIGHBOR_SAFETY  # limitado por col2
    assert cap2 == 320.0 - _NEIGHBOR_SAFETY  # limitado por col3
    assert cap3 == EXPECTED_PAGE_CAP          # ultima coluna -> margem


# =============================================================================
# Sessao #9: cap por bordas verticais (refinamento do right-cap)
# =============================================================================

from src.writer import _BORDER_RIGHT_MARGIN


def test_legacy_call_without_v_lines_works() -> None:
    """Compatibilidade: chamadas sem v_lines mantem comportamento anterior."""
    block = (50.0, 100.0, 200.0, 120.0)
    # Sem v_lines (None ou ausente) -> equivale ao comportamento legacy
    cap = _compute_right_cap(block, [block], PAGE_W)
    assert cap == EXPECTED_PAGE_CAP


def test_v_lines_empty_does_not_restrict() -> None:
    """Lista vazia de bordas nao restringe (legacy behavior)."""
    block = (50.0, 100.0, 200.0, 120.0)
    cap = _compute_right_cap(block, [block], PAGE_W, v_lines=[])
    assert cap == EXPECTED_PAGE_CAP


def test_vertical_border_right_caps_when_no_neighbor() -> None:
    """Bloco isolado mas com borda vertical a direita: cap pela borda."""
    block = (50.0, 100.0, 200.0, 120.0)
    v_lines = [25.0, 220.0, 400.0]  # 25 a esquerda, 220 a direita do bx1
    cap = _compute_right_cap(block, [block], PAGE_W, v_lines=v_lines)
    # 220 - 1 = 219, mais restritivo que page_cap (565) e nao ha vizinho
    assert cap == 220.0 - _BORDER_RIGHT_MARGIN


def test_vertical_border_to_left_ignored() -> None:
    """Borda a esquerda do bloco nao restringe."""
    block = (50.0, 100.0, 200.0, 120.0)
    v_lines = [10.0, 25.0, 49.0]  # todas a esquerda do bx0=50
    cap = _compute_right_cap(block, [block], PAGE_W, v_lines=v_lines)
    assert cap == EXPECTED_PAGE_CAP


def test_closest_vertical_border_wins() -> None:
    """Com multiplas bordas a direita, pega a mais proxima."""
    block = (50.0, 100.0, 200.0, 120.0)
    v_lines = [220.0, 300.0, 400.0]
    cap = _compute_right_cap(block, [block], PAGE_W, v_lines=v_lines)
    assert cap == 220.0 - _BORDER_RIGHT_MARGIN


def test_neighbor_and_border_picks_min() -> None:
    """Cap final = min(neighbor_cap, border_cap, page_cap)."""
    block    = (50.0,  100.0, 200.0, 120.0)
    neighbor = (260.0, 100.0, 400.0, 120.0)   # neighbor cap = 260 - 3 = 257
    v_lines  = [240.0]                          # border cap   = 240 - 1 = 239
    cap = _compute_right_cap(block, [block, neighbor], PAGE_W, v_lines=v_lines)
    assert cap == 240.0 - _BORDER_RIGHT_MARGIN  # borda e mais restritiva


def test_neighbor_more_restrictive_than_border_wins() -> None:
    """Quando vizinho e mais proximo que borda, vence o vizinho."""
    block    = (50.0,  100.0, 200.0, 120.0)
    neighbor = (215.0, 100.0, 400.0, 120.0)   # neighbor cap = 215 - 3 = 212
    v_lines  = [260.0]                          # border cap   = 260 - 1 = 259
    cap = _compute_right_cap(block, [block, neighbor], PAGE_W, v_lines=v_lines)
    assert cap == 215.0 - _NEIGHBOR_SAFETY


def test_empty_cell_scenario_afry_table() -> None:
    """Caso real: 'Documento Afry' com 4 celulas vazias a direita.

    No PDF original, ha bordas verticais separando as celulas mesmo quando
    elas estao vazias. Antes do refinamento, o texto invadia ate a margem
    da pagina. Agora, com v_lines, o cap fica na primeira borda a direita.
    """
    # Simula: bloco 'Documento Afry' em x=[150, 250], com bordas em 320, 400,
    # 480, 540 (4 celulas vazias subsequentes)
    block = (150.0, 100.0, 250.0, 120.0)
    v_lines = [100.0, 320.0, 400.0, 480.0, 540.0]
    cap = _compute_right_cap(block, [block], PAGE_W, v_lines=v_lines)
    assert cap == 320.0 - _BORDER_RIGHT_MARGIN  # pega a primeira (mais proxima)
