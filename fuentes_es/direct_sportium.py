"""Lector DOM público de Sportium ES para fútbol 1X2, sin APIs privadas."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urljoin

from motor_propio.engine import BadQuote, Quote
from fuentes_es.direct_bwin import DirectSourceUnavailable, parse_bwin_time

BOOK = "sportium.es"
SPORTS = {
    "soccer": ("https://www.sportium.es/apuestas/sports/soccer/matches", "MRES", "1x2:regulation"),
    "tennis": ("https://www.sportium.es/apuestas/sports/tennis/matches/today", "HTOH", "winner:completed_match"),
    "basketball": ("https://www.sportium.es/apuestas/sports/basketball/matches/today", "H2HT", "winner:including_ot"),
}

# Sólo equivalencias inequívocas observadas en las etiquetas públicas de ambas
# casas. Si una abreviatura no figura aquí se conserva y el motor no la cruza.
ALIASES = {"celta": "Celta de Vigo", "r. sociedad": "Real Sociedad",
           "afc bournemouth": "Bournemouth", "fc stade rennes": "Stade Rennais",
           "ofi crete": "OFI Creta FC", "olympique lyon": "O. Lyon"}


def parse_cards(cards: Iterable[dict], now: datetime, *, sport="soccer", market="1x2:regulation") -> list[Quote]:
    quotes, seen = [], set()
    for card in cards:
        if not isinstance(card, dict) or card.get("prices") is None:
            continue
        teams, prices = card.get("teams"), card.get("prices")
        expected = 3 if sport == "soccer" else 2
        if not isinstance(teams, list) or len(teams) != 2 or not isinstance(prices, list) or len(prices) != expected:
            continue
        start = parse_bwin_time(str(card.get("start", "")).replace(",", " /", 1), now)
        href = str(card.get("href", ""))
        if not start or not href.startswith("/apuestas/sports/" + sport + "/events/"):
            continue
        home, away = (ALIASES.get(str(name).casefold(), str(name)) for name in teams)
        url = urljoin("https://www.sportium.es", href)
        if url in seen:
            continue
        prices_by_outcome = ({"1": prices[0], "X": prices[1], "2": prices[2]}
                             if expected == 3 else {"1": prices[0], "2": prices[1]})
        try:
            quote = Quote(book=BOOK, sport=sport, home=home, away=away,
                          kickoff=start, market=market, prices=prices_by_outcome,
                          observed_at=now, source="permitted_web", url=url)
        except (BadQuote, TypeError, ValueError):
            continue
        seen.add(url)
        quotes.append(quote)
    return quotes


def _visible_cards(page, market_class: str) -> list[dict]:
    return page.locator("body").evaluate("""() => {
      const clean = x => (x || '').replace(/\\s+/g, ' ').trim();
      return [...document.querySelectorAll('.ta-EventListItem')].map(row => {
        const link = row.querySelector('a.EventListItemDetails');
        const market = row.querySelector('.ta-MarketType-""" + market_class + """');
        return {href: link?.getAttribute('href'),
          teams: [...(link?.querySelectorAll('.ta-participantName') || [])].map(x => clean(x.textContent)),
          start: clean(row.firstElementChild?.textContent),
          prices: [...(market?.querySelectorAll('.ta-price_text') || [])].map(x => clean(x.textContent))};
      });
    }""")


def discover(now: datetime | None = None, sports=("soccer", "tennis", "basketball")) -> list[Quote]:
    if os.getenv("ARBI_DIRECT_SPORTIUM_ALLOWED") != "true":
        raise DirectSourceUnavailable("Sportium directo desactivado: falta ARBI_DIRECT_SPORTIUM_ALLOWED=true")
    now = now or datetime.now(timezone.utc)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            quotes=[]
            for sport in sports:
                if sport not in SPORTS:
                    continue
                url, market_class, market = SPORTS[sport]
                page = browser.new_page(locale="es-ES", timezone_id="Europe/Madrid")
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    if response is None or response.status >= 400:
                        continue
                    page.wait_for_timeout(1200)
                    reject = page.get_by_text("Rechazar", exact=True)
                    if reject.count(): reject.first.click(timeout=3000)
                    page.wait_for_timeout(4000)
                    body = page.locator("body").inner_text(timeout=6000)
                    if re.search(r"captcha|access denied|acceso denegado|verify you", body, re.I):
                        continue
                    quotes.extend(parse_cards(_visible_cards(page, market_class), now, sport=sport, market=market))
                finally:
                    page.close()
            return quotes
        finally:
            browser.close()
