# Fase de medición de pata suelta

Esta fase responde a una sola pregunta:

> Cuando `TENNIS_SPREAD_CAPTURE` llena una sola pata, ¿cuánto cuesta cerrarla enseguida, y cómo
> evoluciona ese coste con el tiempo?

No optimiza nada. No mueve ningún umbral, no entrena ningún modelo, no introduce stops ni
coberturas y no usa dinero real. **Mide el problema; no lo resuelve.**

---

## Por qué esta pregunta

La fase anterior dejó el problema localizado. La captura de spread entra por los dos lados a la vez:

| | Se llenan las dos patas | Se llena solo una |
|---|---|---|
| muestra-1 | 82 × **+1,76** | 62 × −8,51 |
| muestra-2 | 51 × **+1,77** | 28 × −6,88 |
| muestra-3 | 132 × **+1,68** | 132 × −6,39 |

Cuando la estrategia hace lo que dice, gana, y gana lo mismo en tres corridas. Cuando solo se llena
una pata, queda un direccional que nadie pidió, se sostiene una mediana de 586 segundos y cuesta
entre seis y ocho veces lo que se ganaba. Pasa la mitad de las veces. El punto de equilibrio está en
completar el 80 % y se completa el 50 %.

Lo que **no** se sabía es *cuándo* aparece esa pérdida:

- **Si aparece en el primer segundo**, cerrar rápido no evita nada y no hay arreglo por ese lado.
- **Si se acumula a lo largo de los diez minutos**, salir pronto rescataría buena parte.

Los datos anteriores no pueden distinguir los dos casos, porque para la captura de spread nunca se
guardó trayectoria posterior al llenado: entra por dos lados, y medir su recorrido contra un único
precio de entrada no significaba nada. Esta fase construye ese dato.

---

## 1. El motor se congela de verdad

`muestra-3` promocionó un modelo a las 5 h 53 min de una corrida de 8 h, y 186 de sus 680 posiciones
se decidieron con un motor que no existía al arrancar — todas con el mismo `experiment_id`. La
huella se calculaba una sola vez y nadie volvía a mirar.

Ahora, con `validacion.motor_congelado: true`:

- **el reentrenamiento se apaga** antes de tomar la huella, y eso entra en la propia huella: «podía
  cambiar» forma parte de la identidad del motor;
- **la corrida se niega a arrancar con el árbol de trabajo sucio**, porque entonces el commit no
  describe el código que va a correr;
- **la huella incluye el código de simulación** (`fill_model`, `engine`, `ledger`, `book`, `fees`,
  `pata`), no solo el commit — con el árbol sucio el commit no cubre nada;
- **un guardián comprueba cada minuto** que la huella sigue siendo la misma y, si algo se movió,
  **aborta la corrida** con el detalle de qué cambió.

```bash
scalper experimentos --congelar --nota "para qué es esta corrida"
```

## 2. Las órdenes que no se llenan no se tiran

Son la mitad de la muestra: sin ellas no existe una tasa de llenado, porque desaparece el
denominador y todo parece llenarse siempre. Se conservan en `fill_observations` con su estado, y
`calidad.ordenes_conservadas` **hace fallar la corrida** si no queda ni una sin llenar.

El cero tampoco es un reloj roto: `ts_fill = 0` es el centinela de «nunca se llenó» y tiene que
seguir ahí.

## 3. La pata suelta es una entidad, no una deducción

Vive en `scalper/pata.py` y en la tabla `partial_legs`, con `partial_leg_id` propio y estable. **No
se deduce del P&L ni del motivo de cierre**: que una posición perdiera dinero no la convierte en
pata suelta, y que ganara no la excluye. Se crea por lo que pasó en el libro, en el instante en que
pasó.

### T0: el instante del primer llenado

En T0 se guardan las dos alternativas reales a quedarse esperando:

- **completar ahora**, cruzando el libro para ejecutar la pata que falta: precio y coste;
- **deshacer ahora**, cerrando la pata que ya tenemos: precio ejecutable y resultado hipotético.

Más el estado del libro: mejor bid y ask, spread, profundidad.

### La trayectoria

Desde T0 se fotografía en **1, 5, 10, 20, 30, 60, 120, 300 y 600 segundos**. Cada horizonte se mide
una sola vez. Si la posición termina antes, se registra el último estado y el motivo.

## 4. El precio de salida sale del libro, nunca del mid

Es la regla que más fácil se rompe y la que más engaña, porque usar el mid hace que salir parezca
gratis. Cerrar una compra de 50 shares significa **vender contra los bids**, atravesando los niveles
que haga falta:

```
libro:  bid 0,45 × 30   ·   bid 0,44 × 70
salir de 50 shares → VWAP = (30 × 0,45 + 20 × 0,44) / 50 = 0,4460
```

Se registran `salida_precio` (el VWAP), `salida_peor_nivel` y `salida_slippage` contra el mejor
precio de ese lado.

**Si no hay profundidad para el tamaño entero, no hay número.** El punto se guarda marcado como
`sin_profundidad` o `sin_liquidez`, en vez de rellenarse con algo bonito. Un hueco declarado vale;
un hueco tapado con el mid, no. `calidad.precio_ejecutable` hace fallar la corrida si aparece un
P&L contrafactual sin precio de salida, si el precio de salida coincide demasiadas veces con el mid
exactamente, o si hay un hueco sin motivo.

## 5. El resultado hipotético nunca se mezcla con el real

Todo lo que sale de esta fase lleva **`contrafactual`** en el nombre y vive en sus propias tablas.
No toca el efectivo, no ocupa sitio en los topes de riesgo y no entra en ningún P&L realizado. El
esquema del ledger es la primera defensa: una columna contrafactual escrita ahí ni siquiera llega al
archivo. `calidad.pnl_separado` es la segunda.

El resultado realizado sí se guarda **al lado** del hipotético, en `partial_legs.pnl_realizado_final`,
que es lo que permite compararlos.

## 6. Qué preguntas contesta el informe

```bash
scalper patas                                  # el informe entero
scalper patas --experimento exp-...            # una sola versión del motor
scalper calidad --run-id muestra-4             # ¿la corrida vale? código 1 si no
```

- **Resumen**: cuántas patas, cómo terminaron, tasa de recuperación, mediana hasta la segunda pata.
- **Coste por horizonte**: mediana, media, p25, p75 y peor caso de cerrar en cada instante, solo
  sobre las patas que **no** se recuperaron — meter las recuperadas mezclaría dos poblaciones
  distintas.
- **Punto de no retorno**: en qué momento el coste de salir alcanza el 25, 50, 75 y 90 % de la
  pérdida final. Si las medianas están en el primer segundo, la pérdida se decide al entrar; si
  suben con el horizonte, se cuece despacio.
- **Ahorro hipotético**: cuánto se habría ahorrado cerrando en cada horizonte, frente a lo que pasó.
- **Segmentación descriptiva**: por ventaja prometida, spread en T0, lado y mercado.

## 7. Qué NO se ha tocado

- La lógica de entrada de `TENNIS_SPREAD_CAPTURE`: los mismos umbrales, el mismo spread mínimo, el
  mismo sizing, la misma selección de mercados. La muestra es comparable con la fase anterior.
- No hay stop, ni take profit, ni cobertura automática, ni mecanismo de recuperación.
- No se ha entrenado ningún modelo.
- `TENNIS_DIRECTIONAL` queda apagada (`validacion.desactivadas`) y sus señales se registran como
  `DISABLED_FOR_VALIDATION`. **No es un veredicto nuevo**: es dejar de gastar muestra en algo ya
  medido, para no contaminar lo que se está midiendo.
- `ARBITRAGE`, `CRYPTO_5M`, `CRYPTO_UPDOWN_SPREAD_CAPTURE` y `SMART_MONEY` se dejan como están. Sus
  muestras son de 1 a 3 posiciones y no se toca nada para inflarlas.

## 8. Copia de seguridad

`data/` pasa del giga y está en `.gitignore`. De eso, el 95 % son deltas de libro en crudo que se
pueden volver a capturar; lo que no se puede recuperar es el resultado de decisiones ya tomadas.

```bash
python respaldo.py crear                      # ~14 MB: solo lo indispensable
python respaldo.py verificar respaldos/scalper-....tar.gz
python respaldo.py restaurar respaldos/scalper-....tar.gz --en data-restaurada
```

`crear` escribe un manifiesto con el recuento de filas de cada tabla y un `sha256`. `verificar` abre
el archivo, **cuenta las filas de verdad** y las compara: una copia que no se ha probado no es una
copia.

Indispensables: `experiments`, `ledger`, `decisions`, `fill_observations`, `post_fill`,
`partial_legs`, `partial_leg_track`, `feed_health`, `reactions`, `signals`.

## 9. Cómo correr la fase

```bash
git status --porcelain          # tiene que estar limpio: si no, la corrida se niega a arrancar
python3 -m pytest tests/ -q
python respaldo.py crear

scalper experimentos --congelar --nota "fase pata suelta"
scalper paper --duration 28800 --run-id patas-1

scalper calidad --run-id patas-1     # PRIMERO: ¿la corrida vale?
scalper patas                        # y solo entonces, qué dice
```

Si `calidad` sale con código 1, la corrida no vale y el informe no se mira. Ese es el orden.

## 10. Criterio para decidir después

Esta fase **no** decide si construir el mecanismo de recuperación. Lo que producirá es lo que hace
falta para decidirlo, y conviene dejar escrito qué se mirará antes de ver los números:

- **Si el 90 % de la pérdida ya está en T+1 s** en la mayoría de las patas, cerrar rápido no la
  evita: el problema está en la entrada, no en la salida, y el mecanismo de recuperación no
  serviría.
- **Si la pérdida crece con el horizonte** y el ahorro hipotético a 10-60 s es grande y consistente,
  hay algo que construir — y entonces habrá que medir el coste real de esa salida, que esta fase no
  mide: una salida de verdad movería el libro.
- **Si la segunda pata se recupera sola a menudo y pronto**, cerrar rápido destruiría las
  recuperaciones, y el cálculo es entre lo que se ahorra y lo que se deja de ganar.

Ninguna de las tres conclusiones se adelanta. Esta fase produce **datos nuevos, no una estrategia
nueva**.
