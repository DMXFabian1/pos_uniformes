# polymarket_scalper

Bot de scalping para Polymarket enfocado en **NBA**, **tenis** y los mercados **"Up or Down" de
cripto** (ventanas de 5 y 15 minutos). `config.amplio.yaml` guarda la versión con todos los
deportes y política por si se quiere ampliar; el código es el mismo.

> Temporada: la NBA arranca a fines de octubre. Hasta entonces solo aparecen sus futuros; el tenis
> (ATP, WTA, Challengers) aporta partidos en vivo todos los días y es donde se acumulan los datos
> para el modelo in-play.
Esta entrega cubre las fases 1 a 3: recolectar datos, detectar oportunidades deterministas
y simularlas (replay y paper trading) midiendo cuánto se equivoca cada predicción.
La fase 4 (modelo que aprende de ese error) se construye encima cuando haya semanas de datos.

> Proyecto independiente. Vive en esta carpeta solo hasta tener su repo propio:
> `git subtree split -P polymarket_scalper -b polymarket_scalper` y push de esa rama.

## Arrancar (Windows, un solo comando)

```powershell
.\CORRER.ps1              # actualiza, instala si falta, congela el experimento, arranca bot y panel
.\CORRER.ps1 -Informe     # solo mirar cómo va la medición, sin arrancar nada
```

En VS Code: **Ctrl+Shift+B**. Con doble clic: `INICIAR-TODO.bat`, y `VER-VALIDACION.bat` para el
informe. El detalle está en [docs/WINDOWS.md](docs/WINDOWS.md).

## Instalación

```bash
cd polymarket_scalper
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,learn]"    # learn = scikit-learn para gradient boosting (opcional)
pytest
```

En Windows: `powershell -ExecutionPolicy Bypass -File deploy\instalar-windows.ps1`
(ver [`docs/WINDOWS.md`](docs/WINDOWS.md)).

## Uso

**Aplicación de escritorio** (`scalper gui`, o `SCALPER.bat` en Windows): ventana en PyQt6 con el
panel HTML incrustado, la actividad del bot en vivo y los informes, todo en un sitio. Los botones
arrancan y detienen el bot, que se cierra siempre guardando los datos pendientes. Si PyQt6 no está
instalado, abre una versión sencilla en Tkinter (`scalper gui --tk` la fuerza).

Se instala con `pip install -e ".[gui]"`. En máquinas sin aceleración gráfica el panel incrustado
puede no cargar; el botón «Abrir en el navegador» muestra exactamente lo mismo.

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
scalper train                    # fase 5: entrenar P(ganancia) por señal desde el ledger
scalper models                   # versiones, métricas y cuál está en uso
scalper gui                      # ventana de escritorio con botones (sin terminal)
scalper dashboard                # panel web en http://127.0.0.1:8787 (lee data/ en vivo)
scalper dashboard --snapshot panel.html   # página autónoma con los datos actuales, para compartir
scalper retention --dry-run      # disco: qué borraría y compactaría
scalper overview                 # todos los informes de una pasada
scalper updown-study             # ¿a favor o en contra de la racha en cripto?
```

Desde **VS Code**: abrir la carpeta del proyecto y usar Ctrl+Shift+P → `Run Task`, o F5 para
depurar. Las tareas y configuraciones están en `.vscode/`.

Todo se configura en `config.yaml`. Nada de esto toca una wallet ni firma órdenes.

## Cómo funciona

### Fase 1: recolector (`scalper/collector.py`)
- Descubre mercados vía Gamma API por tag (`nba`=745, `tennis`=864), filtra por volumen, tipo de
  mercado (`only_market_types`) y libro habilitado, y lee la tasa de fee real (`feeSchedule.rate`).
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
| `crypto_prices` | precio de referencia de cripto, muestreado cada segundo |
| `updown_windows` | cada ventana "Up or Down": strike, cierre y quién ganó |

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
- Las órdenes maker se llenan **por cola, no por azar**: cuando el volumen que cruza su precio
  consume lo que había delante y llega hasta ellas, o cuando el mercado pasa a través. De cada
  orden se guardan tres escenarios (conservador, base, optimista), la cola inicial, el volumen
  que cruzó y si el nivel fue barrido. Ver *Ejecución medida* más abajo.
- Cada posición cerrada se escribe al `ledger` con `predicted_pnl`, `realized_pnl`, `error`, la
  estrategia, el rol de entrada y el movimiento del precio a 100 ms, 500 ms, 1, 2, 5 y 10 s tras
  el llenado (selección adversa).
- Cada decisión, **incluidas las de no operar**, se escribe a la tabla `decisions` con su motivo.
- `scalper report` agrupa por tipo de señal: tasa de llenado, PnL predicho vs real, error medio,
  tasa de acierto, y calibración de la confianza declarada vs la real.
- `scalper ejecucion` responde la pregunta que decide todo: cuántas órdenes se llenan de verdad
  y si eso basta. `scalper validar` valida hacia adelante y en escenarios peores.

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

### Mercados "Up or Down" de cripto (`crypto_feed.py`, `models/crypto.py`, `signals/updown.py`)
Ventanas de 5 o 15 minutos que pagan según si el precio al cierre supera al de apertura. Son el
único mercado donde tenemos **el mismo dato con el que se resuelven**: Polymarket publica el precio
de referencia en vivo y el bot lo escucha.

- **Modelo:** `P(Up) = Φ(ln(S/K) / (σ·√τ))`, con `K` el precio de apertura, `S` el actual y `τ` la
  fracción de ventana que falta. Sin deriva a propósito: en 5 minutos la tendencia es ruido.
  σ se calibra con los propios datos; por defecto sale de la volatilidad anualizada típica de cada
  símbolo.
- **El strike se toma en la apertura o después, nunca antes.** Las ventanas se descubren por
  adelantado, y tomar el precio previo sesgaba el modelo. Si el bot no estaba escuchando cuando
  abrió la ventana, no hay strike y no se opera.
- **Se compra y se aguanta hasta la resolución.** La comisión de cripto es del 7 %, la más alta de
  la plataforma, y solo la paga quien cruza el libro. Entrar y salir la pagaría dos veces y se
  comería la ventaja; la resolución no cobra nada.
- **Por qué importan aunque sean difíciles:** se resuelven en minutos contra un dato objetivo, así
  que el ledger acumula ejemplos etiquetados cientos de veces más rápido que el deporte. Son el
  combustible del aprendizaje de la fase 5.
- **Advertencia honesta:** son los mercados con más bots compitiendo y la comisión más alta. Al
  abrir la ventana el modelo vale exactamente 0,50, así que operar ahí es apostar a que el sesgo
  del mercado es ruido. Si eso es cierto solo lo dirá el ledger con cientos de posiciones.

### ¿Conviene ir a favor o en contra de la racha? (`scalper updown-study`)
Al abrir una ventana, el precio de referencia y el strike son casi iguales, así que la
probabilidad real es ~0,50. Pero el libro no arranca en 0,50: arranca sesgado por cómo terminó la
ventana anterior. Ese sesgo puede ser **información** (el mercado sabe algo) o **sobrerreacción**
(memoria de la racha). La diferencia decide si conviene seguir la racha o ir en contra.

`scalper updown-study` lo mide con los datos recogidos: toma cada ventana resuelta, mira el precio
del token "Up" a los 20 segundos de abrir, lo compara con el resultado real y calcula lo que
habría dado cada estrategia con la comisión del 7 % incluida. Si con cientos de ventanas "ir en
contra" sale positivo, la sobrerreacción es real y explotable; si sale negativo, el sesgo era
información y seguirla era lo correcto. El informe avisa cuando la muestra es demasiado pequeña.

El arrastre también viaja como feature de cada señal (`prev_up_won`, `prev_return_bps`,
`market_skew`, `elapsed_s`), así que el modelo de la fase 5 lo aprende por su cuenta.

### Maker-first: poner órdenes en vez de cruzarlas
La comisión de Polymarket **solo la paga quien cruza el libro**. Quien pone la orden y espera no
paga nada. La radiografía de los datos propios dejó claro el peso de esa diferencia: cruzar el
libro en un mercado a 0,50 cuesta entre 1,6 % y 4,5 % del precio según la categoría, solo por
entrar. Ese es el listón que cualquier señal tenía que superar antes de ganar un centavo.

Por eso las tres señales direccionales (`updown_model`, `model_deviation`, `smart_money`) entran
poniendo una orden límite dentro del spread, al precio más alto que cumple tres condiciones: no
cruza, deja la ventaja mínima pedida, y no queda por detrás del mejor comprador (si hay que
ponerse detrás de la cola, no compensa y la señal se descarta).

Consecuencias, todas medidas en el ledger:
- La comisión de entrada es **cero**, así que la ventaja es entera.
- Se compra más barato: el límite queda por debajo del precio que pedía el mercado.
- Puede no llenarse. Si pasa el plazo (`signals.maker_entry_timeout_s`) la orden se cancela y la
  posición cierra como `sin_llenar`, con resultado exactamente cero. Eso es coste de oportunidad,
  no pérdida, y queda fuera de las estadísticas.
- Si el mercado baja hasta nuestro límite antes de poner la orden, la ventaja se evaporó y la
  señal se descarta (`price_moved`).

`signals.maker_first: false` vuelve al comportamiento anterior, que sigue probado.

### Ejecución medida (`scalper ejecucion`)
Poner órdenes en vez de cruzarlas solo gana si las órdenes se llenan. Durante un tiempo el
simulador supuso que se llenaba el 60 % de las veces: un número inventado que decidía por sí
solo la rentabilidad de todo lo maker-first. Ya no existe como supuesto operativo. Lo que hay es:

- **Tasa de llenado observada**, contada sobre las órdenes que realmente se pusieron.
- **Conservadora y optimista**: los dos extremos de la incertidumbre sobre la posición en la cola.
  La conservadora supone que toda la liquidez del nivel estaba delante y nadie la canceló; la
  optimista, que estábamos al frente. El resultado real vive entre las dos.
- **Break-even de llenado** = ventaja cruzando ÷ ventaja poniendo la orden. Es la tasa a partir de
  la cual poner la orden gana a cruzar el libro. Si cruzar da ventaja negativa, el break-even es
  cero y cualquier llenado gana.
- **Edge mínimo requerido** = coste de salida medido + selección adversa medida + margen. Por
  debajo de eso la respuesta correcta es no entrar, y la tarjeta de la oportunidad lo dice.
- **Selección adversa**: cuánto se mueve el mid en los segundos siguientes al llenado. Si es
  negativa, nos están llenando justo cuando el mercado se va en contra.

El 60 % sigue apareciendo en los informes, pero etiquetado como *referencia*: está ahí para poder
desmentirlo, no para sostener ningún resultado.

### Fase de validación (`scalper validacion`)
Medir antes de mejorar. El motor se congela antes de cada corrida (commit, umbrales y modelos:
si algo cambia, empieza otro experimento y los datos se separan solos), el feed tiene cuatro
estados explícitos, cada orden puesta guarda sus condiciones y su resultado, cada llenado deja la
trayectoria del precio hasta 15 minutos, y cada señal rechazada se sigue como sombra para saber
si se descartan malos trades o buenas oportunidades. El detalle está en
[docs/VALIDACION.md](docs/VALIDACION.md).

### Reacción del mercado (`scalper/reaction.py`)
La tesis del scalping en vivo es que el marcador cambia antes que el precio. En lugar de suponerlo,
cada cambio de marcador abre una medición: se guarda el mid de cada token y se espera a que se
mueva un tick. El retraso y el tamaño del movimiento van a la tabla `reactions`. De ahí salen el
retraso típico por liga, si el precio aún no ha reaccionado al último evento, y un
`event_risk_score` explicable por componentes (cuán reciente es el evento y cuántos puntos se
anotaron en el último minuto).

### Detectores in-play y de dinero inteligente
- **model_deviation**: para cada token enlazado a un partido en vivo, si
  `p_modelo − ask − fee(entrada) − costo de salida > umbral`, compra como taker. Sale cuando el
  bid alcanza el target (el modelo), en el stop, por tiempo máximo o al terminar el partido
  (liquidación con el marcador final). Desvíos mayores a `max_deviation` se descartan: casi
  siempre son un marcador mal leído, no una oportunidad.
- **smart_money**: cuando el flujo con identidad muestra un trade de una wallet con perfil
  (score y muestra mínimos) en un mercado seguido, sigue el mismo lado si el ask no se ha alejado.
  La ganancia esperada es una hipótesis (fracción de su ROI histórico); el ledger la contrasta.

### Fase 5: el modelo que aprende del error (`scalper/learn/`)
- **Features** (`features.py`): se calculan una sola vez, cuando se emite la señal, con lo que se
  sabe en ese momento (edge, fees, spread, actividad, volatilidad, profundidad, modelo vs mercado,
  tiempo restante, perfil de la wallet, hora, categoría, liga…). Viajan dentro de la señal hasta el
  ledger, así el entrenamiento ve exactamente lo mismo que vio el bot en vivo. Nada del resultado
  entra en las features.
- **Modelo** (`model.py`): gradient boosting de scikit-learn si está instalado
  (`pip install -e ".[learn]"`), regresión logística en Python puro si no. Un modelo por tipo de
  señal. Etiqueta: la posición cerró con ganancia. Se excluyen cierres que no dicen nada de la
  señal (liquidación forzada al fin de corrida, sin llenar).
- **Promoción campeón/retador** (`train.py`): partición temporal (el último 30 % valida). El
  retador se promueve solo si en validación su Brier es mejor que el del campeón actual **y** mejor
  que el de la heurística. Un modelo que no gana a la heurística se guarda con sus métricas pero no
  se usa. Cada versión queda en `data/models/<señal>/vN.json`; `scalper models` muestra el historial.
- **Uso en vivo** (`scorer.py`): la confianza de cada señal pasa a ser una mezcla
  `w·modelo + (1−w)·heurística` con `w = n_train / (n_train + 50)`. Con menos de 30 ejemplos el
  modelo solo informa; con más, descarta señales con P(ganar) < 0,5 y reduce el tamaño de las
  dudosas. En paper trading se reentrena solo cada `learn.retrain_hours` y recarga si hubo promoción.
- `scalper report` compara el Brier de la mezcla, la heurística y el modelo puro por tipo de señal.

Con pocos datos el sistema se comporta como antes (heurística); el aprendizaje entra a medida que
el ledger crece. Ese es el mecanismo por el que "el margen de error se va reduciendo".

## Qué hacer ahora (`scalper ahora`) y cuándo confiar (`scalper listo`)
- **`scalper ahora`** traduce lo que el motor acaba de decidir a lenguaje llano, agrupado por
  mercado: qué comprar, a qué precio, cuánto se invierte, cuánto se espera ganar y por qué, con las
  comisiones ya descontadas. Lo vigente va primero; lo de hace rato se marca como caducado, porque
  en las ventanas de cripto de cinco minutos el precio ya se movió.
- **`scalper listo`** responde si el bot puede operar con dinero real, estrategia por estrategia,
  con siete criterios objetivos: al menos 100 posiciones cerradas, ganancia neta positiva, una
  ventaja que no quepa en la suerte (estadístico t mayor que 2), un intervalo de confianza por
  bootstrap que no toque el cero, una tasa de llenado por encima del break-even, un modelo
  aprendido que no empeore a la heurística, y ganancia que sobreviva a los escenarios peores.
  Más siete días de datos. Mientras no se cumplan, el veredicto dice exactamente qué falta.
- **`scalper ejecucion`** y **`scalper validar`** son el detalle detrás de ese veredicto: la
  primera muestra llenados, break-even, edge mínimo y selección adversa; la segunda valida hacia
  adelante por pliegues y somete cada estrategia a comisión más alta, llenado conservador y
  descarte de los llenados de menos de un segundo.

La capa que firma órdenes no existe a propósito: se construye cuando `scalper listo` diga que sí,
y se prueba con el tamaño mínimo para comprobar que los llenados reales se parecen a los simulados.

## Disco (`scalper retention`)
Los cambios de libro crecen ~4 GB/día y solo sirven para replay detallado de días recientes. La
retención, que corre sola una vez al día dentro del recolector, conserva 3 días de `book_deltas`,
14 de `book_snapshots` y 30 de `markets`, borra lo anterior y compacta cada día cerrado a un
archivo por tabla. Las tablas del aprendizaje no se borran nunca. Crecimiento permanente: ~0,5 GB/día.

## Dónde correrlo
- **Windows** (lo más sencillo para empezar): [`docs/WINDOWS.md`](docs/WINDOWS.md). Instalación con
  `deploy\instalar-windows.ps1`, arranque con `deploy\iniciar-bot.ps1`, tareas programadas para que
  arranque al encender la PC, y bloqueo de suspensión mientras corre.
- **Servidor Linux** (cuando quieras que corra sin depender de tu equipo):
  [`docs/SERVIDOR.md`](docs/SERVIDOR.md). Instalación con `deploy/install.sh`, servicios systemd,
  panel por túnel SSH, disco, copias y actualización.

## Panel web (`scalper dashboard`)
Un servidor local sin dependencias externas sirve una página que lee las tablas Parquet cada
10 segundos: resumen con PnL válido y salud de datos, señales y resultados con calibración,
partidos en vivo con precio de mercado contra modelo, ranking de wallets, flujo grande, versiones
de modelos aprendidos y estado de las tablas. Cada sección trae un "Cómo leer esto" en lenguaje
llano. Con `--snapshot` genera una página autónoma con los datos embebidos.

## Advertencias honestas
- **El feed del CLOB va tarde, y eso limita lo que se puede intentar.** Medido sobre 428 544
  cambios de libro: retraso mediano de unos 0,6 s, con un 17 % de mensajes por encima de 5 s y
  tramos que llegan a más de un minuto. No es el motor (procesa 37 000 eventos por segundo en el
  perfilado, y cuando vamos atrasados recibimos *menos* mensajes, no más). Por eso el bot no
  abre posiciones cuando el retraso supera `sim.max_feed_lag_ms`, y por eso la estrategia de
  poner órdenes y esperar es la adecuada: no depende de llegar primero.
- **Los resultados anteriores a la medición de llenados no son evidencia.** Todo lo que el ledger
  dijo sobre señales maker mientras el simulador usaba el 60 % inventado se generó con ese número.
  La cuenta que vale para el veredicto empieza con los datos nuevos.
- Los arbitrajes puros aparecen poco y duran milisegundos; los bots existentes compiten por ellos.
  El valor de esta fase es medir con datos reales cuántos aparecen, cuánto duran y qué tan seguido
  la latencia los rompe.
- Nada aquí es asesoría financiera. Polymarket restringe usuarios de varios países.
