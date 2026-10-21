"""ArbiiScan: cálculo de cuotas aportadas por el usuario, sin API de pago.

Se ejecuta brevemente desde GitHub Actions y responde en Telegram.
NO verifica cuotas en casas de apuestas ni realiza apuestas.
"""
from __future__ import annotations
import itertools
import json
import os
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

FAMILIES = {
    "bet365": "Bet365", "sportium": "Sportium", "winamax": "Winamax",
    "betfair": "Betfair", "bwin": "bwin", "codere": "Codere",
    "luckia": "Luckia", "william hill": "William Hill", "betway": "Betway",
    "retabet": "RETAbet", "sportybet": "SportyBet",
}
TEMPLATE = """/comparar
Deporte: futbol
Partido: Barcelona vs Real Madrid
Mercado: total goles 2.5 (90 minutos)
Capital: 100
Bet365 ES | mas | 2.10
Sportium ES | menos | 2.05

Cuotas INVENTADAS de ejemplo: sustitúyelas por precios actuales comprobados."""
HELP = ("ArbiiScan · Calculadora gratuita de arbitraje.\n\n"
        "Envía /plantilla y copia el formato. Sustituye partido, mercado, "
        "casas y cuotas, y envíalo en un solo mensaje /comparar.\n"
        "Las cifras introducidas NO se verifican en las casas de apuestas. "
        "No se realizan apuestas. El sistema comprueba los mensajes "
        "periódicamente mediante GitHub Actions (no responde al instante).")

def norm(s):
    return str(s).strip().lower().translate(
        str.maketrans("áéíóúüñ", "aeiouun"))

def num(v):
    try:
        d = Decimal(str(v).strip().replace(",", "."))
    except InvalidOperation as e:
        raise ValueError("Cuota o importe no numérico") from e
    if not d.is_finite():
        raise ValueError("Cuota o importe no válido")
    return d

def market_info(text, sport):
    m, s = norm(text), norm(sport)
    if m.startswith("1x2"):
        if "fut" not in s and "soccer" not in s:
            raise ValueError("1X2 solo se admite para fútbol")
        if not ("90" in m or "reglament" in m):
            raise ValueError("Especifica 1X2 (90 minutos)")
        return ("1", "X", "2")
    if m.startswith("ganador"):
        if "fut" in s:
            raise ValueError("En fútbol usa 1X2 para cubrir el empate")
        if "balonc" in s or "nba" in s or "basket" in s:
            if not ("prorroga" in m or re.search(r"\bot\b", m)):
                raise ValueError("Indica Ganador (incluye prórroga)")
        elif "tenis" not in s:
            raise ValueError("Ganador 2 vías: solo tenis o baloncesto")
        return ("1", "2")
    match = re.search(
        r"(?:total\s+(?:de\s+)?(?:goles|puntos|juegos)|mas\s*/\s*menos)\s+(\d+(?:[.,]\d+)?)", m)
    if not match:
        raise ValueError("Mercado no admitido: usa 1X2, ganador o total x.5")
    if (num(match.group(1))*2) % 2 != 1:
        raise ValueError("Solo totales con línea .5, sin reembolso")
    if "fut" in s and not ("90" in m or "reglament" in m):
        raise ValueError("En fútbol indica 90 minutos")
    if ("balonc" in s or "nba" in s) and not (
            "prorroga" in m or re.search(r"\bot\b", m)):
        raise ValueError("En baloncesto indica si incluye prórroga")
    return ("MAS", "MENOS")

def parse_message(text):
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if not lines or not lines[0].lower().startswith("/comparar"):
        raise ValueError("El mensaje debe empezar por /comparar")
    fields, picks = {}, []
    for line in lines[1:]:
        if ":" in line and "|" not in line:
            k,v = line.split(":",1)
            if norm(k) in ("deporte","partido","mercado","capital"):
                fields[norm(k)] = v.strip()
        elif "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 3:
                raise ValueError("Formato: Casa ES | resultado | 2.10")
            title, selection, price = parts
            n = norm(title).replace(" espana"," es")
            spanish = n.endswith(" es")
            brand_key = n[:-3].strip() if spanish else n
            if "exchange" in brand_key:
                raise ValueError("Betfair Exchange necesita calcular comisiones")
            brand = FAMILIES.get(brand_key)
            if not brand:
                raise ValueError("Casa no reconocida: " + title)
            quote = num(price)
            if quote <= 1 or quote >= 1000:
                raise ValueError("Cuotas válidas: entre 1 y 1000")
            picks.append({"brand": brand, "bookmaker": brand + (" ES" if spanish else ""),
                          "raw": norm(selection), "odds": quote})
    for k in ("deporte","partido","mercado","capital"):
        if not fields.get(k):
            raise ValueError("Falta el campo " + k)
    capital = num(fields["capital"])
    if not 0 < capital <= 100000:
        raise ValueError("Capital fuera de rango")
    outcomes = market_info(fields["mercado"], fields["deporte"])
    names = {"mas":"MAS","over":"MAS","menos":"MENOS","under":"MENOS",
             "local":"1","home":"1","1":"1","x":"X","draw":"X",
             "empate":"X","visitante":"2","away":"2","2":"2"}
    for p in picks:
        p["selection"] = names.get(p["raw"])
        if p["selection"] not in outcomes:
            raise ValueError("Selección incompatible: " + p["raw"])
    if len(picks) < 2:
        raise ValueError("Introduce dos o más cuotas")
    return {"event": fields["partido"],"sport": fields["deporte"],
            "market": fields["mercado"],"capital": capital,
            "outcomes": outcomes, "picks": picks}

def allocate(bankroll, selected):
    cents = int((bankroll * 100).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
    inverse = [Decimal(1)/p["odds"] for p in selected]
    denom = sum(inverse)
    if denom >= 1:
        return None
    raw = [Decimal(cents)*n/denom for n in inverse]
    stakes = [int(x) for x in raw]
    remainder = cents - sum(stakes)
    for i in sorted(range(len(stakes)), key=lambda i:raw[i]-stakes[i],
                    reverse=True)[:remainder]:
        stakes[i] += 1
    payouts = [Decimal(stakes[i])/100*p["odds"]
               for i,p in enumerate(selected)]
    profit = min(payouts)-Decimal(cents)/100
    if profit <= 0:
        return None
    return {"stakes": [Decimal(s)/100 for s in stakes],
            "profit": profit.quantize(Decimal(".01"),rounding=ROUND_HALF_UP),
            "roi": (profit/(Decimal(cents)/100)*100).quantize(
                Decimal(".01"),rounding=ROUND_HALF_UP)}

def evaluate(p):
    by_outcome = [[q for q in p["picks"] if q["selection"] == name]
                  for name in p["outcomes"]]
    missing = [name for name,quotes in zip(p["outcomes"],by_outcome) if not quotes]
    if missing:
        raise ValueError("Falta cubrir: " + ", ".join(missing))
    best = None
    for chosen in itertools.product(*by_outcome):
        if len({q["brand"] for q in chosen}) < 2:
            continue
        calc = allocate(p["capital"],chosen)
        if calc and (best is None or calc["profit"] > best[1]["profit"]):
            best = chosen,calc
    return best

def render(p, result):
    out = (f"ARBIISCAN · COMPARACIÓN MANUAL\n"
           f"⚠️ CUOTAS APORTADAS POR EL USUARIO, NO VERIFICADAS\n\n"
           f"Evento: {p['event']}\nDeporte: {p['sport']}\n"
           f"Mercado: {p['market']}\nCapital: {p['capital']:.2f} €\n\n")
    if result is None:
        return out + "❌ No se detecta arbitraje matemático con esas cuotas."
    chosen, calc = result
    for selection,q,stake in zip(p["outcomes"],chosen,calc["stakes"]):
        out += (f"• {q['bookmaker']}: {selection} a cuota "
                f"{q['odds']} → {stake:.2f} €\n")
    out += (f"\nBeneficio mínimo teórico: +{calc['profit']:.2f} € "
            f"({calc['roi']:.2f}%)\n"
            "Solo si se aceptan todas las apuestas sin anulaciones, "
            "comisiones ni diferencias de reglas. Confirma directamente cada "
            "cuota, límites y liquidación; en tenis, verifica retiradas. "
            "No se han realizado apuestas.")
    return out

def call(token, method, params):
    url = "https://api.telegram.org/bot" + token + "/" + method
    try:
        request = Request(url,data=json.dumps(params).encode(),
                          headers={"Content-Type":"application/json"})
        with urlopen(request,timeout=25) as response:
            result = json.loads(response.read())
    except (HTTPError,URLError) as exc:
        raise RuntimeError("Telegram: error de conexión o API") from exc
    if not result.get("ok"):
        raise RuntimeError("Telegram: " + result.get("description","error"))
    return result["result"]

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN","").strip()
    allowed_chat = os.getenv("TELEGRAM_CHAT_ID","").strip()
    if not token or not allowed_chat:
        raise SystemExit("Faltan secretos de Telegram")
    updates = call(token,"getUpdates",
                   {"limit":100,"timeout":0,"allowed_updates":["message"]})
    highest = None
    for update in updates:
        message = update.get("message")
        if message and str(message.get("chat",{}).get("id")) == allowed_chat:
            msg = str(message.get("text","")).strip()
            try:
                if msg.lower().startswith("/comparar"):
                    parsed = parse_message(msg)
                    response = render(parsed, evaluate(parsed))
                elif msg.lower().startswith("/plantilla"):
                    response = TEMPLATE
                elif msg.lower().startswith(("/start","/ayuda","/help")):
                    response = HELP
                else:
                    response = ""
            except ValueError as exc:
                response = "⚠️ " + str(exc) + "\nEnvía /plantilla."
            if response:
                call(token,"sendMessage",{"chat_id":allowed_chat,
                    "text":response[:4000]})
        if isinstance(update.get("update_id"),int):
            highest = update["update_id"]
    if highest is not None:
        call(token,"getUpdates",{"offset":highest+1,"limit":1,"timeout":0})
    print("Updates processed:",len(updates))

if __name__ == "__main__":
    main()
