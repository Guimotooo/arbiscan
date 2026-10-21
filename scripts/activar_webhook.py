"""Register the Cloudflare ArbiiScan Worker as Telegram's webhook.

Run only through a GitHub Actions manual dispatch. Never print tokens.
"""
import json
import ipaddress
import ssl
import socket
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, quote
from urllib.request import Request, urlopen


def request_api(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if payload else {}
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=20) as res:
            body = res.read(100000)
        return json.loads(body)
    except HTTPError as exc:
        # Do not print the request URL: Telegram embeds the bot token in it.
        if exc.code == 401:
            raise RuntimeError("Telegram devuelve HTTP 401 (token no autorizado). Actualiza TELEGRAM_BOT_TOKEN en GitHub con el token nuevo.") from None
        if exc.code == 403:
            raise RuntimeError("Telegram devuelve HTTP 403 (acceso prohibido). Revisar si Telegram bloquea esta solicitud o si hay una restricción de red.") from None
        if exc.code == 400:
            try:
                error_data = json.loads(exc.read(4096).decode("utf-8", errors="replace"))
                description = str(error_data.get("description", "Solicitud no válida"))
                # Never disclose the bot token or webhook secret in logs.
                description = description.replace(os.getenv("TELEGRAM_BOT_TOKEN", ""), "[REDACTED]")
                description = description.replace(os.getenv("WEBHOOK_SECRET", ""), "[REDACTED]")
                description = re.sub(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b", "[REDACTED]", description)
                raise RuntimeError("Telegram HTTP 400: " + description[:350])
            except (ValueError, UnicodeError):
                raise RuntimeError("Telegram HTTP 400: respuesta no válida") from None
        raise RuntimeError(f"Telegram devuelve HTTP {exc.code} al registrar el webhook.") from None
    except (URLError, ValueError):
        raise RuntimeError("No se pudo contactar con Telegram o interpretar su respuesta.") from None



def resolve_and_validate_ip(hostname):
    """Resolve A records through DNS-over-HTTPS, validate TLS and the health endpoint."""
    endpoint = "https://cloudflare-dns.com/dns-query?name=" + quote(hostname, safe="") + "&type=A"
    try:
        req = Request(endpoint, headers={"Accept": "application/dns-json", "User-Agent": "ArbiiScanWebhookSetup/1.0"})
        with urlopen(req, timeout=15) as response:
            dns = json.load(response)
    except (HTTPError, URLError, ValueError):
        raise RuntimeError("No se pudo consultar DNS-over-HTTPS para el dominio del Worker.") from None
    ips = []
    for record in dns.get("Answer", []):
        if record.get("type") != 1:
            continue
        try:
            addr = ipaddress.ip_address(record.get("data", ""))
        except ValueError:
            continue
        if addr.version == 4 and addr.is_global:
            ips.append(str(addr))
    if not ips:
        raise RuntimeError("DNS no devuelve una IPv4 pública para el Worker. No se fuerza ninguna IP insegura.")
    for ip in ips[:4]:
        try:
            with socket.create_connection((ip, 443), timeout=8) as sock:
                with ssl.create_default_context().wrap_socket(sock, server_hostname=hostname) as tls:
                    tls.settimeout(8)
                    tls.sendall(("GET /health HTTP/1.1\r\nHost: " + hostname +
                                 "\r\nConnection: close\r\n\r\n").encode("ascii"))
                    data = b""
                    while len(data) < 4096:
                        part = tls.recv(4096)
                        if not part:
                            break
                        data += part
                    if b"ArbiiScan webhook disponible" in data and b"200" in data.split(b"\r\n", 1)[0]:
                        return ip
        except (OSError, ssl.SSLError):
            continue
    raise RuntimeError("Ninguna IP pública resuelta supera la comprobación HTTPS del Worker.")


def main():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    secret = os.getenv("WEBHOOK_SECRET", "").strip()
    raw_url = os.getenv("WORKER_URL", "").strip().rstrip("/")
    if not bot_token:
        raise ValueError("Falta el secreto TELEGRAM_BOT_TOKEN en GitHub.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", secret):
        raise ValueError("Añade WEBHOOK_SECRET a GitHub (mismo valor nuevo de Cloudflare, 16-256 caracteres alfanuméricos).")
    parsed = urlsplit(raw_url)
    if (parsed.scheme != "https" or not parsed.hostname or
            not parsed.hostname.endswith(".workers.dev") or parsed.username or
            parsed.password or parsed.port or parsed.query or parsed.fragment or
            parsed.path not in ("", "/")):
        raise ValueError("WORKER_URL debe ser https://nombre.subdominio.workers.dev, sin rutas ni parámetros.")
    print("Comprobando endpoint de salud de Cloudflare...")
    try:
        health_request = Request(raw_url + "/health", headers={
            "User-Agent": "Mozilla/5.0 (compatible; ArbiiScanWebhookSetup/1.0)",
            "Accept": "text/plain,*/*"
        })
        with urlopen(health_request, timeout=15) as response:
            health = response.read(512).decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"Cloudflare devuelve HTTP {exc.code} al runner de GitHub. Revisa reglas WAF o protección de bots para /health.") from None
    except URLError:
        raise RuntimeError("GitHub no puede conectar con el Worker. Revisa la URL y el dominio.") from None
    if health.strip() != "ArbiiScan webhook disponible":
        raise RuntimeError("La URL no contiene todavía el Worker ArbiiScan. Revisa que Cloudflare haya desplegado worker/arbiscan.mjs.")
    print("Worker ArbiiScan verificado: /health OK.")
    base = "https://api.telegram.org/bot" + bot_token + "/"
    payload = {
        "url": raw_url + "/telegram",
        "secret_token": secret,
        "allowed_updates": ["message"],
        "drop_pending_updates": False
    }
    try:
        result = request_api(base + "setWebhook", payload)
    except RuntimeError as exc:
        if "Failed to resolve host" not in str(exc):
            raise
        print("Telegram no resuelve workers.dev. Probando la opción oficial ip_address...")
        fixed_ip = resolve_and_validate_ip(parsed.hostname)
        payload["ip_address"] = fixed_ip
        result = request_api(base + "setWebhook", payload)
        print("Telegram aceptó una IPv4 verificada sin depender de su DNS.")
    if not result.get("ok"):
        raise RuntimeError("Telegram rechazó la activación del webhook: " + str(result.get("description", "Error desconocido")))
    info = request_api(base + "getWebhookInfo")
    webhook = info.get("result", {})
    if not info.get("ok") or webhook.get("url") != raw_url + "/telegram":
        raise RuntimeError("Telegram no confirma la dirección del webhook.")
    print("Webhook registrado y confirmado correctamente.")
    print("Dirección pública: " + webhook.get("url", ""))
    print("Actualizaciones permitidas: mensajes.")
    print("Siguiente acción: desactivar GitHub Actions - consultas Telegram para evitar getUpdates en paralelo.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Print message only, never traceback with URL containing bot token.
        print("ERROR:", str(error))
        sys.exit(1)
