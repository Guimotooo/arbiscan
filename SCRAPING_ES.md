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
