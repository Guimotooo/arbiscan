# Importador manual de cuotas de casas de apuestas

Convierte cuotas que el usuario escribe o copia en un archivo de texto a
registros del motor ArbiiScan, sin depender de OddsPapi. Es un importador
local, no consulta páginas web ni verifica disponibilidad de una apuesta.

Ejemplo de archivo mis_cuotas.txt:

```text
[market]
book=bet365.es
sport=soccer
home=Cambrian United
away=Airbus UK Broughton
kickoff=2026-10-25T20:00:00+01:00
market=1x2:regulation
1=2,80
X=3,20
2=2,60

[market]
book=winamax.es
sport=soccer
home=Cambrian United
away=Airbus UK Broughton
kickoff=2026-10-25T20:00:00+01:00
market=1x2:regulation
1=2,70
X=3,40
2=2,85
```

Los precios del ejemplo son FICTICIOS.

```bash
python -m motor_propio.manual_import --input mis_cuotas.txt --output mercados.json
python -m motor_propio.run --feed mercados.json
```

Los campos del evento y la definición exacta de su mercado son obligatorios.
También se admite escribir cuotas como `1 2,80` o `X @ 3,20`.
Las observaciones se etiquetan como `manual_observation`.

Este flujo no genera alertas de Telegram y no equivale a un sistema de
extracción automática de cuotas en tiempo real.
