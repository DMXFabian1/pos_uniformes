# polymarket_scalper

Bot de scalping para Polymarket enfocado en mercados de **deportes** y **política**.
Esta entrega cubre las fases 1 a 3: recolectar datos, detectar oportunidades deterministas
y simularlas (replay y paper trading) midiendo cuánto se equivoca cada predicción.
La fase 4 (modelo que aprende de ese error) se construye encima cuando haya semanas de datos.

> Proyecto independiente. Vive en esta carpeta solo hasta tener su repo propio:
> `git subtree split -P polymarket_scalper -b polymarket_scalper` y push de esa rama.

## Instalación

```bash
cd polymarket_scalper
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Uso

```bash
scalper discover                 # qué mercados se seguirían con la config actual
scalper collect                  # fase 1: recolectar 24/7 (Ctrl+C para parar)
scalper status                   # qué hay en data/
scalper replay --start 2026-09-09T00:00 --end 2026-09-09T12:00   # fase 3 sobre histórico
scalper paper --duration 3600    # fase 3 en vivo, 1 hora, sin dinero
scalper report                   # predicho vs real por tipo de señal
scalper sql "select kind, count(*) from signals group by 1"
```

Todo se configura en `config.yaml`. Nada de esto toca una wallet ni firma órdenes.

## Cómo funciona

### Fase 1: recolector (`scalper/collector.py`)
- Descubre mercados vía Gamma API por tag (`sports`=1, `politics`=2), filtra por volumen y
  libro habilitado, y lee la tasa de fee real de cada mercado (`feeSchedule.rate`).
- Se suscribe al websocket del CLOB (canal `market`) y mantiene el libro de cada token en memoria.
- Persiste en Parquet particionado por día (`data/<tabla>/date=YYYY-MM-DD/`):

| tabla | contenido |
|---|---|
| `markets` | cada mercado visto, con fee, tick, evento, categoría, estado |
| `book_snapshots` | libro completo (websocket al conectar + resync REST periódico) |
| `book_deltas` | cada cambio de nivel, con mejor bid/ask del momento |
| `trades` | cada trade impreso, con su fee_rate_bps |
| `quotes` | top-of-book muestreado cada N segundos (para features rápidas) |
| `resolutions` | qué token ganó cuando el mercado cerró |

### Fase 2: señales (`scalper/signals/`)
Todas incluyen las comisiones: el taker paga `shares × rate × p × (1−p)`, el maker no paga.

- **complement_buy / complement_sell**: en un mercado binario, `ask_SÍ + ask_NO + fees < 1`
  (comprar ambos y fusionar por 1 USD) o `bid_SÍ + bid_NO − fees > 1` (partir 1 USD y vender ambos).
- **multi_buy_all_yes / multi_buy_all_no**: en eventos negRisk (exactamente un SÍ gana),
  la suma de todos los SÍ cuesta menos de 1, o la suma de todos los NO menos de n−1.
- **spread_capture**: spread ancho con actividad reciente; postear bid y ask dentro del spread
  como maker. Ganancia esperada = medio spread − volatilidad reciente del mid. Es la única señal
  con incertidumbre real y por eso la más interesante para aprender.

Cada señal lleva `edge_net` (USD por share después de fees), `confidence` (heurística 0..1),
`horizon` y `meta` con las features del momento.

### Fase 3: simulación (`scalper/sim/`)
- `engine.py` recibe los mismos eventos en replay y en paper trading. Aplica latencia, slippage
  y fees, arbitrajes rotos (una pata llena y la otra no) se deshacen contra el libro con su costo.
- Las órdenes maker se llenan solo cuando un trade cruza nuestro precio (con probabilidad
  configurable y cola por delante) o cuando el mercado pasa a través de nosotros.
- Cada posición cerrada se escribe al `ledger` con `predicted_pnl`, `realized_pnl` y `error`.
- `scalper report` agrupa por tipo de señal: tasa de llenado, PnL predicho vs real, error medio,
  tasa de acierto, y calibración de la confianza declarada vs la real.

### Lo que viene (fase 4)
Con el ledger y las tablas `quotes`/`trades`, se entrena un modelo (gradient boosting) que
predice, por señal, la probabilidad de que termine en ganancia y el tamaño del error. Se
sustituye la heurística de `confidence` por la salida del modelo y se reentrena por ventana,
comparando siempre contra la versión anterior en replay antes de reemplazarla.

## Advertencias honestas
- Los arbitrajes puros aparecen poco y duran milisegundos; los bots existentes compiten por ellos.
  El valor de esta fase es medir con datos reales cuántos aparecen, cuánto duran y qué tan seguido
  la latencia los rompe.
- Nada aquí es asesoría financiera. Polymarket restringe usuarios de varios países.
