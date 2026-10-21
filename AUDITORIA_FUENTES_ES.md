# ArbiiScan — auditoría de fuentes para cuotas españolas (21/10/2026)

## Decisión: no activar todavía la detección automática de arbitrajes españoles

La funcionalidad de Telegram mediante Cloudflare está operativa, pero **no se ha validado ninguna fuente automática, gratuita y con permiso de integración** que proporcione a la vez Bet365 España, Sportium España, Winamax España y Betfair España.

### Proveedores comprobados

- **The Odds API**: lista Winamax FR/DE y Betfair de otras jurisdicciones, pero no acredita los cuatro operadores ES. Su catálogo público de casas no debe confundirse con licencias españolas. Ya existe en el repositorio para el reporte internacional, con etiquetas de jurisdicción.
- **Oddschecker España**: comparador público gratuito para usuarios finales, con operadores españoles, incluido Sportium y Betfair. No se ha verificado un endpoint público autorizado, estable y apto para extraer automáticamente y redistribuir las cuotas en un bot. No usar scraping no autorizado ni fingir disponibilidad de una API.
- **odds-api.io**: publicita un plan gratuito con dos casas recreativas y un catálogo con varios operadores ES, pero no se ha acreditado cobertura simultánea de Bet365 ES, Sportium ES, Winamax ES y Betfair ES en el plan gratuito. El catálogo europeo genérico no prueba jurisdicción de cada cotización.

### Condiciones obligatorias antes de activar alertas españolas

1. Fuente gratuita dentro del presupuesto acordado, documentada y autorizada para el uso previsto.
2. Identificador inequívoco de cada casa y su jurisdicción **ES**; no deducirla del nombre de marca.
3. Fecha de actualización y evento idéntico, mercado y reglas de liquidación equivalentes.
4. Datos suficientemente recientes, con descarte automático de cuotas caducadas y errores de proveedor.
5. Cobertura de todos los resultados, redondeo a céntimos, comisiones y límites de apuesta.
6. Prueba con eventos reales en las cuatro casas objetivo y validación manual en sus cupones.
7. Mensajes informativos, nunca garantía de ganancia ni confirmación de que la apuesta será aceptada.

**Regla de seguridad:** si cualquiera de estas condiciones falla, no enviar alerta etiquetada como «surebet verificada en España». Mantener la comparación manual y el informe internacional claramente diferenciado.

Fuentes:
- https://the-odds-api.com/sports-odds-data/bookmaker-apis.html
- https://www.oddschecker.com/es/quienes-somos
- https://www.oddschecker.com/es/
- https://odds-api.io/es/pricing/free
- https://odds-api.io/sportsbooks/europe
