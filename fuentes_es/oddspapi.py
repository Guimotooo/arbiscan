"""ArbiiScan: consulta OddsPapi v4 de Bet365 ES y Winamax ES.
Solo 1X2 de fútbol prepartido. Fallo cerrado. No coloca apuestas.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

from scanner import allocate, send_telegram

BASE = "https://api.oddspapi.io/v4"
BOOKS = ("bet365.es", "winamax.es")
OUTCOMES = {"101": "1", "102": "X", "103": "2"}
MARKET_ID = "101"  # 1X2 fulltime fútbol (OddsPapi /v4/markets)
MAX_FIXTURE_UPDATE_AGE_SECONDS = 3600
MAX_PRICE_CHANGE_AGE_SECONDS = 7 * 86400
MIN_LEAD_MINUTES = 15
MAX_RUN_CANDIDATES = 3

def utc(text):
    try:
        dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError):
        return None

def call(endpoint, params, key, opener=urlopen):
    if endpoint not in ("account", "odds-by-tournaments"):
        raise ValueError("Endpoint prohibido")
    if not key:
        raise ValueError("Falta ODDS_PAPI_KEY")
    qs = urlencode({**params, "apiKey": key})
    req = Request(BASE + "/" + endpoint + "?" + qs, headers={"Accept": "application/json"})
    try:
        with opener(req, timeout=25) as response:
            return json.load(response)
    except HTTPError as e:
        raw = e.read(2048).decode("utf-8", errors="replace")
        try:
            err = json.loads(raw)
            diagnostic = " / ".join(str(err.get(field, "")) for field in ("code", "message", "details", "error", "reason") if err.get(field))
        except (ValueError, AttributeError):
            diagnostic = "Respuesta de error no JSON"
        diagnostic = diagnostic.replace(key, "[REDACTED]")[:300]
        raise RuntimeError("OddsPapi: HTTP " + str(e.code) + " · " + diagnostic) from None
    except URLError:
        raise RuntimeError("OddsPapi: sin conexión") from None

def remaining_quota(account):
    if not isinstance(account, dict):
        return 0
    active = [s for s in account.get("subscriptions", []) if s.get("is_active") is True]
    active_id = account.get("current_subscription_id")
    if active_id:
        active = [s for s in active if s.get("subscription_id") == active_id]
    if len(active) != 1:
        return 0
    subscription = active[0]
    allowed = subscription.get("bookmakers", {})
    # Si el proveedor especifica restricciones de casas, deben incluir ambas.
    if isinstance(allowed, dict) and allowed and not set(BOOKS).issubset(allowed):
        return 0
    try:
        limit = int(subscription["request_limit"])
        used = int(subscription["request_count"])
    except (KeyError, ValueError, TypeError):
        return 0
    return max(0, limit-used)

def quotes_for_fixture(fixture, now):
    """Rechaza mercados suspendidos y datos sin actualización reciente del evento.

changedAt significa CAMBIO de precio, no última observación del proveedor.
updatedAt es actualización del evento, una señal imperfecta de vigencia.
"""
    if not isinstance(fixture, dict) or fixture.get("sportId") != 10:
        return None
    if fixture.get("statusId") != 0:
        return None
    kickoff = utc(fixture.get("startTime"))
    if not kickoff or kickoff <= now + timedelta(minutes=MIN_LEAD_MINUTES):
        return None
    books = fixture.get("bookmakerOdds")
    if not isinstance(books, dict):
        return None
    clean = {}
    for slug in BOOKS:
        book = books.get(slug)
        if not isinstance(book, dict) or book.get("bookmakerIsActive") is not True or book.get("suspended") is not False:
            continue
        market = (book.get("markets") or {}).get(MARKET_ID)
        if not isinstance(market, dict) or market.get("marketActive") is not True:
            continue
        out = market.get("outcomes")
        if not isinstance(out, dict):
            continue
        prices = {}
        for outcome_id, label in OUTCOMES.items():
            outcome = out.get(outcome_id)
            if not isinstance(outcome, dict):
                continue
            player = (outcome.get("players") or {}).get("0")
            if not isinstance(player, dict) or player.get("active") is not True:
                continue
            dt = utc(player.get("changedAt"))
            if not dt or not (0 <= (now-dt).total_seconds() <= MAX_PRICE_CHANGE_AGE_SECONDS):
                continue
            try:
                price = float(player["price"])
            except (TypeError, ValueError, KeyError):
                continue
            if not (1 < price < 1000):
                continue
            prices[label] = price
        if len(prices) == 3:
            clean[slug] = prices
    if len(clean) != 2:
        return None
    candidates = []
    for home in BOOKS:
        for draw in BOOKS:
            for away in BOOKS:
                selected = (home, draw, away)
                if len(set(selected)) < 2:
                    continue
                offers = [
                    {"bookmaker": slug, "outcome": label, "price": clean[slug][label],
                     "bookmaker_key": slug}
                    for slug, label in zip(selected, ("1","X","2"))
                ]
                alloc = allocate(100.0, offers)
                if alloc is not None:
                    candidates.append(alloc)
    if not candidates:
        return None
    best = max(candidates, key=lambda c:c["profit"])
    if best["roi_percent"] < 0.5:
        return None
    event = str(fixture.get("participant1Name") or "") + " vs " + str(fixture.get("participant2Name") or "")
    return {"event":event.strip(), "fixture_id":str(fixture.get("fixtureId") or ""),
            "start":kickoff.isoformat(), **best}

def scan(payload, now=None):
    now = now or datetime.now(timezone.utc)
    fixtures = payload if isinstance(payload, list) else payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(fixtures, list):
        raise ValueError("Respuesta de cuotas desconocida")
    results = []
    for fixture in fixtures:
        item = quotes_for_fixture(fixture, now)
        if item:
            results.append(item)
    return sorted(results, key=lambda x:x["profit"], reverse=True)

def merge_bookmaker_fixtures(results_by_book):
    """Combina por fixtureId; nunca mezcla eventos distintos ni infiere precios."""
    merged = {}
    for slug in BOOKS:
        payload = results_by_book.get(slug)
        rows = payload if isinstance(payload, list) else payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            raise ValueError("Formato inesperado de resultados")
        for fixture in rows:
            if not isinstance(fixture, dict):
                continue
            event_id = str(fixture.get("fixtureId") or "")
            if not event_id:
                continue
            book_odds = fixture.get("bookmakerOdds")
            if not isinstance(book_odds, dict) or slug not in book_odds:
                continue
            old = merged.get(event_id)
            if old is None:
                merged[event_id] = {**fixture, "bookmakerOdds": {slug: book_odds[slug]}}
            else:
                for field in ("sportId", "tournamentId", "startTime", "participant1Id", "participant2Id"):
                    if old.get(field) != fixture.get(field):
                        raise ValueError("El proveedor devuelve eventos contradictorios")
                old["bookmakerOdds"][slug] = book_odds[slug]
    return list(merged.values())

def source_diagnostics(fixtures, now):
    """Diagnóstico agregado de cobertura; no muestra datos personales ni tokens."""
    counts = {"fixtures": len(fixtures), "two_books": 0,
              "two_active_books": 0, "two_1x2_markets": 0,
              "two_complete_1x2": 0, "recent_fixture_updates": 0,
              "old_price_change_dates": 0, "alert_eligible_events": 0}
    for fixture in fixtures:
        books = fixture.get("bookmakerOdds") or {}
        if not all(book in books for book in BOOKS):
            continue
        counts["two_books"] += 1
        if not all(books[slug].get("bookmakerIsActive") is True and
                   books[slug].get("suspended") is False for slug in BOOKS):
            continue
        counts["two_active_books"] += 1
        if not all(isinstance(books[slug].get("markets",{}).get(MARKET_ID),dict) and
                   books[slug]["markets"][MARKET_ID].get("marketActive") is True
                   for slug in BOOKS):
            continue
        counts["two_1x2_markets"] += 1
        usable = True
        for slug in BOOKS:
            odds=books[slug]["markets"][MARKET_ID].get("outcomes", {})
            for outcome_id in OUTCOMES:
                player=(odds.get(outcome_id,{}).get("players") or {}).get("0")
                if not isinstance(player,dict) or player.get("active") is not True:
                    usable=False
                    break
                dt=utc(player.get("changedAt"))
                if not dt or not (0 <= (now-dt).total_seconds() <= MAX_AGE_SECONDS):
                    usable=False
                    break
        if usable:
            counts["two_complete_fresh_1x2"] += 1
    return counts

def message(opp):
    lines = [
      "ARBIISCAN | POSIBLE ARBITRAJE (NO CONFIRMADO)",
      opp["event"], "Inicio: " + opp["start"], "Mercado: 1X2 (90 minutos)",
      "Última actualización registrada del evento: " + opp["provider_event_updated_at"],
      "Capital ilustrativo: 100 €",
    ]
    for item in opp["offers"]:
        lines.append(item["bookmaker"] + " | " + item["outcome"] + " @ " +
                     f'{item["price"]:.2f} | {item["stake"]:.2f} €')
    lines += [f'Beneficio matemático estimado: {opp["profit"]:.2f} € ({opp["roi_percent"]:.2f}%).',
              "Cuotas observadas, no confirmadas en cupón. Verifica disponibilidad, reglas y límites en ambas casas antes de apostar.",
              "Fuente: OddsPapi (bet365.es y winamax.es). No se ha apostado."]
    return "\n".join(lines)

def run():
    key = os.getenv("ODDS_PAPI_KEY", "").strip()
    if not key:
        print("Sin ODDS_PAPI_KEY: no se consulta la API ni se envían alertas.")
        return
    account = call("account", {}, key)
    remaining = remaining_quota(account)
    print("Créditos restantes antes de consultar:", remaining)
    if remaining <= 16:
        print("Protección del plan gratuito: cuota insuficiente; no se realiza consulta.")
        return
    tournaments = (os.getenv("ODDSPAPI_TOURNAMENT_IDS") or "").strip() or "8,17"
    if not tournaments or any(not x.isdigit() for x in tournaments.split(",")) or len(tournaments.split(","))>6:
        raise ValueError("IDs de torneos inválidos")
    results_by_book = {}
    for slug in BOOKS:
        results_by_book[slug] = call("odds-by-tournaments", {
            "tournamentIds": tournaments, "bookmaker": slug,
            "language": "es", "verbosity": 3,
        }, key)
    response = merge_bookmaker_fixtures(results_by_book)
    print("Cobertura de cuotas:", source_diagnostics(response, datetime.now(timezone.utc)))
    candidates = scan(response)
    print("Candidatos matemáticos encontrados:", len(candidates))
    if os.getenv("ODDSPAPI_ENABLE_ALERTS") != "true":
        print("DRY RUN: envío desactivado hasta verificar la fuente con credenciales reales.")
        return
    token = os.getenv("TELEGRAM_BOT_TOKEN","").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID","").strip()
    if not token or not chat:
        raise ValueError("Faltan secretos de Telegram")
    for opp in candidates[:MAX_RUN_CANDIDATES]:
        send_telegram(token, chat, message(opp))
    print("Candidatos notificados:", min(MAX_RUN_CANDIDATES,len(candidates)))

if __name__ == "__main__":
    run()
