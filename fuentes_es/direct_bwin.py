"""Lectura de cuotas públicas renderizadas de Bwin ES, sin API interna.

Este conector no inicia sesión, no pulsa cuotas, no intenta sortear controles y
no intercepta tráfico de red.  Sólo lee el DOM que Chromium recibe al visitar
la página pública de fútbol.  La ejecución productiva está deliberadamente
desactivada hasta que el titular confirme que esa automatización está permitida
y exista otra fuente directa compatible: una sola casa no puede formar arbitraje.
"""
from __future__ import annotations

import calendar
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import urljoin

from motor_propio.engine import BadQuote, Quote

BOOK = "bwin.es"
SPORTS = {
    "soccer": ("https://www.bwin.es/es/sports/f%C3%BAtbol-4", "1x2:regulation", ["1", "X", "2"], "resultado del partido"),
    "tennis": ("https://www.bwin.es/es/sports/tenis-5", "winner:completed_match", ["1", "2"], "2 way"),
    "basketball": ("https://www.bwin.es/es/sports/baloncesto-7", "winner:including_ot", ["1", "2"], "2 way"),
}


class DirectSourceUnavailable(RuntimeError):
    """El sitio no mostró un DOM público apto para lectura segura."""


def _madrid_offset(now: datetime) -> timezone:
    """CET/CEST without depending on the optional Windows ``tzdata`` package."""
    utc = now.astimezone(timezone.utc)
    def last_sunday(month: int) -> int:
        last = calendar.monthrange(utc.year, month)[1]
        return last - (datetime(utc.year, month, last).weekday() + 1) % 7
    summer_start = datetime(utc.year, 3, last_sunday(3), 1, tzinfo=timezone.utc)
    summer_end = datetime(utc.year, 10, last_sunday(10), 1, tzinfo=timezone.utc)
    return timezone(timedelta(hours=2 if summer_start <= utc < summer_end else 1))


def _local_now(now: datetime) -> datetime:
    return now.astimezone(_madrid_offset(now))


def parse_bwin_time(value: str, now: datetime) -> datetime | None:
    """Convierte las etiquetas públicas Hoy/Mañana a UTC; lo demás se descarta.

    No se inventan fechas para etiquetas ambiguas (p. ej. un nombre de día sin
    fecha), porque un cruce erróneo de partido es peor que omitirlo.
    """
    match = re.fullmatch(r"\s*(hoy|ma(?:ñ|n)ana)\s*/\s*(\d{1,2}):(\d{2})\s*", value, re.I)
    if not match:
        return None
    hour, minute = int(match.group(2)), int(match.group(3))
    if hour > 23 or minute > 59:
        return None
    local = _local_now(now)
    offset = 1 if match.group(1).casefold().startswith("ma") else 0
    target = (local + timedelta(days=offset)).replace(hour=hour, minute=minute,
                                                        second=0, microsecond=0)
    return target.astimezone(timezone.utc)


def parse_cards(cards: Iterable[dict], now: datetime, *, sport="soccer", market="1x2:regulation", labels_expected=None, market_text="resultado del partido") -> list[Quote]:
    """Valida el subconjunto de tarjetas 1X2 inequívocas extraído del DOM."""
    quotes: list[Quote] = []
    seen: set[str] = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        labels = card.get("labels")
        prices = card.get("prices")
        teams = card.get("teams")
        labels_expected = labels_expected or ["1", "X", "2"]
        if labels != labels_expected or not isinstance(prices, list) or len(prices) != len(labels_expected):
            continue
        if not isinstance(teams, list) or len(teams) != 2 or not all(isinstance(v, str) for v in teams):
            continue
        start = parse_bwin_time(str(card.get("start", "")), now)
        href = str(card.get("href", ""))
        market_heading = str(card.get("market", "")).casefold()
        if not start or not href.startswith("/es/sports/eventos/"):
            continue
        if market_text not in market_heading:
            continue
        url = urljoin("https://www.bwin.es", href)
        if url in seen:
            continue
        try:
            values = ({"1": prices[0], "X": prices[1], "2": prices[2]}
                      if len(labels_expected) == 3 else {"1": prices[0], "2": prices[1]})
            quote = Quote(book=BOOK, sport=sport, home=teams[0], away=teams[1],
                          kickoff=start, market=market, prices=values,
                          observed_at=now, source="permitted_web", url=url)
        except (BadQuote, TypeError, ValueError):
            continue
        seen.add(url)
        quotes.append(quote)
    return quotes


def _visible_cards(page) -> list[dict]:
    """Extrae campos visibles de cada tarjeta, sin tocar respuestas internas."""
    return page.locator("body").evaluate("""() => {
      const clean = value => (value || '').replace(/\\s+/g, ' ').trim();
      const cards = [];
      for (const link of document.querySelectorAll('a[href*="/es/sports/eventos/"]')) {
        let root = link;
        while (root && !root.querySelector?.('ms-event-pick')) root = root.parentElement;
        if (!root) continue;
        const picks = [...root.querySelectorAll('ms-event-pick')];
        const labels = picks.map(p => clean(p.querySelector('.card-result-name-text-alt')?.textContent));
        const prices = picks.map(p => clean(p.querySelector('.option-value')?.textContent));
        const teams = [...link.querySelectorAll('.player-name')].map(x => clean(x.textContent));
        cards.push({href: link.getAttribute('href'), teams,
          start: clean(root.querySelector('.card-date')?.textContent),
          competition: clean(root.querySelector('.card-league')?.textContent),
          market: clean(root.querySelector('.market-name-span')?.textContent), labels, prices});
      }
      return cards;
    }""")


def discover(now: datetime | None = None, *, headless: bool = True, sports=("soccer", "tennis", "basketball")) -> list[Quote]:
    """Abre una página pública Bwin y devuelve sólo 1X2 prepartido validable.

    El permiso se expresa mediante una variable de entorno para impedir que una
    actualización o un workflow active una consulta recurrente por accidente.
    """
    if os.getenv("ARBI_DIRECT_BWIN_ALLOWED") != "true":
        raise DirectSourceUnavailable("Bwin directo desactivado: falta ARBI_DIRECT_BWIN_ALLOWED=true")
    now = now or datetime.now(timezone.utc)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            quotes=[]
            for sport in sports:
                if sport not in SPORTS: continue
                url, market, expected, text = SPORTS[sport]
                page = browser.new_page(locale="es-ES", timezone_id="Europe/Madrid")
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    if response is None or response.status >= 400: continue
                    page.wait_for_timeout(1800)
                    body = page.locator("body").inner_text(timeout=6000)
                    if re.search(r"captcha|access denied|acceso denegado|verify you", body, re.I): continue
                    quotes.extend(parse_cards(_visible_cards(page), now, sport=sport, market=market,
                                              labels_expected=expected, market_text=text))
                finally:
                    page.close()
            return quotes
        finally:
            browser.close()


def main() -> None:
    try:
        values = discover()
    except DirectSourceUnavailable as exc:
        print("BWIN_DIRECTO_NO_DISPONIBLE:", exc)
        return
    print("BWIN_DIRECTO_CUOTAS_1X2:", len(values))
    for quote in values[:5]:
        print(quote.home, "vs", quote.away, quote.kickoff.isoformat(), quote.prices, quote.url)
    print("Sin segunda fuente directa compatible: alertas enviadas 0.")


if __name__ == "__main__":
    main()
