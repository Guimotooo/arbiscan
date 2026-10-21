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
                        text=page.locator("body").inner_text(timeout=3000)[:12000]
                        size=len(text)
                        blocked=bool(BLOCK_TEXT.search(text))
                    except (BrowserTimeout,Exception):
                        size=0
                        blocked=False
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
