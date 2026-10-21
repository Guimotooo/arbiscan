"""Consulta puntual del catálogo real de OddsPapi, con reserva de cuota."""
import os
from fuentes_es.oddspapi import call, remaining_quota
from urllib.request import urlopen
from urllib.parse import urlencode
import json

def catalog_call(endpoint,key):
    if endpoint not in ("sports","markets","bookmakers"):
        raise ValueError("Catálogo no permitido")
    url="https://api.oddspapi.io/v4/"+endpoint+"?"+urlencode({"apiKey":key,"language":"es"})
    with urlopen(url,timeout=25) as response:
        return json.load(response)

def run():
    key=os.getenv("ODDS_PAPI_KEY","").strip()
    if not key:
        print("Falta ODDS_PAPI_KEY; sin consultas.")
        return
    remaining=remaining_quota(call("account",{},key))
    print("Créditos antes del catálogo:",remaining)
    if remaining<40:
        print("Consulta omitida para preservar el plan gratuito.")
        return
    for endpoint in ("sports","markets","bookmakers"):
        rows=catalog_call(endpoint,key)
        if not isinstance(rows,list):
            print(endpoint, "respuesta inesperada")
            continue
        if endpoint=="sports":
            relevant=[r for r in rows if any(n in str(r.get("slug","")).lower() for n in ("soccer","football","basketball","tennis","american"))]
            print("Deportes:",[(r.get("sportId"),r.get("slug"),r.get("sportName")) for r in relevant])
        elif endpoint=="markets":
            relevant=[r for r in rows if r.get("sportId") in (10,11,12,14) and str(r.get("marketType","")).lower() in ("1x2","moneyline","winner","match_winner")]
            print("Mercados de ganador 1X2/2 vías:",[(r.get("sportId"),r.get("marketId"),r.get("marketType"),r.get("period"), [(o.get("outcomeId"),o.get("outcomeName")) for o in r.get("outcomes",[])]) for r in relevant[:30]])
        else:
            relevant=[r for r in rows if any(x in str(r).lower() for x in ("bet365.es","winamax.es","sportium.es","codere.es","bwin.es","betfair.es"))]
            print("Casas potenciales ES:",[str(r)[:260] for r in relevant[:20]])

if __name__=="__main__":run()
