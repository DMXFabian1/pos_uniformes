---
name: actualizar-tienda
description: Llevar una versión nueva del POS a la tienda sin sustos — saber desde la Mac qué le falta (commits, migraciones de la caja, versión de cada kiosko), mostrar en seco el SQL de las migraciones y ensayarlas en una copia local, guiar a Daniel a actualizar en el orden seguro (un solo paso en la PC principal) y verificar después. Usar cuando Daniel diga "actualiza la tienda", "sube la versión nueva a la tienda", "publica a los kioskos", "/actualizar", "¿en qué versión está el kiosko?", "¿qué le falta a la tienda?", "¿ya se actualizó?", "el kiosko no abre", "Programa desactualizado", "Base de datos no lista", "dice que está al día y no baja nada", "regresa los kioskos a la versión anterior", o ANTES de hacer push de una migración al tronco. No es para subir el número de pos_uniformes/VERSION.
---

# Actualizar la tienda

La tienda se actualiza **en un solo paso, en la PC principal**: `scripts\actualizar_pc_principal.bat` (fuera de la tienda: `/actualizar si` en Telegram). Ese paso hace, en orden:

1. `git pull`.
2. Build del kiosko **sin publicar**.
3. **Respaldo** de la caja (solo si hay migraciones) y `alembic upgrade head` contra la caja.
4. **Publicar** en `C:\pos_updates` (la versión anterior queda en `PresupuestosSatelite_anterior`) y aviso por Telegram ✅/⚠️/🛑.
5. **Postactualización** (`postactualizacion.bat --pasos-unicos`): tareas de Windows, reinicio del bot y de la PWA, y pasos que **escriben en la caja cada vez**, aunque no haya migraciones: descuenta del stock las ventas de la Libreta que no se descontaron y borra de `satelite` las PCs que llevan un mes sin latir.

Si algo falla antes de publicar, la base no se toca y el código regresa solo. Cada kiosko toma lo nuevo **al abrir su lanzador**.

El icono «POS Uniformes» también actualiza al abrir, pero sin log, sin «LISTO», sin pasos únicos y sin reintentar lo que ya falló: **no dárselo a Daniel como forma de actualizar**, y menos con una migración de por medio.

Desde la Mac **no se actualiza nada**: esta skill lee, explica, ensaya en una copia local y verifica.

## Scripts

Desde la raíz del repo, con `$PY` (ver `CLAUDE.md`) y `--env-file` del env de la caja (ruta en `CLAUDE.md`). Comparan siempre contra `origin/chore/reorganizacion-repo` después de un `git fetch`, nunca contra la rama local de la Mac (puede ir cientos de commits atrás).

| Script | Qué hace | Escribe |
|---|---|---|
| `scripts/estado_tienda.py` | Tronco contra la revisión de la caja (migraciones pendientes, marcando las que rellenan datos con `get_bind`). Versión que late cada PC: commits atrás, y si su programa **no abriría** con la base actual. Cola del bot e impresión atorada. Con `--esperado <commit>` verifica y sale con 1 si algo no cuadra | No |
| `scripts/migraciones_sql.py` | El SQL de las migraciones pendientes **en seco**: `alembic upgrade <caja>:<cabeza> --sql` en un proceso con entorno limpio. `--ref HEAD` antes de hacer push de una migración nueva | No (`--salida` al scratchpad) |
| `scripts/ensayo_migracion.py` | Ensayo **real**: `pg_dump` de la caja (lectura, ~33 MB), restaura en una base nueva del Postgres **local**, corre `alembic upgrade` contra esa copia y la borra (copia y dump) al final. Es para las migraciones con `get_bind`, que no salen en seco | Solo en la Mac |

## Flujo

### 1. Antes: ¿qué le falta a la tienda?
```bash
"$PY" .claude/skills/actualizar-tienda/scripts/estado_tienda.py --env-file "<env de la caja>"
```
Contarle a Daniel, en palabras de la tienda:
- cuántos commits va atrás cada PC;
- qué trae lo nuevo (`git log --oneline <hash de la PC>..origin/chore/reorganizacion-repo`), agrupado por dominio y sin hashes;
- si hay migraciones pendientes.

### 2. Si hay migraciones pendientes (o vas a hacer push de una)
- `migraciones_sql.py --env-file … --salida <scratchpad>/migracion.sql` (con `--ref HEAD` si la migración aún no está en el tronco). Enseñar el SQL resumido: qué tablas y columnas cambian.
- Si alguna usa `get_bind`, correr `ensayo_migracion.py --env-file … --carpeta <scratchpad>` (con `--ref HEAD` si aplica). Si falla en la copia, fallaría en la tienda: corregir antes.
- **Nunca** `createdb -T` ni `alembic upgrade` (sin `--sql`) con el env de la caja cargado: eso crea o migra bases **en el servidor de producción**.
- **Esperar el OK de Daniel.** La regla de `CLAUDE.md` (nunca migrar la caja sin confirmar) aplica aquí. Darle la indicación de actualizar, o hacer push de una migración al tronco, **es** migrar producción: corre al abrir el icono de la PC principal, o a las 19:30 si la tarea «POS Actualizar» está encendida.

### 3. Lo que hace Daniel en la tienda
1. Revisar los requisitos de la versión (ver «Antes de cada versión», abajo).
2. En la PC principal: doble clic en **`scripts\actualizar_pc_principal.bat`**. Esperar «LISTO» y el Telegram. Si dice «LISTO» y no llega Telegram, puede ser que ya estuviera al día.
3. En la PC principal: **cerrar y volver a abrir el POS**. El programa abierto sigue siendo el viejo hasta reabrirlo.
4. En cada kiosko: **con el carrito vacío**, cerrar el kiosko y volver a abrir su acceso directo; el lanzador copia lo nuevo. No abrir el acceso directo con el kiosko ya abierto: el lanzador lo cierra a la fuerza y una venta a medias se pierde.
5. Si sale 🛑 o «ALGO FALLO», no repetir a ciegas. Pedir el mensaje de Telegram o `reportes\ultimo_update.log`:
   - si viene del `.bat` manual, está en UTF-16LE: `iconv -f UTF-16LE -t UTF-8`;
   - si viene del bot o de la tarea de la noche, está en cp1252: `iconv -f CP1252 -t UTF-8`;
   - si el `git pull` falló, no llega Telegram aunque el `.bat` lo diga.

### 4. Después: verificar
```bash
"$PY" .claude/skills/actualizar-tienda/scripts/estado_tienda.py --env-file "<env de la caja>" --esperado <commit>
```
`✓ OK` quiere decir que la caja está al día y que todos los kioskos que latieron en las últimas 24 h corren ese commit. Hay dos cosas que el script no puede comprobar:
- **El POS de la PC principal y el bot** no laten en `satelite`. `/version` en Telegram dice qué código hay en disco y qué está publicado, no lo que corre un programa abierto. El bot se reinicia solo en la postactualización; el POS, al reabrirlo.
- **El renglón «PC principal»** de `satelite` es su servidor de impresión: se queda en el commit viejo hasta que se reinicia (o se reinicia la PC). El script lo marca como nota, no como falla.

### 5. Cerrar
Anotar con `actualizar-vault`:
- en `21 - Sesión de Trabajo`, la línea «Tienda:» (qué PC quedó en qué commit y la fecha);
- si hubo un susto nuevo, en `29 - Updates y Mensajería`.

## Nunca

- **Nunca dictar pasos sueltos**: `alembic upgrade`, `actualizar_solo_migraciones.ps1`, build o `setup_satelite.ps1` por separado. Ya pasó (8-sep, 13-nov): la base queda migrada, los kioskos se quedan con el programa viejo y **no abren**. El único camino es `actualizar_pc_principal.bat` en la PC principal, que es la única con `C:\pos_updates`. Cualquier otra PC con el repo migraría sin publicar.
- **Nunca correr `alembic` desde la Mac con el env de la caja cargado.** `set -a; . env` + `alembic upgrade` = migrar producción sin respaldo. Los scripts usan `--env-file` con conexión de solo lectura, y alembic solo corre en subprocesos con el entorno limpio.
- **Nunca hacer push al tronco de una migración sin el OK de Daniel**, ni sin enseñarle antes su SQL en seco (`--ref HEAD`).

## Antes de cada versión (requisitos que ya han hecho falta)

- **PIN del dueño** (desde `12842fea`, 19-nov). Antes de actualizar, Daniel debe tener su PIN definido en POS principal › Configuración › Empleadas › Definir PIN. Acepta de 4 a 8 dígitos; se recomiendan 6 a 8. Además, cada kiosko debe abrir una vez con la PC principal encendida para copiar el PIN: sin red, valida contra esa copia.
- La PC principal debe estar en la rama `chore/reorganizacion-repo`. Si quedó en `main`, `git pull` no trae nada y dice «al día». Se revisa con `scripts\revisar_actualizacion.bat`.
- La PC principal está en Wi-Fi y ya ha caído en APIPA (169.254.x.x). Si `git pull` o el share fallan, revisar la red primero.

## Leer bien el estado

- **Encendida** = latió hace ≤150 s, medido con el reloj de la caja contra la hora que escribe cada PC. Una PC con la hora mal se ve apagada o encendida de más; el script avisa si va adelantada.
- «🛑 su programa no conoce la revisión de la caja: NO abre» = ese kiosko está más viejo que la base. Solución: actualizar la PC principal (eso publica) y reabrir el kiosko. Si ya está publicado y el kiosko no abre: `reparar_satelite.bat` en el kiosko.
- «La caja tiene una revisión que el tronco no conoce» = alguien migró desde otra rama o falta un push. **No actualizar** hasta aclararlo; `actualizar.py` se negaría con PROGRAMA_VIEJO.
- Un `--sql` que truena por `get_bind` no quiere decir que la migración esté mal: para esas está `ensayo_migracion.py`.

## Volver atrás

- **Solo los kioskos**: `scripts\volver_version_anterior.bat` en la PC principal. Se niega si la versión anterior no conoce la revisión de la caja. **`/volver si` en Telegram NO revisa la base**: después de una versión con migración, deja kioskos que no abren. Solo usarlo si la versión no traía migración (compruébalo antes con `estado_tienda.py`).
- **La base**: no hay vuelta automática. El respaldo previo está en `pos_uniformes\backups\database\` de la PC principal. Restaurarlo es decisión de Daniel, con él presente.

Notas del vault: `POS Uniformes/29 - Updates y Mensajería.md` (historia de cada susto) y `21 - Sesión de Trabajo.md` (en qué versión quedó la tienda).
