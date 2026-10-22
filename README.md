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
- **fuentes_es/oddspapi_multisport.py** — búsqueda automática de encuentros
  y comparación de cuotas de hasta 3 casas en dos rondas diarias. Utiliza
  OddsPapi (250 consultas/mes en el plan actual) y solo envía posibles
  oportunidades reales, reconfirmadas por segunda lectura y etiquetadas
  como NO verificadas en el cupón.
- **worker/arbiscan.mjs** — Telegram, preferencias por usuario, filtro de casas
  y distribución de alertas vía Cloudflare.
- **scraping_es/** — pruebas anteriores de lectores de páginas con Scrapling y
  Playwright; no se han activado como fuente de alertas.
- **fuentes_es/direct_bwin.py** — descubrimiento DOM-only de partidos y 1X2
  visibles en Bwin ES. No usa APIs internas, sesión ni evasión y exige una
  autorización explícita antes de abrir la página. Por sí solo no puede crear
  un arbitraje ni enviar Telegram.
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

## Estado de la extracción directa (22/10/2026)

- **Bet365 ES:** Chromium ordinario y HTTP público responden 403 con una página
  de bloqueo Cloudflare. No se realizan reintentos de evasión, CAPTCHA, proxy,
  sesión ni endpoints internos. No es una fuente operativa.
- **Winamax ES:** la ruta comprobada devuelve una aplicación JavaScript, pero
  todavía no existe un selector 1X2 estable ni una segunda fuente con la que
  validar cada evento. No es una fuente operativa.
- **Bwin ES:** una navegación Chromium ordinaria mostró tarjetas públicas de
  fútbol con enlaces de evento, equipos, hora y 1X2. El nuevo conector lee sólo
  esos nodos visibles y rechaza fechas o mercados ambiguos. El workflow manual
  `probar_bwin_directo.yml` exige `ARBI_DIRECT_BWIN_ALLOWED=true` como variable
  del repositorio; no se agenda ni difunde alertas.

Una lectura visible no demuestra autorización contractual ni aceptación en el
cupón. Hasta disponer de dos fuentes directas permitidas con evento, reglas y
hora compatibles, no se activará el envío de supuestos arbitrajes directos.
