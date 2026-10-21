"""ArbiiScan: browser-based public page reader for Bet365 ES / Winamax ES.

No login, CAPTCHA bypass, hidden/private endpoints, stealth tooling or automated betting.
One explicit public event page per bookmaker. Strict CSS selectors supplied as JSON.
Runs only when enabled and never sends alerts without matching cross-book evidence.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from scanner import allocate, send_telegram

ALLOWED_HOSTS = {
    "bet365.es": ("bet365.es", "www.bet365.es"),
    "winamax.es": ("winamax.es", "www.winamax.es"),
}
REQUIRED_SELECTORS = ("event", "start", "home", "away", "draw")
BLOCK_TEXT = re.compile(r"captcha|verify you are human|access denied|acceso denegado|verifica que eres humano", re.I)
MARKET = "1X2_90_MIN"
MIN_ROI = 0.5

def parse_price(value):
    text = str(value).strip()
    # No locale/format ambiguity: only standalone decimal odds.
    if not re.fullmatch(r"\d{1,3}(?:[.,]\d{1,3})?", text):
        raise ValueError("Formato de cuota ambiguo")
    amount = float(text.replace(",", "."))
    if not 1.01 <= amount < 1000:
        raise ValueError("Cuota fuera de rango")
    return amount

def validate_config(raw):
    if not isinstance(raw, dict) or set(raw) != set(ALLOWED_HOSTS):
        raise ValueError("Configurar exactamente bet365.es y winamax.es")
    for brand, cfg in raw.items():
        if not isinstance(cfg, dict):
            raise ValueError("Configuración inválida")
        parts = urlsplit(str(cfg.get("url", "")))
        if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS[brand] or parts.username or parts.password or parts.port or parts.fragment:
            raise ValueError("Se requiere una URL pública HTTPS del dominio oficial " + brand)
        if cfg.get("market") != MARKET:
            raise ValueError("Mercado incompatible: usar 1X2_90_MIN")
        selectors = cfg.get("selectors")
        if not isinstance(selectors, dict) or set(selectors) != set(REQUIRED_SELECTORS):
            raise ValueError("Se requieren selectores explícitos para evento, inicio y tres cuotas")
        if not all(isinstance(v, str) and 0 < len(v) <= 180 for v in selectors.values()):
            raise ValueError("Selector vacío o excesivamente largo")
    return raw

def read_config(config_path):
    return validate_config(json.loads(Path(config_path).read_text(encoding="utf8")))

def _get_unique_text(page, selector):
    locator = page.locator(selector)
    if locator.count() != 1:
        raise ValueError("Selector no inequívoco: " + selector)
    return locator.inner_text(timeout=4000).strip()

def read_public_page(browser, brand, cfg, now=None):
    now = now or datetime.now(timezone.utc)
    page = browser.new_page(locale="es-ES", timezone_id="Europe/Madrid")
    try:
        response = page.goto(cfg["url"], wait_until="domcontentloaded", timeout=25000)
        if response is None or response.status >= 400:
            raise ValueError("Sitio no disponible: " + brand)
        if urlsplit(page.url).hostname not in ALLOWED_HOSTS[brand]:
            raise ValueError("Redirección fuera del dominio oficial")
        page.wait_for_timeout(1800)
        body = page.locator("body").inner_text(timeout=8000)[:15000]
        if BLOCK_TEXT.search(body):
            raise ValueError("Página con control de acceso o CAPTCHA: no se intenta eludir")
        selectors = cfg["selectors"]
        event = _get_unique_text(page, selectors["event"])
        kickoff = datetime.fromisoformat(_get_unique_text(page, selectors["start"]).replace("Z","+00:00"))
        if kickoff.tzinfo is None:
            raise ValueError("La fecha de inicio debe incluir zona horaria")
        kickoff = kickoff.astimezone(timezone.utc)
        if kickoff <= now + timedelta(minutes=15):
            raise ValueError("Partido iniciado o demasiado próximo")
        prices = {key: parse_price(_get_unique_text(page, selectors[key]))
                  for key in ("home", "draw", "away")}
        if not 3 <= len(event) <= 180:
            raise ValueError("Nombre de partido inválido")
        return {"book": brand, "event": event, "kickoff": kickoff.isoformat(),
                "market": MARKET, "prices": prices, "observed_at": now.isoformat(),
                "source_url": cfg["url"]}
    finally:
        page.close()

def normalized_event(value):
    return " ".join(re.sub(r"[^\w ]+", " ", value.casefold()).split())

def compare(a, b):
    if a["book"] == b["book"] or {a["book"],b["book"]} != set(ALLOWED_HOSTS):
        raise ValueError("Se necesitan dos casas diferentes")
    if a["market"] != MARKET or b["market"] != MARKET:
        return None
    if normalized_event(a["event"]) != normalized_event(b["event"]) or a["kickoff"] != b["kickoff"]:
        return None
    options = []
    for home in (a,b):
        for draw in (a,b):
            for away in (a,b):
                picked = (home,draw,away)
                if len({p["book"] for p in picked}) != 2:
                    continue
                odds = [{"bookmaker": q["book"],"bookmaker_key":q["book"],
                         "outcome": outcome, "price": q["prices"][label]}
                        for q,label,outcome in zip(picked,("home","draw","away"),("1","X","2"))]
                allocated = allocate(100, odds)
                if allocated is not None and allocated["roi_percent"] >= MIN_ROI:
                    options.append(allocated)
    if not options:
        return None
    best = max(options,key=lambda x:x["profit"])
    return {"event": a["event"], "start": a["kickoff"], "market": MARKET,
            "sources": [a["source_url"],b["source_url"]],**best}

def signature(offer):
    return (offer["event"],offer["start"],
            tuple((v["bookmaker"],v["outcome"],v["price"]) for v in offer["offers"]))

def recheck_same(first, second):
    return first is not None and second is not None and signature(first) == signature(second)

def alert_text(candidate, now):
    lines = ["ARBIISCAN | CANDIDATA DE ARBITRAJE SIN CONFIRMAR",
             candidate["event"],"Inicio: "+candidate["start"],
             "Mercado: 1X2 en 90 minutos",
             "Lectura de páginas públicas (repetida): "+now.isoformat()]
    for offer in candidate["offers"]:
        lines.append(f"{offer['bookmaker']} {offer['outcome']} @ {offer['price']:.2f} → {offer['stake']:.2f} €")
    lines += [f"Retorno mínimo matemático estimado: {candidate['profit']:.2f} € ({candidate['roi_percent']:.2f} %)",
              "Verifica ambas cuotas y límites directamente en los cupones: la lectura web no garantiza aceptación.",
              "Fuentes: "+", ".join(candidate["sources"])]
    return "\n".join(lines)

def main():
    config_path = os.getenv("SCRAPE_CONFIG_PATH","scraping_es/config.json")
    if not Path(config_path).exists():
        print("Sin archivo de URLs y selectores públicos. No se consulta ni se envía nada.")
        return
    cfg = read_config(config_path)
    from playwright.sync_api import sync_playwright
    from time import sleep
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            first = [read_public_page(browser, slug, cfg[slug]) for slug in ALLOWED_HOSTS]
            proposal = compare(*first)
            print("Primera consulta:","candidata matemática" if proposal else "sin candidato")
            if proposal is None:
                return
            sleep(3)
            second = [read_public_page(browser, slug, cfg[slug]) for slug in ALLOWED_HOSTS]
            validated = compare(*second)
            if not recheck_same(proposal, validated):
                print("Candidata descartada tras segunda lectura.")
                return
            if os.getenv("SCRAPING_ENABLE_ALERTS") != "true":
                print("Modo prueba. Sin mensajes de Telegram.")
                return
            token = os.getenv("TELEGRAM_BOT_TOKEN","")
            chat = os.getenv("TELEGRAM_CHAT_ID","")
            if not token or not chat:
                raise ValueError("Faltan secretos Telegram")
            send_telegram(token,chat,alert_text(validated,datetime.now(timezone.utc)))
            print("Aviso candidato enviado (pendiente de comprobar en cupón).")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
