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
scalper games                    # partidos en vivo enlazados a mercados
scalper flow --min-usd 5000      # trades grandes recientes, con score de la wallet
scalper wallets --top 30         # ranking de wallets perfiladas
scalper profile 0x2a69660046d7acc4ab204d7cc5ba78b0776cd2f7
scalper calibrate --nba-csv nbastats_2023.csv   # σ del modelo de básquet con play-by-play real
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

### Feeds para in-play y ballenas (`sports_feed.py`, `flow.py`, `wallets.py`)
- **Partidos en vivo**: websocket de deportes de Polymarket (sin suscripción). Marcador, período
  y estado por partido; el `gameId` enlaza con `event.gameId` de los mercados. Tabla `games`,
  solo se guardan cambios de estado y, por defecto, solo partidos enlazados a mercados seguidos.
- **Flujo con identidad**: sondeo de `data-api /trades`, que trae la wallet de cada trade. Se
  guarda todo lo de los mercados seguidos y cualquier trade global grande (tabla `flow_trades`).
- **Wallets**: un trade de más de `whale_min_usd` pone la wallet en cola. Se leen sus últimas
  posiciones cerradas (ganancia realizada por mercado, ordenadas por fecha: el orden por defecto
  del endpoint es por ganancia y sesga la muestra) y sus abiertas, y se calcula un score con
  encogimiento bayesiano: pocas operaciones o retornos menores al 2 % no dan evidencia; muchas
  operaciones con ROI positivo sí (`wallet_profiles`, `wallet_closed`). `scalper wallets` lista
  el ranking; `scalper profile <wallet>` perfila una a mano; `scalper flow` muestra trades grandes.
- **Retraso**: el flujo con identidad llega 2 a 3 minutos después que el websocket del CLOB. Sirve
  para perfilar y para señales de "entró dinero inteligente"; no para competir en latencia.

### Modelos de probabilidad en vivo (`scalper/models/`)
Todos parten del precio previo al partido (capturado del propio mercado antes de que arranque)
y lo actualizan con el marcador. Sin precio previo, solo se modela si el partido acaba de empezar.

- **Básquet** (`basketball.py`): modelo de Stern. El margen es un movimiento browniano:
  `P(local) = Φ((ventaja + deriva·τ) / (σ·√τ))`. σ calibrado con 1.230 partidos de la NBA
  2023-24: **16,2 puntos** (la literatura clásica decía 11-12; el ritmo actual es mayor). La
  varianza real escala con √τ casi exactamente. `scalper calibrate --nba-csv <archivo>` lo
  recalcula con cualquier temporada del dataset público `shufinskiy/nba_data`; sin argumento,
  usa los partidos terminados de la tabla `games` propia.
- **Tenis** (`tennis.py`): cadena de Markov por puntos (O'Malley). Las probabilidades de punto
  al saque se infieren del precio previo y se propaga desde sets, juegos y tiebreak actuales.
- **Fútbol** (`soccer.py`): goles restantes como Poisson por equipo; las tasas salen del precio
  previo de local/empate/visitante. Devuelve las tres probabilidades para los mercados de 3 salidas.

### Detectores in-play y de dinero inteligente
- **model_deviation**: para cada token enlazado a un partido en vivo, si
  `p_modelo − ask − fee(entrada) − costo de salida > umbral`, compra como taker. Sale cuando el
  bid alcanza el target (el modelo), en el stop, por tiempo máximo o al terminar el partido
  (liquidación con el marcador final). Desvíos mayores a `max_deviation` se descartan: casi
  siempre son un marcador mal leído, no una oportunidad.
- **smart_money**: cuando el flujo con identidad muestra un trade de una wallet con perfil
  (score y muestra mínimos) en un mercado seguido, sigue el mismo lado si el ask no se ha alejado.
  La ganancia esperada es una hipótesis (fracción de su ROI histórico); el ledger la contrasta.

### Lo que viene (fase 5)
Con el ledger y las tablas `quotes`/`trades`/`games`, se entrena un modelo (gradient boosting)
que predice, por señal, la probabilidad de que termine en ganancia y el tamaño del error. Se
sustituye la heurística de `confidence` por la salida del modelo y se reentrena por ventana,
comparando siempre contra la versión anterior en replay antes de reemplazarla.

## Advertencias honestas
- Los arbitrajes puros aparecen poco y duran milisegundos; los bots existentes compiten por ellos.
  El valor de esta fase es medir con datos reales cuántos aparecen, cuánto duran y qué tan seguido
  la latencia los rompe.
- Nada aquí es asesoría financiera. Polymarket restringe usuarios de varios países.
