"""ArbiiScan V4: reporte gratis, comparaciones identificadas y ahorro de créditos.

Advertencia: el proveedor gratuito de este repositorio NO proporciona cuotas de
Bet365 España ni Sportium España. No sustituimos sus cuotas por otras regiones.
"""
from __future__ import annotations
import os
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from scanner import (get_odds, list_sports, market_group, scan_events,
                     send_telegram, iso_dt)

BASE_SPORTS = ('soccer_spain_la_liga', 'soccer_spain_segunda_division',
               'basketball_nba')
BOOKMAKERS = {'winamax_fr': 'Winamax Francia',
              'winamax_de': 'Winamax Alemania',
              'betfair_sb_uk': 'Betfair Sportsbook Reino Unido'}
ELITE_TENNIS = ('australian open', 'french open', 'roland garros',
                'wimbledon', 'us open', 'masters 1000', 'wta 1000',
                'atp finals', 'wta finals', 'indian wells', 'miami open',
                'madrid open', 'italian open', 'rome masters', 'monte carlo',
                'canadian open', 'cincinnati', 'shanghai masters', 'paris masters')
MAX_QUERIES = 4
MIN_QUOTA = 30
MAX_AGE_SECONDS = 300


def selected_sports(api_key):
    """Usar el listado de deportes activo (solicitud sin gasto de créditos)."""
    available = list_sports(api_key)
    active = {s.get('key') for s in available if s.get('active')}
    chosen = [s for s in BASE_SPORTS if s in active]
    tournaments = []
    for sport in available:
        if not sport.get('active') or sport.get('has_outrights'):
            continue
        title = (str(sport.get('title', '')) + ' ' +
                 str(sport.get('key', '')).replace('_', ' ')).lower()
        if ('tennis' in title or 'atp' in title or 'wta' in title) and any(
                text in title for text in ELITE_TENNIS):
            tournaments.append(sport)
    if tournaments:
        chosen.append(sorted(tournaments, key=lambda s: str(s.get('key','')))[0]['key'])
    return chosen[:MAX_QUERIES]


def market_for_sport(sport, today):
    if sport.startswith('soccer_') or sport.startswith('tennis_'):
        return 'h2h'
    return ('h2h', 'totals', 'spreads')[today.toordinal() % 3]


def brand(key):
    if key.startswith('winamax_'):
        return 'Winamax'
    if key.startswith('betfair_'):
        return 'Betfair'
    return key


def diagnostic(events, market_key, now):
    """Contar solo cuotas recientes, mercados idénticos y marcas diferentes."""
    counts = Counter()
    two_brands = comparable = discarded = 0
    for event in events:
        group_brands = defaultdict(set)
        brands = set()
        for book in event.get('bookmakers', []):
            key = str(book.get('key', ''))
            if key not in BOOKMAKERS:
                continue
            has_valid = False
            for market in book.get('markets', []):
                if market.get('key') != market_key:
                    continue
                updated = iso_dt(market.get('last_update') or book.get('last_update'))
                valid_age = updated is not None and 0 <= (now - updated).total_seconds() <= MAX_AGE_SECONDS
                group = market_group(event, market) if valid_age else None
                if group is None:
                    discarded += 1
                    continue
                kind, line, outcomes, _ = group
                group_brands[(kind, line, outcomes)].add(brand(key))
                has_valid = True
            if has_valid:
                counts[key] += 1
                brands.add(brand(key))
        if len(brands) >= 2:
            two_brands += 1
        if any(len(b) >= 2 for b in group_brands.values()):
            comparable += 1
    return counts, two_brands, comparable, discarded


def analyze_day(api_key, today=None, now=None):
    """Máximo cuatro llamadas de cuotas de un mercado; no garantiza coste exacto."""
    now = now or datetime.now(timezone.utc)
    today = today or now.date()
    lines = []
    events = []
    remaining = None
    spent = 0
    try:
        sports = selected_sports(api_key)
    except (RuntimeError, ValueError) as exc:
        return [], ['Catálogo no disponible: ' + str(exc)[:100]], None, 0
    if not sports:
        return [], ['Ninguna competición objetivo activa.'], None, 0
    for sport in sports:
        if remaining is not None and remaining < MIN_QUOTA:
            lines.append('Pausa preventiva: quedan menos de 30 créditos.')
            break
        market = market_for_sport(sport, today)
        try:
            rows, quota, last_cost = get_odds(sport, [market], 'eu', api_key)
            events.extend(rows)
            counts, two, comparable, discarded = diagnostic(rows, market, now)
            detail = ', '.join(f'{BOOKMAKERS[k]}: {v}' for k,v in sorted(counts.items()))
            if not detail:
                detail = 'sin cotizaciones objetivo válidas y recientes'
            lines.append(f'{sport} [{market}]: {detail}. '
                         f'Eventos con 2 marcas: {two}; mercados comparables: {comparable}; '
                         f'cotizaciones descartadas: {discarded}.')
            try:
                spent += max(0, int(last_cost))
            except (ValueError, TypeError):
                pass
            try:
                remaining = int(quota)
            except (ValueError, TypeError):
                remaining = None
        except (RuntimeError, ValueError) as exc:
            lines.append(f'{sport} [{market}]: sin datos ({str(exc)[:100]})')
            if '429' in str(exc) or 'quota' in str(exc).lower():
                lines.append('API sin créditos; consultas detenidas.')
                break
    opportunities = scan_events(events, now=now, bankroll=100, min_roi=0.5,
                                max_age_seconds=MAX_AGE_SECONDS)
    return opportunities, lines, remaining, spent


def report_text(candidates, lines, remaining, spent, now):
    date_text = now.strftime('%d/%m/%Y %H:%M UTC')
    return ('ARBIISCAN · INFORME DIARIO\n' + date_text + '\n\n'
            + '\n'.join('• ' + line for line in lines)
            + f'\n\nCandidatas MATEMÁTICAS internacionales: {len(candidates)}'
            + f'\nCréditos consumidos según cabeceras: {spent}'
            + f'\nCréditos restantes: {remaining if remaining is not None else "desconocidos"}'
            + '\n\nBET365 ESPAÑA Y SPORTIUM ESPAÑA: SIN COBERTURA VERIFICADA. '
              'También faltan Winamax España y Betfair España. '
              'Esta fuente solo proporciona Winamax FR/DE y Betfair Sportsbook UK '
              'según disponibilidad. No se presentan como cuotas españolas. '
              'No se ha verificado que las cuotas puedan apostarse. '
              'No se han realizado apuestas.')


def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
    chat_id = os.getenv('TELEGRAM_CHAT_ID', '').strip()
    api_key = os.getenv('ODDS_API_KEY', '').strip()
    if not (token and chat_id):
        raise SystemExit('Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID.')
    if not api_key:
        send_telegram(token, chat_id,
                      'ArbiiScan: falta ODDS_API_KEY. No se han consultado cuotas.')
        return
    now = datetime.now(timezone.utc)
    candidates, lines, remaining, spent = analyze_day(api_key, now=now)
    send_telegram(token, chat_id,
                  report_text(candidates, lines, remaining, spent, now))
    # No se envían ofertas internacionales como arbitrajes verificados en España.


if __name__ == '__main__':
    main()
