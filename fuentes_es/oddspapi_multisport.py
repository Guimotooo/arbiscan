"""ArbiiScan v2: rotación multideporte y cinco operadores españoles verificados en el catálogo.

Cuota gratuita: una ronda diaria = 1 catálogo de torneos + 5 casas (6 créditos).
Si hay posibles arbitrajes, repetir las cinco consultas y exigir coincidencia.
Nunca garantiza aceptación de cuotas en el cupón de las casas.
"""
from __future__ import annotations
import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from itertools import product, combinations
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

from scanner import allocate
from fuentes_es.oddspapi import utc, remaining_quota, broadcast_alert, BASE

BOOKS = ("bet365.es", "winamax.es", "betfair.es", "bwin.es", "codere.es",
         "888sport.es", "betway.es", "goldenpark.es", "leovegas.es", "paf.es", "pokerstars.es")
# IDs contrastados en GET /v4/sports y GET /v4/markets el 21-10-2026.
SPORTS = (
    (10, "Fútbol", "101", {"101": "1", "102": "X", "103": "2"}, "1X2 (90 minutos)"),
    (11, "Baloncesto", "111", {"111": "1", "112": "2"}, "Ganador del partido"),
    (12, "Tenis", "121", {"121": "1", "122": "2"}, "Ganador del partido"),
    (14, "Fútbol americano", "141", {"141": "1", "142": "2"}, "Ganador del partido"),
)
MAX_AGE_SECONDS = 7 * 86400
MAX_LEAGUES_PER_SCAN = 5
MIN_LEAD_MINUTES = 15
MAX_ALERTS = 30
MIN_ROI = 0.5
MIN_CREDITS_FOR_SCAN = 22

def api(endpoint, params, key, opener=urlopen):
    if endpoint not in ("account", "tournaments", "odds-by-tournaments"):
        raise ValueError("Endpoint no permitido")
    query = urlencode({**params, "apiKey": key})
    req = Request(BASE + "/" + endpoint + "?" + query, headers={"Accept": "application/json"})
    try:
        with opener(req, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        reason=exc.read(700).decode("utf-8",errors="replace").replace(key,"[REDACTED]")
        if (endpoint=="odds-by-tournaments" and exc.code==400 and
            "Invalid bookmaker specified" in reason and
            "does not have any fixtures available" in reason):
            print("Sin encuentros en la fuente:",params.get("bookmaker"))
            return []
        raise RuntimeError("OddsPapi HTTP " + str(exc.code) + " en " + endpoint + " · " + reason[:380]) from None
    except URLError:
        raise RuntimeError("Error de conexión a OddsPapi") from None

def choose_sport(now):
    # A cada ejecución programada le corresponde un deporte distinto.
    return SPORTS[now.date().toordinal() % len(SPORTS)]

def choose_tournaments(rows, now):
    if not isinstance(rows, list):
        raise ValueError("Respuesta de torneos no válida")
    eligible = sorted({
        int(row["tournamentId"])
        for row in rows
        if isinstance(row, dict)
        and str(row.get("tournamentId", "")).isdigit()
        and int(row.get("futureFixtures") or 0) + int(row.get("upcomingFixtures") or 0) > 0
    })
    if not eligible:
        return []
    # Rota por todas las competiciones con partidos; nunca por popularidad.
    k=min(MAX_LEAGUES_PER_SCAN, len(eligible))
    index=now.date().toordinal() % len(eligible)
    return [eligible[(index+i) % len(eligible)] for i in range(k)]

def join_results(per_book):
    joined={}
    for brand, response in per_book.items():
        rows=response if isinstance(response,list) else response.get("data") if isinstance(response,dict) else None
        if not isinstance(rows,list):
            raise ValueError("Respuesta de cuotas no reconocida")
        for row in rows:
            if not isinstance(row,dict) or not row.get("fixtureId"):
                continue
            odds=row.get("bookmakerOdds")
            if not isinstance(odds,dict) or brand not in odds:
                continue
            fid=str(row["fixtureId"])
            if fid not in joined:
                joined[fid]={**row, "bookmakerOdds": {brand: odds[brand]}}
            else:
                prior=joined[fid]
                for field in ("sportId","tournamentId","startTime","participant1Id","participant2Id"):
                    if prior.get(field)!=row.get(field):
                        raise ValueError("Los datos del mismo partido no coinciden")
                prior["bookmakerOdds"][brand]=odds[brand]
    return list(joined.values())

def valid_prices(fixture, sport, now):
    sid, _, market_id, outcomes, _ = sport
    if fixture.get("sportId")!=sid or fixture.get("statusId")!=0:
        return {}
    kickoff=utc(fixture.get("startTime"))
    if not kickoff or kickoff<=now+timedelta(minutes=MIN_LEAD_MINUTES):
        return {}
    books=fixture.get("bookmakerOdds")
    if not isinstance(books,dict):
        return {}
    result={}
    for brand in BOOKS:
        book=books.get(brand)
        if not isinstance(book,dict) or book.get("bookmakerIsActive") is not True or book.get("suspended") is not False:
            continue
        market=(book.get("markets") or {}).get(market_id)
        if not isinstance(market,dict) or market.get("marketActive") is not True:
            continue
        selections=market.get("outcomes") or {}
        clean={}
        for oid,label in outcomes.items():
            outcome=selections.get(oid)
            if not isinstance(outcome,dict):
                break
            player=(outcome.get("players") or {}).get("0")
            if not isinstance(player,dict) or player.get("active") is not True:
                break
            stamp=utc(player.get("changedAt"))
            if not stamp or not (0 <= (now-stamp).total_seconds() <= MAX_AGE_SECONDS):
                break
            try:
                price=float(player["price"])
            except (KeyError, TypeError, ValueError):
                break
            if not 1.01 <= price < 1000:
                break
            clean[label]=price
        if len(clean)==len(outcomes):
            result[brand]=clean
    return result

def evaluate_fixture_options(fixture, sport, now):
    """Mejor arbitraje por cada conjunto de casas usado.

    Permite que usuarios con pares diferentes reciban una alternativa que
    realmente pueden apostar, sin obligarles a usar la oferta global.
    """
    quotes=valid_prices(fixture,sport,now)
    labels=list(sport[3].values())
    if len(quotes)<2:
        return []
    names=[str(fixture.get("participant1Name") or ""),str(fixture.get("participant2Name") or "")]
    if not all(names) or not fixture.get("fixtureId"):
        return []
    best_by_set={}
    for combination in product(list(quotes),repeat=len(labels)):
        brands=frozenset(combination)
        if len(brands)<2:
            continue
        offers=[{"bookmaker":brand,"bookmaker_key":brand,"outcome":label,
                 "price":quotes[brand][label]} for brand,label in zip(combination,labels)]
        calculation=allocate(100.0, offers)
        if not calculation or calculation["roi_percent"]<MIN_ROI:
            continue
        prior=best_by_set.get(brands)
        if prior is None or calculation["profit"]>prior["profit"]:
            best_by_set[brands]=calculation
    return [{
        "fixture_id":str(fixture["fixtureId"]),"sport":sport[1],
        "market":sport[4],"event":names[0]+" vs "+names[1],
        "start":utc(fixture["startTime"]).isoformat(), **calculation
    } for calculation in best_by_set.values()]

def evaluate_fixture(fixture,sport,now):
    choices=evaluate_fixture_options(fixture,sport,now)
    return max(choices,key=lambda x:x["profit"]) if choices else None

def scan(rows,sport,now):
    found=[]
    for row in rows:
        found.extend(evaluate_fixture_options(row,sport,now))
    return sorted(found,key=lambda x:x["profit"],reverse=True)

def signature(opp):
    return (opp["fixture_id"],opp["sport"],opp["market"],opp["start"],
            tuple((q["bookmaker_key"],q["outcome"],q["price"]) for q in opp["offers"]))

def double_check(first,second,now):
    signatures={signature(value) for value in second}
    return [{**v,"observed_at":now.isoformat()} for v in first if signature(v) in signatures]

def format_alert(opp):
    out=["ARBIISCAN | POSIBLE ARBITRAJE NO CONFIRMADO",
         "Deporte: "+opp["sport"],"Partido: "+opp["event"],
         "Mercado: "+opp["market"],"Inicio: "+opp["start"],
         "Doble lectura de OddsPapi: "+opp["observed_at"],"Capital ilustrativo: 100 €"]
    out.extend(f"{v['bookmaker']} | {v['outcome']} @ {v['price']:.2f} → {v['stake']:.2f} €"
               for v in opp["offers"])
    out.append(f"Beneficio teórico mínimo: {opp['profit']:.2f} € ({opp['roi_percent']:.2f}%).")
    out.append("Cuotas NO confirmadas en cupón. Comprueba mercados, reglamento, disponibilidad y límites antes de apostar.")
    return "\n".join(out)

def book_selection(now, pair_demand=None):
    """Elige hasta cinco casas según parejas de usuarios, o rota todo el catálogo."""
    available=list(BOOKS)
    max_books=5
    valid={}
    if isinstance(pair_demand,dict):
        for key,value in pair_demand.items():
            names=str(key).split("|")
            if len(names)!=2 or names[0]==names[1] or not set(names).issubset(BOOKS):
                continue
            if isinstance(value,int) and 0 < value < 100000:
                valid[frozenset(names)]=value
    if valid:
        # 11 choose 5 = 462 combinaciones: suficiente para optimización exacta.
        rotation={slug:(i-now.date().toordinal())%len(BOOKS)
                  for i,slug in enumerate(BOOKS)}
        return tuple(max(combinations(available,max_books), key=lambda chosen: (
            sum(weight for pair,weight in valid.items() if pair.issubset(chosen)),
            -sum(rotation[name] for name in chosen)
        )))
    # Sin preferencias activas: priorizamos continuidad de las dos fuentes ya probadas,
    # mientras rotamos el resto para explorar nuevos operadores españoles.
    extras=[b for b in available if b not in ("bet365.es","winamax.es")]
    index=now.date().toordinal()%len(extras)
    return ("bet365.es","winamax.es") + tuple(extras[(index+i)%len(extras)] for i in range(3))

def subscriber_demand(worker_url, secret):
    if not worker_url.startswith("https://") or not worker_url.endswith(".workers.dev") or not secret:
        return {}
    req=Request(worker_url.rstrip("/")+"/scan-preferences",
                headers={"Authorization":"Bearer "+secret,"Accept":"application/json","User-Agent":"curl/8.5.0"})
    try:
        with urlopen(req,timeout=18) as response:
            data=json.load(response)
        return data.get("pairs",{}) if isinstance(data,dict) else {}
    except (HTTPError,URLError,ValueError,TimeoutError):
        print("No disponible la demanda agregada; aplicando rotación automática.")
        return {}

def run():
    key=os.getenv("ODDS_PAPI_KEY","").strip()
    if not key:
        print("Falta API key; no se consulta.")
        return
    now=datetime.now(timezone.utc)
    sport=choose_sport(now)
    worker=os.getenv("ARBI_WORKER_URL","").strip()
    secret=os.getenv("WEBHOOK_SECRET","").strip()
    books=book_selection(now,subscriber_demand(worker,secret))
    print("Casas elegidas según suscriptores:",", ".join(books))
    remaining=remaining_quota(api("account",{},key))
    print("Créditos disponibles:",remaining,"Deporte de la ronda:",sport[1])
    if remaining<MIN_CREDITS_FOR_SCAN:
        print("Reserva de créditos alcanzada; no se consulta.")
        return
    tournament_list=api("tournaments",{"sportId":sport[0],"language":"es"},key)
    ids=choose_tournaments(tournament_list,now)
    print("Torneos cubiertos en esta ronda:",len(ids))
    if not ids:
        return
    params={"tournamentIds":",".join(str(i) for i in ids),"language":"es","verbosity":3}
    first={}
    for index,brand in enumerate(books):
        if index: time.sleep(2.5)
        first[brand]=api("odds-by-tournaments",{**params,"bookmaker":brand},key)
    data=join_results(first)
    print("Partidos emparejados:",len(data))
    candidates=scan(data,sport,datetime.now(timezone.utc))
    print("Candidatos matemáticos:",len(candidates))
    if not candidates:
        return
    # No repetir si la cuota restante está al límite. Consumiremos como máximo 5 consultas adicionales.
    if remaining<MIN_CREDITS_FOR_SCAN+5:
        print("Sin presupuesto de confirmación.")
        return
    time.sleep(3)
    second={}
    for index,brand in enumerate(books):
        if index: time.sleep(2.5)
        second[brand]=api("odds-by-tournaments",{**params,"bookmaker":brand},key)
    confirmed=double_check(candidates,scan(join_results(second),sport,datetime.now(timezone.utc)),datetime.now(timezone.utc))
    print("Candidatos coincidentes en dos lecturas:",len(confirmed))
    if os.getenv("ODDSPAPI_ENABLE_ALERTS")!="true":
        print("Prueba sin envío de Telegram.")
        return
    worker=os.getenv("ARBI_WORKER_URL","").strip()
    secret=os.getenv("WEBHOOK_SECRET","").strip()
    if not worker or not secret:
        print("Faltan credenciales de difusión; no se envía.")
        return
    for item in confirmed[:MAX_ALERTS]:
        books=sorted({v["bookmaker_key"] for v in item["offers"]})
        event_key="multi:"+hashlib.sha256(repr((item["fixture_id"],item["sport"],item["market"],item["start"])).encode()).hexdigest()[:24]
        result=broadcast_alert(worker,secret,format_alert(item),event_key,books)
        print("Difusión:",result)

if __name__=="__main__":
    run()
