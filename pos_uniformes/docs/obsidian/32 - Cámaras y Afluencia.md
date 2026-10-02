---
tags: [pos-uniformes, camaras, dvr, afluencia, satelite]
---

# Cámaras (DVR) y Afluencia (2026-09-08)

> [!success] Qué es
> El DVR Dahua de la tienda entrega video por RTSP en la red local. El kiosko lo reproduce sin dependencias nuevas (QtMultimedia trae ffmpeg dentro de PyQt6 6.10), la Libreta abre la grabación de cualquier movimiento ("Ver momento") y un proceso aparte en la PC servidor cuenta personas que entran con YOLO para sacar la conversión por hora.

## Red y DVR

| Dato | Valor |
|------|-------|
| DVR | Dahua HCVR (OEM "浩云安防"), por cable al Deco, **IP fija `192.168.0.11`** (configurada en el propio DVR), MAC `4c:11:bf:7b:1e:89` |
| Puertos | 80/443 web · 554 RTSP · 37777 app (DMSS, tipo XVR, P2P SN `2J02AFBPAGQ1B47`) |
| Usuario para el POS | **`dany`** (grupo admin). El `admin` tiene otra contraseña; `888888` es solo login local |
| Reloj | NTP `time.windows.com`, zona **GMT-6, sin DST** (venía GMT+6 y 2001) |
| Canales | 1 VESTIDOR · 2 CAJA · 3 ENTRADA2.2 · 4 ENTRADA1 · 5 ENTRADA1.1 · 6 ENTRADA2 · 7 MOSTRADOR2 · 8 MOSTRADOR1 |
| Streams | principal 960×1080 @15 fps 1.5 Mbps · substream 352×240 @7 fps 160 kbps |
| RTSP | `rtsp://dany:PASS@192.168.0.11:554/cam/realmonitor?channel=N&subtype=0|1` · grabación: `cam/playback?channel=N&subtype=0&starttime=AAAA_MM_DD_HH_MM_SS&endtime=…` (hora local del DVR; QMediaPlayer reporta duración y permite seek) |
| Impresora HP Smart Tank 750 | reconectada al Deco: `HP644ED72F27FC.local`, IP DHCP `192.168.0.9`. Sin pantalla táctil ni Ethernet: para cambiar de WiFi, ⓘ 5 s → Wi-Fi+Cancelar 5 s (parpadea) y configurar por HP Smart o por su red DIRECT-xx en `http://192.168.223.1` |

## Reglas de acceso (decisión de Daniel)

- **Empleadas**: solo las cámaras marcadas como *entrada* (canales 3, 4, 5, 6).
- **Administrador** (PIN `634700`): todas. Al cerrar el visor se olvida el modo admin (el vestidor no queda a la vista en el mostrador).
- El dueño en la Libreta (gafete VEND-1) abre "Ver momento" ya en modo admin, en CAJA.

## Visor en el kiosko

- Botón **Cámaras** al final del menú lateral (no cambia de página) o **Ctrl+Shift+C** → `CameraWallDialog` (no modal). Mosaico en substream; doble clic amplía una cámara con el stream principal; Esc regresa; "Sin señal · reintentando" cada 5 s.
- **Administración (Ctrl+Shift+A) → pestaña 📹 Cámaras**: IP, usuario, contraseña, puertos, **Detectar canales** (API CGI `configManager.cgi?name=ChannelTitle`, digest) y casillas de entrada. Se guarda por máquina en `data/dvr_settings.json` (en el exe: `%APPDATA%\PresupuestosSatelite\data\`), gitignored porque lleva la contraseña; defaults por env `POS_UNIFORMES_DVR_HOST/_USER/_PASSWORD`. Ojo: el texto gris de los campos es ejemplo, hay que teclear la IP.
- **Ver momento** (Libreta): botón 📹 en las acciones del dueño y en el detalle de cada operación (también empleada, solo entradas). `CameraPlaybackDialog`: clip desde 1 min antes hasta 2 min después del `created_at` (UTC → local naive), pausa, barra, reloj de la grabación, saltos ±1 min. El DVR sobreescribe a las semanas: movimientos viejos pueden ya no tener video.

## Afluencia (personas que entran)

Proceso aparte en la PC servidor, **con su propio venv** (YOLO y OpenCV no entran al exe del kiosko): `pos_uniformes/afluencia/`.

- `conteo.py` — lógica pura (`Linea`, `ContadorLinea`, `ContadorPaso`, `AcumuladorHora`), probada en la suite del POS.
- `contador_afluencia.py` — un hilo por cámara sobre el **stream principal** (el substream casi no detecta), YOLOv8n + ByteTrack, imgsz 416, 4 fps. Modo `linea` (cruces de la línea de la puerta: entra/sale) para **ENTRADA1.1 (canal 5)** y **ENTRADA2.2 (canal 3)** que miran hacia adentro; modo `paso` (personas distintas vistas) para **ENTRADA1 (4)** y **ENTRADA2 (6)** que miran a la banqueta. Upsert aditivo cada minuto en `afluencia_hora`. `--calibrar` deja un cuadro por cámara con cuadrícula 0.1 y la línea en rojo; `--sin-db --duracion N --debug-frames DIR` para probar.
- Líneas vigentes (`afluencia.json.example`): ENTRADA1.1 `[0.30, 0.62, 0.62, 0.62]` horizontal; ENTRADA2.2 **`[0.5, 0.6, 0.7, 0.8]`** cruzando el pasillo entre el exhibidor redondo y la ropa roja (2026-09-13: la anterior `[0.58, 0.38, 0.92, 0.50]` iba sobre el piso claro de la banqueta y contaba a quien pasaba por fuera); `lado_dentro: abajo` (la calle queda arriba-derecha).
- **Daniel dibuja las líneas con el ratón (2026-09-13):** `afluencia\dibujar_lineas.bat` toma un cuadro fresco de cada cámara (`--calibrar` deja también `calibracion/cuadros/*.jpg` limpios) y abre `dibujar_lineas.py` (PyQt6, con el venv del POS): clic donde empieza, clic donde termina, "la tienda queda: arriba/abajo/izquierda/derecha" pintado en **verde**, Guardar → escribe `afluencia.json`. Los extremos se arrastran. **El contador vigila el mtime del archivo y cambia la línea en caliente** (`aplicar_cambios`, ~3 s; probado contra el DVR real); cámara nueva o cambio de canal siguen pidiendo reinicio y lo dicen en el log. `afluencia.json` es la verdad en el servidor; el ejemplo solo sirve la primera vez (el instalador ya no lo pisa).
- **Se ve por qué falla (2026-09-13):** log rotativo en `logs\afluencia.log`; `afluencia\diagnostico_afluencia.bat` (6 revisiones → `reportes\afluencia.txt`, luego `scripts\enviar_reporte.bat`). El instalador crea la tarea **oculta** vía `correr_oculto.vbs`, baja el contador que corría y lo arranca de nuevo; `INFRA_VERSION 5` la mantiene en la postactualización si existe `afluencia\.venv`. Verificado desde la Mac contra las 4 cámaras: streams abren, detecta y cuenta "pasan"; la tabla de producción estaba vacía solo porque el servidor no lo corría.
- Validado en la Mac: ~37 ms por inferencia (M-series), un "sale" real detectado en ENTRADA1.1; en la PC servidor será más lento (si estorba: 2 fps o quitar las de banqueta).
- **Instalar (una vez)**: `afluencia\instalar_afluencia.bat` → venv, requirements (ultralytics, lap, opencv-headless, psycopg), config, calibración, tarea "POS Afluencia" al iniciar sesión y arranca `contador_afluencia.bat`. **Desde 2026-09-15 lo corre sola la actualización** (paso único `instalar_afluencia` en `postactualizacion.py`) y al terminar abre la ventana de dibujar líneas; necesita `data\dvr_settings.json` en esa PC para la calibración, si no queda PENDIENTE y se reintenta. Ver [[29 - Updates y Mensajería]].
- **Libreta del dueño → sección AFLUENCIA**: hora · entran · pasan por fuera · ventas · conversión (`services/afluencia_service.py` cruza `afluencia_hora` con ventas+apartados de la Libreta). Oculta si no hay datos. Va también en el resumen de Telegram.

## Infraestructura

| Pieza | Archivo |
|-------|---------|
| Config DVR | `services/dvr_settings_cache_service.py` (rtsp_url, playback_url, canal_por_nombre, detectar_canales) |
| Visor / playback | `ui/dialogs/camera_wall_dialog.py` · `ui/dialogs/camera_playback_dialog.py` |
| Kiosko | `_open_camera_wall`, `_ver_momento_libreta` en `ui/quote_satellite_window.py`; pestaña en `satellite_admin_dialog.py` |
| Afluencia | `afluencia/` + `services/afluencia_service.py` + migración `s2a3b4c5d6e7` (`afluencia_hora`) |
| Empaquetado | `PyQt6.QtMultimedia`, `QtMultimediaWidgets` y los módulos nuevos en `hiddenimports` del spec |
| Tests | `test_dvr_settings_cache_service`, `test_camera_wall_dialog`, `test_camera_playback_dialog`, `test_libreta_ver_momento`, `test_afluencia_conteo` (incluye la línea calibrada por Daniel), `test_afluencia_dibujar_lineas` (sombra, clics, guardar, recarga en caliente), `test_afluencia_service`, `test_libreta_afluencia` |

## Pendiente

- Probar el video en el exe de Windows (el spec ya incluye QtMultimedia; si no reproduce, revisar que PyInstaller copie los plugins `multimedia` de Qt).
- ~~Instalar el contador en la PC servidor~~ (lo hace la próxima actualización sola); dibujar la línea de ENTRADA2.2 en la ventana que se abre al final y validar con gente entrando (`logs\afluencia.log` debe traer entra/sale).
- Ideas que Daniel dejó pensando: foto de CAJA por venta (para cuando el DVR ya borró), alertas fuera de horario con el detector, vestidor con tiempo, Frigate en una mini PC + Coral si quiere vigilancia completa (la MacBook Air 2017 con Linux sirve).

Relacionado: [[28 - Libreta Digital]] · [[34 - Telegram y Resumen Diario]] · [[22 - Referencia Rápida]]
