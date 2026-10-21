"""ArbiScan gratuito: The Odds API -> detección prudente -> Telegram.

Solo datos informativos. No realiza apuestas. Python 3.10+ y stdlib.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API_BASE = "https://api.the-odds-api.com/v4"
SUPPORTED_MARKETS = {"h2h", "totals", "spreads"}
TARGET_BOOKMAKERS = {"winamax_fr", "winamax_de", "betfair_sb_uk"}
TARGET_NAMES = ("Winamax", "Bet365", "Sportium", "SportyBet", "Betfair")
BASE_SPORTS = ("soccer_spain_la_liga", "soccer_spain_segunda_division", "basketball_nba")
TENNIS_WORDS = ("atp", "wta", "grand slam", "australian open", "french open", "roland garros", "wimbledon", "us open", "masters 1000")


def load_local_env() -> None:
    env = Path(__file__).with_name(".env")
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def request_json(url: str, post_data: dict | None = None):
    body = None if post_data is None else json.dumps(post_data).encode("utf-8")
    headers = {"User-Agent": "ArbiScanMVP/1.0"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(url, data=body, headers=headers), timeout=20) as response:
            return json.loads(response.read()), dict(response.headers.items())
    except HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"HTTP {err.code}. {detail}") from err
    except URLError as err:
        raise RuntimeError(f"Error de conexión: {err.reason}") from err


def get_odds(sport: str, markets: list[str], region: str, api_key: str):
    # Usar nombres concretos cuenta como una sola región (hasta 10 casas).
    # Evita pagar créditos por cuotas de otras casas no solicitadas.
    params = urlencode({"apiKey": api_key, "bookmakers": ",".join(sorted(TARGET_BOOKMAKERS)),
                        "markets": ",".join(markets), "oddsFormat": "decimal"})
    url = f"{API_BASE}/sports/{quote(sport, safe='')}/odds/?{params}"
    data, headers = request_json(url)
    if not isinstance(data, list):
        raise ValueError("Respuesta inesperada de la API de cuotas")
    remaining = headers.get("X-Requests-Remaining", headers.get("x-requests-remaining", "?"))
    last = headers.get("X-Requests-Last", headers.get("x-requests-last", "?"))
    return filter_target_books(data), remaining, last


def filter_target_books(events):
    return [{**e, "bookmakers": [b for b in e.get("bookmakers", [])
            if b.get("key", "").lower() in TARGET_BOOKMAKERS]} for e in events]


def selected_sports(api_key):
    chosen = list(BASE_SPORTS)
    try:
        available = list_sports(api_key)
        active_keys = {x.get("key") for x in available if x.get("active")}
        chosen = [key for key in chosen if key in active_keys]
        active = [x for x in available if x.get("active") and not x.get("has_outrights")
                  and any(w in (str(x.get("key", "")) + " " + str(x.get("title", ""))).lower() for w in TENNIS_WORDS)]
        active.sort(key=lambda x: (not any(w in (str(x.get("key", "")) + " " + str(x.get("title", ""))).lower()
                         for w in ("grand slam", "wimbledon", "roland", "us open", "australian")), str(x.get("key", ""))))
        if active:
            chosen.append(active[0]["key"])
    except (RuntimeError, ValueError):
        pass
    return chosen


def list_sports(api_key: str):
    data, _ = request_json(f"{API_BASE}/sports/?{urlencode({'apiKey':api_key})}")
    return data


def iso_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def half_point(value) -> bool:
    """Solo líneas .5: evita pushes y reglas de reembolso complejas."""
    try:
        point = Decimal(str(value))
        return abs(point * 2) % 2 == 1
    except Exception:
        return False


def market_group(event: dict, market: dict):
    """Devuelve (mercado, linea, etiquetas, precios) o None.

    Mercado y líneas deben ser *idénticos* en todas las casas.
    """
    key = market.get("key")
    if key not in SUPPORTED_MARKETS:
        return None
    raw = market.get("outcomes", [])
    home, away = event.get("home_team"), event.get("away_team")
    if not home or not away or not isinstance(raw, list):
        return None
    odds = {}
    for outcome in raw:
        try:
            name = str(outcome["name"])
            price = float(outcome["price"])
        except (ValueError, TypeError, KeyError):
            return None
        if not (1.0 < price < 1001.0):
            return None
        if name in odds:
            return None
        odds[name] = price
    if key == "h2h":
        expected = {home, away}
        # Empates son posibles en ligas de fútbol: un 'h2h' sin empate no es cobertura total segura.
        if str(event.get("sport_key", "")).startswith("soccer_"):
            expected.add("Draw")
        elif "Draw" in odds:
            expected.add("Draw")
        if set(odds) != expected:
            return None
        return (key, None, tuple(sorted(expected)), odds)
    if key == "totals":
        if set(odds) != {"Over", "Under"}:
            return None
        points = {str(x.get("point")) for x in raw}
        if len(points) != 1:
            return None
        line = next(iter(points))
        if not half_point(line):
            return None
        return (key, line, ("Over", "Under"), odds)
    # Spreads: comprobamos que los hándicaps de local y visitante sean opuestos.
    if key == "spreads":
        if set(odds) != {home, away}:
            return None
        by_name = {str(x.get("name")): x.get("point") for x in raw}
        if not (half_point(by_name[home]) and half_point(by_name[away])):
            return None
        try:
            h = Decimal(str(by_name[home]))
            a = Decimal(str(by_name[away]))
        except Exception:
            return None
        if h != -a:
            return None
        return (key, str(h), tuple(sorted([home, away])), odds)
    return None


def allocate(bankroll: float, offers: list[dict]):
    """Redondea apuestas a céntimos y comprueba *beneficio mínimo real redondeado*."""
    cents = int((Decimal(str(bankroll)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if cents <= 0:
        raise ValueError("El capital debe ser superior a cero")
    inverse = [1 / item["price"] for item in offers]
    denominator = sum(inverse)
    if denominator >= 1:
        return None
    stakes_cents = [int(round(cents * x / denominator)) for x in inverse[:-1]]
    stakes_cents.append(cents - sum(stakes_cents))
    payouts = [s / 100 * item["price"] for s, item in zip(stakes_cents, offers)]
    minimum = min(payouts)
    profit = minimum - cents / 100
    if profit <= 0:
        return None
    result_offers = [dict(item, stake=round(s / 100, 2)) for item, s in zip(offers, stakes_cents)]
    return {"offers": result_offers, "profit": round(profit, 2),
            "roi_percent": round(100 * profit / (cents / 100), 3),
            "bankroll": cents / 100}


def scan_events(events: list[dict], now=None, bankroll=100.0, min_roi=0.5,
                max_age_seconds=300, min_minutes_before=15, allowed_bookmakers=None):
    """Solo mercados prepartido y cotizaciones recientes; ignora exchanges con comisiones."""
    now = now or datetime.now(timezone.utc)
    opportunities = []
    for event in events:
        start = iso_dt(event.get("commence_time"))
        if not start or start <= now + timedelta(minutes=min_minutes_before):
            continue
        groups = defaultdict(list)
        for book in event.get("bookmakers", []):
            book_key = str(book.get("key", ""))
            if (not book_key or "_ex_" in book_key or "exchange" in book_key or
                    (allowed_bookmakers is not None and book_key not in allowed_bookmakers)):
                continue
            for market in book.get("markets", []):
                updated = iso_dt(market.get("last_update") or book.get("last_update"))
                if not updated or not (0 <= (now - updated).total_seconds() <= max_age_seconds):
                    continue
                entry = market_group(event, market)
                if entry is None:
                    continue
                market_type, line, outcomes, prices = entry
                groups[(market_type, line, outcomes)].append({
                    "bookmaker": book.get("title", book_key),
                    "bookmaker_key": book_key, "prices": prices,
                    "updated": updated.isoformat()})
        for (kind, line, outcomes), books in groups.items():
            # Dos países de Winamax son la misma marca, no dos casas independientes.
            def brand(key):
                return 'Winamax' if key.startswith('winamax_') else ('Betfair' if key.startswith('betfair_') else key)
            if len({brand(item["bookmaker_key"]) for item in books}) < 2:
                continue
            offers = []
            for outcome in outcomes:
                best = max(books, key=lambda b: b["prices"][outcome])
                offers.append({"outcome": outcome, "price": best["prices"][outcome],
                               "bookmaker": best["bookmaker"], "bookmaker_key": best["bookmaker_key"],
                               "updated": best["updated"]})
            if len({brand(x["bookmaker_key"]) for x in offers}) < 2:
                continue
            alloc = allocate(bankroll, offers)
            if alloc and alloc["roi_percent"] >= min_roi:
                opportunities.append({"event": f"{event['home_team']} vs {event['away_team']}",
                                      "sport": event.get("sport_title", event.get("sport_key", "?")),
                                      "start": start.isoformat(), "market": kind, "line": line,
                                      **alloc})
    return sorted(opportunities, key=lambda a: a["roi_percent"], reverse=True)


def message_for(opp: dict) -> str:
    descriptions = {"h2h": "Resultado del partido", "totals": "Más/menos", "spreads": "Hándicap"}
    line = f" ({opp['line']})" if opp["line"] is not None else ""
    rows = [f"📊 {opp['event']} | {opp['sport']}",
            f"Mercado: {descriptions[opp['market']]}{line}",
            f"Retorno mínimo TEÓRICO: +{opp['profit']:.2f} € ({opp['roi_percent']:.2f}%)",
            f"Capital simulado: {opp['bankroll']:.2f} €", ""]
    for item in opp["offers"]:
        rows.append(f"• {item['bookmaker']}: {item['outcome']} @ {item['price']:.2f} → {item['stake']:.2f} €")
    rows += ["", "⚠️ Solo alerta informativa. Cuotas y disponibilidad pueden cambiar; verifica reglas, límites y liquidación. No garantiza ganancias."]
    return "\n".join(rows)


def bot_call(token: str, method: str, data=None):
    url = f"https://api.telegram.org/bot{quote(token, safe=':')}/{method}"
    result, _ = request_json(url, data)
    if not result.get("ok"):
        raise RuntimeError(f"Telegram: {result.get('description', 'error desconocido')}")
    return result.get("result")


def send_telegram(token: str, chat_id: str, message: str):
    return bot_call(token, "sendMessage", {"chat_id": chat_id, "text": message})


def demo_data():
    now = datetime.now(timezone.utc)
    now_text = now.isoformat()
    return [{"id": "demo", "sport_key": "basketball_nba", "sport_title": "Baloncesto (DEMO)",
        "commence_time": (now + timedelta(days=1)).isoformat(), "home_team": "Equipo A", "away_team": "Equipo B",
        "bookmakers": [
            {"key": "casa_demo_a", "title": "Casa ficticia A", "markets": [{"key": "h2h", "last_update": now_text, "outcomes": [{"name": "Equipo A", "price": 2.10}, {"name": "Equipo B", "price": 1.80}]}]},
            {"key": "casa_demo_b", "title": "Casa ficticia B", "markets": [{"key": "h2h", "last_update": now_text, "outcomes": [{"name": "Equipo A", "price": 1.80}, {"name": "Equipo B", "price": 2.05}]}]},
        ]}]


def main():
    load_local_env()
    parser = argparse.ArgumentParser(description="ArbiScan Gratis · analizador de arbitrajes con alertas Telegram")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true", help="Usa cuotas ficticias")
    group.add_argument("--live", action="store_true", help="Consulta cuotas reales de la API")
    group.add_argument("--list-sports", action="store_true", help="Lista códigos de deportes activos")
    group.add_argument("--chat-id", action="store_true", help="Busca tu ID de chat tras escribir /start en Telegram")
    group.add_argument("--test-telegram", action="store_true", help="Envía mensaje de prueba a Telegram")
    parser.add_argument("--send", action="store_true", help="Envía oportunidades al chat configurado")
    parser.add_argument("--report", action="store_true", help="Envía resumen incluso cuando no hay arbitrajes")
    args = parser.parse_args()
    api_key = os.getenv("ODDS_API_KEY", "")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    try:
        if args.chat_id:
            if not token:
                raise ValueError("Falta TELEGRAM_BOT_TOKEN")
            updates = bot_call(token, "getUpdates")
            chats = {str(x["message"]["chat"]["id"]) for x in updates if "message" in x and "chat" in x["message"]}
            print("ID(s) encontrados:", ", ".join(sorted(chats)) if chats else "ninguno. Envía /start al bot y repite")
            return
        if args.test_telegram:
            if not token or not chat_id:
                raise ValueError("Necesitas TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID")
            send_telegram(token, chat_id, "✅ ArbiScan conectado. Esto es una prueba; ninguna apuesta se ha realizado.")
            print("Mensaje de prueba enviado")
            return
        if args.list_sports:
            if not api_key:
                raise ValueError("Falta ODDS_API_KEY")
            for sport in list_sports(api_key):
                if sport.get("active"):
                    print(f"{sport['key']:40s} {sport['title']}")
            return
        bankroll = float(os.getenv("BANKROLL_EUR", "100"))
        min_roi = float(os.getenv("MIN_ROI_PERCENT", "0.5"))
        max_age = int(os.getenv("MAX_ODDS_AGE_SECONDS", "300"))
        events = []
        if args.demo:
            events = demo_data()
            print("MODO DEMO · cuotas inventadas")
        else:
            if not api_key:
                raise ValueError("Falta ODDS_API_KEY")
            sports = [s.strip() for s in os.getenv("SPORT_KEYS", "soccer_spain_la_liga,basketball_nba").split(",") if s.strip()]
            markets = [m.strip() for m in os.getenv("MARKETS", "h2h,totals,spreads").split(",") if m.strip()]
            if not sports or not markets or not set(markets).issubset(SUPPORTED_MARKETS):
                raise ValueError("SPORT_KEYS/MARKETS incorrectos")
            region = os.getenv("REGION", "eu").strip()
            if region not in {"eu", "uk", "us", "au"}:
                raise ValueError("Para controlar créditos usa UNA sola REGION: eu, uk, us o au")
            if len(sports) * len(markets) > 12:
                raise ValueError("Configuración potencialmente cara en créditos; máximo 12 por ejecución")
            for sport in sports:
                data, remaining, cost = get_odds(sport, markets, region, api_key)
                events.extend(data)
                print(f"{sport}: {len(data)} eventos | último coste: {cost} créditos | restantes: {remaining}")
        opportunities = scan_events(events, bankroll=bankroll, min_roi=min_roi, max_age_seconds=max_age)
        print(f"Oportunidades candidatas: {len(opportunities)}")
        for opp in opportunities[:10]:
            print("\n" + message_for(opp))
        if args.send:
            if not token or not chat_id:
                raise ValueError("Para enviar necesitas TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID")
            for opp in opportunities[:5]:
                send_telegram(token, chat_id, message_for(opp))
            if not opportunities and args.report:
                send_telegram(token, chat_id, "ArbiScan: análisis finalizado sin arbitrajes candidatos. No se han realizado apuestas.")
            print(f"Telegram: {min(5, len(opportunities)) if opportunities else int(args.report)} mensaje(s) enviado(s)")
    except (ValueError, RuntimeError, KeyError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
