"""Conector de solo lectura a la API oficial de Betfair Exchange.

Utiliza credenciales del usuario en variables de entorno. La clave de desarrollo
puede devolver precios retrasados (1-180 s): NUNCA genera avisos de arbitraje.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

ENDPOINT = "https://api.betfair.com/exchange/betting/json-rpc/v1"
API_METHODS = {"listMarketCatalogue", "listMarketBook"}

def rpc(method, params, *, app_key, session_token, opener=urlopen):
    if method not in API_METHODS:
        raise ValueError("Método de Betfair no permitido")
    if not app_key or not session_token:
        raise ValueError("Faltan BETFAIR_APP_KEY o BETFAIR_SESSION_TOKEN")
    body = json.dumps({"jsonrpc": "2.0", "method": "SportsAPING/v1.0/" + method,
                       "params": params, "id": 1}).encode("utf-8")
    request = Request(ENDPOINT, data=body, method="POST", headers={
        "X-Application": app_key, "X-Authentication": session_token,
        "Content-Type": "application/json", "Accept": "application/json"})
    with opener(request, timeout=20) as response:
        payload = json.load(response)
    if "error" in payload:
        error = payload["error"]
        raise RuntimeError("Error de Betfair: " + str(error.get("message", "desconocido")))
    if not isinstance(payload.get("result"), list):
        raise ValueError("Respuesta inesperada de Betfair")
    return payload["result"]

def snapshot(*, app_key, session_token, now=None, opener=urlopen):
    """Obtiene candidatos prepartido; solo información, no cuotas surebet verificadas."""
    now = now or datetime.now(timezone.utc)
    until = now + timedelta(days=2)
    catalog = rpc("listMarketCatalogue", {
        "filter": {"marketTypeCodes": ["MATCH_ODDS"],
                   "marketStartTime": {"from": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                       "to": until.strftime("%Y-%m-%dT%H:%M:%SZ")}},
        "maxResults": "30", "marketProjection": ["EVENT", "RUNNER_DESCRIPTION", "MARKET_START_TIME"],
        "sort": "FIRST_TO_START", "locale": "es"
    }, app_key=app_key, session_token=session_token, opener=opener)
    if not catalog:
        return []
    ids = [str(m["marketId"]) for m in catalog if m.get("marketId")]
    if not ids:
        return []
    books = rpc("listMarketBook", {"marketIds": ids,
        "priceProjection": {"priceData": ["EX_BEST_OFFERS"]}},
        app_key=app_key, session_token=session_token, opener=opener)
    by_id = {str(b.get("marketId")): b for b in books}
    results = []
    for market in catalog:
        book = by_id.get(str(market.get("marketId")), {})
        if book.get("status") != "OPEN" or book.get("inplay") is True:
            continue
        available = {r.get("selectionId"): r.get("ex", {}).get("availableToBack", [])
                     for r in book.get("runners", []) if r.get("status") == "ACTIVE"}
        selections = []
        for runner in market.get("runners", []):
            levels = available.get(runner.get("selectionId"), [])
            if not levels:
                continue
            best = levels[0]
            try:
                price, size = float(best["price"]), float(best["size"])
            except (ValueError, TypeError, KeyError):
                continue
            if not (1 < price < 1000 and size > 0):
                continue
            selections.append({"selection": runner.get("runnerName", ""),
                               "price": price, "available_eur_unverified": size})
        results.append({
            "provider": "betfair_exchange_official",
            "jurisdiction": "UNVERIFIED",  # Una cuenta ES no se deduce de la API.
            "market_id": str(market.get("marketId")), "event": market.get("event", {}).get("name", ""),
            "market": "MATCH_ODDS", "runners": selections,
            "source": "exchange", "price_delayed_possible": True,
            "captured_at": now.isoformat(), "eligible_for_alerts": False
        })
    return results

def main():
    key = os.getenv("BETFAIR_APP_KEY", "").strip()
    token = os.getenv("BETFAIR_SESSION_TOKEN", "").strip()
    if not key or not token:
        print("SIN DATOS: configurar BETFAIR_APP_KEY y BETFAIR_SESSION_TOKEN como secretos; no se emiten alertas.")
        return
    data = snapshot(app_key=key, session_token=token)
    print("Mercados consultados:", len(data))
    print("Resultados de prueba; precios potencialmente retrasados y jurisdicción sin verificar.")
    # No registrar tokens ni cuotas como oportunidades de arbitraje.
    print("Mercados con cotizaciones:", sum(bool(x["runners"]) for x in data))
    print("Alertas enviadas: 0")

if __name__ == "__main__":
    main()
