# Descansos y vacaciones — entrega del 2026-10-12

Estado: **sin commit, sin desplegar**. Producción sigue en `c8d9e0f1a2b3`.
Pruebas: **3,861 pasan** (suite completa, `-n 6 --dist load`). En una corrida falló
una vez `test_catalog_search_refresh_uses_single_debounce_timer`, que es intermitente
y no tiene que ver con esto: sola pasa 3 de 3, y la segunda corrida completa salió verde.

> **2026-10-13 — Vacaciones queda EN CONSTRUCCIÓN** (`vacaciones_service.EN_CONSTRUCCION = True`).
> Daniel: *«lo de vacaciones lo dejaremos oculto o en construcción, quiero que lo de ellas siga
> funcionando como hasta ahora, solo sí dejar mi periodo vacacional claro»*. Con la bandera: nadie ve
> el botón en la Libreta (ni él), el bot contesta «en construcción» a `/vacaciones`, `/primas` e
> `/ingreso`, el menú no lo ofrece y el vigilante no genera periodos. Código, tablas y migraciones
> se quedan. Lo único que sí se usa: **`/receso 2026-10-27 2026-11-04`** apunta su receso en el
> calendario (`calendario_empleadas_service.marcar_receso`): esos días su martes no ocupa el cupo
> y el calendario y los pendientes dicen «Daniel (vacaciones)». `/receso quitar` lo borra.
> Los descansos (motor común, D2/D3/D4) sí van tal como se describen abajo.
>
> Lo que sigue describe el módulo como quedará cuando se estrene (poner la bandera en `False`).

> **Quién usa las vacaciones (Daniel, 2026-10-12): por ahora SOLO Daniel**, desde su Libreta
> (botón «🏖️ Vacaciones del equipo»). Ahí captura la fecha de ingreso, registra vacaciones
> (quedan aprobadas en ese momento, con todas las validaciones), cancela, marca primas
> pagadas y abre a cada empleada «Le dejo pedir desde su Libreta» cuando vea que no hay
> fallos. Mientras no se le abra, ella no ve nada y el servicio rechaza cualquier pedido
> suyo (`expediente_vacacional.autoservicio`, que empieza en NO).

---

## 1. Estado inicial del repositorio

- El modelo antiguo de descansos estaba completo en `HEAD`:
  - autoservicio del Calendario (`65613837`);
  - tope de 2 al mes (`9578380b`);
  - 75 pruebas que pasan.
- También existía la solicitud de la Libreta con aprobación por Telegram (`70757d6f`), sin anticipación, cupo ni tope.
- En el directorio de trabajo había un rediseño mío, sin commit, que borraba el autoservicio. **Se revirtió.**
- En producción, el autoservicio se usó una sola vez (Cristal, 5-nov, pedido el 19-sep). No hay intercambios ni solicitudes de la Libreta.
- No existía nada de vacaciones, ni fecha de ingreso de ninguna empleada.

## 2. Diferencias entre el modelo antiguo y el código actual

**Se conserva igual:**
- 7 días de anticipación.
- Cupo: nadie más descansando ese día. Cuenta cualquier horario, incluidos Daniel e inactivas. D1 **no** se corrigió, por decisión de Daniel.
- 2 cambios al mes, contando pedidos e intercambios.
- El descanso de la semana se mueve al día pedido; si esa semana no tenía, se otorga.
- Intercambio directo con el gafete de la compañera, sin pasar por Daniel.
- Sugerencias de días libres.
- Marcas directas del dueño o el encargado.

**Correcciones mínimas autorizadas:**

| | Antes | Ahora |
|---|---|---|
| D2 | El tope contaba el mes en que se pidió, y borrar el día devolvía el cambio | Cuenta el mes del día que pasa a descansar, y revocar no lo devuelve |
| D3 | Si la semana ya tenía 2 descansos, movía uno y quedaban 2 | Se rechaza («revísalo con Daniel») |
| D4 | Intercambio entre semanas distintas: cada una perdía un descanso | Solo días de la misma semana (la pantalla ya solo ofrece esos) |

**La Libreta:** la solicitud con aprobación de Daniel se conserva, ahora con **las mismas reglas** que el Calendario. Antes era la vía para brincarse el tope.

**Mejoras de integridad, sin cambiar reglas:**
- todo se aplica en una sola transacción (antes un pedido eran 2 commits y un intercambio 4);
- candado de Postgres contra pedidos simultáneos;
- cada cambio queda como solicitud ligada a sus eventos;
- bitácora en `auditoria_ausencias`;
- un pago y un descanso el mismo día ya no se pisan;
- botones viejos de Telegram sin efecto;
- lo pedido en la Libreta vence si nadie contesta, se recuerda cada 24 h y ella ve la respuesta.

## 3. Archivos

**Nuevos:**
- `services/vacaciones_service.py` (lógica de vacaciones)
- `services/telegram_vacaciones_service.py` (vacaciones en Telegram)
- `services/auditoria_ausencias_service.py` (bitácora)
- `ui/dialogs/vacaciones_dialog.py` (ventana «Mis vacaciones»)
- `scripts/reporte_discrepancias_descansos.py` (solo lectura)
- Migraciones: `d9e0f1a2b3c4_descansos_ligados_y_bitacora.py` y `e0f1a2b3c4d5_vacaciones.py`
- 7 archivos de prueba: `test_vacaciones_service`, `test_vacaciones_dialog`, `test_vacaciones_concurrencia`, `test_telegram_vacaciones`, `test_descansos_concurrencia`, `test_libreta_descanso_respuesta`, más `test_descansos_service` reescrito.

**Modificados:**
- `calendario_empleadas_service`: autoservicio restaurado sobre el motor transaccional, tipo `vacaciones`, origen de cada día, marcas auditadas.
- `descansos_service`: motor común de Calendario y Libreta.
- Otros servicios: `telegram_descansos`, `telegram_bot`, `telegram_menu`, `alertas`, `nomina` (vacaciones pagadas en modo por día), `asistencia`, `pendientes`.
- `models.py`.
- `api/routers/movil.py`: marcas auditadas y etiqueta de vacaciones.
- Kiosko: `quote_satellite_window.py` y `calendario_empleadas_dialog.py`. El calendario vuelve a la versión de `HEAD`, más color y leyenda de vacaciones, la línea de «origen del día» y el filtro D4.
- Pruebas: `test_calendario_empleadas` (restaurada de `HEAD`; solo se agregaron tablas y se fijaron fechas en 2 pruebas que dependían del día de hoy), más las bases de prueba de 5 archivos.

**Eliminados:** nada de `HEAD`.

## 4. Esquema y migraciones

| Revisión | Contenido | Bajada |
|---|---|---|
| `d9e0f1a2b3c4` | `solicitud_descanso` con estados `vencido`/`revocado`, intercambio, origen, recordatorios y aviso; `empleada_evento.solicitud_id`; tabla `auditoria_ausencias` | Se niega si hay vencidas, revocadas o intercambios |
| `e0f1a2b3c4d5` | `expediente_vacacional`, `periodo_vacaciones`, `solicitud_vacaciones`, `movimiento_vacaciones`, `prima_vacacional` (una por solicitud), `empleada_evento.vacacion_id` | Se niega si hay movimientos |

Probadas arriba, abajo y arriba en `pos_uniformes_test` y en **`pos_uniformes_copia`**, una copia de producción hecha con `pg_dump` el 2026-10-12.

## 5. Módulo de vacaciones

**Ley Federal del Trabajo, reforma de 2023:**
- **Art. 76:** 12 días el primer año, +2 por año hasta 20; desde el sexto año, +2 cada cinco años.
- **Art. 81:** fecha límite de 6 meses después del aniversario, para concederlas.
- **Art. 78:** 12 días continuos. Se **informa**, no se impone: es un derecho de ella.
- **Art. 80:** prima de al menos 25 %.

**Funcionamiento:**
- **Periodos:** se generan en el aniversario de cada quien, no en enero, y cuentan desde el ingreso o desde la antigüedad reconocida.
- **Solo días laborables:** se cuentan según el patrón real de cada empleada.
- **Expediente:** sin fecha de ingreso sale «pendiente de completar» y no hay saldo. Las condiciones especiales se señalan para revisión y no se sustituyen.
- **Saldo:** se reconstruye sumando movimientos: generación, reserva, liberación, consumo y ajuste con motivo. Nunca queda negativo.
- **Ciclo de una solicitud:**
  - pedir no descuenta, solo aparta;
  - aprobar reserva los días y los pinta en el calendario;
  - cada día que pasa se registra como disfrutado;
  - cancelar o revocar devuelve lo no disfrutado.
- **Conflictos:** detecta faltas, pagos, descansos pedidos y otra compañera de vacaciones esos días. La cobertura se muestra a Daniel.
- **Concurrencia:** candado contra solicitudes simultáneas.
- **Anticipación:** configurable y **apagada** (`ANTICIPACION_VACACIONES_DIAS = None`).

**Pantallas:**
- **Libreta de Daniel:** «🏖️ Vacaciones del equipo» (`ui/dialogs/vacaciones_equipo_dialog.py`).
- **Libreta de ella:** «🏖️ Mis vacaciones», con saldo, periodos, solicitudes, respuestas, pedir y retirar. **Solo aparece si Daniel se lo abrió.**
- **Telegram:** `/vacaciones` con botones (fechas, días, saldo, plazo de ley, quién más falta), `/vacaciones no N motivo`, `/primas` e `/ingreso Nombre AAAA-MM-DD`. También está en el menú.
- **Calendario:** color y leyenda propios, y al tocar un día dice de dónde salió (fijo, cambio, intercambio, vacaciones o marca a mano).

## 6. Pruebas ejecutadas

- **Suite completa:** 3,851 pasan, 0 fallan.
- **Modelo antiguo:**
  - las 34 de `test_calendario_empleadas` (restauradas de `HEAD`);
  - 40 de `test_descansos_service`, que incluyen D2, D3, D4, intercambio atómico y que la Libreta no brinque el tope.
- **Vacaciones:**
  - 41 de servicio: ley, periodos, sin fecha de ingreso, consumo parcial, cancelación, conflictos, prima, conciliación, fallo de transacción y duplicados;
  - 6 de Telegram;
  - 2 de la ventana;
  - **concurrencia en Postgres real**: la prueba falla si se quita el candado.
- **Descansos simultáneos en Postgres real:** también falla sin candado.
- **Migraciones** arriba, abajo y arriba en la base de prueba y en la copia de producción.
- **Calendario y nómina** de todas las empleadas, del 1-ago al 31-dic, código viejo contra código nuevo sobre la copia:
  - **nómina idéntica**;
  - 1 diferencia esperada en el calendario: Evelyn (inactiva) el 17-sep tenía pago y descanso. Antes salía el que llegara último de la base; ahora sale «descanso».
- **Revisión visual:** la ventana de vacaciones renderizada y revisada; se corrigieron columnas cortadas y el botón desactivado.

## 7. Integración con nómina

- **Sueldo semanal:** sigue igual. Las vacaciones no cuentan como falta, así que el sueldo semanal las paga.
- **Modo por día:** los días de vacaciones se pagan.
- **Prima:**
  - al aprobar queda **pendiente** en `prima_vacacional`, una por solicitud, así que nunca se registra dos veces;
  - Daniel la paga aparte y la marca pagada en `/primas`, una sola vez;
  - si las vacaciones se cancelan antes de disfrutarse, la prima pendiente se cancela; si se disfrutan a medias, se ajusta a los días tomados;
  - si ya estaba pagada no se toca: queda una nota para revisar.
- **Conciliación:** `conciliacion_nomina(desde, hasta)` da por empleada los días de vacaciones, las faltas encimadas (debe dar ninguna) y las primas pendientes y pagadas.

## 8. Limitaciones y pendientes

1. **No hay fecha de ingreso de nadie.** Daniel la captura con `/ingreso`. La antigüedad reconocida y las condiciones especiales todavía no tienen pantalla; hoy solo se capturan por código.
2. **REVISAR con el contador:** la base de la prima es sueldo semanal / 7, sin comisiones (LFT art. 89, salario variable).
3. Falta definir la anticipación de vacaciones y si puede haber más de una empleada de vacaciones a la vez (hoy: una).
4. D1 sigue: tu martes y las inactivas con horario bloquean días en el cupo.
5. Casos reales sin corregir, solo informados:
   - Cristal: 5 y 8 de nov, y semana del 21-sep;
   - Cristal 12–13 sep y Stayce 5–6 sep: pago en el día fijo, dudoso.
6. Las vacaciones no se pueden pedir desde el celular (no se pidió). El celular sí las muestra en el calendario.
7. El texto legal se verificó en fuentes secundarias, no en el sitio de la Cámara de Diputados.

## 9. Despliegue (no ejecutado)

1. Respaldar producción: `pg_dump -Fc` en la PC principal.
2. Correr `python -m pos_uniformes.scripts.reporte_discrepancias_descansos` y guardar la salida.
3. Commit y push, luego `scripts\actualizar_pc_principal.bat` (`git pull` + `alembic upgrade head` + build de kioskos).
4. Volver a correr el reporte y comparar.
5. Capturar las fechas de ingreso con `/ingreso`.

## 10. Reversión

1. `alembic downgrade c8d9e0f1a2b3`. Se niega si ya hay datos nuevos: respaldarlos primero.
2. Volver al commit anterior y reconstruir el satélite.
3. Si algo quedó mal, restaurar el respaldo del paso 1 del despliegue.
