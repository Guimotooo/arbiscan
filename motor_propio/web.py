"""Lector propio de páginas HTML de operadores que permiten lectura automatizada.

Contrato por fuente (JSON): enlace HTTPS oficial, permiso explícito de uso,
selectores CSS unívocos para participantes/mercado/cuotas y reglas de liquidación.
No hay evasión de CAPTCHA, proxies, suplantación, peticiones a APIs privadas,
sesiones de usuario, cookies ni apuestas.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .engine import BadQuote, Quote, MARKETS, aware, decimal_odds

# Catálogo verificado de entidades españolas, no permiso de scraping.
BOOK_HOSTS = {
    "888sport.es","betfair.es","betway.es","bwin.es","codere.es",
    "goldenpark.es","leovegas.es","paf.es","pokerstars.es","winamax.es",
}
# Sus condiciones prohíben expresamente extraer cuotas automáticamente.
DIRECT_SCRAPE_PROHIBITED = {"bet365.es"}

BLOCK_RE = re.compile(
    r"captcha|access denied|acceso denegado|verify you are human|"
    r"comprueba que eres humano|security check|temporarily restricted",
    re.I,
)


def _domain(url: str, brand: str):
    if not isinstance(url, str) or len(url)>2000:
        raise BadQuote("URL inválida")
    parsed=urlsplit(url)
    if (parsed.scheme!="https" or parsed.username or parsed.password or parsed.port or
        parsed.hostname not in (brand,"www."+brand) or parsed.hostname is None):
        raise BadQuote("Dominio HTTPS oficial no verificado")
    return parsed.hostname


def validate_profile(value):
    if not isinstance(value, dict):
        raise BadQuote("El perfil debe ser un objeto")
    brand=str(value.get("book",""))
    if brand in DIRECT_SCRAPE_PROHIBITED:
        raise BadQuote("Bet365 ES prohíbe la extracción directa: utiliza una fuente licenciada")
    if brand not in BOOK_HOSTS:
        raise BadQuote("Dominio desconocido: requiere nueva revisión individual")
    if value.get("permission_confirmed") is not True:
        raise BadQuote("Falta confirmar permiso de extracción para este operador")
    _domain(value.get("url"),brand)
    sport=value.get("sport")
    market=value.get("market")
    outcomes=MARKETS.get((sport,market))
    if outcomes is None:
        raise BadQuote("Mercado o reglas no validados")
    selectors=value.get("selectors")
    required={"home","away","kickoff",*outcomes}
    if not isinstance(selectors,dict) or set(selectors)!=required:
        raise BadQuote("Se requieren selectores únicos de participantes, hora y todas las cuotas")
    for target,spec in selectors.items():
        if isinstance(spec,str):
            spec={"css":spec}
        if (not isinstance(spec,dict) or
                not isinstance(spec.get("css"),str) or
                not 1<=len(spec["css"])<=180 or
                spec.get("attribute","text") not in ("text","datetime","content","data-odds","aria-label")):
            raise BadQuote("Selector no permitido: "+str(target))
    if value.get("mode") not in ("html","browser"):
        raise BadQuote("Modo requerido: html o browser")
    return value


def _select_text(document, spec):
    spec={"css":spec} if isinstance(spec,str) else spec
    matched=document.css(spec["css"])
    if len(matched)!=1:
        raise BadQuote("Selector ausente o ambiguo: "+spec["css"])
    node=matched[0]
    attr=spec.get("attribute","text")
    if attr=="text":
        raw=node.text
    else:
        raw=node.attrib.get(attr)
    text=str(raw or "").strip()
    if not text or len(text)>200:
        raise BadQuote("Valor vacío/excesivo en "+spec["css"])
    return text


def parse_html(html: str | bytes, profile: dict, observed_at=None) -> Quote:
    validate_profile(profile)
    if len(html)>3_000_000:
        raise BadQuote("HTML excesivo")
    from scrapling.parser import Selector
    document=Selector(content=html)
    visible=str(document.get_all_text() or "")[:15000]
    if BLOCK_RE.search(visible):
        raise BadQuote("Control de acceso / CAPTCHA: abortando")
    s=profile["selectors"]
    home=_select_text(document,s["home"])
    away=_select_text(document,s["away"])
    start=_select_text(document,s["kickoff"])
    labels=MARKETS[(profile["sport"],profile["market"])]
    prices={name:decimal_odds(_select_text(document,s[name])) for name in labels}
    return Quote(
        book=profile["book"],sport=profile["sport"],home=home,away=away,
        kickoff=aware(start),market=profile["market"],prices=prices,
        observed_at=aware(observed_at or datetime.now(timezone.utc)),
        source="permitted_web",url=profile["url"],
    )


def fetch_page(profile):
    """Una lectura normal; si hay 403 o un challenge NO intenta superarlo."""
    validate_profile(profile)
    url=profile["url"]
    book=profile["book"]
    if profile["mode"]=="html":
        req=Request(url,headers={"User-Agent":"ArbiiScan/1.0 (public-data-check)","Accept":"text/html"})
        try:
            with urlopen(req,timeout=20) as response:
                _domain(response.geturl(),book)
                if response.status!=200:
                    raise BadQuote("HTTP no disponible: "+str(response.status))
                if "html" not in str(response.headers.get("content-type","")).lower():
                    raise BadQuote("Respuesta no HTML")
                return response.read(3_000_001)
        except HTTPError as e:
            raise BadQuote("HTTP "+str(e.code)+" (sin evasión)") from None
        except URLError:
            raise BadQuote("No hay conexión con el sitio") from None

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(locale="es-ES",timezone_id="Europe/Madrid")
            response=page.goto(url,wait_until="domcontentloaded",timeout=24000)
            if response is None or response.status!=200:
                raise BadQuote("Navegación no disponible, HTTP "+
                               str(response.status if response else 0))
            page.wait_for_timeout(2500)
            _domain(page.url,book)
            return page.content()
        finally:
            browser.close()


def load_profiles(filepath: str):
    profiles=json.loads(Path(filepath).read_text(encoding="utf-8"))
    if not isinstance(profiles,list) or not 1<=len(profiles)<=12:
        raise BadQuote("La configuración requiere de 1 a 12 perfiles")
    for p in profiles:
        validate_profile(p)
    identifiers={(p["book"],p["url"],p["market"]) for p in profiles}
    if len(identifiers)!=len(profiles):
        raise BadQuote("Perfil duplicado")
    return profiles


def scrape_profiles(profiles, wait_seconds=3):
    if not profiles:
        return []
    readings=[]
    for index,profile in enumerate(profiles):
        if index:
            time.sleep(max(3,int(wait_seconds)))
        observed=datetime.now(timezone.utc)
        body=fetch_page(profile)
        reading=parse_html(body,profile,observed)
        readings.append(reading)
    return readings


def local_records(filepath):
    """Importa feeds autorizados en JSON para cualquier casa.

    No se accede a webs ni se transforma una cuota sin participantes,
    fecha, mercado, reglas, y fuente identificada.
    """
    from .engine import from_record
    data=json.loads(Path(filepath).read_text(encoding="utf-8"))
    if not isinstance(data,list) or len(data)>20000:
        raise BadQuote("Formato de feed inesperado")
    return [from_record(item) for item in data]
