import json
import os
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
if not token:
    raise SystemExit("Falta TELEGRAM_BOT_TOKEN en GitHub Actions.")
try:
    with urlopen("https://api.telegram.org/bot" + token + "/getWebhookInfo", timeout=15) as res:
        data = json.load(res)
except (HTTPError, URLError):
    raise SystemExit("No se pudo consultar Telegram. Revisa el token de GitHub.")
if not data.get("ok"):
    raise SystemExit("Telegram no pudo devolver la información del webhook.")
info = data.get("result", {})
print("Webhook registrado:", bool(info.get("url")))
print("URL:", info.get("url", "(ninguna)"))
print("IP configurada:", info.get("ip_address", "(automática)"))
print("Actualizaciones pendientes:", info.get("pending_update_count", 0))
print("Último error:", info.get("last_error_message", "(ninguno)"))
print("Fecha del último error (Unix):", info.get("last_error_date", "(ninguna)"))
print("Último error de sincronización:", info.get("last_synchronization_error_date", "(ninguno)"))
