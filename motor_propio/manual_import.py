"""Convert manually copied bookmaker odds into ArbiiScan records, without scraping.

This module never opens a bookmaker site, reads browser sessions, or attempts
to overcome access restrictions. It labels manually entered data explicitly.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .engine import BadQuote, Quote, aware, market_outcomes

META = {"book", "sport", "home", "away", "kickoff", "market"}
MAX_SIZE = 80_000
MAX_MARKETS = 30
ODDS_LINE = re.compile(r"^(1|X|2|OVER|UNDER)\s*(?:=|:|@|\s)\s*(\d{1,3}(?:[,.]\d{1,3})?)$", re.I)


def parse_manual_text(content: str, observed_at=None) -> list[Quote]:
    """Parse human-copied odds with explicit event identity and settlement rules.

    Syntax: [market], then one key=value per line for required metadata,
    followed by selection=decimal_price. Can contain multiple [market] blocks.
    """
    if not isinstance(content, str) or len(content) > MAX_SIZE:
        raise BadQuote("Texto vacío o demasiado grande")
    lines = content.splitlines()
    blocks = []
    current = None
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower() == "[market]":
            if current is not None:
                blocks.append(current)
            current = {}
            continue
        if current is None:
            raise BadQuote("Falta el encabezado [market]")
        odds_match = ODDS_LINE.fullmatch(line)
        if odds_match:
            key, value = odds_match.groups()
            key = key.upper() if key.upper() in {"X", "OVER", "UNDER"} else key
        else:
            if "=" not in line:
                raise BadQuote("Línea no reconocida: " + str(number))
            key, value = [part.strip() for part in line.split("=", 1)]
            key = key.lower()
            if key not in META:
                raise BadQuote("Campo no permitido en línea " + str(number))
            if not value:
                raise BadQuote("Campo vacío en línea " + str(number))
        if key in current:
            raise BadQuote("Clave duplicada en línea " + str(number))
        current[key] = value
    if current is not None:
        blocks.append(current)
    if not 1 <= len(blocks) <= MAX_MARKETS:
        raise BadQuote("Se necesitan entre 1 y 30 mercados")

    timestamp = aware(observed_at or datetime.now(timezone.utc))
    result = []
    for index, data in enumerate(blocks, 1):
        if not META.issubset(data):
            raise BadQuote("Faltan datos del evento en bloque " + str(index))
        labels = market_outcomes(data["sport"], data["market"])
        if labels is None or set(data) != META | set(labels):
            raise BadQuote("Mercado, resultados o liquidación ambiguos en bloque " + str(index))
        result.append(Quote(
            book=data["book"], sport=data["sport"],
            home=data["home"], away=data["away"],
            kickoff=aware(data["kickoff"]), market=data["market"],
            prices={label: data[label] for label in labels},
            observed_at=timestamp, source="manual_observation",
        ))
    return result


def records(quotes: list[Quote]) -> list[dict]:
    return [{
        "book": q.book, "sport": q.sport, "home": q.home,
        "away": q.away, "kickoff": q.kickoff.isoformat(),
        "market": q.market, "prices": {k: str(v) for k, v in q.prices.items()},
        "observed_at": q.observed_at.isoformat(),
        "source": "manual_observation",
    } for q in quotes]


def main():
    parser = argparse.ArgumentParser(
        description="Importa cuotas COPIADAS MANUALMENTE sin consultar casas ni OddsPapi"
    )
    parser.add_argument("--input", required=True, help="Archivo de texto con [market]")
    parser.add_argument("--output", required=True, help="JSON para motor_propio.run --feed")
    args = parser.parse_args()
    if Path(args.input).resolve() == Path(args.output).resolve():
        parser.error("Entrada y salida deben ser diferentes")
    quotes = parse_manual_text(Path(args.input).read_text(encoding="utf-8"))
    Path(args.output).write_text(
        json.dumps(records(quotes), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"{len(quotes)} mercados manuales importados. Cuotas NO verificadas en directo.")


if __name__ == "__main__":
    main()
