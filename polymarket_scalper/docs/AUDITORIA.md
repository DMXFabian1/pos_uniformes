# Auditoría de arquitectura (FASE 1 de la misión)

Fecha: 2026-09-11. Estado auditado: commit `ec3b2d6` (89 tests, maker-first recién incorporado).
**Estado de ejecución del plan al final de esta sesión: cambios A, B, C, D, E, F, G y H hechos
(142 tests). Lo que queda pendiente está al final, en §9.**

Este documento responde, antes de tocar código, a las ocho preguntas de la misión: qué existe,
qué está duplicado, qué datos se capturan y no se usan, qué métricas faltan, qué partes del
simulador pueden producir resultados falsos, y en qué orden conviene evolucionar el sistema.
Cada cambio propuesto lleva motivo, archivos, impacto esperado, tests y métricas de verificación.

---

## 1. Qué hay hoy (mapa honesto)

| Capa | Módulos | Estado |
|---|---|---|
| Captura | `collector.py`, `clob.py`, `sports_feed.py`, `crypto_feed.py`, `flow.py`, `wallets.py` | Libro completo por websocket (snapshot + deltas absolutos por nivel), trades impresos, feed de partidos, precio spot cripto, flujo con wallet (data-api, 2–5 min de retraso). Persistencia Parquet por día. |
| Libro | `book.py` | Mejor bid/ask, mid, spread, imbalance **solo en el mejor nivel**, profundidad acumulada a N ticks, walk taker. |
| Modelos | `models/basketball.py` (Stern, σ calibrada 16.2), `tennis.py` (O'Malley), `soccer.py`, `crypto.py` (difusión) | Probabilidad en vivo. Sin modelo de *reacción* del mercado: el modelo dice "vale X", no "cuánto tarda el precio en llegar a X". |
| Señales | `signals/*` (6 detectores, 8 `kind`) | Emiten edge bruto/neto y confianza heurística. Maker-first en los tres direccionales. |
| Simulador | `sim/engine.py`, `sim/fill_model.py`, `sim/ledger.py` | Latencia fija, slippage por ticks, taker camina el libro, maker se llena con trades que cruzan más un dado aleatorio (`maker_fill_prob = 0.6`). |
| Aprendizaje | `learn/*` | P(ganar) por `kind`, campeón/retador con partición temporal, mezcla con la heurística. Un solo modelo por señal: no separa fill de salida. |
| Informes | `readiness.py`, `opportunities.py`, `diagnostico.py`, `studies.py`, `dashboard/*`, `qtapp.py` | Veredicto "listo" con t-stat, tarjetas de decisión, radiografía del mercado. |

## 2. Cobertura de los 48 puntos de la misión

Leyenda: ✅ existe · 🟡 parcial · ❌ falta.

| Punto de la misión | Estado | Dónde / qué falta |
|---|---|---|
| RAW / EXECUTABLE / REALIZED edge | 🟡 | Hay `edge_gross`, `edge_net` (ejecutable estimado) y `realized_pnl`. No se guarda el edge ejecutable *conservador* ni el edge aparente vs realizado como métrica agregada. |
| Microestructura: profundidad 1/2/3/5 ticks | 🟡 | `depth_within` existe pero solo se usa a 5 ticks en `quotes` y en features. |
| Imbalance por profundidad | 🟡 | Solo mejor nivel. |
| Order flow / cancelaciones | ❌ | Los deltas guardan tamaño absoluto; el flujo neto (altas − bajas) no se deriva ni se usa. |
| Velocidad de precio 250 ms…60 s | ❌ | `mid_vol` a 5 min. No hay ventanas cortas. |
| Market Reaction Engine (evento → reacción) | ❌ | Se tiene el marcador y el libro con timestamps, pero nadie mide el retraso entre cambio de marcador y movimiento del precio. |
| `event_risk_score` | ❌ | |
| Entrada MAX / IDEAL / AGRESIVA por edge y P(fill) | 🟡 | `precio_maker` calcula un solo precio (el más alto que no cruza y deja `min_edge`). |
| Fill model: P(fill), P(mov. favorable\|fill), P(salida\|fill), escenarios, posición en cola | 🟡→❌ | Hay cola inicial (`queue_ahead`) pero el llenado final depende de un dado con probabilidad inventada. Sin escenarios. |
| Exit engine: salida conservadora/ideal, stop, time stop | 🟡 | Target/stop existen. `max_hold_directional = 4 h`: para scalping no es un time stop, es una siesta. No hay salida maker. |
| Tiempo hasta reacción por señal | ❌ | |
| Filtro global NO TRADE | 🟡 | Los filtros existen dentro de cada detector, pero la decisión de no operar **no se registra**. |
| Strategy IDs separados | 🟡 | Existe `kind`. No hay separación NBA/tenis en `model_deviation` ni 5m/15m en cripto. |
| Selección adversa (precio tras el fill a 100 ms…10 s) | ❌ | |
| Edge aparente vs realizado | 🟡 | Solo `error = realizado − predicho` por posición. |
| Backtest event-driven sin look-ahead | ✅ | `replay.py` reproduce la corriente ordenada por timestamp. Ver auditoría de fugas en §5. |
| Walk-forward | ❌ | Una única partición temporal 70/30. |
| Métricas obligatorias y deciles | 🟡 | Hay t-stat, Brier, tasa de acierto. Faltan deciles por edge, drawdown, PnL por hora. |
| Sizing con topes por mercado / partido / correlación | 🟡 | Solo `max_position_usd` y `max_open_positions`. |
| Bankroll simulado | ✅ | `cash`, `start_cash`. |
| Costes completos | 🟡 | Fee taker y slippage. Falta coste de oportunidad de la orden no llenada y latencia real medida. |
| Fills parciales | 🟡 | El taker rellena lo que hay; el maker acumula parciales. No se reportan. |
| Latencia registrada | ❌ | El colector guarda el timestamp del exchange, no el de recepción. |
| Oportunidades perdidas | ❌ | |
| Opportunity Score explicable | 🟡 | Confianza heurística con fórmulas ad hoc. |
| ML solo para P(trade rentable) | ✅ | Ya es así. |
| Fill model y exit model separados | ❌ | |
| Criterios de activación estrictos | ✅ | `readiness.py` (100 posiciones, t ≥ 2, 7 días, modelo no peor). Faltan drawdown y validación fuera de muestra. |
| Monte Carlo / bootstrap / stress | ❌ | |
| Prioridad S/A/B/C/NO TRADE | 🟡 | ENTRAR / AJUSTADA / YA PASÓ. |
| Tarjeta con "por qué existe este trade" | 🟡 | Hay razón en palabras; falta la frase única de desalineación temporal. |
| Log de cada decisión, incluidas NO TRADE | ❌ | |
| Benchmark vs heurística anterior / hold / azar | ❌ | |
| 60 % de fill como BASELINE con tasa observada, conservadora y break-even | ❌ | Es lo más urgente: hoy el 60 % **genera** los resultados. |

## 3. Duplicaciones

1. **Ruta taker dentro de los tres detectores direccionales.** `model_deviation`, `smart_money` y `updown` repiten el bloque "si maker: `precio_maker`; si no: `walk_buy` + fee". Es tolerable (tres copias, 12 líneas) pero debe salir a una función común cuando entre la elección MAX/IDEAL/AGRESIVA, o habrá tres implementaciones divergentes.
2. **Métricas del ledger por triplicado**: `sim/metrics.py`, `dashboard/data.py::_ledger_sections` y `readiness.py` recalculan "válidas = llenadas y no excluidas", tasa de acierto y Brier con pequeñas diferencias. Riesgo real: un informe puede decir "listo" y otro no sobre los mismos datos. Debe existir una sola función de métricas por estrategia que los tres consuman.
3. **`EXCLUDED_EXITS`** vive en `learn/train.py` y se importa desde `readiness` y `dashboard`; el `FORCED` del HTML es otra copia a mano. `sin_llenar` no está en ninguna (se filtra por `size_filled > 0`, que funciona pero es implícito).

## 4. Datos capturados que no se usan

| Dato | Dónde se guarda | Uso hoy | Uso posible |
|---|---|---|---|
| Tamaño absoluto por nivel en cada delta | `book_deltas` | Reconstruir libro en replay | Flujo de órdenes: altas − bajas por lado y ventana; tasa de cancelación. |
| `best_bid`/`best_ask` que trae cada delta | `book_deltas` | Nada | Velocidad de precio a 250 ms sin reconstruir el libro. |
| Trades con lado y tamaño | `trades` | Solo para `tpm` en spread capture y para fills maker | Flujo agresor comprador − vendedor por ventana; volumen que cruza cada precio (base del fill model). |
| Profundidad a 5 ticks | `quotes` | Feature de aprendizaje | Profundidad 1/2/3 ticks; ratio profundidad/tamaño propio (P(fill)). |
| Timestamp de cada cambio de marcador | `games` | Modelo de probabilidad | Retraso evento → reacción del precio (Market Reaction Engine). |
| Trades del flujo con precio y wallet | `flow_trades` | Smart money | Detección de agresión institucional (cluster de trades grandes en < 5 s). |
| `hash` de libro | `book_snapshots` | Nada | Detección de deltas perdidos (comparar hash tras aplicar). |

## 5. Partes del simulador que pueden producir resultados falsos

Ordenadas de más a menos grave.

1. **`maker_fill_prob = 0.6`.** Cada trade que cruza nuestro precio nos llena con probabilidad 0,6 independientemente del tamaño del trade, de cuánto había delante o de si el nivel fue cancelado. Es una constante inventada que decide directamente la tasa de llenado y, por tanto, el PnL de todo lo maker-first. *Nada de lo que hoy dice el ledger sobre señales maker es evidencia.*
2. **Selección adversa invisible.** `maker_on_book` llena la orden entera cuando el ask baja hasta nuestro precio: eso es correcto (nos cruzaron), pero el simulador no mide qué pasa con el precio después. Los fills que ocurren porque el mercado se hunde son los peores y no se distinguen de los buenos.
3. **Sin latencia medida.** `latency_ms = 400` fijo. El timestamp del exchange se guarda; el de recepción no. No se puede saber si 400 es optimista.
4. **Cola estática.** `queue_ahead` se toma al poner la orden y solo baja con trades; las cancelaciones delante de nosotros no la reducen ni las altas la aumentan (las altas van detrás, así que eso último es correcto).
5. **Salida de posiciones direccionales**: `target` se declara alcanzado cuando `best_bid ≥ target`, y la salida se simula cruzando el libro (taker, con fee). Correcto y conservador. Pero el `stop` mira el mid, no el bid al que realmente se vendería: ligeramente optimista.
6. **`max_hold_directional = 4 h`** convierte una señal de scalping en una apuesta al resultado. El PnL que salga de ahí no mide la tesis de "desalineación temporal".
7. **Valoración de posiciones abiertas al cerrar la corrida** (`_valorar`): ya se corrigió (precio tocable → último mid → peor caso) y esas filas quedan excluidas de las estadísticas. Correcto.
8. **Fugas de información (look-ahead)**: revisado `replay.py`, `engine.py`, `learn/features.py`.
   - La corriente se ordena por `(ts, prioridad)`; los partidos previos al rango se aplican antes. ✅
   - Las features se calculan **en el momento de la señal** y viajan en `meta` hasta el ledger; el entrenamiento las lee de ahí. ✅ No hay reconstrucción a posteriori.
   - La etiqueta es `realized_pnl > 0`, conocida solo al cerrar. ✅
   - `prev_window` (cripto) usa la ventana **anterior ya liquidada**. ✅
   - El strike se toma del primer precio en o después de la apertura. ✅
   - Riesgo pendiente: en `paper`, el feed de partidos y el libro llegan por canales distintos; si el feed de partidos se retrasa, el modelo "ve" un marcador viejo con un precio nuevo. No es look-ahead (es look-behind), pero infla la aparente desalineación. El Market Reaction Engine debe medirlo.
9. **Duplicado de señal**: la misma oportunidad se re-detecta cada 250 ms; `_on_signal` la descarta si ya hay posición con ese `kind` y mercado. ✅ Pero no se cuenta cuánto tiempo estuvo disponible (oportunidad perdida / decay).

## 6. Métricas que faltan

Por estrategia, además de las actuales (n, PnL, media, t, acierto, fees, Brier):

- Tasa de llenado **observada** (por escenario: conservador / base / optimista), frente al 60 % de baseline.
- **Break-even fill rate**: tasa de llenado a la que poner la orden iguala a cruzar el libro:
  `p* = edge_taker / edge_maker` (si `edge_taker ≤ 0`, cualquier fill positivo gana).
- **Edge mínimo requerido**: `coste_salida + selección_adversa_media + margen` — por debajo de ese edge la señal es NO TRADE por construcción.
- Selección adversa: movimiento del mid contra la posición a 100 ms, 500 ms, 1 s, 2 s, 5 s, 10 s tras el fill.
- Edge aparente vs realizado (medias y ratio), por estrategia y por decil de edge.
- Tiempo hasta target / stop / time-stop; distribución de duración.
- Drawdown máximo del bankroll, PnL por hora de exposición, Sharpe por operación.
- Fills parciales: fracción llenada media.
- Oportunidades perdidas: señales que pasaron el edge pero no la ejecución (sin cash, tope de posiciones, sin llenar), con el PnL que habrían tenido a "mark".
- Latencia feed → motor (mediana, p95) por canal.

---

## 7. Plan incremental

Principio: **primero que el simulador deje de inventar, luego que mida, luego que decida mejor.**
Nada de lo siguiente añade estrategias nuevas; todo mejora la capacidad de saber si las actuales
valen.

### Cambio A — Fill model por cola, sin dado (FASE 5, adelantada porque es lo que falsea todo)
- **Motivo**: §5.1. Sustituir la probabilidad inventada por un modelo determinista de cola: la orden se llena cuando el volumen que cruza su precio supera lo que había delante más su propio tamaño. Tres escenarios por orden: CONSERVADOR (cola completa, cancelaciones delante no cuentan), BASE (cola menos cancelaciones observadas en el nivel), OPTIMISTA (solo el propio tamaño). El ledger opera con BASE; los tres se registran para poder comparar.
- **Archivos**: `sim/fill_model.py`, `sim/engine.py`, `sim/ledger.py`, `config.py` (`maker_fill_prob` → `fill_baseline_prob`, solo informativo), `tests/test_engine.py`, `tests/test_maker_first.py`, nuevo `tests/test_fill_model.py`.
- **Impacto**: la tasa de llenado pasa a depender de datos observados. Se espera que **baje** respecto al 60 %.
- **Tests**: cola delante que se consume por trades; cancelación en el nivel reduce la cola en BASE pero no en CONSERVADOR; fill parcial; mercado que cruza nos llena entero.
- **Métricas**: tasa de llenado por escenario, break-even fill rate, comparación con baseline en `scalper ejecucion` y en el panel.

### Cambio B — Timestamps de recepción y flujo firmado en captura (FASE 2)
- **Motivo**: §5.3 y §4. Sin `recv_ms` no hay latencia medible; sin el signo del cambio de nivel no hay order flow.
- **Archivos**: `collector.py`, `storage.py` (columnas `recv_ms`, `delta_size`), `book.py` (`apply_delta` devuelve el cambio).
- **Impacto**: cero en decisiones; habilita métricas de latencia y microestructura. Compatible con datos viejos (columnas nulas).
- **Tests**: `apply_delta` devuelve delta firmado; el escritor acepta filas con y sin las columnas nuevas.
- **Métricas**: latencia feed→motor mediana/p95 en el log de estado.

### Cambio C — Features de microestructura (FASE 3)
- **Motivo**: §2. Profundidad 1/2/3/5, imbalance por profundidad, flujo de órdenes (altas − bajas), flujo agresor, velocidad de precio a 250 ms / 1 s / 5 s / 15 s / 60 s.
- **Archivos**: nuevo `micro.py`, `signals/base.py` (`TokenHistory` guarda cambios de nivel y mids), `learn/features.py` (nuevas columnas numéricas), `sim/engine.py` (calcula y adjunta a `meta["micro"]`).
- **Impacto**: features disponibles para el modelo y para el opportunity score. No cambia decisiones hasta que el modelo las use.
- **Tests**: valores exactos sobre libros sintéticos; velocidad con mids sintéticos; ventanas vacías dan 0.
- **Métricas**: importancia por permutación en `scalper train`.

### Cambio D — Log de decisiones (incluidas NO TRADE), strategy IDs y selección adversa
- **Motivo**: §2 y §6. Sin registro de lo que se descartó no se puede saber si los filtros son demasiado estrictos o demasiado laxos.
- **Archivos**: `storage.py` (tabla `decisions`), `sim/engine.py` (registrar cada rechazo con motivo, deduplicado por mercado y motivo cada 30 s; marcas post-fill a 100 ms…10 s), `signals/base.py` (`strategy_id` derivado de `kind` + deporte/ventana), `sim/ledger.py` (columna `strategy`).
- **Impacto**: nuevo dato; decisiones sin cambios.
- **Tests**: un rechazo por tope de posiciones queda registrado con motivo; marcas post-fill se rellenan con los libros posteriores.
- **Métricas**: rechazos por motivo; selección adversa por horizonte y estrategia.

### Cambio E — Exit engine: time stop y stop sobre precio tocable (FASE 6)
- **Motivo**: §5.5 y §5.6.
- **Archivos**: `config.py` (`time_stop_s` por estrategia), `sim/engine.py`.
- **Impacto**: posiciones direccionales duran minutos, no horas. El PnL medirá la tesis de scalping y no el resultado del partido.
- **Tests**: posición que no converge sale por `time_stop` al vencer; stop usa `best_bid`.
- **Métricas**: distribución de motivos de salida y duración.

### Cambio F — Market Reaction Engine y `event_risk_score` (FASE 4)
- **Motivo**: §2. Medir, por partido y mercado, cuánto tarda el mid en moverse tras un cambio de marcador, y cuánto se mueve. El resultado alimenta `time_to_reaction` de la señal y el filtro de riesgo de evento (marcador muy reciente = riesgo de que el feed vaya por delante o por detrás del mercado).
- **Archivos**: nuevo `reaction.py`, `storage.py` (tabla `reactions`), `sim/engine.py`, `signals/model_deviation.py` (adjunta `event_risk_score`, `time_to_reaction_ms`).
- **Impacto**: nuevo dato y nueva feature. Sin cambio de decisión hasta tener distribución.
- **Tests**: cambio de marcador seguido de movimiento del mid → una fila de reacción con el retraso correcto; sin movimiento en 60 s → reacción nula registrada.
- **Métricas**: retraso mediano por liga; fracción de eventos sin reacción.

### Cambio G — Métricas unificadas, walk-forward y bootstrap (FASE 7–9, 11)
- **Motivo**: §3.2, §6. Una sola función `metricas_por_estrategia` que consuman `readiness`, `metrics`, `dashboard`. Walk-forward con k ventanas temporales en `learn`. Bootstrap del PnL medio (IC 95 %) y stress (fees ×1,5, fill CONSERVADOR, latencia ×2) en un comando `scalper validar`.
- **Archivos**: nuevo `evaluacion.py`, `learn/train.py`, `readiness.py`, `dashboard/data.py`, `cli.py`.
- **Impacto**: los informes dejan de discrepar; el veredicto "listo" exige además IC 95 % del PnL medio > 0 y walk-forward estable.
- **Tests**: bootstrap sobre una muestra conocida; walk-forward sobre ejemplos sintéticos.

### Cambio H — Panel: tasa de llenado, edge mínimo, tarjeta con "por qué existe"
- **Motivo**: la misión lo exige explícitamente.
- **Archivos**: `dashboard/data.py`, `dashboard/static/index.html`, `opportunities.py`.

### Qué NO se hace todavía
- Modelos de ML separados para fill y salida: hacen falta cientos de órdenes maker con sus tres escenarios registrados. Se construye el dato (A, D) y se entrena cuando lo haya.
- Capa de ejecución real: sigue fuera hasta que `scalper listo` y `scalper validar` pasen.

---

## 8. Reglas de evidencia que se aplican a cada cambio

- Ningún número del ledger anterior a estos cambios cuenta como evidencia de rentabilidad maker: se generó con el dado del 60 %.
- Todo fill maker registra los tres escenarios; el informe muestra siempre observado vs baseline.
- Cada métrica nueva nace con su test sobre datos sintéticos de resultado conocido.
- No se ajusta ningún umbral a mano "porque mejora el PnL de la muestra". Los umbrales se mueven solo con walk-forward.


---

## 9. Qué se hizo y qué falta

### Hecho en esta sesión

| Cambio | Qué cambió | Cómo se comprueba |
|---|---|---|
| **A** | El fill maker ya no sale de un dado. Una orden se llena cuando el volumen que cruza su precio consume la cola que tenía delante. Se registran tres escenarios (conservador, base, optimista), la cola inicial, el volumen cruzado y si el nivel fue barrido. `maker_fill_prob` pasó a llamarse `fill_baseline_prob` y solo aparece en los informes como referencia. | `tests/test_fill_model.py`, `scalper ejecucion` |
| **B** | Cada mensaje del CLOB guarda `recv_ms`; cada delta guarda el cambio firmado del nivel. El recolector reporta latencia mediana y p95 del feed. | línea de estado del recolector, `tests/test_micro.py` |
| **C** | `micro.py`: profundidad e imbalance a 1/2/3/5 ticks, altas y bajas por lado, tasa de cancelación, flujo agresor y velocidad del mid a 250 ms…60 s, adjuntos a cada señal y disponibles como features. | `tests/test_micro.py` |
| **D** | Tabla `decisions` con cada decisión, incluidas las de NO operar y su motivo. `strategy_id` separa NBA, tenis, cripto 5m/15m, arbitraje y dinero inteligente. Marcas de selección adversa a 100 ms…10 s tras el fill. `edge_taker` guardado en cada señal. | `tests/test_decisiones.py`, panel → Ejecución |
| **E** | Time stop de 15 minutos para direccionales; el stop mira el mejor bid, no el mid; topes de exposición por mercado y por evento. | `tests/test_decisiones.py` |
| **F** | `reaction.py` mide el retraso entre cambio de marcador y movimiento del mid (tabla `reactions`) y expone `ms_since_event`, retraso típico por liga y `event_risk_score` explicable. | `tests/test_reaction.py`, panel → Ejecución |
| **G** | `evaluacion.py` es la única fuente de métricas: tasa de llenado observada/conservadora/optimista, break-even de llenado, edge mínimo requerido, selección adversa, aparente vs realizado, deciles, bootstrap y pruebas de resistencia. `readiness.py` la consume y añade tres criterios nuevos. `learn/train.py` añade walk-forward. | `tests/test_evaluacion.py`, `scalper ejecucion`, `scalper validar`, `scalper listo` |
| **H** | Panel con sección Ejecución; tarjetas con prioridad S/A/B/C/NO TRADE y la frase de por qué existe el trade. | `tests/test_dashboard.py` |

### Pendiente, y por qué

1. **Modelos separados de fill y de salida.** Necesitan cientos de órdenes maker con sus tres
   escenarios registrados. El dato ya se está generando (cambio A y D); entrenarlos ahora sería
   ajustar ruido.
2. **Activar el filtro `event_risk_score`.** Está medido y guardado, pero `max_event_risk` sigue
   en 1.0 (no filtra). Fijar un umbral sin ver la distribución sería inventarlo.
3. **Entradas MAX / IDEAL / AGRESIVA.** Hoy `planear_entrada` calcula un solo precio límite. La
   elección entre varios precios según P(fill) necesita el modelo de fill del punto 1.
4. **Benchmark contra comprar y mantener y contra azar.** Requiere una muestra con varios días
   de partidos; con las horas que hay, cualquier comparación diría más del muestreo que de la
   estrategia.
5. **Capa de ejecución real.** Sigue deliberadamente fuera hasta que `scalper listo` y
   `scalper validar` pasen a la vez.

### La regla que no cambia

Ningún número del ledger anterior al cambio A cuenta como evidencia sobre las señales maker: se
generó con el dado del 60 %. La cuenta de posiciones válidas para el veredicto empieza de cero
con los datos nuevos.
