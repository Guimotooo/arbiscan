# ArbiiScan — comparador de cuotas y alertas para Telegram

Proyecto experimental de alertas informativas de arbitraje deportivo.
Las cuotas pueden cambiar o no ser aceptadas por las casas: **no hay
ganancias garantizadas** ni apuestas automáticas.

## Bot

https://t.me/ArbiiScan_bot

- /start: selecciona las casas españolas que utilizas.
- /casas: modifica las casas.
- /estado: consulta preferencias.
- /stop: cancela alertas.

## Componentes

- **motor_propio/** — código nuevo escrito para ArbiiScan: lectura HTML permitida,
  normalización de cuotas, compatibilidad de reglas de mercado, cálculo de
  arbitrajes, doble lectura y filtros de calidad. Ver motor_propio/README.md.
- **fuentes_es/oddspapi_multisport.py** — escáner actualmente programado mediante
  el proveedor OddsPapi y limitado por sus 250 consultas mensuales gratuitas.
- **worker/arbiscan.mjs** — Telegram, preferencias por usuario, filtro de casas
  y distribución de alertas vía Cloudflare.
- **scraping_es/** — pruebas anteriores de lectores de páginas con Scrapling y
  Playwright; no se han activado como fuente de alertas.
- **test_motor_propio.py** — pruebas de cálculo y extracción (51 verificadas).
- **.github/workflows/motor_propio_tests.yml** — tests del motor en GitHub Actions.

## Prueba del motor nuevo

    python -m pip install 'scrapling>=0.5,<0.6'
    python -m unittest -v test_motor_propio.py
    python -m motor_propio.run --demo

La demo utiliza precios ficticios y no envía alertas.

Para comprobar el acceso autorizado a Bet365 ES mediante OddsPapi:

    ODDS_PAPI_KEY=... python -m motor_propio.run --odds-papi-audit

Esta comprobación consume créditos del plan gratuito y no envía avisos.

## Estado y límites

- El motor propio ha superado 51 tests y sus comprobaciones de ejecución.
- La auditoría real previa del 22/10/2026 devolvió 30 partidos y 41
  cotizaciones normalizadas de Bet365 ES y Winamax ES. Se corrigió un
  falso descarte: updatedAt describe el evento, mientras changedAt describe
  los cambios de cuotas de cada selección (según OddsPapi). Ahora se exige
  changedAt reciente para todas las selecciones; falta una auditoría real
  posterior a esta corrección para medir cobertura efectiva.
- Los sitios deportivos pueden denegar el acceso o prohibir scraping. **Bet365
  España prohíbe expresamente la extracción automatizada de cuotas** en sus
  términos; el proyecto no incluye evasión de acceso a esa página.
- No existe un scraper que garantice cuotas en directo de todas las casas.
- No hay conexión entre el scraper web experimental y las alertas de producción
  hasta comprobar una fuente accesible y sus reglas de liquidación.
- No se ha contratado ningún servicio nuevo de pago.

El objetivo es incorporar adaptadores de fuentes permitidas uno por uno,
verificando sus precios antes de generar alertas, y reutilizando el motor
matemático y los controles de calidad ya implementados.
