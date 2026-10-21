"""Una ejecución diaria en GitHub Actions (solo The Odds API, sin scraping)."""
import os
from datetime import datetime, timezone
from scanner import (get_odds, selected_sports, scan_events, send_telegram,
                     message_for, TARGET_NAMES)


def analyze_day(api_key):
    markets = ['h2h', 'totals', 'spreads']
    sport_keys = selected_sports(api_key)
    if not sport_keys:
        return [], ['No hay competiciones objetivo activas en la API.'], None
    events=[]; status=[]; last_remaining=None
    for sport in sport_keys[:4]:
        try:
            rows, remaining, cost = get_odds(sport, markets, 'eu,uk', api_key)
            events.extend(rows)
            count = sum(bool(e.get('bookmakers')) for e in rows)
            status.append(f'{sport}: {count} eventos con alguna casa objetivo')
            if remaining != '?':
                last_remaining=remaining
                try:
                    if int(remaining) < 25:
                        status.append('Límite de seguridad: menos de 25 créditos. No se consultan más deportes.')
                        break
                except ValueError:
                    pass
        except (RuntimeError, ValueError) as ex:
            status.append(f'{sport}: sin datos ({str(ex)[:90]})')
    candidates=scan_events(events, now=datetime.now(timezone.utc),
                           bankroll=100, min_roi=0.5, max_age_seconds=300)
    return candidates, status, last_remaining


def main():
    api_key=os.getenv('ODDS_API_KEY','').strip()
    telegram_token=os.getenv('TELEGRAM_BOT_TOKEN','').strip()
    chat_id=os.getenv('TELEGRAM_CHAT_ID','').strip()
    if not (api_key and telegram_token and chat_id):
        raise SystemExit('Faltan secretos. Consulta GUIA_GITHUB.txt. No se hace ninguna petición.')
    candidates, status, remaining=analyze_day(api_key)
    summary=('🤖 ARBIISCAN · REPORTE DIARIO (FUENTE GRATUITA)\n'
             + '\n'.join(status)
             + f'\nCréditos según última consulta: {remaining or "no informado"}\n'
             + f'Candidatas matemáticas: {len(candidates)}\n'
             + 'Casas de esta API: Winamax FR/DE y Betfair Sportsbook UK, si la fuente publica cuotas. '
             + 'Bet365 ES, Sportium y SportyBet NO están cubiertas. '
             + 'No implica verificación de las cuotas en webs españolas.\n'
             + 'No se realizaron apuestas.')
    send_telegram(telegram_token,chat_id,summary)
    for opp in candidates[:3]:
        send_telegram(telegram_token,chat_id,'⚠️ CANDIDATA SIN VERIFICAR EN LA CASA\n'+message_for(opp))

if __name__=='__main__':
    main()
