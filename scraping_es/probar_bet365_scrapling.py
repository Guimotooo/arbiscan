"""Single read-only test of Scrapling against user-provided Bet365 ES public event URL.

Uses ordinary Fetcher and a separate standard browser renderer. Does not log
credentials, invoke private APIs, solve CAPTCHA, rotate proxies, or wager.
"""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlsplit
from scrapling.fetchers import Fetcher
from scrapling.parser import Selector

def main():
    url=json.loads(Path("scraping_es/targets.json").read_text(encoding="utf-8"))["bet365.es"]
    if urlsplit(url).hostname not in ("bet365.es","www.bet365.es"):
        raise ValueError("Dominio no permitido")
    print("Casa: bet365.es; evento indicado por usuario; prueba de solo lectura")
    try:
        response=Fetcher.get(url)
        status=int(getattr(response,"status",0) or 0)
        body=response.body
        print("Scrapling Fetcher HTTP:",status)
        if status==200:
            text=" ".join(str(Selector(content=body).get_all_text() or "").split())
            print("Texto estático (caracteres):",len(text))
            print("Ruta de evento E202645795 identificable en HTML:",b"E202645795" in body)
            print("Candidatos de valores cuota decimal en texto:",len(__import__("re").findall(r"(?<!\d)\d{1,2}[.,]\d{2}(?!\d)",text)))
        else:
            print("No se interpreta contenido de respuesta no exitosa")
    except Exception as error:
        print("Error Fetcher:",type(error).__name__)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            try:
                page=browser.new_page(locale="es-ES",timezone_id="Europe/Madrid")
                nav=page.goto(url,wait_until="domcontentloaded",timeout=25000)
                page.wait_for_timeout(4500)
                status=nav.status if nav else 0
                html=page.content()
                final=urlsplit(page.url)
                text=" ".join(str(Selector(content=html).get_all_text() or "").split())
                print("Scrapling + Chromium HTTP:",status)
                print("Dominio oficial conservado:",final.hostname in ("bet365.es","www.bet365.es"))
                print("Texto renderizado (caracteres):",len(text))
                print("Ruta evento E202645795 en HTML:", "E202645795" in html)
                print("Cuotas decimales candidatas en texto (no verificadas):",len(__import__("re").findall(r"(?<!\d)\d{1,2}[.,]\d{2}(?!\d)",text)))
                print("Texto compatible con bloqueo:",bool(__import__("re").search(r"access denied|captcha|verify you are human|acceso denegado",text,__import__("re").I)))
                print("Datos de mercado 1X2 confirmados:",False)
            finally:
                browser.close()
    except Exception as error:
        print("Error Chromium:",type(error).__name__)
    print("Alertas enviadas:",0)

if __name__=="__main__":
    main()
