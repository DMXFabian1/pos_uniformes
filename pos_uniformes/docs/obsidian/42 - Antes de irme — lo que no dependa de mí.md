# 42 — Antes de irme: lo que no dependa de mí

Daniel se va una semana (sábado 03/10/2026) y deja la tienda a las muchachas.
Preguntó: *"siento que falta algo… ¿hay algo que se me pase?"*. Había tres
cosas, y las tres eran del mismo tipo: **cosas que solo él podía hacer**.

---

## 1. No había respaldo automático

`scripts/run_scheduled_backup.py` estaba escrito desde siempre y **nada lo
corría**: no había instalador ni tarea, y `postactualizacion` —que es la que
mantiene las tareas al día— no la incluía. Las únicas garantizadas eran
supervisor, cortes, resumen, pendientes y asistencia.

Por eso el último respaldo de la Mac tenía 21 días: nadie lo estaba haciendo.

**Ahora:** tarea `POS Respaldo`, diaria a las 20:30, dentro de
`tareas_esperadas` junto al supervisor (no cuelga de que Telegram exista: una
PC sin bot también necesita respaldo). `INFRA_VERSION` subió a 7, así que las
PCs que ya tenían tareas instaladas la reciben al actualizar.

### Las dos vigilancias, por caminos distintos a propósito

| Quién avisa | De qué | Por qué ahí |
|---|---|---|
| La tarea del respaldo | Que **tronó** | Lo sabe en el momento |
| El bot (`Vigilante`) | Que está **viejo** | Lo nota aunque la tarea no haya corrido nunca |

Si las dos colgaran del mismo proceso, un proceso caído se llevaría también la
manera de enterarse. **El silencio se veía igual que el éxito**: ese era el
hueco de fondo.

Otros detalles:

- Un dump de menos de 50 KB se marca como **sospechoso** aunque `pg_dump` haya
  dicho que todo bien. Un dump de 0 bytes es un éxito para el programa y una
  catástrofe para la tienda.
- Si sale bien y antes también salía, **se calla**. Un aviso diario de que todo
  está bien se vuelve ruido, y el ruido se ignora — que es como se pierde el
  aviso que sí importaba.
- Si sale después de haber fallado, lo dice una vez para cerrar el tema.
- El aviso de "viejo" espera a las 10 de la mañana: uno a las 3 AM se lee
  mezclado con todo o no se lee.

**Probado de punta a punta en la Mac:** `respaldo_diario` hizo el dump y
`revisar_respaldos --probar` lo restauró en una base de juguete — 5,081
variantes, 620 ventas, 16 cortes, 3,326 conteos.

| Pieza | Archivo |
|---|---|
| Decidir si está al día | `services/respaldo_estado_service.py` (`leer_estado`, `al_dia`, `sospechoso`, textos) |
| Hacerlo y avisar | `scripts/respaldo_diario.py` / `.bat` (`--revisar`, `--sin-avisar`) |
| Notarlo desde fuera | `alertas_service.Vigilante._respaldo_viejo` |
| La tarea | `postactualizacion.tareas_esperadas` → `POS Respaldo` |
| Tests | `test_respaldo_estado` (30) |

---

## 2. El corte dependía de que él contestara

**En el kiosko el botón del corte solo sale con el gafete VEND-1**
(`_libreta_is_owner = code == "VEND-1"`). Ni León (ENC-1) lo ve, aunque
`corte_caja_service` sí se lo permitiría: el candado está en la pantalla, no en
la regla. O sea: **nadie en la tienda puede cerrar el día sin Daniel.**

Y la tarea de las 16:30/17:30 solo *proponía* y esperaba su `/corte`. Si no
contestaba, no había corte: el cajón se acumulaba sin registro y al volver no
se sabría de qué día es cada peso. El `Vigilante` avisaba "cerraron sin corte",
pero **avisar desde lejos no hace el corte**.

**Ahora:** tarea `POS Corte final` a las 18:50 con `--cerrar`. Es el último
eslabón de una cadena que ya existía:

```
16:30/17:30  propone  →  16:50/17:50  recuerda  →  18:50  lo hace solo
```

`corte_propuesta_service.toca_cerrar_solo()` (pura, testeable) exige que **todo
el camino normal haya pasado**: que hoy se haya propuesto, que ya se le
recordara, que no haya dicho `/nocorte`, que no exista ya un corte, que haya
habido movimiento, y que hayan pasado 45 min del cierre. Falta cualquiera y no
se toca nada.

El mensaje lo dice de frente: *"Cerré el día por ti… Es la cifra real, sin
ajustes. Si algo no cuadra, lo arreglas desde «Cortes anteriores»."*

> **Por qué siempre y no solo en viajes:** un "modo viaje" hay que acordarse de
> encenderlo, y eso es justo lo que se olvida. Un corte automático que él puede
> ajustar después es mejor que un día sin corte: **el ajuste deja rastro y el
> hueco no.**

---

## 3. No había nada escrito para ellas

`scripts/hoja_emergencia.py` → `reportes/hoja_tienda.html`, una hoja carta para
pegar junto a la caja. Nueve casos en el orden en que pasan, sin una sola
palabra del programa («base de datos», «servidor», «caché» no le sirven a quien
está atendiendo con un cliente enfrente). Hay un test que lo verifica.

La regla que encabeza todo: **casi nada se arregla apagando cosas, y vender
nunca se detiene.**

Los teléfonos van en blanco: se escriben con pluma, que es más rápido que
regenerar la hoja y no se queda viejo en el archivo.

---

## De paso: una falla que solo salía de noche

`conteo_jornada_service.cuando()` tomaba por hora local un dato que viene en
UTC. En Postgres no se nota (la columna es `DateTime(timezone=True)` y devuelve
con zona), pero el SQLite de las pruebas devuelve el UTC pelón: después de las
6 de la tarde «hoy» se volvía «02/10 05:35» y **dos pruebas se ponían rojas
cada noche**.

La normalización va al construir `UltimoConteo` desde la base, no dentro de
`UltimoConteo`: una fecha escrita a mano sin zona sí quiere decir hora local, y
meterla adentro rompía las pruebas que la escriben así.

---

## Hecho después, el 02/10

- **El bot cuenta su propio silencio** al recuperar la línea — ver
  [[34 - Telegram y Resumen Diario]].
- **Cinco bugs de anuncios** y el acuse que sobrevive a que se caiga la PC.
- **Los préstamos se deciden desde el aviso**, con chips para el motivo.
- Un aviso **ya no sale encima** de lo que la empleada está haciendo.

## Sin confirmar (lo más importante antes de irse)

```
schtasks /query /TN "POS Respaldo" /TN "POS Corte final"
```

Nunca se vio el estado de los respaldos **de la tienda**: solo los de la Mac.
`scripts\revisar_respaldos.bat` lo contesta.

## Lo que queda dependiendo de él

- **Aprobar préstamos** (por Telegram — está bien, es decisión suya).
- **Cambiar precios**, borrar o ajustar cortes (`VEND-1` nada más).
- **Que León pueda cortar**: lo ofrecí y no lo quiso. El candado de pantalla
  sigue ahí.

## Lo que ya estaba cubierto

Vender, cobrar con tarjeta, apuntar gastos y pedir préstamos; el resumen de las
17:45 y la asistencia de las 11:00; alertas de movimientos fuera de horario;
los kioskos venden aunque la PC principal esté apagada; y los avisos de
[[34 - Telegram y Resumen Diario]].

---

**Antes de irse:** correr `scripts\actualizar_pc_principal.bat` (trae la
migración de los avisos, instala las tareas nuevas y reinicia el bot), e
imprimir la hoja con `scripts\hoja_emergencia.bat`.

Relacionado: [[33 - Caja, Nómina y Corte Automático]] · [[34 - Telegram y Resumen Diario]] · [[19 - Deuda Técnica]]
