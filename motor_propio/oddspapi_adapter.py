"""Puente entre OddsPapi autorizado y el motor propio de ArbiiScan.

Independiente de cómo se hayan recogido las cuotas en origen.
No scrapea bet365.es; utiliza un proveedor con permisos contractuales.
"""
from __future__ import annotations

from datetime import datetime, timezone
from .engine import BadQuote, Quote, aware

# Markets/order verified in OddsPapi /v4/markets, 21 Oct 2026.
# "moneyline" settlement conditions differ: include them only after validating
# their rules against bookmaker rules. Soccer 1X2 regulation is unambiguous.
SPORT_SPEC = {
    10: ("soccer","101",{"101":"1","102":"X","103":"2"},"1x2:regulation"),
    11: ("basketball","111",{"111":"1","112":"2"},"winner:including_ot"),
    12: ("tennis","121",{"121":"1","122":"2"},"winner:completed_match"),
    14: ("american_football","141",{"141":"1","142":"2"},"winner:including_ot"),
}
REQUIRES_SETTLEMENT_CONFIRMATION = {11,12,14}


def convert_fixture(fixture: dict, observed_at=None, confirm_settlement=None):
    if not isinstance(fixture,dict) or fixture.get("statusId")!=0:
        return []
    sport=SPORT_SPEC.get(fixture.get("sportId"))
    if not sport:
        return []
    sport_id=fixture["sportId"]
    if sport_id in REQUIRES_SETTLEMENT_CONFIRMATION and sport_id not in (confirm_settlement or set()):
        # La equivalencia de "winner" con y sin OT, y retiradas de tenis,
        # no se puede inferir del nombre genérico del mercado.
        return []
    sport_name,market_id,outcome_names,settlement=sport
    books=fixture.get("bookmakerOdds")
    if not isinstance(books,dict):
        return []
    now=aware(observed_at or datetime.now(timezone.utc))
    try:
        fixture_updated=aware(fixture["updatedAt"]) if fixture.get("updatedAt") else None
        start=aware(fixture["startTime"])
    except BadQuote:
        return []
    result=[]
    for slug,book in books.items():
        if not isinstance(book,dict) or book.get("bookmakerIsActive") is not True or book.get("suspended") is not False:
            continue
        market=(book.get("markets") or {}).get(market_id)
        if not isinstance(market,dict) or market.get("marketActive") is not True:
            continue
        raw=market.get("outcomes")
        if not isinstance(raw,dict):
            continue
        prices={}
        valid=True
        for key,label in outcome_names.items():
            row=raw.get(key)
            item=((row or {}).get("players") or {}).get("0") if isinstance(row,dict) else None
            if not isinstance(item,dict) or item.get("active") is not True:
                valid=False
                break
            try:
                change_at=aware(item["changedAt"])
                change_age=(now-change_at).total_seconds()
                if not 0<=change_age<=7*86400:
                    valid=False
                    break
                prices[label]=item["price"]
            except (BadQuote,KeyError):
                valid=False
                break
        if not valid:
            continue
        try:
            result.append(Quote(
                book=slug,sport=sport_name,
                home=str(fixture.get("participant1Name") or ""),
                away=str(fixture.get("participant2Name") or ""),
                kickoff=start,market=settlement,prices=prices,
                observed_at=now,provider_updated_at=fixture_updated,
                source="licensed_feed",
            ))
        except BadQuote:
            continue
    return result


def convert_fixtures(rows, observed_at=None, confirm_settlement=None):
    if isinstance(rows,dict):
        rows=rows.get("data")
    if not isinstance(rows,list):
        raise BadQuote("La respuesta del proveedor no contiene una lista")
    results=[]
    for fixture in rows:
        results.extend(convert_fixture(fixture,observed_at,confirm_settlement))
    return results
