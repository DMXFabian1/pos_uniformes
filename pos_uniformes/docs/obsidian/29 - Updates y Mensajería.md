---
tags: [deploy, infraestructura, pos-uniformes]
---

# Updates automáticos y Mensajería por git

> [!info] Las "dos ventanas rebeldes" eran el bot y la PWA (2026-09-14)
> Windows 11 con **Windows Terminal como terminal por defecto** muestra como pestaña (`C:\…\python.exe`) cualquier consola, aunque el proceso se lance con `CREATE_NO_WINDOW` (y `DETACHED_PROCESS` además lo anula). Los vigías ahora arrancan el bot y uvicorn con **`pythonw.exe`** (`utils.config.python_sin_consola()`), que no tiene consola. Además el icono del satélite salía blanco: los `.ico` traían una sola imagen de 128 px; ahora 7 tamaños (16–256) **con los iconos originales de Daniel** (la **M** de Medium para el POS y el **átomo** para el kiosko; fuentes en `~/Downloads/Nueva carpeta con elementos/`, commit `9384ff8c` — la M café/crema que se probó primero se descartó). Ambas cosas entran al actualizar (el build del satélite es parte de `actualizar_pc_principal`). Y `MeilisearchPOS` corría `meilisearch.exe` con `LogonType Interactive` → a `S4U`: lo hace solo el paso único `meilisearch_s4u` (abajo) y `setup_meilisearch_windows.ps1` ya la registra así de origen.

> [!info] Pasos de una sola vez al actualizar (2026-09-15)
> Lo que antes había que correr a mano en la principal después de actualizar ahora lo hace **`postactualizacion.bat --pasos-unicos`**, que solo llama `actualizar_pc_principal.bat` (nunca `abrir_pos.bat`, para que abrir el POS no tarde ni reintente instaladores). `PASOS_UNICOS` en `postactualizacion.py`, en orden:
> 1. **`meilisearch_s4u`** — si existe la tarea `MeilisearchPOS` y no está en S4U: `New-ScheduledTaskPrincipal … -LogonType S4U -RunLevel Highest`, `Set-ScheduledTask`, mata `meilisearch.exe` y la relanza. Puede pedir admin; si falla, reintenta.
> 2. **`descontar_ventas_pasadas`** — `python -m pos_uniformes.scripts.descontar_ventas_pasadas --aplicar` desde la raíz del repo (timeout 10 min). Idempotente (salta `libreta:N` ya descontados). Salida en `logs\descontar_ventas_pasadas.log`. **Corre en CADA actualización** (`cada_vez=True`, no se anota): un kiosko que todavía no se reinició con el código nuevo sigue vendiendo sin descontar, y la siguiente actualización barre lo que dejó.
> 3. **`instalar_afluencia`** — `cmd /c afluencia\instalar_afluencia.bat` con **stdin a NUL** (su `pause` no detiene nada), timeout 30 min; si sale bien abre en ventana propia `dibujar_lineas.bat` (`start "Lineas de afluencia"`). Sin `instalar_afluencia.bat` en esa PC no hace nada.
>
> Cada paso queda en **`data\pasos_unicos.txt`** (una línea por nombre) **solo si salió bien**; si falla o truena se anota `PENDIENTE (se reintenta al actualizar): …` en pantalla y en `logs\postactualizacion.log`, los demás siguen, y vuelve a intentarlo la siguiente actualización. Fuera de Windows no corre nada. `_correr()` ahora acepta `cwd`, `guardar_en` (dónde dejar stdout+stderr) y siempre manda `stdin=DEVNULL`. Para agregar otro: una función `paso_x() -> bool` y una línea en `PASOS_UNICOS`; para que se repita, borrar su línea de `pasos_unicos.txt`. Tests: `PasosUnicosTests` en `test_postactualizacion` (orden, anota solo los buenos, reintento, truena = fallido, Mac no corre, `main` solo con la bandera, cada paso).

> [!warning] «Ya estás al día» era mentira (2026-10-02)
> Daniel le dio al acceso directo y **no pasaba nada**. `abrir_pos.bat` cuenta lo que le falta a la rama actual **contra su propia rama remota**: si la copia estuviera parada en `main` —que quedó en el 11 de julio, porque todo lo nuevo vive en `chore/reorganizacion-repo`— no le falta nada *de main*, y la respuesta es «Ya estás al día»: correcta a la pregunta equivocada.
> Y había un segundo silencio peor: `set BEHIND=0` **antes** del conteo, con el error mandado a `nul`, así que si el conteo **fallaba** (rama sin remota, por ejemplo) BEHIND se quedaba en 0 y también decía «al día». **No poder saber se veía igual que estar al día** — el mismo patrón del respaldo que nadie disparaba.
> Ahora el centinela es `?` y cada caso dice lo suyo; cuando de verdad está al día dice **en cuál rama** lo está. Y `scripts\revisar_actualizacion.bat` contesta la pregunta de verdad: rama, rama remota, commits que faltan, cambios locales que estorban el pull, versión que corren los kioskos — y cuando el problema es la rama, escribe el comando exacto. Tests con repos git de verdad en carpetas temporales (`test_revisar_actualizacion`).
>
> **La causa real aquel día no era la rama: era la red.** Ver [[22 - Referencia Rápida]] § Red.

> [!info] INFRA_VERSION 7 (2026-10-01)
> **v7:** tarea **`POS Respaldo`** diaria a las 20:30 (`respaldo_diario.bat --callado`). No existía ninguna tarea de respaldo: `run_scheduled_backup.py` estaba escrito desde siempre y **nada lo corría**. Va junto al supervisor y **no depende de que Telegram exista** — una PC sin bot también necesita respaldo. También entra **`POS Corte final`** (18:50, `corte_automatico.bat --cerrar`). Ver [[42 - Antes de irme — lo que no dependa de mí]].

> [!info] INFRA_VERSION 6 (2026-09-14)
> **v6:** las tareas del **corte propuesto** (`POS Corte 1630/1730` y los recordatorios 1650/1750) entran a las esperadas **si alguna existía**: en la PC de Daniel estaban creadas con `corte_automatico.bat` directo (instalador viejo) y **eran la ventana negra**. Además `revisar_tareas` leía mal el Windows en español (la columna "Tarea que se ejecutará" llegaba con el acento roto y marcaba TODAS como "abre ventana"); ahora busca las columnas sin acentos. Arreglo inmediato que se corrió en PowerShell: recrear las dos tareas del corte con `schtasks /Create /F … /TR "wscript.exe correr_oculto.vbs corte_automatico.bat"`.
>
> [!info] INFRA_VERSION 5 (2026-09-13)
> **v5:** **"POS Afluencia"** (ONLOGON, `..\afluencia\contador_afluencia.bat` por `correr_oculto.vbs`) entra a las tareas esperadas **solo si** la tarea ya existía o existe `afluencia\.venv`. El instalador de afluencia la crea; la postactualización la mantiene oculta.
>
> **v3:** se sumó **"POS Snapshot Casa"** a las tareas que la postactualización deja ocultas (si existe, se recrea vía `correr_oculto.vbs` con la misma `/TN`). Era la ventana negra que sobrevivió a la v2: `programar_snapshot_casa.bat` la creaba directo. El instalador ya la crea oculta.
> **v4:** nace **"POS Asistencia"** (11:00, `resumen_diario_telegram.bat --asistencia`), solo si hay Telegram.
>
> Tareas vivas hoy: POS Supervisor (ONLOGON) · POS Supervisor check (30 min) · POS Resumen 1645 / 1745 · POS Pendientes (13:30) · POS Asistencia (11:00) · POS Snapshot Casa (15 min, si estaba) · POS Afluencia (ONLOGON, si está instalada) · las de corte propuesto si se instalaron. Todas por `correr_oculto.vbs`. Diagnóstico: `scripts\revisar_tareas.bat` (`--arreglar` aplica la postactualización a la fuerza).

> [!success] Desde 2026-09-03 los kioskos se actualizan solos por red (sin USB)
> Probado en piso: kiosko instalado, actualizado a `2026.09.03` y con impresión de etiquetas funcionando.

---

## Cómo fluye una actualización

```
Mac (Claude) → git push → PC principal: scripts\actualizar_pc_principal.bat
   (pull + alembic upgrade head + build + publica a C:\pos_updates)
→ Kiosko: al abrir el lanzador, compara VERSION.txt, copia lo nuevo y arranca
```

- ~~VERSION debe bumpearse en cada entrega~~ **Desde 2026-09-08 ya no**: la build escribe `VERSION.txt` = `VERSION+commit` (p.ej. `2026.11.11+3c69b5b`) dentro del bundle y en el share; el lanzador y la app comparan esa cadena, así que **cada build publicada actualiza los kioskos**. (El 2026-09-08 se dictaron alembic+build por separado y salió "Base de datos no lista" — base migrada, exe viejo; lección: **siempre `actualizar_pc_principal.bat`**, un solo paso.)
- El lanzador **se refresca a sí mismo** desde el share (mejoras al lanzador tampoco necesitan USB).
- Con la PC principal apagada, el kiosko arranca su versión local — nunca queda tirado.
- El `.env` personalizado en `%APPDATA%\PresupuestosSatelite\` sobrevive updates (gana sobre el del bundle).

## Piezas

| Pieza | Dónde |
|-------|-------|
| Carpeta publicada | PC principal `C:\pos_updates` → share `\\192.168.0.10\pos_updates` (creado con `scripts\preparar_share_updates.bat` como admin) |
| Usuario de acceso | **`kiosko` / `pos2026`** (local en la principal, password sin expirar, oculto del login). Win11 bloquea invitados; el lanzador hace `net use` con él en cada arranque |
| Lanzador (en cada kiosko) | `C:\PresupuestosSatelite\lanzador_satelite.bat` + `.ps1` · acceso directo en Escritorio (y `shell:startup` para abrir al prender) |
| App instalada (kiosko) | `%LOCALAPPDATA%\PresupuestosSatelite\app\` |
| Requisito por kiosko (una vez) | **VC++ Redistributable x64**: `https://aka.ms/vs/17/release/vc_redist.x64.exe` (sin él: "DLL load failed importing QtWidgets") |

## Instalar un kiosko nuevo (resumen)

1. Instalar `vc_redist.x64.exe`
2. cmd: `net use \\192.168.0.10\pos_updates pos2026 /user:kiosko /persistent:no`
3. `copy \\192.168.0.10\pos_updates\lanzador_satelite.* C:\PresupuestosSatelite\`
4. Abrir el `.bat` (descarga la app sola) + acceso directo a Escritorio/`shell:startup`

## Mensajería por git (Mac ↔ PC principal)

> [!tip] Regla: nunca dictar comandos largos
> Todo lo que deba correr en Windows viaja como `.bat` corto en `scripts/` (**ASCII puro** — PowerShell 5.1 lee sin BOM como ANSI y los acentos/guiones largos rompen las comillas).

| Comando (PC principal) | Hace |
|------------------------|------|
| `scripts\actualizar_pc_principal.bat` | pull + migraciones + build + publicar (auto-loguea a `reportes\ultimo_update.log`) |
| `scripts\enviar_reporte.bat` | Sube `reportes\` al repo (logs + `reportes\mensaje.txt` de texto libre) → Claude lo lee en la Mac con `git pull` |
| `scripts\preparar_share_updates.bat` (admin) | Setup único: carpeta + share + firewall 445 + usuario kiosko |

Flujo de ida y vuelta: Claude empuja `.bat` → Daniel corre una línea → si algo truena, `enviar_reporte.bat` → Claude lee el error exacto. Se acabaron las fotos de consola.

## Roles de cada PC (cómo se identifican)

| Rol | Se define en |
|-----|--------------|
| PC principal (datos + updates) | `.env` (`POS_UNIFORMES_SERVER_HOST=192.168.0.10`) — única fuente de la IP; los kioskos y el lanzador la leen de ahí |
| Quién imprime | Config local por máquina (admin `Ctrl+Shift+A`): 🖨 Servidor de impresión vs 📡 Estación (encola en la DB) |
| Quién publica updates | La que tenga `C:\pos_updates` (la principal) |

## Alexa (evaluado 2026-09-03, en pausa)

- Camino corto (enchufe virtual LAN, "Alexa enciende X" → acción sin parámetros): factible en una tarde.
- Dictar producto/talla/cantidad ("imprime 10 etiquetas de calceta blanca 13-18"): requiere skill en la nube + túnel + matching contra ~4,800 variantes → riesgo de etiquetas mal impresas. **Recomendado en su lugar:** mini-flujo de etiquetas por escáner en el kiosko → cola de impresión central (pendiente si Daniel lo pide).

---

## Fixes de la sesión 2026-09-04 (el updater quedó fino)

- **Bug raíz del "siempre hay versión nueva"**: en el exe, `app_version()` buscaba VERSION fuera del bundle (`sys._MEIPASS`) y caía al default `2026.03.18` → la app ofrecía actualizar por siempre y el cmd "no hacía nada" (no había nada que copiar). Corregido en `utils/app_metadata.py`.
- **Proceso zombi**: "Actualizar ahora" cerraba la ventana pero no el proceso (cartelera + candado de instancia) → robocopy bloqueado y "ya se está ejecutando el satélite". Fix doble: la app hace `QApplication.quit()` y el **lanzador mata al satélite vivo** antes de copiar (matazombis).
- **Scripts nuevos**: `instalar_kiosko_aqui.bat` (kiosko completo en un comando — local en la principal, por red con credencial en las demás) · `forzar_update_satelite.bat` (taskkill + lanzador, para desatorar).
- Regla vigente: **bump de VERSION en cada release** — hoy quedó en `2026.10.04`.


## 2026-09-08 — un solo paso y versión con commit

- `build_presupuestos_satelite_windows.ps1` publica `VERSION.txt` con versión+commit **dentro del bundle y en el share**; `satellite_update_service.version_local()` lee ese archivo junto al exe (antes comparaba `VERSION` interno contra la cadena con commit y avisaba "versión nueva" en cada arranque).
- Regla con Daniel: nunca dictar alembic/build/setup sueltos; la instrucción es **`scripts\actualizar_pc_principal.bat`** y reabrir el satélite en cada kiosko (o `forzar_update_satelite.bat` si se atora). La principal debe estar en la rama del trabajo (`git pull` sin args jala la actual).
- Instaladores de un paso nuevos en la principal: `afluencia\instalar_afluencia.bat` (contador de personas), `scripts\instalar_resumen_diario.bat` (bot + resumen + pendientes de Telegram). Ver [[32 - Cámaras y Afluencia]] y [[34 - Telegram y Resumen Diario]].

## Tareas de Windows sin ventana negra (2026-09-09)

Las tareas ya no llaman al `.bat` directo (eso abría una consola un instante): pasan por **`scripts/correr_oculto.vbs`** (`wscript.exe "...\correr_oculto.vbs" archivo.bat [args]` → `sh.Run cmd, 0, False`). `scripts/quitar_parpadeo_tareas.bat` repara de un golpe las tareas ya creadas sin reinstalar nada. Test: `test_tareas_windows_sin_ventana` (ninguna tarea puede invocar el `.bat` directo).

## La infraestructura se aplica sola al actualizar (2026-09-10)

Antes, cada cambio de infraestructura (tareas de Windows, servicios) pedía correr un instalador a mano en la principal. Ahora **es parte de la actualización**: `abrir_pos.bat` y `actualizar_pc_principal.bat` terminan llamando a `scripts\postactualizacion.bat`.

`scripts/postactualizacion.py`:

| Concepto | Cómo funciona |
|----------|---------------|
| `INFRA_VERSION` | Número en el módulo. Si el archivo `data/infra_version.txt` de la PC está atrasado, se aplica todo; si ya coincide, no toca nada (correrlo cuesta ~1 s) |
| `tareas_esperadas()` | Las tareas que deben existir: **POS Supervisor** (logon) · **POS Supervisor check** (30 min) · con Telegram configurado, **POS Resumen 1645/1745** y **POS Pendientes**. Todas ocultas vía `correr_oculto.vbs`. Si Daniel eligió hora fija (`POS Resumen diario`), se respeta y no se crean las dos automáticas |
| `TAREAS_OBSOLETAS` | Se borran solas: POS Telegram bot/vigia, POS PWA servidor/vigia (las de cada 5 min que parpadeaban) |
| Servicios | Al final deja la bandera de reinicio y levanta el supervisor si no corre: bot y PWA toman el código nuevo |
| A prueba de todo | Nunca detiene la actualización: si algo falla lo anota en `logs/postactualizacion.log` y el POS abre igual. Fuera de Windows no hace nada |

> [!tip] Para el futuro
> Cambio de infraestructura nuevo = agregarlo en `tareas_esperadas()` (o en `TAREAS_OBSOLETAS` si se retira) y **subir `INFRA_VERSION`**. Entra solo en la siguiente actualización, sin pedirle nada a Daniel. `instalar_supervisor.bat` quedó como atajo manual (`postactualizacion.bat --forzar`).

Tests: `test_postactualizacion`.

## Un clic lo hace todo — y ahora también republica (2026-09-22)

Daniel: *"¿podemos hacer que esto se haga solo al presionar, como lo hacía antes? solo presiono el icono de POS Uniformes y ejecuta todo"*. Ya lo hacía (`scripts/abrir_pos.bat`: fetch → pull → migraciones → build y publicación a kioskos → tareas → abre), **pero tenía un hueco**: solo construía cuando había commits nuevos. Tras un `git pull` a mano (o una build fallida), decía "ya estás al día" y los kioskos se quedaban con código viejo contra una base ya migrada → *"Base de datos no lista"*.

Ahora compara el commit publicado en `PresupuestosSatelite\VERSION.txt` con el de ahora y, si no coinciden, **republica antes de abrir**: *"Los kioskos corren 2026.11.11+2bfb6c1f y el código va en 2619b7ee - republicando…"*. Test `tests/test_abrir_pos_bat.py` cuida que el guion no pierda pasos.

**Además** (`72c0cf23`): si un kiosko se quedó atrás, el arranque ya **no bloquea**. `database/preflight.py` distingue si la versión de la base es *descendiente* de la que pide el programa (la base va adelante) y en ese caso solo lo anota en el log; la base **atrasada** sigue bloqueando, que es lo peligroso. Antes decía "la base de datos está desactualizada", justo lo contrario de lo que pasaba.

> **Regla:** si se corre una migración fuera de `actualizar_pc_principal.bat`, hay que publicar el satélite después — o abrir el icono, que ahora lo hace solo.
