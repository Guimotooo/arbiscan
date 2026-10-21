# ArbiiScan: activación de suscripciones automáticas

## Objetivo

Cada persona envía **/start** al bot una vez. El webhook de Cloudflare registra el ID privado del chat en Cloudflare KV. Cuando el escáner OddsPapi detecta un candidato 1X2 que supera dos consultas, lo remite al endpoint privado del propio Worker, que avisa a los suscriptores. El usuario no necesita introducir cuotas ni ejecutar comandos adicionales. **/stop** cancela y **/estado** consulta la suscripción.

## Activación inicial en Cloudflare (una vez)

1. En el panel Cloudflare, abre **Storage & Databases → KV**, crea un namespace llamado `arbiscan-subscribers`, y copia su **Namespace ID** (identificador público, no es un token).
2. En GitHub, repositorio `Guimotooo/arbiscan` → **Settings → Secrets and variables → Actions → Variables**, añade:
   - `ARBI_KV_NAMESPACE_ID` = Namespace ID de Cloudflare KV.
   - `CLOUDFLARE_ACCOUNT_ID` = Account ID de Cloudflare, que se muestra en el panel Cloudflare.
3. En Cloudflare → **My Profile → API Tokens**, crea un token limitado a **Workers Scripts: Edit** y los permisos KV requeridos solo en tu cuenta. No compartas el token por chat.
4. En GitHub → **Settings → Secrets and variables → Actions → Secrets**, añade `CLOUDFLARE_API_TOKEN` con ese token.
5. En GitHub → **Actions → ArbiiScan - desplegar suscripciones Telegram → Run workflow**. Este workflow incorpora el binding KV `SUBSCRIBERS` y despliega el código actual con `--keep-vars` para conservar `TELEGRAM_CHAT_ID` y los demás ajustes existentes.
6. Envía `/start` al bot y luego `/estado`. Debe mostrar la suscripción activa. Para dejar de recibir alertas usa `/stop`. Los usuarios que ya enviaron `/start` antes de este despliegue deberán enviarlo nuevamente.

## Seguridad y límites

- El Worker valida el encabezado secreto de Telegram para comandos y exige autenticación de GitHub Actions para `/broadcast`. No hay una lista pública de chat IDs.
- El Worker almacena únicamente chat ID y fecha de suscripción. Nunca se almacenan contraseñas de casas de apuestas.
- El escáner permanece limitado por los créditos gratuitos de OddsPapi, examina fútbol prepartido 1X2 y repite las consultas solo ante candidatos.
- Las notificaciones indican **posible arbitraje NO CONFIRMADO**. Los precios pueden cambiar o no estar disponibles al intentar apostar.
- No se envía ninguna alerta de muestra a destinatarios reales durante la configuración.
- La escritura KV puede tardar en propagarse. Esperar brevemente después de `/start` antes de comprobar una difusión.
- Un envío masivo síncrono tiene límites de ejecución: para muchos usuarios será necesario una cola y control de tasa de Telegram. La versión inicial está pensada para un grupo pequeño.
- En Cloudflare KV, el plan gratuito tiene límites diarios de lecturas/escrituras; comprobarlos si la base de usuarios aumenta.

## Diagnóstico

- Si `/start` responde que el registro no está configurado, falta desplegar el nuevo Worker o añadir su binding KV.
- Si no responde, revisar Cloudflare **Workers & Pages → arbiscan → Observability** y `getWebhookInfo` mediante la acción de diagnóstico existente.
- Si `/estado` confirma la suscripción y no llegan alertas, puede ser que el escáner todavía no haya detectado ningún candidato.
- El último código y pruebas están en `worker/arbiscan.mjs` y `worker/arbiscan.test.mjs`. El escáner está en `fuentes_es/oddspapi.py`.
