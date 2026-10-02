---
tags: [sesion, pos-uniformes]
---

# Referencia Rápida

Datos operativos que se buscan seguido. Sin contexto — solo los datos.

---

## Red y acceso a DB

> [!info] Conexión PostgreSQL
> **IP PC principal:** `192.168.0.10`
> **Puerto:** `5432` · **Base de datos:** `pos_uniformes`
> **Usuario:** `postgres` · **Password:** `1234`

> [!tip] Mac — auto-detección de DB (desde 2026-05-25)
> El app detecta automáticamente si Windows está en LAN.
> **En tienda:** conecta directo a `192.168.0.10` · título muestra 🟢 Tienda
> **Sin LAN:** usa DB local de Mac · título muestra 🟡 Local
> No hay que tocar el `.env` manualmente.

---

## Red — el diagnóstico del 2026-10-02 (leer antes de volver a sufrir)

La PC principal no podía con `git`, y el bot llevaba horas muerto. Lo que se
fue descartando, en orden, porque cada paso parecía la respuesta:

| Síntoma | Lo que parecía | Lo que era |
|---|---|---|
| `Could not resolve host: github.com` | token de GitHub caducado | DNS |
| `ping 8.8.8.8` → responde `169.254.63.36` | DNS mal configurado | la PC sin dirección válida |
| `169.254.x.x` (APIPA) | el router viejo apagado | el router **sí** contestaba |
| ruta por 192.168.0.1 con gateway que responde | un adaptador fantasma robando la ruta | ruta única y limpia |
| al revisar, la APIPA ya no estaba | — | el Wi-Fi se reasoció solo |

**Lo que quedó claro y sigue sin arreglarse:**

- **La PC principal —la que tiene Postgres— está en Wi-Fi.** El `192.168.0.10`
  vive en el adaptador inalámbrico. Los kioskos le preguntan todo por el aire.
- **El Ethernet tiene un cable conectado a nada** (`169.254.21.235`, sin
  gateway). El puerto existe y está libre.
- **El DNS del Wi-Fi son puras direcciones IPv6** (`2806:260:…`). Las IPv4
  (`189.194.224.51`) están en el Ethernet, que no sirve.

> [!tip] Lo que falta hacer
> **Enchufar el cable de red a la PC principal.** Un servidor de base de datos
> por Wi-Fi es frágil por diseño, y explica también la lentitud del kiosko.
> Y poner DNS IPv4 en el Wi-Fi:
> `Set-DnsClientServerAddress -InterfaceAlias "Wi-Fi" -ServerAddresses 8.8.8.8,1.1.1.1`
> (admin; se revierte con `-ResetServerAddresses`).

**Comandos que sirvieron** (PowerShell; ojo: **no acepta `&&`**):

```
Get-NetIPConfiguration -Detailed | Select-Object InterfaceAlias, @{n='IP';e={$_.IPv4Address.IPAddress -join ','}}, @{n='Gateway';e={$_.IPv4DefaultGateway.NextHop -join ','}}, @{n='DNS';e={$_.DNSServer.ServerAddresses -join ','}} | Format-Table -AutoSize
Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Format-Table ifIndex, InterfaceAlias, NextHop, RouteMetric, InterfaceMetric -AutoSize
Get-NetIPAddress -InterfaceAlias "Wi-Fi" -AddressFamily IPv4 | Format-Table IPAddress, PrefixLength, PrefixOrigin, SuffixOrigin, AddressState -AutoSize
```

> [!warning] Lentitud del kiosko (2026-10-02)
> Se midieron las dos sospechas que se podían medir y **las dos salieron
> limpias**: guardar el catálogo en disco cada 5 min son **25 ms**, y
> reconstruir índice + navegador **38 ms**. El escaneo ya resuelve del catálogo
> en memoria desde 2026-09-17. Queda la red: medir con `ping -n 20
> 192.168.0.10` **desde un kiosko** (por cable debe dar 1-2 ms parejos).

## PINs del satélite

> [!example] PINs para imprimir etiquetas
> | Rol | PIN |
> |-----|-----|
> | Admin | `634700` |
> | Empleadas | `12345` |

---

## Comandos de un solo golpe (PC principal, 2026-09)
- `scripts\diagnostico_impresora_carta.bat` — ¿por qué no imprime la HP? Lista impresoras (Qt y Windows), manda hoja de prueba a cada HP, deja `reportes\impresora_carta.txt` → `scripts\enviar_reporte.bat`

| Comando | Hace |
|---------|------|
| `scripts\actualizar_pc_principal.bat` | pull + migraciones + build + publicar a kioskos (loguea a `reportes\ultimo_update.log`) |
| `scripts\enviar_reporte.bat` | sube la consola/mensajes a git para que Claude los lea en la Mac |
| `scripts\preparar_share_updates.bat` (admin) | setup único del share de updates + usuario kiosko + firewall |

## Updates de kioskos (2026-09)

> [!info] Share y credencial
> **Share:** `\\192.168.0.10\pos_updates` · **Usuario:** `kiosko` / `pos2026`
> **Lanzador en kiosko:** `C:\PresupuestosSatelite\lanzador_satelite.bat` (acceso directo en Escritorio / `shell:startup`)
> **App instalada:** `%LOCALAPPDATA%\PresupuestosSatelite\app\`
> **Requisito por kiosko:** vc_redist.x64 (`https://aka.ms/vs/17/release/vc_redist.x64.exe`)
> Desde 2026-09-08 la build publica `VERSION.txt` = versión+commit (p.ej. `2026.11.11+3c69b5b`) y la app lo lee como versión instalada: **cada build publicada actualiza los kioskos** sin tocar `VERSION`

## DVR de cámaras y afluencia (2026-09-08)

> [!info] DVR Dahua
> **IP fija** `192.168.0.11` · usuario del POS **`dany`** (la contraseña vive en `data/dvr_settings.json` / `POS_UNIFORMES_DVR_PASSWORD`, no en el vault) · RTSP 554 · web 80 · app DMSS (XVR, SN `2J02AFBPAGQ1B47`)
> Canales: 1 VESTIDOR · 2 CAJA · 3 ENTRADA2.2 · 4 ENTRADA1 · 5 ENTRADA1.1 · 6 ENTRADA2 · 7 MOSTRADOR2 · 8 MOSTRADOR1
> Kiosko: botón **Cámaras** / **Ctrl+Shift+C** · admin PIN `634700` ve todas · config por kiosko en Ctrl+Shift+A → 📹 Cámaras
> Contador de personas (PC servidor, una vez): `afluencia\instalar_afluencia.bat` · **dibujar las líneas con el ratón:** `afluencia\dibujar_lineas.bat` (el contador las toma solo) · ¿por qué no cuenta?: `afluencia\diagnostico_afluencia.bat` + `scripts\enviar_reporte.bat` · log: `logs\afluencia.log`
> Impresora HP Smart Tank 750: `192.168.0.9` (DHCP), `HP644ED72F27FC.local`; cola en la Mac `HP_Smart_Tank_750_series__2F27FC_`

## Caja, nómina y Telegram (2026-09-08)

> [!example] Asistencia (2026-09-12) — desde el 13: `/descanso_X` mueve el fijo; `/vino_X` en su descanso tapa una falta (faltas netas)
> `/asistencia` → quién vino (deducido del primer movimiento) + `/falta_Nombre · /descanso_Nombre` por empleada; tocar marca, repetir quita. Sola a las **11:00**. Con espacio también: `/falta Fanny`, `/vino Fanny`.

> [!example] Reglas
> Reactivo inicial **$11,160** · sueldo **$1,300**/7 días + **$2**/comisión − **$216.67**/falta · por días: sueldo/6 por día · cierre 18:00 (jue y dom 17:00), corte 30 min antes
> Solo **VEND-1** y **ENC-1** cortan, pagan y apuntan retiros · León: **Hacer corte** = un botón (ticket: SE VENDIO · PAGAR A · YA SALIO · SACAR DE LA VENTA)

| Comando (PC principal) | Hace |
|------------------------|------|
| `scripts\instalar_resumen_diario.bat [HH:MM] [auto]` | Tareas: bot de Telegram (al iniciar sesión), resumen 15 min antes de cerrar (17:45; jue/dom 16:45), pendientes 13:30; `auto` = corte automático 16:30/17:30 (apagado por default) |
| `scripts\resumen_diario_telegram.bat [--imprimir] [--chat-ids] [--pendientes]` | Manda (o muestra) el resumen; `--chat-ids` descubre tu chat |
| `scripts\corte_automatico.bat [--simular] [--forzar]` | Corte de un botón desde la consola |
| `scripts\telegram_bot.bat` | Deja el bot escuchando (`/corte` `/estado` `/resumen` `/pendientes`) y **manda las alertas** (corte hecho, retiro, cierre sin corte, fuera de horario). Ya no deja ventana. Lo cuida el **supervisor** (`scripts\supervisor.bat`, un proceso oculto que revisa bot y PWA cada 60 s); `instalar_supervisor.bat` lo deja instalado. Las actualizaciones piden reinicio con `supervisor.bat --pedir-reinicio`. Log: `logs\telegram_bot.log` |
| `scripts\supervisor.bat [--reiniciar\|--pedir-reinicio]` | El proceso oculto que cuida **bot de Telegram + PWA** (revisa cada 60 s). Log: `logs\supervisor.log` |
| `python -m pos_uniformes.scripts.reubicar_conteos_por_prenda [--aplicar]` | Si una jornada de una prenda de básicos trae tallas de otras prendas, las manda a la jornada que les toca (dry-run sin `--aplicar`). Desde la Mac apunta a producción |
| `scripts\postactualizacion.bat [--forzar] [--pasos-unicos]` | Deja tareas y servicios al día. **Lo corre sola cada actualización**; a mano solo si algo se descuadró. `--pasos-unicos` (solo desde `actualizar_pc_principal.bat`): Meilisearch S4U, descontar ventas pasadas, instalar afluencia — una vez, anotados en `data\pasos_unicos.txt` |
| `scripts\instalar_servidor_pwa.bat` | Deja la Libreta móvil corriendo sola (`http://192.168.0.10:8000/app`) |
| `afluencia\instalar_afluencia.bat` | Contador de personas (venv propio + tarea "POS Afluencia" oculta; reinicia el contador si ya corría). **Lo corre sola la primera actualización** (paso único) |
| `afluencia\dibujar_lineas.bat` | Dibujar la línea de conteo de cada cámara con el ratón; se aplica en caliente |
| `afluencia\diagnostico_afluencia.bat` | Seis revisiones del contador → `reportes\afluencia.txt` |

> Env de Telegram: `POS_UNIFORMES_TELEGRAM_BOT_TOKEN` + `POS_UNIFORMES_TELEGRAM_CHAT_ID` en `pos_uniformes.env` de la principal.

## Celular — dónde ver y qué gesto (2026-09-18)

| Quiero… | Dónde |
|---|---|
| Regresar | `‹ Atrás` arriba a la izquierda, o el botón/gesto de atrás del celular (ya regresa dentro de la app) |
| Actualizar la pantalla | `↻` arriba, o jalar hacia abajo (menos dentro de la hoja de captura) |
| Traer la última versión de la app | `⋯` → *Traer la última versión* (sustituye al "recargar dos veces") |
| Cerrar sesión | `⋯` → *Cerrar sesión* (los botones Salir siguen abajo) |
| Ver qué mercancía ha llegado | Bodega → *📜 Lo que ha llegado* (celular) · POS → Historial inventarios (ENTRADA_COMPRA "Llegó: …") |
| Ver qué está contado y qué no | Celular → 🗺 Mapa de conteos · Kiosko → **sección Conteos** (el mapa está donde estaba la tabla; *Ver tabla* la trae; 🗺 Mapa lo abre grande): verde al día, ámbar vencido, gris nunca, naranja en proceso; escuela → prenda → tallas |
| Quitar una falta/descanso mal apuntado | Celular → 👥 Asistencia → la persona → *Apuntado (últimas dos semanas)* → **Quitar** · Kiosko → Libreta → Equipo → nombre → Quitar marca · Telegram → repetir `/falta_X` |
| Un pago o retiro que no salió del cajón | Kiosko → Hacer corte → desmarcar esa línea (queda anotado, el ticket no lo lista) |
| Etiquetas de lo que llegó | casilla en *Llegó mercancía*; si falló la impresora, desde Buscar → Imprimir etiqueta |

## Nombres, no códigos (2026-09-18)

`nombres_empleadas_service.mostrar(texto, nombres=None, corto=False)`: donde se enseñe algo que pueda traer `VEND-1`/`ENC-1`, pásalo por aquí. `nombres_por_codigo(session)` carga y cachea (5 min) y deja copia local; llámalo una vez donde haya sesión (ya está en `refresh_all` del POS, el refresco de fondo del kiosko, el resumen de Telegram y los diálogos de corte/historial). `invalidar()` tras dar de alta o renombrar. Los códigos se siguen **guardando**: permisos (`== "VEND-1"`) y filtros no cambian. Tests: `test_nombres_empleadas_service`; en `conftest.py` la copia local se desvía a un temporal y la caché se limpia por test.

## Red — si el POS y el kiosko se van a modo local a la vez (2026-09-18)

Casi seguro la principal perdió la `192.168.0.10`. En CMD: `ipconfig | findstr IPv4` → si sale `169.254…`, otro aparato tomó la `.10` por DHCP y Windows tiró la fija. Encontrarlo en el ARRIS (192.168.0.1 → LAN → Lista de clientes) o la app Deco, desconectarlo, y en CMD **como administrador**: `netsh interface ip set address name="Wi-Fi" static 192.168.0.10 255.255.255.0 192.168.0.1`. Ya está **reservada la `.10`** en el ARRIS (DESKTOP-0DVVFV8); falta apartar `.9` (HP) y `.11` (DVR). El servidor va por **dongle Wi-Fi**: pendiente un cable.

## POS principal — qué se ve y qué no (2026-09-10)

> [!example] Pestañas
> **Se ven:** Resumen · Inventario · Bodega · Historial inventarios · Panel Uniformes · Analitica · Configuracion
> **Ocultas:** Caja · Presupuestos · Apartados · Catalogo — su trabajo se mudó al kiosko. Para volver a ver una, quitar su nombre de `PESTANAS_MUDADAS_AL_KIOSKO` en `ui/main_window.py`.
> Con la caja fuera ya no sale "Caja pendiente de corte" al abrir, ni el botón Corte, ni el recordatorio de las 5. Interruptor: `caja_en_el_pos()`.

> [!example] Analítica — qué mira cada bloque
> **Ventas reales (Libreta del kiosko)** y **Lo que se perdió** leen datos vivos. La "Vista general" de abajo lee `venta`/`apartado`, tablas muertas desde abril. Ver [[12 - Servicios - Analítica e Historia]] · [[35 - Demanda No Atendida]].

> [!warning] Interruptores que hay que recordar
> `EXISTENCIA_CONFIABLE` en `services/demanda_service.py` — **apagado**. Prender solo cuando la venta descuente stock **y** esté contado lo que se mueve. Ver [[07 - Servicios - Catálogo e Inventario]].

## Conteos en el kiosko (2026-09-10)

> [!example] Flujo
> Conteos → gafete → **1** Imprimir la hoja (elige escuela y luego **carta** en la HP o **tira** en la de tickets) · **2** contar en el piso · **3** Capturar. Se puede dejar a medias ("Guardar y seguir después"); solo quien la abrió (o `VEND-1`) puede seguirla. **Nada toca el inventario** hasta que Daniel pasa su gafete y, en "Por revisar", **Aplica** o **Descarta**. Ver [[36 - Conteos por Jornada]].

## Libreta (2026-09)

> [!example] Accesos
> Empleada: su gafete → piezas/comisiones sin dinero · Dueño: gafete `VEND-1` → todo con montos + corte con conteo + Pendientes + Pagos + Equipo + Retiro + Caja y nómina + Ver momento · Encargado: gafete `ENC-1` (León) → resumen del día (descansos/pagos), apuntar falta/descanso/vino a trabajar, ver cortes, **Hacer corte** (un botón), Saqué dinero

### PWA móvil (2026-09-05)
- Servidor de prueba en la Mac: `pos_uniformes/.venv/bin/python -m uvicorn pos_uniformes.api.main:app --host 0.0.0.0 --port 8000` → celular `http://<ip-mac>:8000/app/`
- PIN Daniel (VEND-1): `634700` · León (ENC-1): `1234` temporal · empleadas: pendiente asignar
- Abrir el satélite en la Mac: `pos_uniformes/.venv/bin/python pos_uniformes/presupuestos_satelite_main.py` (desde la raíz del repo)

### Scripts nuevos (2026-09-04)
- `scripts\instalar_kiosko_aqui.bat` — instala el kiosko completo en cualquier PC (un comando)
- `scripts\forzar_update_satelite.bat` — mata al satélite atorado y actualiza
- `python -m pos_uniformes.scripts.recalcular_comisiones_libreta [--aplicar] [--desde AAAA-MM-DD]` — recalcula comisiones ya anotadas con la regla vigente (2026-09-06; vista previa por defecto)
- `scripts\servidor_pwa_tienda.bat` — PWA en la principal (http://192.168.0.10:8000)
- `scripts\servidor_pwa_casa.bat` + `enviar_snapshot_casa.bat` + `programar_snapshot_casa.bat` — servidor 24/7 en casa ([[31 - PWA Libreta Móvil]])
> Comisión terminal: **4.5%** · Comisiones: 3pz=2 (desde 2026-09-06), resto 1/unidad · Abonos: registran, no comisionan

---

## Rutas en producción

| Qué | Ruta |
|-----|------|
| PC principal — repo | `C:\Users\Pc\pos_uniformes\pos_uniformes` |
| PC satélite — bundle actual | `%LOCALAPPDATA%\PresupuestosSatelite\app\` (auto-update; antes era carpeta en Escritorio) |
| PC satélite — env | `[bundle]\pos_uniformes.env` |
| PC satélite — cache catálogo | `[bundle]\data\catalog_cache.json` |

## Estructura del repo (desde reorg 2026-08-02)

| Qué | Dónde |
|-----|-------|
| Proyectos activos | `pos_uniformes/`, `Gestor_de_Inventarios/`, `pwa/`, `mapa_tienda/`, `libro_mayor/`, `cien_mexicanos/` |
| Lanzador API+PWA | `dev.sh` (raíz) |
| Huérfanos/duplicados archivados | `_archivo/` (con README que explica cada cosa) |
| Tarifarios: regenerar | `cd Gestor_de_Inventarios && python3 generar_tarifario_escuelas_db.py && python3 generar_indices_tarifario.py` (en ese orden) |
| Ya NO se versionan | logs del Gestor, zips, exe, `ownership-map-out*`, respaldos `.sql`, `pos.db` (`productos.db` SÍ sigue versionado) |

---

## Comandos frecuentes

### Mac — desarrollo
- **Pruebas:** mientras construyes, solo el archivo que tocas o `--fast` (~4 s). Antes de subir, TODO en paralelo: `pos_uniformes/.venv/bin/python -m pytest pos_uniformes/tests -q -n 6 --dist load` (~28 s). Ver [[18 - Cobertura de Tests]].
```bash
cd "Playground 2"
# Ciclo diario: solo tests puros (~4 s, sin Qt ni base)
pos_uniformes/.venv/bin/python -m pytest pos_uniformes/tests --fast -q
# Suite completa (~70 s; usa la base local pos_uniformes_test en 127.0.0.1, nunca producción)
pos_uniformes/.venv/bin/python -m pytest pos_uniformes/tests -q
# Un archivo
pos_uniformes/.venv/bin/python -m pytest pos_uniformes/tests/test_nombre.py -q
# Migrar la base de pruebas local tras una migración nueva
cd pos_uniformes && POS_UNIFORMES_DB_HOST=127.0.0.1 POS_UNIFORMES_DB_NAME=pos_uniformes_test .venv/bin/alembic upgrade head
```
> Los scripts se corren desde la raíz: `pos_uniformes/.venv/bin/python -m pos_uniformes.scripts.<nombre>`.

### Mac → Windows (al regresar a la tienda)
```bash
# Empuja links de escuelas y productos/variantes nuevos a Windows
cd "Playground 2"
pos_uniformes/.venv/bin/python pos_uniformes/scripts/sync_catalog_to_windows.py

# Luego regenerar panel (ya desde Windows DB automáticamente)
pos_uniformes/.venv/bin/python pos_uniformes/scripts/generar_panel_uniformes.py
```

### Windows — build + instalar satélite (todo en uno)
```powershell
cd C:\Users\Pc\pos_uniformes\pos_uniformes
git pull origin main
.\.venv\Scripts\python.exe -m PyInstaller packaging\windows\presupuestos_satelite_windows.spec --noconfirm
# Verificar nombre de carpeta generada:
ls dist\
# Luego instalar (ajustar nombre si cambió):
.\scripts\setup_satelite.ps1 -TargetDir "C:\Users\Pc\pos_uniformes\pos_uniformes\dist\PresupuestosSatelite-2026.04.24" -DbHost "192.168.0.10" -DbPassword "1234" -AutoStart
```

> **Nota:** el spec está en `packaging\windows\`, no en `scripts\`.

### Windows — BUILD 2026.07.11 (despachador satélite, desde la rama)

> Rama `feat/despachador-satelite`. El POS (fuente) solo necesita pull; el satélite necesita rebuild del bundle.

```powershell
# ── PC PRINCIPAL: repo + migraciones + build del bundle ──
cd C:\Users\Pc\pos_uniformes\pos_uniformes
git fetch origin
git checkout feat/despachador-satelite
git pull origin feat/despachador-satelite

# Migraciones (crea tabla `trabajo`, columnas de reintento y trigger NOTIFY)
.\.venv\Scripts\python.exe -m alembic upgrade head

# Reconstruir bundle del satélite (sale PresupuestosSatelite-2026.07.11)
.\.venv\Scripts\python.exe -m PyInstaller packaging\windows\presupuestos_satelite_windows.spec --noconfirm
ls dist\
```
```powershell
# ── PC SATÉLITE: instalar el bundle copiado ──
.\scripts\setup_satelite.ps1 -TargetDir "C:\Users\Daniel\Desktop\PresupuestosSatelite-2026.07.11" -DbHost "192.168.0.10" -DbPassword "1234" -AutoStart
```

**Configurar tras instalar (menú admin = Ctrl+Shift+A en el satélite/kiosko):**
- **Satélite** (impresoras): 🖨 Impresoras → Modo = **Imprimir local**; Impresoras de etiquetas → Normal/Split/Continua = **Brother QL-800 RCT**, Label = **Brother QL-800 SQR**.
- **Principal (POS)**: Configuración → Negocio e impresión → **Enviar al satélite**.
- **Principal (kiosko/bundle)**: Ctrl+Shift+A → 🖨 Impresoras → **Enviar al satélite**.

**Atajos satélite:** Ctrl+Shift+Q (cola de trabajos) · Ctrl+Shift+P (tablero de pedidos).

**Ojo:** la cola vive en la Postgres de la principal. Si la principal está apagada, el satélite no recibe trabajos (es el hub). Guía de pruebas: `pos_uniformes/docs/PRUEBAS_DESPACHADOR_SATELITE.md`.

**Qué trae el bundle 2026.07.11:**
- Despachador POS/kiosko → satélite (tickets, etiquetas, conteo, tablero de pedidos).
- Impresora de etiqueta por tipo (Normal/Split → RCT, Label → SQR); elegir tipo al imprimir faltantes (Ctrl+S).
- Kiosko: papelera en "Piezas agregadas", paginación de escuelas y modelos, ocultos "Continua" y sección "Catálogo".
- **Calendario de conteos** (recordar conteos periódicos por escuela): banner en kiosko + orden que se imprime sola al vencer + calendario visual.

**Calendario de conteos — cómo se usa:**
- **En piso (kiosko):** pestaña **"Calendario"** (en la barra izquierda, tras Tarifarios) = calendario visual del mes con chips de resumen (requieren conteo / al día / este mes) + botón **"Imprimir orden de conteo"**. También sale un banner cuando hay vencidas.
- **Configurar frecuencia (solo admin):** POS → menú **"Mas"** → "Calendario de conteos", o satélite → **Ctrl+Shift+A** → pestaña **📋 Conteos** → "Abrir calendario". Ahí se ajusta `días vigencia` por escuela (tabla con pastillas de estado).
- **Subir conteo / registrar físico (solo admin satélite):** Ctrl+Shift+A → 📋 Conteos → **"Subir conteo"** → eliges escuela → cargas piezas → capturas el físico → "Registrar conteo" (mismo backend que el panel de uniformes; reinicia el ciclo del calendario solo).
- **Automático:** el satélite (modo LOCAL, online) revisa cada 6 h y encola sola la orden de las escuelas vencidas (candado anti-spam: no repite hasta que se registre el conteo).
- El ciclo se reinicia solo al registrar el conteo (con "Subir conteo" o el conteo físico del POS). Las escuelas nunca contadas no salen en el grid hasta su primer conteo; el chip "requieren conteo" y "Imprimir orden" las cubren mientras tanto.

### Windows — deploy módulo Bodega
```powershell
cd C:\Users\Pc\pos_uniformes\pos_uniformes
git pull origin main
.\.venv\Scripts\python.exe -m alembic upgrade head
# Verificar: .\.venv\Scripts\python.exe -m unittest pos_uniformes.tests.test_bodega_service -v
```

### Windows — tests
```powershell
py -m unittest discover -s pos_uniformes\tests -p "test_*.py"
```

---

## Versiones

| App | Bundle instalado | Código |
|-----|-----------------|--------|
| POS Principal | pull 2026-06-11 en PC tienda (pull pendiente) | rama `feat/despachador-satelite` (`b6f7dc1`, 2026-07-12) — solo pull en la principal |
| App Satélite | `2026.06.11` (build `2026.07.11` **pendiente**) | rama `feat/despachador-satelite` `2026.07.11` — despachador + etiquetas por tipo + paginación + papelera + calendario de conteos (pestaña "Calendario", subir conteo, calendario visual) + fixes |

> **Rama activa:** `feat/despachador-satelite` (aún NO mergeada a `main`). Todo lo nuevo vive ahí. Al terminar de probar, mergear a `main`.

---

## Impresora de etiquetas

> [!tip] Brother QL-800
> Puede estar conectada a PC principal **o** PC satélite (cable disponible en ambas).
> El satélite la detecta automáticamente si está enchufada.

### Modos de impresión (diálogo de etiquetas)
| Modo | Rollo | Cómo imprime |
|------|-------|--------------|
| Normal | continuo | 1 etiqueta por pieza, vía driver Windows (GDI) |
| Split | continuo | 4 etiquetas por hoja, calcula hojas |
| Continua | continuo DK-22210 (29 mm) | 1 job por etiqueta, autocut |
| **Label** | **die-cut DK-1221 (23×23 mm)** | QR + nombre del producto, vía **brother_ql → spooler RAW** |

> [!warning] Label (DK-1221) — cómo funciona y requisitos
> - Imagen cuadrada **202×202 px** (área imprimible real del DK-1221).
> - Usa `brother_ql` para generar el raster nativo (incluye el comando de **autocut**)
>   y lo manda al **spooler de Windows en modo RAW** (`StartDocPrinter` datatype `"RAW"`).
>   Esto **evita el GDI/DEVMODE** (frágil con drivers Brother) y **no necesita libusb**.
> - Requiere en Windows: `pip install brother_ql` (ya instalado).
> - **El driver default es 29×90 mm (`DC03`/paper ID 370 es el de 23×23).** Si imprime
>   con el tamaño equivocado o se queja de "el rollo no coincide", el problema casi
>   siempre es **físico**: hay que cargar bien el rollo DK-1221 (23 mm, más angosto que
>   el 29 mm), guías ajustadas, y que el sensor lo detecte (status monitor debe decir 23×23).

---

## Ver también
- [[17 - App Satélite]] — arquitectura y roadmap
- [[20 - Pendientes y Fase 5]] — qué falta para cerrar la fase
- [[21 - Sesión de Trabajo]] — sesión activa

| Atajo | Dónde | Qué hace |
|-------|-------|----------|
| `Libreta → 🧾 Cortes` | Con tu gafete | **✏️ Ajustar la venta** (cambia lo que se reporta de un corte ya hecho) · **↩ Quitar el ajuste** · **🗑 Borrar corte** |
| `Ctrl+Shift+R` | Libreta del dueño e historial de cortes | Asoma lo **real**: lo que de verdad se vendió, sin tus ajustes. Lo normal son las cifras **oficiales** (con ajustes) y no llevan ninguna marca. Se repite para volver |

## Catálogo: uniformes y recetas (fases 2/3, 2026-09-21)

```bash
# en la principal, después de actualizar (migraciones 1c2d3e4f5a6b y 2d3e4f5a6b7c)
python -m pos_uniformes.scripts.armar_uniformes            # dry-run: qué uniforme se arma por escuela
python -m pos_uniformes.scripts.armar_uniformes --aplicar
python -m pos_uniformes.scripts.crear_piezas_faltantes     # dry-run: pants sueltos / playeras que faltan
python -m pos_uniformes.scripts.crear_piezas_faltantes --aplicar
python -m pos_uniformes.scripts.armar_recetas              # dry-run: de qué se arma cada 3pz / chamarra
python -m pos_uniformes.scripts.armar_recetas --aplicar    # guarda recetas y reescribe el stock de 3pz/chamarra
```
Luego en el POS: **Más → Uniformes por escuela** (generales, grupo, opcional, color, "Se arma de"). Ver [[38 - Catálogo Fase 2 - Uniformes]].
