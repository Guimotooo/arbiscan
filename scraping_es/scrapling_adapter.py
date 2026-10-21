"""Scrapling adapter for ArbiiScan's public, authorised match pages.

Separate from the production OddsPapi scanner. No stealth, CAPTCHA solving,
proxy rotation, session reuse, private endpoints, or automatic wagers.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from scraping_es.browser_scan import (
    ALLOWED_HOSTS, MARKET, BLOCK_TEXT, parse_price, validate_config, compare,
    recheck_same,
)

REQUIRED = ("event", "start", "home", "draw", "away")


def _one_text(page, selector: str) -> str:
    matches = page.css(selector)
    if len(matches) != 1:
        raise ValueError("El selector no es único: " + selector)
    raw = matches[0].text
    value = str(raw or "").strip()
    if not value:
        raise ValueError("El selector está vacío: " + selector)
    return value


def parse_html(html: str | bytes, brand: str, config: dict, observed_at=None):
    """Extract one precise full-time soccer 1X2 market from known CSS selectors.

    All selectors must be anchored to a single match/market page. Rejects missing,
    ambiguous, suspended or invalid prices rather than guessing from nearby games.
    """
    from scrapling.parser import Selector

    validate_config({brand:config, **{
        other: {"url":"https://"+other+"/",
                "market":MARKET,
                "selectors":{k:".unused" for k in REQUIRED}}
        for other in ALLOWED_HOSTS if other != brand
    }})
    now = observed_at or datetime.now(timezone.utc)
    page = Selector(content=html)
    text = str(page.get_all_text() or "")[:12000]
    if BLOCK_TEXT.search(text):
        raise ValueError("Página bloqueada o con CAPTCHA: no se intenta eludir")
    s=config["selectors"]
    event=_one_text(page,s["event"])
    start=_one_text(page,s["start"])
    kickoff=datetime.fromisoformat(start.replace("Z","+00:00"))
    if kickoff.tzinfo is None:
        raise ValueError("El inicio requiere zona horaria explícita")
    kickoff=kickoff.astimezone(timezone.utc)
    if kickoff <= now + timedelta(minutes=15):
        raise ValueError("Partido iniciado o demasiado próximo")
    if not 3 <= len(event) <= 180:
        raise ValueError("Nombre de encuentro no válido")
    prices={outcome:parse_price(_one_text(page,s[outcome]))
            for outcome in ("home","draw","away")}
    return {"book":brand, "event":event, "kickoff":kickoff.isoformat(),
            "market":MARKET, "prices":prices, "observed_at":now.isoformat(),
            "source_url":config["url"]}


def fetch_public_html(brand: str, url: str, mode: str = "http"):
    """One ordinary request to an official public page. Fail closed on 4xx/blocks.

    Dynamic mode is optional for JS-rendered pages and uses the standard
    DynamicFetcher, not a stealth fetcher.
    """
    if brand not in ALLOWED_HOSTS:
        raise ValueError("Casa no admitida")
    parts=urlsplit(url)
    if parts.scheme!="https" or parts.hostname not in ALLOWED_HOSTS[brand]:
        raise ValueError("Solo dominios HTTPS oficiales")
    if mode == "http":
        from scrapling.fetchers import Fetcher
        response=Fetcher.get(url)
    elif mode == "dynamic":
        from scrapling.fetchers import DynamicFetcher
        response=DynamicFetcher.fetch(url, network_idle=False)
    else:
        raise ValueError("Modo desconocido")
    status=int(getattr(response,"status",0) or 0)
    if status<200 or status>=400:
        raise ValueError("El sitio respondió HTTP "+str(status))
    real_url=str(getattr(response,"url",url))
    if urlsplit(real_url).hostname not in ALLOWED_HOSTS[brand]:
        raise ValueError("Redirección fuera del dominio oficial")
    return response.body


def scan_single_match(config_path: str, mode: str = "http"):
    """Do not send alerts. Inspect two known authorised public event pages."""
    import json
    from pathlib import Path
    config=validate_config(json.loads(Path(config_path).read_text(encoding="utf-8")))
    snapshots=[]
    for brand in ALLOWED_HOSTS:
        html=fetch_public_html(brand,config[brand]["url"],mode=mode)
        snapshots.append(parse_html(html,brand,config[brand]))
    return compare(*snapshots)


if __name__=="__main__":
    import os
    source=os.getenv("SCRAPLING_CONFIG_PATH","scraping_es/config.json")
    if not os.path.isfile(source):
        print("Modo seguro: sin URLs/selector 1X2 confirmados. No se realiza scraping ni se envían alertas.")
    else:
        opp=scan_single_match(source,os.getenv("SCRAPLING_MODE","http"))
        print("Arbitraje candidato no confirmado:" if opp else "Sin arbitraje matemático")
        if opp:
            print("Partido:",opp["event"],"Mercado:",opp["market"],"Beneficio hipotético:",round(opp["profit"],2))
