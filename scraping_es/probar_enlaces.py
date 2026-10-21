"""Accessibility-only browser probe for user-supplied public match links.
Never logs page contents, cookies, credentials, or bookmaker account information.
Does not bypass bot checks, and does not collect odds or place wagers.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
from scraping_es.browser_scan import ALLOWED_HOSTS, BLOCK_TEXT

def main():
    urls=json.loads(Path("scraping_es/targets.json").read_text(encoding="utf8"))
    if set(urls)!=set(ALLOWED_HOSTS):
        raise ValueError("Unexpected list of bookmaker hosts")
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            for brand,url in urls.items():
                parts=urlsplit(url)
                if parts.scheme!="https" or parts.hostname not in ALLOWED_HOSTS[brand]:
                    raise ValueError("Unexpected external URL")
                page=browser.new_page(locale="es-ES",timezone_id="Europe/Madrid")
                try:
                    response=page.goto(url,wait_until="domcontentloaded",timeout=22000)
                    page.wait_for_timeout(4000)
                    actual_host=urlsplit(page.url).hostname
                    code=response.status if response is not None else None
                    try:
                        text=page.locator("body").inner_text(timeout=6000)[:100000]
                        size=len(text)
                        blocked=bool(BLOCK_TEXT.search(text))
                    except (BrowserTimeout,Exception):
                        size=0
                        blocked=False
                    if brand == "winamax.es" and code == 200:
                        # Comprobar si se mantiene la ruta de evento y no solo portada.
                        path_now=urlsplit(page.url).path
                        event_id="74165970"
                        selectors={
                            "main_nodes": page.locator("main").count(),
                            "loading_words": len(re.findall(r"\\bloading\\b", text, re.I)),
                            "event_id_visible": event_id in text,
                            "match_path_retained": event_id in path_now,
                            "odds_like_dom_nodes": page.locator("[data-testid*='odd'], [class*='odd'], [class*='Odd']").count(),
                        }
                        print("Winamax match rendering:", json.dumps(selectors, ensure_ascii=False))
                        print("Winamax page tail:", json.dumps(" ".join(text.split())[-800:], ensure_ascii=False))
                        excerpt=text[15000:17500]
                        print("Winamax content section:", json.dumps(" ".join(excerpt.split())[:1500],ensure_ascii=False))
                        headings=page.locator("h1,h2,h3").all_inner_texts()
                        print("Winamax headings:",json.dumps(headings[:25],ensure_ascii=False)[:1100])
                        print("Winamax has exact match marker:", "74165970" in page.content())
                        print("Winamax candidate odds elements:", json.dumps(page.locator("[class*=odd], [class*=Odd]").all_inner_texts()[-15:])[:800])
                        # Sólo texto público visible: buscar encabezados del mercado 1X2 en el evento, no en menú.
                        terms=["match result","match winner","full time result","1x2","result of the match","winner (90","90 minutes","resultado del partido"]
                        lower=text.casefold()
                        matched=[]
                        for term in terms:
                            start=0
                            while len(matched)<15:
                                pos=lower.find(term,start)
                                if pos<0:break
                                matched.append({"term":term,"position":pos,"excerpt":" ".join(text[max(0,pos-140):pos+340].split())})
                                start=pos+len(term)
                        print("Winamax 1X2 market labels:",json.dumps(matched[:15],ensure_ascii=False)[:3500])
                        # Identificar estructuras del DOM asociadas a nombres de equipos; no volcar HTML, scripts ni cookies.
                        context=page.evaluate("""() => {
                          const terms=['real madrid','rb leipzig','match result','1x2','full time result'];
                          const nodes=[...document.querySelectorAll('body *')].filter(e =>
                            e.children.length===0 && terms.some(t=>(e.textContent||'').toLowerCase().includes(t)));
                          return nodes.slice(-12).map(e=>({text:(e.innerText||e.textContent||'').trim().slice(0,90),
                            tag:e.tagName,cls:typeof e.className==='string'?e.className.slice(0,140):'',
                            parentText:(e.parentElement?.innerText||'').trim().slice(0,190),
                            parentClass:typeof e.parentElement?.className==='string'?e.parentElement.className.slice(0,140):''}));
                        }""")
                        print("Winamax event DOM nodes:",json.dumps(context,ensure_ascii=False)[:2800])

                    if brand == "winamax.es" and code == 200 and size:
                        clean=" ".join(text.split())
                        print("Winamax public page excerpt:", json.dumps(clean[:450], ensure_ascii=False))
                        print("Winamax decimal-like values:", len(re.findall(r"(?<!\\d)\\d{1,2}[,.]\\d{2}(?!\\d)", clean)))
                    print(json.dumps({"bookmaker":brand,"http_status":code,
                          "stayed_on_official_domain":actual_host in ALLOWED_HOSTS[brand],
                          "rendered_text_length":size,"has_access_challenge_text":blocked,
                          "document_title_available":bool(page.title())},ensure_ascii=False))
                except BrowserTimeout:
                    print(json.dumps({"bookmaker":brand,"error":"navigation_timeout"}))
                except Exception as exc:
                    print(json.dumps({"bookmaker":brand,"error":type(exc).__name__}))
                finally:
                    page.close()
        finally:
            browser.close()
if __name__=="__main__": main()
