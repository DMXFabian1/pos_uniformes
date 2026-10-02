---
tags: [sesion, pos-uniformes]
---

# Sesión de Trabajo — Activa

> Cuando la sesión cierre, mover el contenido a [[21 - Historial de Sesiones]] y dejar esta nota limpia.

---

## Próxima sesión

> [!tip] Para arrancar
> Abrir esta nota primero. Todo lo que necesitas está aquí y en [[22 - Referencia Rápida]].

### Estado al 2026-09-21

```
Rama:  chore/reorganizacion-repo @ c2f5b764 (pusheada a GitHub)
Tests: completa 2,475 en verde (~38 s con -n 6) · tres corridas limpias tras desactivar dos bombas de Qt
Base:  producción en 4f5a6b7c8d9e (al día) · catálogo fases 2/2b/3 aplicadas en la tienda el 22/09
```

> [!check] Lo de hoy (2026-09-22), todo en GitHub y listo para la tienda
> Se toma con el **icono de POS Uniformes** (ya republica a los kioskos solo). Lleva dos migraciones que entran solas: `5a6b7c8d9e0f` (la Licra) y las de las recetas.
> - **Catálogo aplicado en la tienda**: 52 uniformes, 16 productos nuevos, 114/114 recetas, stock de 3pz y chamarras calculado; los conjuntos ya no inflan los totales (16,366 piezas, no 19,534).
> - **Conteos rediseñado**: la pantalla se acomoda a quién entra (las chicas ven lo suyo; tú, lo que espera revisión), abre en 31 ms en vez de 3.2 s congelada, y sin scroll horizontal.
> - **📊 Historial de conteos** (tuyo): todos los conteos de cada escuela, comparar con el anterior, decidir pedidos y sacar la hoja — sin entrar a Revisar.
> - **Lo que falta contar se mide talla por talla**: lo que se cerró a medias vuelve a aparecer ("faltan 36 de 42 tallas") y su hoja sale solo con lo que falta. En la tienda: 32 pendientes, 26 a medio contar.
> - La **Licra** ya no sale como "Sin tipo" en el mapa.

> [!check] Catálogo, fase 2 — base lista, nada en producción (2026-09-21)
> Ver [[38 - Catálogo Fase 2 - Uniformes]]: `uniforme` + `uniforme_pieza`, `services/uniforme_service.py`, `scripts/armar_uniformes.py` (dry-run / `--aplicar`), POS **Más → Uniformes por escuela**. Probado en la Mac sobre una copia de producción del 21/09. Cuando Daniel lo vea y diga: `actualizar_pc_principal.bat` → en la principal `python -m pos_uniformes.scripts.armar_uniformes` (leer) → `--aplicar` → completar en el POS lo que la base no sabe (qué generales usa cada escuela, opcionales, colores). **2b ya hecha** (hoja/mapa, tarifario y guiado leen del uniforme si la escuela lo tiene armado; si no, como siempre); al final, con todas las escuelas armadas, retirar las ligas. **Conteos rediseñado y optimizado** (22/09, `caac66da` + `2d670a3d`): la sección se acomoda a quién entra y abre en 31 ms (antes 3.2 s congelada) — ver [[36 - Conteos por Jornada]]. Falta la misma mano en **Contar** del celular. **Fase 3 hecha** (`1e3a53ef`): receta de 3pz/chamarra, la venta mueve las piezas, stock calculado; `crear_piezas_faltantes` + `armar_recetas`: **114/114 recetas** sin nada pendiente (22/09: se crean los 15 pants sueltos y la playera de Vicente Guerrero; el 3pz del SABES lleva playera de hombre o de mujer). Pasos para la tienda en la nota 38 §4. **Fase 3 ya decidida** (misma nota, §5b): 3pz y Chamarra artificiales — vender 3pz baja 2pz + playera; vender chamarra baja un 2pz y deja un suelto; stock calculado.


> [!check] Actualizar la PC principal — trae todo del 13 al 20, y **ya no hay nada que correr a mano**
> **Lo del 17 y 18 encima de lo de abajo:** rendimiento (kiosko: flujo guiado, banner en hilo, tarifarios, escaneo cache-primero; POS: buscador con caché, 1.9 → 1.2 s al abrir; Conteos ~85 → ~10 consultas), índices `ef5a6b7c8d9e`, hojas impresas `f06b7c8d9e0f` y en_cajon `0b1c2d3e4f5a` (cuarta a sexta migración), celular con básicos por prenda y Contar con pestañas/buscador/grupos y la hoja de captura arreglada; **imprimir la hoja abre la jornada**, Llegó mercancía con las reglas de la hoja, barra superior con Atrás/Actualizar/Menú, etiquetas al llegar y 'Lo que ha llegado', sin 'Sin color' junto a las tallas; corte con desglose de pagos/retiros; asistencia con Quitar en el celular (cache v23) y **nombres en vez de códigos** en todos lados.
> Una sola actualización (`actualizar_pc_principal.bat`, va a tardar más de lo normal): migraciones `bc2d3e4f5a6b` (pedido en conteo), `cd3e4f5a6b7c` (stock puede ser negativo) y `de4f5a6b7c8d` (prenda en la jornada) se aplican solas; el corte ofrece los pagos de hoy; la venta ya descuenta stock; `INFRA_VERSION 6`; iconos originales (M y átomo) en 7 tamaños; PWA cache v25 (recargar dos veces en el celular; desde ahí, ⋯ → Traer la última versión). Al final corren solos los **pasos de una sola vez** (`--pasos-unicos`, ver [[29 - Updates y Mensajería]]): **Meilisearch a S4U** (sin ventana negra), **`descontar_ventas_pasadas --aplicar`** (lo que imprimió queda en `logs\descontar_ventas_pasadas.log`) e **instalar afluencia** (varios minutos: baja torch/ultralytics), que al terminar **abre sola la ventana de dibujar líneas** — lo único de Daniel: ENTRADA2.2, dos clics, verde = tienda, Guardar. En pantalla y en `logs\postactualizacion.log` cada paso dice "hecho" o "PENDIENTE (se reintenta al actualizar)". Después, en este orden:
> 1. `scripts\revisar_tareas.bat` → POS Afluencia, POS Asistencia 11:00, snapshot oculto, MeilisearchPOS S4U; ya sin ventana negra. Si sigue saliendo una, foto.
> 2. A los minutos `logs\afluencia.log` debe traer "entra/sale"; si sale cero (o el paso quedó PENDIENTE por no encontrar el DVR: necesita `data\dvr_settings.json` en la principal), `afluencia\diagnostico_afluencia.bat` + `scripts\enviar_reporte.bat`.
> 3. Telegram: a las 11:00 llega la asistencia; `/falta_Fanny` marca, repetirlo quita.
> 4. Celular: **📋 Contar** → elegir escuela (dice "hace N días (Nombre)"; las contadas hace poco no salen, "Ver todas") → hoja completa sin Pedido → cerrar y volver → Terminar.
> 5. Kiosko → Conteos → Empezar → Básicos: el tipo dice su fecha y el tercer combo deja elegir **una sola prenda** (o todas). Abajo, el tablero **ESCUELAS Y BÁSICOS** con las 59 filas (20 contadas esta semana, 10 conteo viejo, 29 nunca); **doble clic en Práxedis → comparativo** (había / hay / vendidas / sin explicar). En las tarjetas a medias, **Eliminar** (borrar la Emiliano Zapata duplicada) y **Reasignar**. Empezar: selector con `EN PROCESO (Fanny)`; que Ana elija una que Fanny empezó → "Seguirla / Imprimir otra hoja". Imprimir pregunta carta o tira.
> 6. Como VEND-1 → Por revisar → **Revisar**: A la mano · En cajas (tooltip con las cajas) · Surtir · Sugerido · Pedido editable (si no hay nada que pedir, muestra todas y lo dice); Guardar pedido; Hoja de pedido → Mandar por Telegram; doble clic en una talla → historia; **Historia de la escuela** (por prenda de mayor a menor, "Ver tallas").
> 7. Celular, vista del dueño → **📦 Bodega**: *Llegó mercancía* (prenda → llegaron por talla, prellenado con lo pedido; casilla "Guardar parte en una caja"), *Pasar al piso* (caja → cuántas al rack) y *Corregir caja* (recuento). Cache v13: recargar dos veces.
> 8. Telegram: `/descanso_Fanny` en un día que no es el suyo → su fijo de esa semana queda como trabajo; `/vino_Stayce` un sábado compensa una falta de la semana (nómina completa). Pero descanso movido + otra falta = sí descuenta 1 (arreglado 15/09).
> 9. Libreta → doble clic en un movimiento → **🖨 Reimprimir ticket** (sale copia con REIMPRESION, no registra). Después de una venta, Inventario debe bajar esa talla (stock que descuenta).
> 10. Buscar "Bata Infantil Estampado" en el kiosko: $75 (se llamaba Mandil; renombrada el 20/09).
> 11. POS: solo siete pestañas; Analítica con "Lo que se perdió".

> [!info] Práxedis Guerrero se partió en dos (2026-09-14, en producción)
> Compartían nombre y lista de conteo. Ahora: **Práxedis G Guerrero** (id 19, Primaria: 6 prendas, nombres renombrados a "…Práxedis G Guerrero") y **Práxedis Guerrero Secundaria** (id 49, nueva: las 8 prendas de Secundaria). La jornada del 13 de Stayce (94 tallas, contó las dos) se **partió en dos**: la 24 queda en Secundaria (56 tallas) y la 26 nueva en Primaria (38), mismos datos y ambas aplicadas; el tablero muestra las dos como "ayer · Stayce · Aplicada". El avance ya cuenta solo tallas que siguen en el alcance (`5874ec81`). Los kioskos toman los nombres al refrescar el catálogo.
> **Miguel Hidalgo (Rancho Nuevo)** (id 50, nueva, mismo día): las mismas piezas que Miguel Hidalgo pero en **gris** y sin chaleco — 6 prendas / 66 tallas (SKU005376–SKU005441), mismos precios, stock 0. Creada con `CatalogService` (SKUs de la secuencia). La Chamarra y el Pants 3pz no salen en el alcance de conteo porque el alcance omite prendas sin stock/virtuales, igual que en las demás. **Ignacio Allende (Jaral)** (id 51): clon de Ignacio Allende sin suéteres, 7 prendas / 73 tallas, stock 0.

> [!question] Decisiones que Daniel tiene pendientes
> - **Red:** apartar en el ARRIS la `.9` (impresora) y la `.11` (DVR) como la `.10`; cable de red a la principal en vez del dongle.
> - **Descansos fijos de las demás empleadas** (Equipo → Horario): solo Stayce lo tiene (sábado). Sin eso, "vino en su descanso" no compensa faltas en la nómina.
> - **Color de los suéteres de Miguel Hidalgo (Rancho Nuevo)**: no son grises; quedaron "Sin color" hasta que Daniel diga cuál.
> - **Internet para las empleadas** (bloquear redes/video, dejar el servicio y WhatsApp): el Deco está en modo AP y no filtra; propuesta = **NextDNS** puesto como DNS en el módem Telmex + tarea oculta que actualiza la IP. Falta que cree la cuenta en nextdns.io.
> - ~~Que la venta descuente stock~~ hecho el 14/09; ~~`descontar_ventas_pasadas --aplicar`~~ corre solo en la próxima actualización (paso único). Falta: contar los 185 SKUs del 80% → prender `EXISTENCIA_CONFIABLE`.
> - **Básicos, punto 4 (tuyo):** recontar las 31 cajas de Bodega una tarde con el celular (📦 Bodega → *Corregir caja*); llevan desde el 16 de julio sin moverse y hasta entonces "En cajas" en Revisar trae números viejos.
> - **Rediseño del catálogo:** fase 1 hecha (nombres limpios, escuelas partidas, duplicados fundidos). **Fase 2** con la base lista (ver [[38 - Catálogo Fase 2 - Uniformes]]); falta verla, aplicarla y la 2b. Luego **fase 3** (conjuntos 3pz/Chamarra).
> - **Colores del catálogo (anotación de Daniel, 2026-09-14):** muchas escuelas se dieron de alta con prisa y sus prendas quedaron "Sin color". Medido: **214 de 322 prendas de escuela (en 47 de 50 escuelas), 1,606 tallas**. Los suéteres de Miguel Hidalgo (Rancho Nuevo) también quedaron sin color (no son grises; falta que Daniel diga cuál). Se trabaja después; cuando toque, conviene una pantalla "poner color a una escuela" que aplique a todas sus prendas de una vez.
> - ~~PWA básicos por prenda~~ hecho 17/09 (recargar dos veces en el celular, cache v15).
> - **Después para básicos:** "hoy tocan" por movimiento (3–4 prendas al día) y desactivar las 605 tallas sin venta ni conteo (Chamarra, Pants Suelto, Chaleco).

### Estado al 2026-09-10

> [!check] Actualizar la PC principal (2026-09-13)
> Trae **Contar desde el celular** (la hojita en la PWA) y la asistencia con comandos tocables. Al actualizar, la postactualización reinicia el servidor de la PWA; los teléfonos toman la página nueva al abrirla (cache v5). Probar: en el celular, Contar → Práxedis → teclear dos tallas → salir → Seguir → Terminar; luego en el kiosko, Conteos con tu gafete → Por revisar.

> Daniel actualizó a media mañana: ya trae `INFRA_VERSION 4` (ventana negra resuelta, tarea "POS Asistencia" 11:00) y la primera asistencia con botones. **Lo de después no lo trae:** la asistencia sin botones, con los comandos tocables `/falta_Fanny · /descanso_Fanny`. Actualizar otra vez desde el acceso directo.

> [!success] 2026-09-12
> **Ventana negra:** era "POS Snapshot Casa" (creada directo, sin el vbs). Recreada oculta por la postactualización v4. **Asistencia por Telegram:** `/asistencia` y tarea a las 11:00; presencia deducida (primer movimiento en la Libreta o conteo abierto), descanso/falta del calendario, y Daniel marca con un comando tocable por empleada; repetirlo quita la marca. Ver [[34 - Telegram y Resumen Diario]].

> [!success] 2026-09-11 en la tienda
> PC principal actualizada (producción en `ab1c2d3e4f5a`), paso 4 hecho y **el flujo completo de Conteos probado con gafete real**: hay 5 jornadas en producción. La HP empezó a fallar → al imprimir la hoja se elige **carta (HP) o tira (tickets)**. Ver [[36 - Conteos por Jornada]].

> [!success] Ya funcionando en la tienda
> Base de producción en `x7f8a9b0c1d2` (al día). Bot de Telegram contestando, alertas al instante, PWA en el celular, cámaras del DVR, corte por periodo con reactivo, nómina calculada.

> [!warning] 1. Actualizar la PC principal (trae lo del 2026-09-10)
> Abrir **POS Uniformes** desde el Escritorio. Ya no hay que correr instaladores: la actualización termina con `postactualizacion.bat`, que **borra las 4 tareas viejas que hacían parpadear la ventana negra**, deja un solo supervisor oculto (bot + PWA) y los reinicia con el código nuevo. Ver [[29 - Updates y Mensajería]].
> **Además, lo del 10 de septiembre:** Analítica sobre ventas reales + "Lo que se perdió", POS de once pestañas a siete, se acabó el aviso diario de "Caja pendiente de corte", y **Conteos por jornada en el kiosko** (sección nueva, gafete, pausar/retomar, revisión del dueño). Dos migraciones nuevas, `z9b0c1d2e3f4` y `ab1c2d3e4f5a`, se aplican solas.
> Trae: tickets de corte más simples, borrar corte y deshacer pago, ajustes que mandan también en la Libreta (Ctrl+Shift+R = lo real), supervisor único, textos sin nombres de familia, Meilisearch con SKU corto y ranking por ventas.
> También: la pestaña **Analítica** ya no lee las tablas muertas (`venta`, de abril); ahora muestra **lo que de verdad se vende** desde la Libreta — resumen, forma de cobro y seis cortes: producto, prenda, escuela, talla, hora y empleada.
> Después, abrir el satélite en cada kiosko (se actualiza solo; `scripts\forzar_update_satelite.bat` si se atora). Si algo truena: `scripts\enviar_reporte.bat`.

> [!check] 2. Confirmar en piso
> Que **ya no aparezca la ventana negra** (ni al arrancar ni cada 5 min). Que `/estado` conteste desde el celular. Un retiro chico debe avisarte al instante. Que el corte de las 17:30 **te pregunte** antes de imprimir y que `/corte` lo cierre.

> [!check] 3. Cámaras en cada kiosko
> Ctrl+Shift+A → 📹 Cámaras → IP `192.168.0.11`, `dany`, contraseña → Detectar canales → marcar las 4 ENTRADA → Guardar. Probar Ctrl+Shift+C y Ver momento. Opcional en la principal: `afluencia\instalar_afluencia.bat` (contador de personas; revisar `afluencia\calibracion\*.jpg`).

> [!check] 4. Equipo y horarios (Libreta → 👥 Equipo)
> Dar de baja a Lupita · ✏️ Horario a cada activa: descanso fijo + último pago; Naye = "Por días" sáb/dom · ⚙ Caja y nómina: confirmar reactivo $11,160 y descuento por falta ($216.67 supuesto).

### Demanda no atendida (nuevo, 2026-09-10)

> [!info] Lo que pidieron y no se pudo vender
> Ninguna tabla lo tenía: la Libreta solo dice qué SÍ había. Ahora se junta **sin que la empleada llene nada**, deduciéndolo de lo que ya hace:
> - `busqueda_vacia` — buscó algo que el catálogo no tiene (antes moría en la etiqueta "Sin resultados").
> - `talla_agotada` — eligió una talla en cero. **Apagado para las empleadas** (`EXISTENCIA_CONFIABLE = False` en `services/demanda_service.py`): hoy el stock no es confiable, así que no se muestra nada distinto. La señal se anota igual, en silencio. **Cuando se prenda se verá así:** (1) en **Presupuesto guiado**, en los resultados de la barra "Buscar producto rapido…", la talla agotada sale **punteada y gris** y al tocarla se pinta **verde con "anotado ✓"**; (2) en el buscador de **Ctrl+S** (el de Venta Rápida), columna nueva **"Hay"** con el número o "agotado" en gris. En los dos casos se puede seguir eligiendo: no se bloquea nada.
> - `carrito_vacio` — piezas escaneadas y canceladas sin cobrar.
>
> Anotar va a un JSON local (funciona sin red, nunca lanza excepción). El drenado colapsa las cadenas de tecleo (cami → camis → camisa deja solo "camisa") y marca **urgente** lo que se repite 3 veces o más. Servicio: `services/demanda_service.py`.
>
> **Dónde se lee:** pestaña **Analítica**, bloque "Lo que se perdió", debajo de las ventas reales. Dos listas: **Qué pedir** (producto y talla que eligieron estando en cero) y **No lo encuentran** (texto buscado sin resultado — catálogo incompleto o sinónimo faltante). Con veces, piezas y última vez; lo repetido 3 veces o más sale en rojo.
>
> **Falta:** decidir si preguntar "¿se llevó otra o se fue?" — eso sí necesita a una persona y se dejó para cuando haya meses de toques acumulados.

### Inventario: el número está congelado (medido 2026-09-10)

> [!danger] La venta del kiosko NO descuenta stock
> El único camino que lo descontaba es `venta_service.registrar_salida_venta`, del POS viejo, muerto desde marzo (6 movimientos SALIDA_VENTA, último 19/03). El último movimiento de inventario de cualquier tipo es del **16 de julio**.
>
> | Dato | Valor |
> |------|-------|
> | Variantes activas | 4,795 |
> | Nunca contadas | 3,630 |
> | Vendidas después de su último conteo y aún marcando stock | 122 (220 piezas) |
> | SKUs distintos vendidos (Libreta, 02–10 sep) | 360 |
> | SKUs que hacen el 80% del dinero | 185 (110 nunca contados) |
>
> **Ojo con las cifras:** `libreta_venta` arranca el **2026-09-02**. Lo que se reportó como "60 días" son en realidad 9 días.

> [!tip] Recomendación (en este orden)
> 1. **Que la venta descuente stock**, aplicado al drenar la cola a Postgres (funciona sin red, no bloquea la venta, amarrado al folio de la Libreta para no descontar doble). Dejar que llegue a negativo: el negativo es la lista de qué recontar. **Falta luz verde de Daniel.**
> 2. **Contar solo lo que se mueve**, no las 4,795. Lista generada: los 185 SKUs del 80% del dinero.
> 3. Recién entonces prender `EXISTENCIA_CONFIABLE = True`.
>
> No hacer todavía el conteo periódico por escuela: cobra sentido cuando el número se sostenga solo. Detalle en [[07 - Servicios - Catálogo e Inventario]].

### POS adelgazado (2026-09-10)

> [!info] De once pestañas quedan siete
> Ocultas: **Caja, Presupuestos, Apartados, Catalogo**. Su trabajo se mudó al kiosko (corte desde el satélite, presupuestos en Presupuesto guiado, apartados en Venta Rápida, catálogo desde Panel Uniformes e Inventario). Los datos lo confirmaban: última sesión de caja 01/06, último presupuesto del POS 20/05, último apartado 20/03.
>
> **Se ocultan, no se borran.** Constante `PESTANAS_MUDADAS_AL_KIOSKO` en `ui/main_window.py`: quitar un nombre de ahí la vuelve a mostrar.
>
> Con la caja fuera se apagó todo lo que la acompañaba, que era lo que molestaba a diario: en producción quedó la **sesión id 18 abierta el 1 de junio** que nunca se cerró, y por eso cada arranque saludaba con "Caja pendiente de corte". Se apagaron seis puntos: aviso al abrir, bloqueo para operar, etiqueta del encabezado, botón Corte, recordatorio de las 5 y la consulta que lo alimentaba (`caja_en_el_pos()`).
>
> **Efecto lateral:** el rol CAJERO se queda sin pestañas visibles. No estorba porque nadie entra al POS con ese rol, pero si algún día hace falta, hay que darle alguna.

### Conteos que las empleadas pueden hacer solas (2026-09-10, pasos 1–3 hechos)

> [!success] Lo que ya está
> **Paso 1** — El menú del kiosko: se fue el botón Cámaras (sigue en Ctrl+Shift+C) y entró **Conteos**. Calendario quedó solo con el calendario del mes.
> **Paso 2** — Conteos abre con **gafete** (cada conteo lleva nombre). La captura ya **no muestra lo que el sistema cree** ni pinta diferencias en vivo. **Vacío = no la conté**: no se registra ni se toca la fecha de conteo.
> **Paso 3** — La **jornada** (`conteo_jornada`, migración `ab1c2d3e4f5a`): empezar por escuela o prenda básica, **dejar a medias** y seguir otro día, ver el avance por tallas y por prendas, solo quien la abrió (o Daniel) puede seguirla. **Daniel revisa por bloque**: cada talla con su diferencia, y Aplica o Descarta desde el kiosko con su gafete `VEND-1`. Nada cambia el inventario hasta que él aplica.
>
> Servicio: `services/conteo_jornada_service.py` · diálogos: `ui/dialogs/conteo_jornada_dialogs.py` · tarjetas: `ui/helpers/conteos_jornadas_helper.py`.

> [!success] Paso 4 hecho (2026-09-11)
> Hoja carta con el formato de Daniel y selector carta / tira. Queda para después: código de barras en la hoja.

> [!success] Migraciones al día
> Producción en `ab1c2d3e4f5a` desde el 2026-09-11.

### Decisiones que faltan

| Tema | Qué falta |
|------|-----------|
| Hora de apertura | La alerta de "movimiento fuera de horario" supone que abren a las **09:00** (`horario_tienda_service.APERTURA`). Confirmar |
| Descuento por falta | $216.67 (1/6 del sueldo) sigue siendo supuesto |
| Windows Update | Poner horas activas 8:00–19:00 en la principal (las etiquetas se trababan mientras actualizaba) |
| Meilisearch | Hechos los puntos 1-5 de la auditoría; faltan **6** (el stock del índice se queda viejo: update parcial al vender + reindex diario) y **7** (datos sucios: tallas Uni/Unitalla/Ch/M, Basico/Básico, Blanca/Blanco, escuelas repetidas en los nombres). Ver [[13 - Servicios - Utilidades]] |

### Backlog

Estrenar la PWA con las empleadas (PINes) · merge a `main` · kioskos restantes · foto de CAJA por venta · Frigate en mini PC + Coral · mini vista de entradas siempre visible.
