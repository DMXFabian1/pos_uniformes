---
tags: [pos-uniformes, pwa, movil, servidor]
---

# PWA Libreta Móvil (2026-09-04)

> [!success] Fase 2: Contar y Bodega (2026-09-13)
> **📦 Bodega** (solo el dueño, en la tienda): *Llegó mercancía* (entra al piso; "Guardar parte en una caja" destapa la columna A caja) *Pasar al piso*, *Corregir caja* (recuento) y **📜 Lo que ha llegado** (último mes por día + nota + quién; 18/09). *Llegó mercancía* imprime **una etiqueta por pieza** si se marca la casilla (solo en tienda); "Sin color"/"Único" no se enseñan junto a la talla (`colorVisible`); 19/09: **👥 Asistencia** en el inicio del dueño (mismo flujo del encargado: `encSub`/`encMenu` pintan en `dueno-sub` cuando `rolActual === "dueno"`), marcas recientes con *Quitar* y *Sí vino*; 20/09: **🗺 Mapa de conteos** en el inicio del dueño. Cache `maximoda-v25` (17/09: básicos por prenda; 18/09: pestañas, buscador y grupos en Contar, y la hoja de captura otra vez visible; la ficha en proceso dice si ya se imprimió la hoja; Bodega → Llegó mercancía con las reglas de la hoja: `bodega_movil_service.buscar_prendas` excluye `_TIPOS_VIRTUALES` (Pants 3pz, Chamarra), ordena por `_PIEZA_ORDER` y tallas con `_talla_sort_key`, y devuelve `tipo_pieza`). Ver [[37 - Revisar y Pedidos]].
>
> Botón **Contar** en la nav para todos. Es **la misma hojita, sin papel**: la hoja completa de la escuela (o prenda básica), una tarjeta por prenda numerada N/total igual que en papel y en el kiosko, con Talla y "Cuántas hay" (sin Pedido: eso lo gestiona Daniel) y teclado numérico. Cada prenda se guarda sola (al dejar de teclear); si falla el WiFi queda en el teléfono y se reintenta. Corregir actualiza (no duplica); vacío = no la conté. "Dejar para después" → aparece en *A medias* con Seguir; "Terminar conteo" → queda para la revisión de Daniel en el kiosko ([[36 - Conteos por Jornada]]). No viaja el stock del sistema; nada toca el inventario.
> API: `api/routers/conteos_movil.py` — GET/POST `/api/v1/movil/conteos`, GET `/{id}`, POST `/{id}/tallas`, POST `/{id}/terminar`; JWT + candado *solo en tienda*. Servicio: `guardar_tallas`, `hoja_de_jornada`. Service worker en `maximoda-v5`.
> Pendiente: revisión de Daniel desde el celular; escáner (requiere HTTPS).

> App instalable para los celulares de Daniel, León y las empleadas. **Nueva y desde cero**
> (la PWA React de 2026-05 quedó descartada). Visión: llevar la experiencia completa del
> kiosko al teléfono, por fases.

## Arquitectura: dos servidores, una app

Daniel apaga las PCs de la tienda en la noche → la PWA vive en dos lugares:

| | Modo **TIENDA** | Modo **CASA** |
|---|---|---|
| Dónde | PC principal (`scripts/servidor_pwa_tienda.bat`, puerto 8000) | PC siempre prendida en casa (`scripts/servidor_pwa_casa.bat`) |
| Datos | Base Postgres **viva** | **Snapshot SQLite** que la tienda manda cada 15 min |
| Acceso | Celulares en el WiFi del Deco → `http://192.168.0.10:8000` | Celulares por **Tailscale** |
| Puede | Todo: consulta + **encolar etiquetas** | Solo consulta (24/7, datos del último snapshot) |

El modo se deriva solo del backend del engine (`sqlite` = casa). Snapshot: `scripts/exportar_snapshot_movil.py` (12 tablas: libreta, calendario, cortes, **catálogo completo**; ventas 120 días; swap atómico) + `enviar_snapshot_casa.bat` (SMB sobre Tailscale, IP editable) + `programar_snapshot_casa.bat` (schtasks 15 min). Override de conexión: `POS_UNIFORMES_DB_URL=sqlite:///...` (agregado en `utils/config.py`).

## Qué hace ya (Fases 1 + B + C — hechas y verificadas en navegador)

- **Login**: lista de empleadas + PIN (JWT de la API existente `api/`; valida `Empleada.pin_hash`).
- **Empleada**: banner (comisiones desde último pago, siguiente descanso, próximo pago) + calendario navegable.
- **León**: cortes — fecha y cifra, nada más.
- **Dueño**: VENTA DE HOY, ranking del día, ciclos por empleada, últimos cortes.
- **🔍 Buscar precio** (todos): búsqueda por nombre (families), **escáner de cámara** (html5-qrcode vendorizada — Android e iPhone), tarjeta con precio grande y stock.
- **🏷 Imprimir etiqueta** (solo modo tienda): `POST /movil/etiqueta` → `render_inventory_label` → cola `trabajo` → la imprime el **despachador del satélite** en la Brother.

## Infraestructura

| Pieza | Archivo |
|-------|---------|
| Frontend | `pwa/` (index.html único, manifest, sw, iconos, html5-qrcode) servido en `/app` |
| API | `api/routers/movil.py` (`/inicio` por rol, `/calendario`, `/etiqueta`) + routers existentes (`auth`, `catalog/sku/{sku}`, `search`) |
| Tests | `tests/test_api_movil.py` (TestClient + SQLite StaticPool; snapshot round-trip; etiqueta tienda/casa) |

## Probada en vivo (2026-09-05)

Servida desde la Mac contra la base REAL (`uvicorn pos_uniformes.api.main:app --host 0.0.0.0 --port 8000`, lanzado por Bash — el proceso del preview de Claude no tiene permiso de Red local en la Mac y da "No route to host"). Celular en el WiFi: `http://192.168.0.8:8000/app/`. Vistas verificadas con datos vivos: dueño (venta del día, ranking, ciclos), Stayce (empleada), León (encargado).

- **Jalar para actualizar** (pull-to-refresh nativo) en las vistas de inicio; "falta 1 día" en singular.
- **Modo encargado completo** = espejo del kiosko: Apuntar falta o descanso (¿de quién? → ¿qué pasó? → hoy/mañana/otro día, con "Me equivoqué"), Ver cortes, **Hacer corte de hoy** (cifra calculada sin editar; el ticket se ENCOLA a la impresora de la tienda vía cola `trabajo`), quién descansa en 7 días. Acciones solo en modo tienda; endpoints `/movil/encargado/*` protegidos a dueño/encargado (403).
- **PINes**: VEND-1 = `634700` (el admin de siempre ya estaba); ENC-1 = `1234` temporal; Stayce (VEND-4) tiene un PIN viejo desconocido — para abrir su vista se le fabricó un token (`TokenService.create_token`) sin tocarle el PIN. Las demás sin PIN.
- **Limitación conocida**: la cámara 📷 no abre en el celular por HTTP simple (los navegadores exigen HTTPS) — solución: HTTPS vía Tailscale (`tailscale serve`) en la versión definitiva.

## Decisiones

- Teléfonos **mezcla Android/iPhone** → librería de escáner (no BarcodeDetector nativo).
- Red: teléfonos en el **WiFi principal del Deco** (modo AP no da VLANs; invitados aísla la LAN).
- Servidor de casa: arrancar con el **Ryzen 5600** (~$50–130 MXN/mes de luz); candidata **mini PC N100** (~$15/mes) — y si entra IA local, **Mac mini M4 16GB**. Decisión pendiente de definir el caso de IA.

## Pendiente para estrenar

1. Tailscale en PC de casa + celulares · repo+venv en PC casa · compartir `C:\pos_movil` · IP en `enviar_snapshot_casa.bat`.
2. **PINes de las empleadas** (hoy no tienen — `EmployeeIdentityService.set_pin`; falta script de alta).
3. Fases futuras: **D** venta rápida móvil (carrito + ticket a cola + Libreta) · **E** conteos desde el teléfono · acciones de calendario desde el celular (pedir/intercambiar fuera de la tienda).

## Encargado v2 (2026-09-08)

- `/encargado` devuelve además `resumen` (descansa hoy/mañana, pagos de la semana) y `pagos`; el menú muestra la tarjeta "📌 Hoy".
- **Hacer corte** ya es de un botón: `GET /encargado/corte_hoy` (venta, pagos de hoy, retiros apuntados, lo que se saca) y `POST /encargado/corte` sin cuerpo → `cerrar_corte_automatico` + ticket del encargado a la cola de la tienda. Respuesta: venta, pagos, retiro, reactivo.
- **💸 Saqué dinero del cajón**: `POST /encargado/retiro {monto, motivo}` con chips de motivo.
- Endpoints de pago (`/encargado/pago_pendiente/{code}`, `/encargado/pagar`) existen pero el botón se quitó del menú (León ya no paga a mano; el corte lo hace). Tests en `test_api_movil.py` (15).

Relacionado: [[28 - Libreta Digital]] · [[30 - Calendario de Empleadas]] · [[29 - Updates y Mensajería]] · [[33 - Caja, Nómina y Corte Automático]]

## Fase D — el celular al día con el kiosko (2026-09-09/10)

### Empleada
Tarjetas del ciclo (⭐ comisiones desde su último pago · 💵 próximo pago · 🛌 siguiente descanso) y **"Tus movimientos"** en lenguaje simple, sin montos. El texto sale del **mismo lugar** que el kiosko: `services/libreta_presentacion_service.py` (puro, sin Qt ni base) con `tiles_ciclo(datos)` y `texto_movimiento(row, con_dia=False)` — así el celular y la pantalla dicen exactamente lo mismo. En la API, `_movimientos_empleada` toma desde su último pago pero **nunca esconde lo de hoy** (tope 50).

### Encargado
Espejo del menú del kiosko: tarjetas de descansa hoy/mañana (nombre de pila) y pagos **una línea por persona** con la fecha en español (`nomina_service.cuando_pago`, marca `urgente` si es HOY o ATRASADO). "Hacer corte" primero y en acento. Los cortes traen periodo, lo retirado y el fondo que quedó; los viejos muestran "—" (`historial_cortes_service.es_legacy`).

### Dueño
Solo dinero real: **EN EL CAJÓN · CON TARJETA (neto 4.5%) · ABONOS · COMISIONES** + ranking del día, igual que la Libreta. Nada de "vendido en total" (un apartado no es dinero recibido).

**🧾 Tu corte desde el celular** (solo VEND-1 y solo conectado a la tienda): muestra el periodo y lo que debe haber, él cuenta el cajón, captura su cifra (la oficial), el fondo que se queda y otros retiros; el ticket se **encola a la impresora de la tienda**. Valida que el fondo no exceda lo contado. Endpoints nuevos: `GET /dueno/corte_estado` y `POST /dueno/corte` (guards `_solo_dueno` + `_solo_tienda`). La casilla **Ocultar los cobros con tarjeta** llega como la dejó la última vez, aquí o en el kiosko (`caja_parametros.ocultar_tarjeta`, 2026-09-10).

### La PWA se levanta sola (2026-09-09)
`scripts/servidor_pwa_vigia.py/.bat`: si `/health` no contesta, mata lo pegado y levanta uvicorn sin ventana (`data/servidor_pwa.pid`). Desde el 2026-09-10 quien lo vigila es el **supervisor único** ([[34 - Telegram y Resumen Diario]]); `instalar_servidor_pwa.bat` delega en él. Puerto por `POS_PWA_PUERTO` (8000).

### Endpoints hoy (`/api/v1/movil`)
`GET /inicio` · `GET /calendario` · `POST /etiqueta` · `GET /encargado` · `POST /encargado/marcar` · `GET /encargado/corte_hoy` · `POST /encargado/corte` · `GET /encargado/pago_pendiente/{code}` · `POST /encargado/pagar` · `POST /encargado/retiro` · `GET /dueno/corte_estado` · `POST /dueno/corte`.

### Vistas de `pwa/index.html`
`#vista-login` · `#vista-empleada` (ciclo, movimientos, calendario con leyenda Descanso/Falta/Pago) · `#vista-encargado` (menú + subflujos) · `#vista-dueno` (dinero, ranking, ciclos, cortes, corte) · `#vista-buscar` (precio, escáner, etiqueta) + `#nav`.

Tests: `test_api_movil` (corte del dueño ×3, privados, payloads de encargado/dueño, ciclo y movimientos), `test_servidor_pwa_vigia`.

## Probarla desde la Mac (2026-09-18)

Los paneles de navegador de Claude no sirven en esta sesión (conflicto de nombre del MCP), así que:
- **Servidor de pruebas:** `POS_UNIFORMES_DB_HOST=localhost POS_UNIFORMES_DB_NAME=pos_uniformes python -m uvicorn pos_uniformes.api.main:app --host 0.0.0.0 --port 8765` desde `Playground 2` → el celular entra por `http://192.168.0.4:8765/app` (misma Wi-Fi; PIN real; en la copia local Daniel tiene **1234**, puesto ese día solo ahí). Es la copia de la Mac: catálogo y escuelas reales, sin ventas.
- **Capturas:** `scratchpad/pwa_shot.py salida.png "irContar()" [js…] [full]` (Playwright + Brave, 390×844, hace login con el PIN de prueba y corre cada JS antes de la captura).

## Navegación (2026-09-18)

- **Barra superior** `#topbar`: `‹ Atrás` (solo si hay pila), título (el `<h1>` visible), `↻` (`navActualizar`: re-pinta la pantalla actual; en Inicio = `cargarInicio`, en la hoja = vuelve a pedir la jornada), `⋯` (`navMenu`: hoja con quién / modo / `PWA_VERSION`, actualizar, *traer la última versión* = `navReinstalar` borra `caches` + desregistra el SW + `reload`, cerrar sesión). `body.con-topbar` da el padding.
- **Pila** `navPila` de `{nombre, args}`: las funciones de `NAV_PANTALLAS` se envuelven al final del script (`window[nombre] = wrapper`) y al llamarse hacen `navApilar` → `history.pushState({i})`; las raíces (`pintarEmpleada/Encargado/Dueno`, `irBuscar`, `contCargarLista`) reinician la pila con `replaceState`; `encMenu`/`duenoMenu` colapsan a la raíz. `popstate` recorta la pila y re-pinta con `navRestaurando=true` (no vuelve a apilar). Las de `NAV_ACCIONES` (guardar/marcar/cobrar) no se apilan y al terminar dejan la pila en la raíz. `test_pwa_index_html.NavegacionTests` vigila que ambas listas existan y no se crucen.
- **Jalar para actualizar** en cualquier pantalla logueada salvo la hoja de captura; llama `navActualizar`.
- **Bodega:** `POST /movil/bodega/llego` acepta `imprimir_etiquetas` → `_encolar_etiquetas` (una `trabajo` etiqueta por talla con `copies` = piezas, `origen="pwa"`); `GET /movil/bodega/llegadas` → `bodega_movil_service.llegadas_recientes` (ENTRADA_COMPRA con observación "Llegó:…", agrupado por día+nota+quién, tallas ordenadas).
