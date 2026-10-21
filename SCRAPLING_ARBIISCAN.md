# Scrapling en ArbiiScan (21-10-2026)

El repositorio ahora incluye una alternativa basada en **Scrapling** para leer HTML y extraer cuotas de páginas públicas. El escáner de producción con OddsPapi y sus alertas de Telegram **no se han sustituido**.

## Archivos

- `scraping_es/scrapling_adapter.py`: integración de `scrapling.parser.Selector` para extraer cuotas mediante selectores CSS exactos; permite lectura HTML simple con `Fetcher.get`, o contenido JavaScript renderizado con **Playwright convencional** (Scrapling 0.5 ya no expone `DynamicFetcher`).
- `test_scrapling_es.py`: 7 pruebas, incluidas rechazo de precios ambiguos, páginas bloqueadas, eventos diferentes y HTTP 403.
- `scraping_es/scrapling_probe.py`: diagnóstico puntual de lectura pública de Winamax, sin obtener datos de cuentas ni enviar alertas.
- `.github/workflows/probar_scrapling.yml` y `.github/workflows/diagnostico_scrapling.yml`: tests y prueba puntual sin credenciales.

## Lo demostrado y lo pendiente

- Scrapling instalado en GitHub Actions; extracción sobre HTML de ejemplo pasa 7/7 tests.
- `Fetcher.get` desde GitHub obtiene HTTP 200 en el enlace Winamax proporcionado pero solo el HTML inicial de carga JavaScript (aprox. 1.252 caracteres de texto, sin el ID de partido dentro del HTML estático).
- Para leer Winamax se requiere navegador que ejecute JavaScript; el diagnóstico utiliza Playwright convencional y después Scrapling para interpretar el HTML.
- No se ha validado un selector estable para las cuotas 1X2 concretas de la página de Winamax.
- Bet365 ES había devuelto HTTP 403 desde GitHub; Scrapling no garantiza acceso ni cambia automáticamente el permiso técnico del servidor. No se incluyen CAPTCHA solving, proxies rotatorios ni técnicas para eludir controles de acceso.
- **No hay alertas de scraping activadas ni ganancias garantizadas.** El servicio anterior de OddsPapi sigue siendo la fuente operativa mientras se verifica la alternativa.

## Instalación

```bash
pip install "scrapling[fetchers]"
python -m unittest -v test_scrapling_es.py
```

Si se utiliza la opción de navegador dinámico, instalar Playwright y Chromium por separado:

```bash
python -m playwright install chromium
```

La lectura exacta del evento requiere crear `scraping_es/config.json` con URLs públicas y selectores CSS validados, siguiendo `SCRAPING_ES.md`. No se han inventado esos selectores. Una ejecución sin config es segura y no envía nada por Telegram.
