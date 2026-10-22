"""Herramienta de línea de comandos para el scraper y motor de ArbiiScan.

python -m motor_propio.run --demo
python -m motor_propio.run --feed example.json
python -m motor_propio.run --profiles scraping_es/profiles_local.json
python -m motor_propio.run --odds-papi-audit

Por defecto NUNCA se mandan alertas. Para páginas públicas se requieren
permisos de extracción confirmados; se detiene ante respuestas 403/CAPTCHA.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime,timedelta,timezone

from .engine import Quote, BadQuote, opportunities, confirm, fingerprint, alert
from .web import load_profiles, scrape_profiles, local_records


def _render(ops, label):
    print(label,"candidatos:",len(ops))
    for item in ops[:5]:
        print(" -",item["sport"],item["home"],"vs",item["away"],
              "mercado",item["market"],"casas",",".join(item["books"]),
              "ROI teórico",item["roi_percent"]+" %")


def demo():
    now=datetime.now(timezone.utc)
    kickoff=now+timedelta(days=1)
    def quote(book, prices):
        return Quote(book=book,sport="soccer",home="Equipo Demo Local",
                     away="Equipo Demo Visitante",kickoff=kickoff,
                     market="1x2:regulation",prices=prices,
                     observed_at=now,source="fixture_test")
    first=[
        quote("bet365.es",{"1":"3.6","X":"3.8","2":"1.8"}),
        quote("winamax.es",{"1":"1.8","X":"3.0","2":"3.8"}),
    ]
    before=opportunities(first,now)
    after=opportunities(first,now+timedelta(seconds=3))
    confirmed=confirm(before,after,now,now+timedelta(seconds=3))
    _render(confirmed,"DEMO CON PRECIOS INVENTADOS; NO SON CUOTAS REALES.")
    if confirmed:print(alert(confirmed[0]))
    print("Telegram: NO SE ENVÍAN ALERTAS EN LA DEMO")


def run_feed(path):
    results=local_records(path)
    now=datetime.now(timezone.utc)
    _render(opportunities(results,now),"FEED LOCAL - SOLO UNA LECTURA")
    print("Las oportunidades de este feed no se envían: falta segunda lectura.")


def run_web(path, send=False):
    from fuentes_es.oddspapi import broadcast_alert
    profiles=load_profiles(path)
    first_time=datetime.now(timezone.utc)
    before=scrape_profiles(profiles)
    first=opportunities(before,datetime.now(timezone.utc))
    _render(first,"PRIMERA LECTURA WEB")
    if not first:
        print("Sin candidatos: no se consultan las páginas una segunda vez.")
        return
    time.sleep(3)
    second_time=datetime.now(timezone.utc)
    after=scrape_profiles(profiles)
    second=opportunities(after,datetime.now(timezone.utc))
    matches=confirm(first,second,first_time,second_time)
    _render(matches,"DOS LECTURAS COINCIDENTES")
    if not send:
        print("DRY RUN: sin alertas Telegram. Ejecuta --send solo cuando las fuentes estén autorizadas.")
        return
    worker=os.getenv("ARBI_WORKER_URL","").strip()
    secret=os.getenv("WEBHOOK_SECRET","").strip()
    if not worker or not secret:
        raise BadQuote("Faltan las credenciales del Worker para enviar mensajes")
    for item in matches[:10]:
        response=broadcast_alert(worker,secret,alert(item),fingerprint(item),item["books"])
        print("Alerta candidata:",response)


def run_provider_audit():
    """Verifica cotizaciones de Bet365 ES y Winamax ES con pocos créditos.

    Esta operación no usa scraping directo y NO envía alertas; puede haber
    datos que todavía no se han actualizado en los cupones oficiales.
    """
    from fuentes_es.oddspapi import remaining_quota
    from fuentes_es.oddspapi_multisport import api,choose_tournaments,join_results
    from .oddspapi_adapter import convert_fixtures

    key=os.getenv("ODDS_PAPI_KEY","").strip()
    if not key:
        print("No hay ODDS_PAPI_KEY: consulta omitida.")
        return
    left=remaining_quota(api("account",{},key))
    print("Créditos disponibles antes:",left)
    if left<40:
        print("La reserva de créditos impide esta prueba.")
        return
    now=datetime.now(timezone.utc)
    tournaments=api("tournaments",{"sportId":10,"language":"es"},key)
    ids=choose_tournaments(tournaments,now)
    if not ids:
        print("El proveedor no ofrece torneos elegibles en esta ronda.")
        return
    by_book={}
    params={"tournamentIds":",".join(map(str,ids)),"language":"es","verbosity":3}
    for index,book in enumerate(("bet365.es","winamax.es")):
        if index:time.sleep(2.5)
        by_book[book]=api("odds-by-tournaments",{**params,"bookmaker":book},key)
    merged=join_results(by_book)
    parsed=convert_fixtures(merged,datetime.now(timezone.utc))
    fresh=sum(q.valid_at(datetime.now(timezone.utc)) for q in parsed)
    print("Eventos de fútbol consultados:",len(merged))
    print("Cotizaciones completas aceptadas como registros:",len(parsed))
    print("Cotizaciones suficientemente recientes para alertas:",fresh)
    _render(opportunities(parsed,datetime.now(timezone.utc)),
            "ARBITRAJES MATEMÁTICOS DE FUENTE LICENCIADA (NO CONFIRMADOS EN CUPONES)")
    print("No se enviaron avisos: prueba de una sola lectura de OddsPapi.")


def main():
    parser=argparse.ArgumentParser(description="ArbiiScan motor de cuotas propio")
    sources=parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--demo",action="store_true")
    sources.add_argument("--feed",help="JSON normalizado de feed autorizado")
    sources.add_argument("--profiles",help="JSON con URLs de páginas permitidas y selectores")
    sources.add_argument("--odds-papi-audit",action="store_true")
    parser.add_argument("--send",action="store_true",
                        help="Solo para --profiles, después de dos lecturas coincidentes")
    args=parser.parse_args()
    if args.send and not args.profiles:
        parser.error("--send solo está permitido para páginas verificadas con --profiles")
    if args.demo:demo()
    elif args.feed:run_feed(args.feed)
    elif args.profiles:run_web(args.profiles,args.send)
    else:run_provider_audit()


if __name__=="__main__":
    main()
