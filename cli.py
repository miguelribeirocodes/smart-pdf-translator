"""
CLI: tradutor de PDF via linha de comando.

Uso:
    python cli.py input.pdf -o output.pdf --from en --to pt
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.pipeline import translate_pdf
from src.translator import SUPPORTED_LANGUAGES


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tradutor de PDF com preservacao de layout (Fase 0)."
    )
    parser.add_argument("input", help="PDF de entrada.")
    parser.add_argument(
        "-o", "--output",
        help="PDF de saida (default: input_<lang>.pdf).",
        default=None,
    )
    parser.add_argument(
        "--from", dest="source", default="en",
        help=f"Idioma de origem. Opcoes: {', '.join(SUPPORTED_LANGUAGES)}",
    )
    parser.add_argument(
        "--to", dest="target", default="pt",
        help=f"Idioma de destino. Opcoes: {', '.join(SUPPORTED_LANGUAGES)}",
    )
    parser.add_argument(
        "--provider", default="google", choices=["google", "mymemory"],
        help="Provider de traducao (default: google).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Logs detalhados.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Arquivo nao encontrado: {input_path}", file=sys.stderr)
        return 1

    output_path = Path(args.output) if args.output else input_path.with_name(
        f"{input_path.stem}_{args.target}.pdf"
    )

    def progress(stage: str, pct: float) -> None:
        print(f"[{pct:5.1f}%] {stage}")

    result = translate_pdf(
        input_pdf=str(input_path),
        output_pdf=str(output_path),
        source_lang=args.source,
        target_lang=args.target,
        provider=args.provider,
        on_progress=progress,
    )

    print()
    print(f"OK -> {output_path}")
    print(f"  Paginas:        {result.page_count}")
    print(f"  Spans:          {result.span_count}")
    print(f"  Cache hits:     {result.cache_hits}")
    print(f"  Falhas:         {result.failed_spans}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
