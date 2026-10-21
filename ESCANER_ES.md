# Escáner automático de cuotas Bet365 ES + Winamax ES

Fuente: [OddsPapi](https://oddspapi.io/es/sign-up), documentación [odds-by-tournaments](https://oddspapi.io/es/docs/get-odds-by-tournaments) y [GET account](https://oddspapi.io/es/docs/get-account).

- Formato: `bet365.es` y `winamax.es` únicamente, sin mezclas con otras jurisdicciones.
- Mercado: fútbol, **1X2 a 90 minutos**, mercado 101 de OddsPapi. Solo antes del inicio y con precios activos que informan actualización en los últimos 5 minutos.
- Capital ilustrativo 100 €, mínimo 0,5 % de rentabilidad matemática; no cubre impuestos, limitaciones, cancelaciones ni cambios.
- Solo se envían oportunidades **candidatas**, no ganancias garantizadas ni apuestas automáticas.
- No se intentará usar la cuenta de Bet365 del usuario. La clave de OddsPapi se guarda como secreto de GitHub.
- El workflow consulta cada seis horas (unas 120 llamadas mensuales) y puede omitir ejecuciones programadas por GitHub. Comprueba los créditos disponibles con `GET /account` antes de gastar uno y detiene las consultas con 15 o menos restantes.
- Torneos por defecto: LaLiga (8) y Premier League (17), IDs documentados por OddsPapi; esta selección se puede cambiar mediante `ODDSPAPI_TOURNAMENT_IDS` validando IDs en su catálogo.
- **Por seguridad está en modo diagnóstico**. Activar las alertas solo tras verificar resultados reales y configurar variable de repositorio `ODDSPAPI_ENABLE_ALERTS=true`.

## Para empezar

1. Regístrate en https://oddspapi.io/es/sign-up y obtén una clave gratuita (250 peticiones por mes anunciadas por el proveedor). **No pegues esa clave en conversaciones.**
2. GitHub → Guimotooo/arbiscan → Settings → Secrets and variables → Actions → New repository secret → nombre `ODDS_PAPI_KEY`; pega ahí la clave.
3. GitHub → Actions → «ArbiiScan - escaner Bet365 ES y Winamax ES» → Run workflow. Lee el resultado, que debe indicar créditos restantes y candidatos. No envía mensajes hasta validación.
4. Una vez comprobada la cobertura real, activar variable `ODDSPAPI_ENABLE_ALERTS` como `true` desde GitHub Actions Variables; nunca activar antes de validar.

La cuota de 250 consultas por mes permite unas 8 al día. No es un feed minuto a minuto ni una cobertura 24/7 de todos los deportes. Consultar otras APIs en la misma cuenta consume créditos adicionales. Los datos del proveedor pueden contener retrasos: las alertas requieren verificación en ambos cupones.
