# ArbiiScan — estado de producción (21/10/2026)

## Experiencia del usuario en Telegram
- `/start`: pregunta qué casas españolas usa el usuario mediante botones; **no da de alta hasta que pulse «Guardar selección»**.
- `/casas`: permite modificar la selección.
- `/estado`: indica las casas guardadas.
- `/stop`: cancela las alertas.
- La selección persiste en Cloudflare KV y cada alerta se envía solo si sus casas requeridas están entre las elegidas. Si no hay dos casas, no se pueden detectar arbitrajes entre operadores.
- Hay botones **Todas** y **Ninguna**. Al marcar o desmarcar se actualiza el mismo mensaje de Telegram.
- Las suscripciones antiguas que no guardaron preferencias mantienen las dos casas originales (Bet365 ES y Winamax ES) como único filtro hasta que usen `/casas`.

## Operadores en catálogo
OddsPapi `/v4/bookmakers` devolvió estos 11 slugs `.es`:
`888sport.es`, `bet365.es`, `betfair.es`, `betway.es`, `bwin.es`, `codere.es`, `goldenpark.es`, `leovegas.es`, `paf.es`, `pokerstars.es`, `winamax.es`.

**Estar en el catálogo NO garantiza disponibilidad de precios en un partido.** OddsPapi rechazó `betfair.es` para los torneos de tenis elegidos el 21/10/2026; el escáner lo trató como falta de cobertura, nunca como cuota.

## Deportes y mercados habilitados
Los ID y mercados se verificaron en el catálogo real `/v4/sports` y `/v4/markets`:
- Fútbol `sportId=10`, `marketId=101`: 1X2 de tiempo reglamentario, 3 resultados.
- Baloncesto `sportId=11`, `marketId=111`: moneyline del resultado del partido, 2 resultados.
- Tenis `sportId=12`, `marketId=121`: moneyline del resultado del partido, 2 resultados.
- Fútbol americano `sportId=14`, `marketId=141`: moneyline del resultado del partido, 2 resultados.

Las competiciones se obtienen dinámicamente de `/v4/tournaments` en cada ronda, sin clasificar por fama ni tamaño. Se rotan **máximo 5 torneos por día**, ya que el proveedor rechaza más de cinco IDs por petición. Se revisa **un deporte diferente por día**. No se examinan todos los eventos del mundo simultáneamente.

## Presupuesto
- Plan gratuito: 250 peticiones facturables/mes.
- Una ronda diaria: 1 consulta de torneos + como máximo 5 de casas = 6 peticiones/día; 186 en 31 días sin confirmaciones.
- Una ronda con candidatos puede gastar hasta 5 peticiones de reconfirmación adicionales; hay una reserva que suspende nuevos escaneos antes de agotar la cuota.
- **0 € pagados por estas pruebas.** No se prometen oportunidades ni ganancias.
- `/v4/account` permite consultar el saldo sin coste de solicitudes según la documentación del proveedor.

## Cómo selecciona qué casas consultar
El Worker ofrece una consulta privada autenticada `GET /scan-preferences` con **solo recuentos agregados de parejas**, nunca chat IDs. El escáner escoge la combinación de máximo cinco casas que permite cubrir más preferencias de suscriptores. Si no hay preferencias, usa Bet365 y Winamax más tres casas rotatorias.

## Cómo se envían avisos
- Alerta solo si matemáticamente cubre todos los resultados del mismo mercado, entre al menos dos operadores, con ROI teórico >=0,5 %.
- Se exige una segunda lectura de cuotas tras al menos 3 segundos y coincidencia exacta de selección, precio, mercado y partido.
- El Worker distribuye **solo al público cuyas casas pueden ejecutar esa combinación**; deduplicación por partido/mercado y usuario durante 24 h.
- Cada mensaje está etiquetado como **posible arbitraje NO CONFIRMADO**. La lectura de OddsPapi no demuestra que la cuota pueda colocarse en ambos cupones.
- La conexión GitHub–Worker utiliza el secreto independiente `BROADCAST_SECRET` del token que valida los mensajes entrantes de Telegram. Se verificó la autorización sin enviar alertas ficticias.

## Horarios y repositorio
- Workflow programado: `.github/workflows/escaner_multisport.yml`, una vez al día **18:15 UTC**. GitHub Actions puede ejecutar con retraso.
- Versión anterior de solo dos casas y fútbol: `.github/workflows/escaner_es.yml` **sin programación recurrente**.
- Escáner: `fuentes_es/oddspapi_multisport.py`.
- Pruebas: `test_oddspapi_multisport.py` y `worker/arbiscan.test.mjs`.
- Menú y notificaciones: `worker/arbiscan.mjs`.
- No habilitar dos escáneres recurrentes simultáneamente bajo el mismo plan gratuito.

## Resultados de validación
- Catálogo real identificado: 11 casas españolas, 4 deportes y sus 4 mercados.
- Primera ronda real de tenis: 29 partidos, sin arbitraje candidato.
- Pruebas de matemática de combinaciones: **13/13** (última validación de lógica con 11 casas).
- Pruebas de webhook: **10/10**.
- Despliegue Cloudflare y GET /health correctos.
- GET /scan-preferences autenticado y POST /broadcast con carga inválida (HTTP 400) verificados desde GitHub Actions. Ningún usuario recibió alerta ficticia.

## Límites reconocidos
No es cobertura instantánea ni total: con 250 consultas/mes solo se pueden muestrear cinco casas, cinco torneos y un deporte por ronda. Para ampliar sustancialmente la cobertura/frecuencia harían falta más solicitudes o un contrato apropiado con OddsPapi, pero no se ha contratado nada.
