# Motor propio ArbiiScan (22 de octubre de 2026)

Este código implementa lectura de páginas, normalización de cuotas, un motor
matemático de arbitraje y adaptadores. No confunde un precio leído en una API con
una cuota confirmada disponible para apostar.

## Estado comprobado

- 51 pruebas automáticas del motor original superadas (incluidas 1X2, ganador,
  totales de línea x.5, comprobación de cuotas, mercados incompatibles, fechas,
  resultados incompletos, contenido HTML ambiguo y páginas de acceso bloqueado).
- Lector HTML de contenido estático o generado con JavaScript mediante Playwright
  y Scrapling; exige selectores CSS específicos de evento y mercado.
- Fuente JSON de feed autorizado y adaptador de cotizaciones OddsPapi.
- Auditoría posterior a la corrección, 22/10/2026: 30 partidos y 30
  cotizaciones del proveedor (21 Bet365 ES, 9 Winamax ES); ninguna cumplió
  una hora máxima desde changedAt de TODAS las selecciones. En la versión
  anterior, updatedAt del EVENTO producía falsos descartes porque se refiere
  a metadatos del partido. El criterio actual usa changedAt por selección,
  pero no acredita disponibilidad en el cupón.
- Ninguna alerta enviada desde las pruebas del motor nuevo. El antiguo bot sigue
  activo; no se sustituye sin una fuente validada y doble comprobación.

## Límites esenciales

Ningún programa garantiza el 100 % de disponibilidad en todos los operadores.
Bet365 ES prohíbe expresamente el scraping automatizado de cuotas en sus términos.
Para esa casa se mantiene la vía de datos de OddsPapi. El nuevo lector HTML
requiere permiso real de extracción de cada web configurada. No hay evasión de
CAPTCHA, proxies rotativos, API privada ni automatización de apuestas.

## Uso seguro

Instalación:
    python -m pip install 'scrapling>=0.5,<0.6'

Pruebas matemáticas y de HTML:
    python -m unittest -v test_motor_propio.py

Demo con cuotas inventadas, nunca envía alertas:
    python -m motor_propio.run --demo

Auditoría de cuotas de proveedor, usa pocos créditos y nunca envía alertas:
    ODDS_PAPI_KEY=... python -m motor_propio.run --odds-papi-audit

Feed JSON autorizado normalizado, una lectura sin envío:
    python -m motor_propio.run --feed /ruta/datos.json

Lector HTML permitido:
    python -m motor_propio.run --profiles /ruta/perfiles.json

Los perfiles tienen libro/casa, URL HTTPS oficial, permiso verdadero de lectura,
sport, market con liquidación inequívoca, market_scope, market_label, mode html
o browser, y selectores únicos para home, away, kickoff, market_heading y todas
las cuotas del mercado. El archivo perfiles_ejemplo.json es intencionadamente
NO funcional hasta verificar URL, selectores y permiso de extracción.

Una alerta solo se enviaría expresamente con --send en el modo de perfiles
de páginas permitidas, con claves de Worker configuradas y dos lecturas
independientes idénticas. No se ha habilitado este envío automáticamente.

## Mercados explícitamente definidos

- soccer + 1x2:regulation: resultados 1, X, 2, 90 minutos.
- basketball + winner:including_ot: resultados 1 y 2 con prórroga.
- american_football + winner:including_ot: resultados 1 y 2 con prórroga.
- tennis + winner:completed_match / winner:retirement_counts: reglas sobre
  retiradas explícitas. No comparar dos reglas distintas.
- soccer + total:regulation:2.5: OVER/UNDER en 90 minutos.
- basketball/american_football + total:including_ot:224.5 (líneas x.5):
  OVER/UNDER con prórroga.

Se prohíben líneas con posible devolución o reglas indeterminadas.

## Protocolo para una fuente nueva

1. Revisar sus condiciones y conseguir acceso permitido.
2. Identificar en una página o feed real el evento, hora con huso horario,
   mercado, reglas de liquidación y selección/cuota decimal.
3. Añadir su perfil CSS o conversor a Quote (motor_propio/engine.py).
4. Ejecutar test_motor_propio.py y probar que se rechazan datos ambiguos.
5. Comparar dos consultas distintas y comprobar que las cuotas no están
   suspendidas ni anticuadas.
6. Solo entonces activar alertas filtradas por casas en Telegram.

En nuestra cuenta gratuita OddsPapi requiere exactamente UNA casa por consulta
odds-by-tournaments (error HTTP 400 al intentar agrupar dos), aunque otros planes
y la documentación general admitan varios operadores. Se siguen reservando
créditos y no se contratan servicios de pago sin autorización.
