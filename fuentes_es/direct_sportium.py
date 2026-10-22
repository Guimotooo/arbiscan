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
SOURCE_URL = "https://www.sportium.es/apuestas/sports/soccer/matches"

# Sólo equivalencias inequívocas observadas en las etiquetas públicas de ambas
# casas. Si una abreviatura no figura aquí se conserva y el motor no la cruza.
ALIASES = {"celta": "Celta de Vigo", "r. sociedad": "Real Sociedad",
           "afc bournemouth": "Bournemouth", "fc stade rennes": "Stade Rennais",
           "ofi crete": "OFI Creta FC", "olympique lyon": "O. Lyon"}


def parse_cards(cards: Iterable[dict], now: datetime) -> list[Quote]:
    quotes, seen = [], set()
    for card in cards:
        if not isinstance(card, dict) or card.get("prices") is None:
            continue
        teams, prices = card.get("teams"), card.get("prices")
        if not isinstance(teams, list) or len(teams) != 2 or not isinstance(prices, list) or len(prices) != 3:
            continue
        start = parse_bwin_time(str(card.get("start", "")).replace(",", " /", 1), now)
        href = str(card.get("href", ""))
        if not start or not href.startswith("/apuestas/sports/soccer/events/"):
            continue
        home, away = (ALIASES.get(str(name).casefold(), str(name)) for name in teams)
        url = urljoin("https://www.sportium.es", href)
        if url in seen:
            continue
        try:
            quote = Quote(book=BOOK, sport="soccer", home=home, away=away,
                          kickoff=start, market="1x2:regulation",
                          prices={"1": prices[0], "X": prices[1], "2": prices[2]},
                          observed_at=now, source="permitted_web", url=url)
        except (BadQuote, TypeError, ValueError):
            continue
        seen.add(url)
        quotes.append(quote)
    return quotes


def _visible_cards(page) -> list[dict]:
    return page.locator("body").evaluate("""() => {
      const clean = x => (x || '').replace(/\\s+/g, ' ').trim();
      return [...document.querySelectorAll('.ta-EventListItem')].map(row => {
        const link = row.querySelector('a.EventListItemDetails');
        const market = row.querySelector('.ta-MarketType-MRES');
        return {href: link?.getAttribute('href'),
          teams: [...(link?.querySelectorAll('.ta-participantName') || [])].map(x => clean(x.textContent)),
          start: clean(row.firstElementChild?.textContent),
          prices: [...(market?.querySelectorAll('.ta-price_text') || [])].map(x => clean(x.textContent))};
      });
    }""")


def discover(now: datetime | None = None) -> list[Quote]:
    if os.getenv("ARBI_DIRECT_SPORTIUM_ALLOWED") != "true":
        raise DirectSourceUnavailable("Sportium directo desactivado: falta ARBI_DIRECT_SPORTIUM_ALLOWED=true")
    now = now or datetime.now(timezone.utc)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale="es-ES", timezone_id="Europe/Madrid")
        try:
            response = page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=30000)
            if response is None or response.status >= 400:
                raise DirectSourceUnavailable("Sportium no devolvió una página pública utilizable")
            page.wait_for_timeout(1200)
            reject = page.get_by_text("Rechazar", exact=True)
            if reject.count():
                reject.first.click(timeout=3000)
            page.wait_for_timeout(4000)
            body = page.locator("body").inner_text(timeout=6000)
            if re.search(r"captcha|access denied|acceso denegado|verify you", body, re.I):
                raise DirectSourceUnavailable("Sportium presentó un control de acceso; no se intenta eludir")
            return parse_cards(_visible_cards(page), now)
        finally:
            page.close()
            browser.close()
