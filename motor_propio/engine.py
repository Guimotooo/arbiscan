"""ArbiiScan: motor independiente, sin dependencias para comparar cuotas.

No considera 'cuota vista en una API' prueba de disponibilidad en el cupón.
Las reglas de mercado, el partido y las cuotas deben corresponder exactamente.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR
from itertools import product
from typing import Mapping

# No se cruza un 1X2 de 90 minutos con un ganador que incluya prórroga.
# El parámetro de reglas es obligatorio: los retiros en tenis, por ejemplo,
# pueden liquidarse de manera distinta según operador.
MARKETS = {
    ("soccer", "1x2:regulation"): ("1", "X", "2"),
    ("basketball", "winner:including_ot"): ("1", "2"),
    ("american_football", "winner:including_ot"): ("1", "2"),
    ("tennis", "winner:completed_match"): ("1", "2"),
    ("tennis", "winner:retirement_counts"): ("1", "2"),
}
CENT = Decimal("0.01")
MIN_ROI = Decimal("0.5")
MAX_QUOTE_AGE_SECONDS = 180
MIN_KICKOFF_LEAD_SECONDS = 900
MAX_START_DISCREPANCY_SECONDS = 120

class BadQuote(ValueError):
    """No se debe calcular ni enviar alerta con este dato."""


def aware(value) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            raise BadQuote("Fecha ISO no válida") from None
    if result.tzinfo is None:
        raise BadQuote("Falta la zona horaria")
    return result.astimezone(timezone.utc)


def token(value):
    normalized = unicodedata.normalize("NFKD", str(value).casefold())
    ascii_name = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_name).split())


def decimal_odds(value) -> Decimal:
    # Rechaza 2/1, 1.000, 2.0x, HTML, NaN/Infinity y los miles.
    if isinstance(value, bool):
        raise BadQuote("Cuota booleana")
    s = str(value).strip()
    if not re.fullmatch(r"\d{1,3}(?:[.,]\d{1,3})?", s):
        raise BadQuote("Formato de cuota dudoso")
    price = Decimal(s.replace(",", "."))
    if not Decimal("1.01") <= price < Decimal("1000"):
        raise BadQuote("Cuota fuera de rango")
    return price


@dataclass(frozen=True)
class Quote:
    book: str
    sport: str
    home: str
    away: str
    kickoff: datetime
    market: str
    prices: Mapping[str, Decimal]
    observed_at: datetime
    source: str
    url: str = ""
    provider_updated_at: datetime | None = None

    def __post_init__(self):
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,64}", self.book):
            raise BadQuote("Identificador de casa inválido")
        expected = MARKETS.get((self.sport, self.market))
        if not expected:
            raise BadQuote("Mercado, deporte o reglas de liquidación no validados")
        if not 2 <= len(token(self.home)) <= 90 or not 2 <= len(token(self.away)) <= 90:
            raise BadQuote("Equipos sin identificar")
        if token(self.home) == token(self.away):
            raise BadQuote("Equipo local y visitante iguales")
        start = aware(self.kickoff)
        observed = aware(self.observed_at)
        object.__setattr__(self, "kickoff", start)
        object.__setattr__(self, "observed_at", observed)
        if self.provider_updated_at is not None:
            object.__setattr__(self, "provider_updated_at", aware(self.provider_updated_at))
        if set(self.prices) != set(expected):
            raise BadQuote("No se conocen todos los resultados del mismo mercado")
        clean = {name: decimal_odds(self.prices[name]) for name in expected}
        object.__setattr__(self, "prices", clean)
        if self.source not in ("licensed_feed", "permitted_web", "fixture_test"):
            raise BadQuote("Fuente no identificada")

    @property
    def group(self):
        return (self.sport,token(self.home),token(self.away),self.market)

    def valid_at(self, now=None):
        now = aware(now or datetime.now(timezone.utc))
        age = (now - self.observed_at).total_seconds()
        lead = (self.kickoff-now).total_seconds()
        if not (0 <= age <= MAX_QUOTE_AGE_SECONDS and lead > MIN_KICKOFF_LEAD_SECONDS):
            return False
        if self.provider_updated_at:
            # Un updatedAt antiguo no demuestra que la cuota individual sea
            # antigua, pero para las alertas falla cerrado.
            age_of_feed = (now-self.provider_updated_at).total_seconds()
            if not (0 <= age_of_feed <= 3600):
                return False
        return True


def from_record(record: dict) -> Quote:
    if not isinstance(record, dict):
        raise BadQuote("El registro debe ser un objeto")
    required = ("book","sport","home","away","kickoff","market","prices","observed_at","source")
    if any(field not in record for field in required):
        raise BadQuote("Faltan campos obligatorios")
    return Quote(
        book=str(record["book"]),sport=str(record["sport"]),
        home=str(record["home"]),away=str(record["away"]),
        kickoff=aware(record["kickoff"]),market=str(record["market"]),
        prices=record["prices"],observed_at=aware(record["observed_at"]),
        source=str(record["source"]),url=str(record.get("url") or ""),
        provider_updated_at=(aware(record["provider_updated_at"])
                             if record.get("provider_updated_at") else None),
    )


def _stakes(bankroll: Decimal, selected: list[tuple[Quote,str]]):
    prices = [q.prices[outcome] for q,outcome in selected]
    denominator = sum((Decimal(1)/p for p in prices),Decimal(0))
    if denominator >= Decimal(1):
        return None
    cents = int((bankroll/CENT).to_integral_value())
    exact = [(Decimal(cents)/p)/denominator for p in prices]
    floors = [int(x.to_integral_value(rounding=ROUND_FLOOR)) for x in exact]
    remaining = cents - sum(floors)
    order = sorted(range(len(exact)),key=lambda i: exact[i]-Decimal(floors[i]),reverse=True)
    for i in order[:remaining]:
        floors[i] += 1
    amounts=[Decimal(c)*CENT for c in floors]
    worst = min((stake*price for stake,price in zip(amounts,prices)))
    profit = worst-bankroll
    roi = (profit/bankroll)*Decimal(100)
    if profit<=0 or roi<MIN_ROI:
        return None
    return amounts, profit.quantize(CENT,rounding=ROUND_FLOOR),roi


def opportunities(quotes: list[Quote], now=None, bankroll=Decimal("100.00")):
    """Busca alternativas por parejas/tríos de casas, no solo la más rentable."""
    now = aware(now or datetime.now(timezone.utc))
    bankroll = Decimal(str(bankroll))
    if bankroll<=0 or bankroll>Decimal("100000"):
        raise ValueError("Capital fuera de rango")
    groups={}
    for q in quotes:
        if not q.valid_at(now):
            continue
        groups.setdefault(q.group,[]).append(q)
    found=[]
    for key, items in groups.items():
        # El horario puede diferir varios minutos por errores de proveedor;
        # nunca agrupamos partidos ambiguos por fechas distintas.
        items=sorted(items,key=lambda q:q.kickoff)
        for base in items:
            matched=[q for q in items if
                     abs((q.kickoff-base.kickoff).total_seconds())<=MAX_START_DISCREPANCY_SECONDS]
            if len({q.book for q in matched})<2:
                continue
            # Rechaza múltiples cuotas ambiguas de la misma casa/mercado.
            if len({q.book for q in matched}) != len(matched):
                continue
            labels = MARKETS[(base.sport,base.market)]
            best_by_books={}
            for selection in product(matched,repeat=len(labels)):
                distinct=frozenset(q.book for q in selection)
                if len(distinct)<2:
                    continue
                chosen=list(zip(selection,labels))
                result=_stakes(bankroll,chosen)
                if result is None:
                    continue
                stakes,profit,roi=result
                previous=best_by_books.get(distinct)
                if previous and previous["profit"]>=profit:
                    continue
                offers=[{"book":q.book,"outcome":label,"price":str(q.prices[label]),
                         "stake":str(stake),"source":q.source}
                        for (q,label),stake in zip(chosen,stakes)]
                best_by_books[distinct]={
                    "sport":base.sport,"home":base.home,"away":base.away,
                    "kickoff":base.kickoff.isoformat(),"market":base.market,
                    "books":sorted(distinct),"offers":offers,
                    "bankroll":str(bankroll),"profit":str(profit),
                    "roi_percent":str(roi.quantize(Decimal("0.001"))),
                    "source_urls":sorted({q.url for q in selection if q.url}),
                }
            found.extend(best_by_books.values())
    unique={}
    for candidate in found:
        identity=(candidate["sport"],token(candidate["home"]),token(candidate["away"]),
                  candidate["kickoff"],candidate["market"],tuple(candidate["books"]))
        existing=unique.get(identity)
        if existing is None or Decimal(candidate["profit"])>Decimal(existing["profit"]):
            unique[identity]=candidate
    return sorted(unique.values(),key=lambda x:Decimal(x["profit"]),reverse=True)


def _signature(candidate):
    return (candidate["sport"],token(candidate["home"]),token(candidate["away"]),
            candidate["kickoff"],candidate["market"],
            tuple((v["book"],v["outcome"],v["price"]) for v in candidate["offers"]))


def confirm(first: list[dict], second: list[dict], first_time, second_time):
    """Confirma dos lecturas de fuentes hechas en momentos distintos."""
    before,after=aware(first_time),aware(second_time)
    if not 2 <= (after-before).total_seconds() <= 180:
        raise BadQuote("La comprobación debe ser independiente y reciente")
    acceptable={_signature(v) for v in second}
    return [item for item in first if _signature(item) in acceptable]


def fingerprint(candidate):
    # Se deduplica por evento + mercado + casas; no se repite cada cuota distinta.
    identity={k:candidate[k] for k in ("sport","home","away","kickoff","market","books")}
    return "scrape:"+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24]


def alert(candidate):
    lines=[
        "ARBIISCAN | POSIBLE ARBITRAJE (SIN CONFIRMAR)",
        candidate["sport"]+": "+candidate["home"]+" vs "+candidate["away"],
        "Inicio: "+candidate["kickoff"],
        "Mercado/reglas: "+candidate["market"],
        "Capital ilustrativo: "+candidate["bankroll"]+" €",
    ]
    for item in candidate["offers"]:
        lines.append(item["book"]+" | "+item["outcome"]+
                     " @ "+item["price"]+" | "+item["stake"]+" €")
    lines.extend([
        "Beneficio mínimo matemático aproximado: "+candidate["profit"]+
        " € ("+candidate["roi_percent"]+" %).",
        "No es una apuesta garantizada: verifica precios en el cupón, reglas, límites y disponibilidad.",
    ])
    return "\n".join(lines)
