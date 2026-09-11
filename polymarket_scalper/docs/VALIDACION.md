# Fase de validación de ejecución

Esta fase no busca que el bot gane más. Busca poder demostrar que, cuando el bot dice que hay una
oportunidad, esa oportunidad sigue teniendo ventaja después de la cola, la liquidez, la selección
adversa, la latencia y la salida. Si los datos dicen que no la hay, la respuesta correcta es
NO TRADE.

Durante esta fase están congeladas las estrategias: no se añade ninguna, no se entrena ningún
modelo nuevo y no se ajusta ningún umbral buscando mejorar el resultado en los datos ya vistos.

---

## 1. El motor se congela antes de medir

Comparar operaciones producidas por motores distintos no mide nada. Antes de cada corrida,
`scalper/experimento.py` toma una huella de todo lo que decide el comportamiento:

- el commit del repositorio, y si el árbol de trabajo tenía cambios sin comprometer;
- todos los umbrales de detectores, simulador, aprendizaje y descubrimiento;
- la versión de cada modelo aprendido que esté promovido.

De ahí sale un `experiment_id`. Cada fila del ledger, cada decisión, cada observación de llenado
y cada punto de trayectoria lo llevan. **Si algo de lo anterior cambia, la huella cambia y empieza
otro experimento**: los datos quedan separados sin que nadie tenga que acordarse.

```bash
scalper experimentos                 # qué versiones han operado y qué cambió entre ellas
scalper experimentos --congelar --nota "prueba de llenado"
scalper validacion --experimento exp-20260911-0c13b8f5
```

Si la corrida arranca con el árbol sucio, el log lo avisa: esos datos no se podrán reproducir.

## 2. Tres ventajas distintas, más una cuarta

La medición anterior dejó un caso que resume la fase entera: una señal con **+13,8 % de ventaja
según el modelo** terminó con **−22 % realizado**. Desde entonces el sistema trata como métricas
independientes:

| Ventaja | Qué es | Dónde sale |
|---|---|---|
| **Bruta** | La diferencia entre lo que el modelo cree que vale y lo que cuesta. Sin costes. | `edge_raw` |
| **Ejecutable** | La bruta menos comisiones de entrada y salida estimadas. Es lo que promete el detector. | `edge_net` |
| **Conservadora** | Lo que se cobraría si hubiera que deshacer la posición al bid de ese mismo instante. | `edge_conservador` |
| **Realizada** | Lo que de verdad quedó, por share. | del ledger |

Que la conservadora sea negativa mientras la ejecutable es positiva significa que la ventaja
depende enteramente de que el mercado converja. Eso es una hipótesis, no un hecho.

## 3. Qué se captura ahora

| Tabla | Una fila por | Para qué |
|---|---|---|
| `experiments` | versión congelada del motor | separar datos de motores distintos |
| `fill_observations` | orden puesta | estimar P(llenado \| condiciones) sin suponer nada |
| `post_fill` | llenado × horizonte | saber en qué intervalo aparece la ventaja |
| `decisions` | decisión, **incluidas las de no operar** | saber qué se descarta y por qué |
| `feed_health` | muestra periódica del feed | separar el dato limpio del sucio |
| `reactions` | evento del partido | medir el retraso entre el partido y el precio |

Y en cada fila del ledger, además del resultado: la estrategia, el rol de entrada, los tres
escenarios de llenado, el MFE y el MAE con sus tiempos, cuánto tardó el precio en moverse medio
tick, uno, dos y tres a favor y en contra, cuándo se tocó el objetivo y el stop, la selección
adversa a 100 ms, 500 ms, 1, 2, 5, 10, 30 y 60 s, la frescura del libro con la que se decidió, el
estado del feed y la cadena de retrasos separada.

### Condiciones de llenado

Cada orden puesta guarda el momento: precio, tamaño, distancia al mejor comprador y al mejor
vendedor en ticks, spread, profundidad de los dos lados, cola por delante, desequilibrio a 1 y 3
ticks, velocidad del mid a 1 y 5 s, volatilidad a 60 s, actividad, frescura del feed, hora,
tramo del partido y segundos restantes. Y el resultado: si se llenó, qué fracción, cuánto esperó,
cuánto volumen cruzó su precio, y si el nivel fue barrido.

Con eso se puede estimar después P(llenado | condiciones). **Todavía no se entrena nada**: primero
hace falta muestra.

## 4. El feed tiene estado

Cuatro estados explícitos, en `scalper/salud.py`:

- **SANO**: el libro describe el mercado de ahora.
- **DEGRADADO**: llega con retraso apreciable pero sigue llegando.
- **VIEJO**: el retraso es tal que el libro ya no describe el mercado. No se abre nada.
- **CONGELADO**: ha dejado de llegar.

Los umbrales (`salud.*` en la configuración) son **una hipótesis**. Por eso cada decisión guarda
la frescura con la que se tomó, y el informe evalúa qué habría dejado pasar cada umbral posible
entre 250 ms y 10 s. No se elige el que más ganancia dé en los datos vistos: eso sería ajustar al
ruido.

Las operaciones tomadas con el feed VIEJO o CONGELADO se cuentan aparte y no se mezclan.

### El reloj no está sincronizado, y eso cambia cómo se lee la frescura

La frescura se mide restando: la hora a la que llega el mensaje menos la que lleva estampada. Esa
resta lleva dentro el desfase entre los dos relojes, que nadie conoce. En la primera corrida larga
la mediana salió en **−98 ms**, con mínimos de −207 ms: el mensaje parecía llegar antes de haber
salido. No es que el libro venga del futuro; es que nuestro reloj va detrás.

Esto tenía una consecuencia silenciosa: una frescura negativa no encajaba en ningún tramo de
análisis y terminaba en el último, `10s+`. El dato más fresco posible se contaba como el más viejo.
Afectaba a **179 de 206 decisiones** y a **55 de 69 posiciones** de esa corrida, así que el corte
por frescura —la pregunta 8 entera— decía justo lo contrario de lo que pasaba.

Ahora el informe estima el desfase con un filtro de mínimo (el mensaje que menos tardó es el que
menos transporte lleva dentro, el mismo truco de NTP), lo descuenta de toda frescura y lo imprime
en la cabecera. La consecuencia hay que decirla entera: **el retraso absoluto del feed no se puede
medir sin relojes sincronizados**. Lo que sí vale, y es lo que necesita esta fase, es la comparación
entre un momento y otro sobre ese suelo común.

## 5. Lo que se rechaza también se mide

Cada señal que el motor descarta deja una **posición sombra**: ejecuta y se cierra igual que una
real, con el mismo modelo de cola y el mismo seguimiento, pero no toca el efectivo, no ocupa sitio
en los topes de riesgo, no bloquea operaciones reales y su fila va marcada.

Así se responde la pregunta que de otro modo queda abierta: si rechazamos malos trades o buenas
oportunidades. El informe lo dice por motivo de rechazo, y el resultado hipotético **nunca** se
suma al real.

Las señales descartadas dentro de un detector (por ejemplo, ventaja insuficiente antes de que la
señal llegue a existir) se cuentan en `decisions` pero todavía no generan sombra.

Una limitación deliberada: el seguimiento posterior al llenado cubre las entradas direccionales y
las que esperan a la resolución. La captura de spread entra por los dos lados a la vez, así que
medir su MFE y su MAE contra un único precio de entrada no significaría nada; sus órdenes sí
quedan en `fill_observations`, pero sin trayectoria.

## 6. El informe

```bash
scalper validacion                   # las diez preguntas, con el tamaño de muestra al lado
```

Responde, por estrategia: tasa de llenado observada contra la necesaria, sensibilidad a otras
tasas de llenado, a partir de qué ventaja el valor esperado cambia de signo, resultado por tramos
de ventaja, qué hace el precio después del llenado, cuánto tarda el movimiento a favor y en
contra, dónde aparece la ventaja en el tiempo, cómo cambia todo con la frescura del libro, y qué
habría pasado con lo rechazado.

### Etiquetas de confianza

| Operaciones | Etiqueta |
|---|---|
| menos de 20 | SOLO DESCRIPTIVO |
| 20 a 99 | PRELIMINAR |
| 100 a 249 | MEDIBLE |
| 250 a 499 | EVIDENCIA MÁS FIRME |
| 500 o más | EVIDENCIA ROBUSTA |

Son etiquetas de confianza, no garantías estadísticas.

### Semáforo

| Luz | Qué significa |
|---|---|
| 🟢 EVIDENCIA POSITIVA | el intervalo de confianza queda entero por encima de cero |
| 🟡 DATOS INSUFICIENTES | todavía no se puede concluir nada |
| 🟠 PROBLEMA DE EJECUCIÓN | hay ventaja, pero se llena menos de lo que haría falta |
| 🔴 VALOR ESPERADO NEGATIVO | el intervalo queda entero por debajo de cero |
| ⚫ DATO NO VÁLIDO | se decidió con el feed viejo o congelado |

**Verde no significa que gane: significa que se ha demostrado que gana.** Naranja no significa que
pierda: significa que la ejecución se come la ventaja. Amarillo es la respuesta honesta la mayor
parte del tiempo.

Y una regla que no se salta: **un resultado negativo con pocas operaciones no demuestra que una
estrategia no sirva**. Siete operaciones perdedoras son muestra insuficiente, no una sentencia.
Lo único que quedó demostrado del modelo anterior es que sobreestimaba la rentabilidad al suponer
llenados irreales.

## 7. Escalera de madurez

1. **MEDIBLE** (`listo_para_medir` en el informe): hay muestra suficiente, el llenado sale de
   observaciones, los datos no están contaminados, la frescura está registrada, la selección
   adversa medida y el edge mínimo calculado.
2. **RENTABLE**: además, la ganancia está demostrada (`scalper listo`).
3. **VALIDADA EN PAPEL**: se mantiene fuera de muestra, con validación hacia adelante.
4. **PRUEBA REAL MÍNIMA**: solo entonces, y como experimento aparte, con el tamaño mínimo y
   límites estrictos.

Durante esta fase **no se usa dinero real**. El modelo de llenado no se valida con capital: se
valida construyendo muestra en papel.

## 8. Lo que esta fase todavía no hace

- No entrena un modelo de llenado ni uno de salida. Construye el dato para poder hacerlo después.
- No mueve ningún umbral en función de lo medido. Registra qué habría pasado con cada uno.
- No compara contra comprar y mantener ni contra una estrategia al azar. La infraestructura queda
  lista; la comparación necesita muestra de varios días.
- No genera sombras para los descartes internos de los detectores.

Cuando haya muestra, el orden es: presentar el informe, decidir con él en la mano, y solo entonces
cambiar algo.
