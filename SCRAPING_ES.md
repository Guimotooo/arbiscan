# ArbiiScan scraping ES — modo laboratorio

Prototipo de navegador (Playwright) sin OddsPapi, diseñado para leer **páginas públicas** de eventos prepartido en Bet365 España y Winamax España. Nunca inicia sesión, no elude CAPTCHAs, no accede a endpoints internos ni efectúa apuestas.

**Estado actual: motor y pruebas locales implementados; NO se ha validado ninguna página real ni sus selectores.** Se necesitan enlaces de partidos concretos y selectores CSS públicos estables. Sin ellos, el workflow únicamente ejecuta tests y no consulta webs ni envía mensajes.

## Configuración

Crear `scraping_es/config.json` (no incluido de forma deliberada) con este esquema; los ejemplos de selectores son *marcadores*, NO selectores validados:

```json
{
  "bet365.es": {
    "url": "https://www.bet365.es/URL-PUBLICA-REAL-DEL-PARTIDO",
    "market": "1X2_90_MIN",
    "selectors": {
      "event": "SELECTOR_EXACTO_NOMBRE",
      "start": "SELECTOR_FECHA_ISO_CON_ZONA_HORARIA",
      "home": "SELECTOR_CUOTA_LOCAL",
      "draw": "SELECTOR_CUOTA_EMPATE",
      "away": "SELECTOR_CUOTA_VISITANTE"
    }
  },
  "winamax.es": {
    "url": "https://www.winamax.es/URL-PUBLICA-REAL-DEL_MISMO_PARTIDO",
    "market": "1X2_90_MIN",
    "selectors": {
      "event": "SELECTOR_EXACTO_NOMBRE",
      "start": "SELECTOR_FECHA_ISO_CON_ZONA_HORARIA",
      "home": "SELECTOR_CUOTA_LOCAL",
      "draw": "SELECTOR_CUOTA_EMPATE",
      "away": "SELECTOR_CUOTA_VISITANTE"
    }
  }
}
```

Los selectores son *estrictos*: se rechaza cualquier selector ausente, duplicado o cuota no interpretable. Las webs con renderizado complejo o bloqueo de automatización podrían no ser accesibles.

**Limitaciones del prototipo:** solo lee un partido común por ejecución; no descubre partidos, no sincroniza nombres distintos entre casas, no valida oficialmente el permiso aportado, ni garantiza cuotas apostables o que GitHub permita acceder a estas webs. La correspondencia exige nombre y hora idénticos, por seguridad. No está listo para monitorizar ligas completas. El usuario debe facilitar una URL pública de evento de cada casa y comprobar que la autorización permite consultas automatizadas a intervalos razonables.

La integración OddsPapi existente sigue intacta. Evitar ejecutar simultáneamente múltiples escáneres que envíen alertas sobre los mismos eventos.

## Prueba con enlaces facilitados por el usuario (21/10/2026)

Enlaces ensayados:
- `https://www.bet365.es/#/AC/B1/C1/D8/E202645795/F3/I1/P30024/H1/`
- `https://www.winamax.es/en/sports-betting/match/74165970`

Un navegador Chromium sin cuenta desde GitHub Actions obtuvo **HTTP 403 en bet365.es** y **HTTP 200 en winamax.es**. Winamax renderizó contenido de la portada deportiva, pero la prueba NO confirmó todavía el partido específico ni tres cuotas 1X2. El contenido inicial leído no contenía precios decimales. Por tanto, **ninguna cuota ha sido extraída o validada** y no se envían alertas de scraping.

Se corrigió el validador de direcciones para admitir el fragmento de rutas `#/` de Bet365; esto no evita el bloqueo del servidor. No se habilita ningún bypass técnico de CAPTCHA, acceso restringido o bloqueo HTTP.

Workflow de diagnóstico: `ArbiiScan - comprobar enlaces scraping ES`; workflow de tests: `ArbiiScan - prueba scraping ES`.

## Diagnóstico exhaustivo de acceso — 21/10/2026 (ejecuciones reales)

- Bet365 ES respondió **HTTP 403** desde GitHub Actions en todas las pruebas (navegador público, sin inicio de sesión). Un segundo servicio de lectura de páginas devolvió bloqueo de bot. No se intentan evasiones.
- Winamax ES respondió HTTP 200 y renderizó más de 18.000 caracteres de texto, con mercados de apuestas. En el texto del evento se encontraron **Real Madrid y RB Leipzig** y selecciones con cuotas como «Over 2.5». Ya no se trata de una página vacía; sin embargo, aún no se han identificado selectores estables para el mercado **1X2 completo** del partido. La prueba no ha validado ninguna comparación entre casas.
- La ruta del evento Winamax permanece en la URL, pero la coincidencia del nombre y la hora del evento con Bet365 no se puede verificar porque Bet365 no devuelve datos.
- **Estado:** scraper solo diagnóstico, sin programación recurrente ni envío de alertas. El lector y el comparador tienen tests, pero no han demostrado una extracción integrada de dos webs.
- **Bloqueo externo:** para tener acceso directo desde GitHub, la entidad que autorizó el uso de Bet365 debe indicar un medio de acceso técnico que responda desde ese entorno (por ejemplo, acceso oficial documentado). Una autorización general de consulta no elimina automáticamente el bloqueo del servidor. No solicitar ni publicar contraseñas, sesiones o tokens personales.
- Mantener el escáner alternativo de OddsPapi separado si se desea cobertura mientras se valida la fuente directa.

Última ejecución de diagnóstico: https://github.com/Guimotooo/arbiscan/actions/runs/39645736856
