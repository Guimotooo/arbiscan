"""One-shot, read-only Scrapling probe for the public Winamax match URL.

Only prints HTTP/render facts and never logs cookies, credentials or full HTML.
Does not attempt to circumvent anti-bot mechanisms.
"""
from __future__ import annotations
import json
from pathlib import Path

def main():
    from scrapling.fetchers import Fetcher
    from scrapling.parser import Selector
    urls=json.loads(Path("scraping_es/targets.json").read_text(encoding="utf-8"))
    url=urls["winamax.es"]
    print("Comprobación pública: Winamax ES con Scrapling Fetcher normal")
    try:
        result=Fetcher.get(url)
        status=int(getattr(result,"status",0) or 0)
        html=result.body
        page=Selector(content=html)
        extracted=" ".join(str(page.get_all_text() or "").split())
        print("Código HTTP:",status)
        print("Longitud de texto:",len(extracted))
        print("El enlace contiene ID de partido:", "74165970" in url)
        print("HTML contiene ID de partido:", b"74165970" in html)
        print("Contenido parece carga JS:", "loading" in extracted.lower())
        print("Bloqueo detectado:",status in (401,403,429))
        print("Avisos Telegram enviados: 0")
    except Exception as exc:
        print("Fallo del lector público:",type(exc).__name__)
        print("Avisos Telegram enviados: 0")
if __name__=="__main__":main()
