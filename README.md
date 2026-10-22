# ArbiiScan — comparador de cuotas y alertas para Telegram

Proyecto experimental de alertas informativas de arbitraje deportivo.
Las cuotas pueden cambiar o no ser aceptadas por las casas: **no hay
ganancias garantizadas** ni apuestas automáticas.

## Bot

https://t.me/ArbiiScan_bot

- /start: selecciona las casas españolas que utilizas.
- /casas: modifica las casas.
- /estado: consulta preferencias.
- /escaneo: muestra el último escaneo real y sus cifras (no necesita indicar un partido).
- /stop: cancela alertas.

## Referencia externa Cuotiva · Alertas (22/10/2026)

La captura de Telegram de `@CuotivaAlertasBot` permite observar registro
de acceso sujeto a autorización, selección de casas y una mención a
`Cuotiva Cartera`. No revela el código ni la procedencia de las cuotas:
no se debe afirmar que emplea scraping de Bet365 ni que haya demostrado
un arbitraje real. Las webs llamadas Cuotiva encontradas en búsquedas
públicas tratan de cobros a plazos, sin prueba de relación con ese bot.

ArbiiScan ya tiene selecciones por casa y alertas automáticas. Se añade
`/escaneo`, con estado real guardado por el propio escáner en Cloudflare:
horario UTC, fuente, casas, partidos obtenidos, candidatos y avisos enviados.
El registro explicita `OddsPapi`, porque no equivale a extracción directa.

La API oficial de Betfair Exchange española es una alternativa de fuente
directa y ya tiene un conector experimental en `fuentes_es/betfair_exchange.py`,
pero requiere claves y sesión del titular. Su App Key gratuita de desarrollo
devuelve datos retrasados y NO permite certificar cuotas actuales. Betfair
Exchange y Betfair Sportsbook son productos diferentes; las comisiones y la
liquidez del Exchange requieren comprobación. No se crean alertas falsas.

## Componentes

- **motor_propio/** — código nuevo escrito para ArbiiScan: lectura HTML permitida,
  normalización de cuotas, compatibilidad de reglas de mercado, cálculo de
  arbitrajes, doble lectura y filtros de calidad. Ver motor_propio/README.md.
- **fuentes_es/oddspapi_multisport.py** — búsqueda automática de encuentros
  y comparación de cuotas de hasta 3 casas en dos rondas diarias. Utiliza
  OddsPapi (250 consultas/mes en el plan actual) y solo envía posibles
  oportunidades reales, reconfirmadas por segunda lectura y etiquetadas
  como NO verificadas en el cupón.
- **worker/arbiscan.mjs** — Telegram, preferencias por usuario, filtro de casas
  y distribución de alertas vía Cloudflare.
- **scraping_es/** — pruebas anteriores de lectores de páginas con Scrapling y
  Playwright; no se han activado como fuente de alertas.
- **test_motor_propio.py** — pruebas de cálculo y extracción (51 verificadas).
- **.github/workflows/motor_propio_tests.yml** — tests del motor en GitHub Actions.

## Búsqueda automática sin introducir partidos

GitHub Actions ejecuta `.github/workflows/escaner_multisport.yml` a las
07:15 y 18:15 UTC. No necesitas enviar /comparar ni /plantilla para recibir
una alerta automática. Las casas se seleccionan según las preferencias
guardadas en Telegram; se revisan competiciones distintas en cada ronda.
Para limitar las peticiones gratuitas, hay como máximo 3 casas por escaneo
y una reserva mínima de créditos (por eso puede detenerse a final de mes).
Se prioriza fútbol 1X2, cuyos resultados están claramente definidos.

Si hay un arbitraje matemático de al menos el 0,5 %, se vuelven a solicitar
las cuotas de las casas implicadas y solo se difunde si coincide exactamente
en ambas lecturas. Las alertas no certifican que las cuotas estén disponibles
al apostar. **No es un scraper directo de Bet365 y no garantiza cobertura
continua o en tiempo real; sigue usando OddsPapi.**

El webhook de Telegram recibe mensajes, pero es el escáner programado quien
envía las alertas sin interacción del usuario. /estado permite revisar la
suscripción en el bot; no dispara un escaneo.

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
- El 22/10/2026 se corrigió un falso descarte: updatedAt describe el
  evento, mientras changedAt describe los cambios de cuotas de cada selección
  (según OddsPapi). La auditoría real posterior, sobre main, obtuvo 30
  partidos y 30 cotizaciones (21 de Bet365 ES y 9 de Winamax ES), pero
  ninguna con todas las selecciones cambiadas en la última hora. Son
  snapshots reales del proveedor, no cuotas verificadas en el cupón.
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
