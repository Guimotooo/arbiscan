"""Estado observable de los escaneos reales para Telegram, sin enviar alertas.

El endpoint remoto está protegido por el secreto de difusión. El estado
identifica expresamente la fuente y nunca inventa arbitrajes ni cuotas.
"""
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

def publish_scan_status(*, worker_url, secret, state, books=(),
                        fixture_count=0, candidates=0, confirmed=0, sent=0,
                        opener=urlopen, checked_at=None):
    if not secret or not worker_url:
        return False
    address=urlsplit(worker_url.rstrip("/"))
    if (address.scheme!="https" or not address.hostname or
        not address.hostname.endswith(".workers.dev") or
        address.username or address.password or address.port or
        address.path or address.query or address.fragment):
        return False
    if state not in ("running","finished","failed","skipped"):
        raise ValueError("Estado de escaneo no válido")
    counts=(fixture_count,candidates,confirmed,sent)
    if any(type(x) is not int or x<0 or x>100000 for x in counts):
        raise ValueError("Contadores no válidos")
    timestamp=(checked_at or datetime.now(timezone.utc)).isoformat()
    data=json.dumps({"state":state,"checked_at":timestamp,"books":list(books),
                     "fixture_count":fixture_count,"candidates":candidates,
                     "confirmed":confirmed,"sent":sent}).encode("utf-8")
    request=Request(worker_url.rstrip("/")+"/scan-status",data=data,method="POST",
                    headers={"Authorization":"Bearer "+secret.strip(),
                             "Content-Type":"application/json"})
    try:
        with opener(request,timeout=12) as response:
            return response.status==200 and json.load(response).get("ok") is True
    except (HTTPError,URLError,TimeoutError,OSError,ValueError):
        return False
