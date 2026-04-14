# Handoff para continuar en Claude Code

Fecha: `2026-04-13`
Proyecto: `pos_uniformes`
Rama actual: `codex/etiquetas-windows`

## 1. Que es este proyecto

`pos_uniformes` es el POS principal en Python para operacion diaria del negocio.

Hoy conviven dos frentes:

- POS principal
  - venta
  - caja
  - catalogo
  - inventario
  - apartados
  - presupuestos
  - analitica
  - configuracion
- app satelite de presupuestos
  - consulta catalogo y precios
  - arma presupuestos
  - no cobra
  - no descuenta inventario
  - no sustituye a Caja

La arquitectura de trabajo real ha sido de estabilizacion incremental, no de reescritura.

## 2. Como hemos trabajado

Reglas operativas que ya se vienen usando y conviene mantener:

- trabajar un bloque funcional por vez
- no mezclar refactor estructural y feature grande nueva en la misma ronda
- `ui/main_window.py` debe actuar como coordinador, no como lugar para meter logica nueva densa
- si una regla es de negocio o calculo puro, moverla a `services/`
- si una pieza es presentacion, shape de tabla o estado visible, moverla a `ui/helpers/`, `ui/dialogs/` o `ui/views/`
- cada cambio importante debe cerrar con checkpoint documentado
- si el cambio toca Caja, descuentos, cobro, inventario o configuracion sensible:
  - pruebas
  - precheck
  - y validacion manual cuando aplica

Estado metodologico actual:

- `docs/plan_estabilizacion.md`
  - Fase vigente: `Fase 5. Optimizacion fina`
- `docs/protocolo_cambios.md`
  - define el orden obligatorio de trabajo y verificaciones minimas
- `docs/historial_refactors.md`
  - es la bitacora viva de checkpoints, extracciones y decisiones ya cerradas
- `docs/hoja_ruta_mejoras.md`
  - guarda ideas abiertas y futuras, aunque aun no se implementen

## 3. Como documentamos

Los documentos base que otra IA debe leer primero son:

- `docs/plan_estabilizacion.md`
- `docs/protocolo_cambios.md`
- `docs/historial_refactors.md`
- `docs/hoja_ruta_mejoras.md`
- `docs/mapa_modulos.md`

Cuando una mejora es conceptual o de producto, aunque aun no se programe, se anota en:

- `docs/hoja_ruta_mejoras.md`

Cuando un cambio estructural o funcional ya se hizo y tuvo checkpoint, se registra en:

- `docs/historial_refactors.md`

Cuando un flujo es delicado o se quiere preservar entendimiento operativo, se crea documento propio:

- `docs/subflujo_*.md`
- `docs/*_windows.md`
- `docs/*_cache_*.md`
- `docs/*_conteo_*.md`

Los checkpoints se etiquetan con tres estados:

- `validated-manual`
  - se corrio y se comprobo en flujo real
- `validated-tests`
  - paso pruebas y/o checks tecnicos, pero falta confirmacion humana
- `pending-manual`
  - se sabe que todavia necesita prueba real en Windows o en operacion

## 4. Mapa tecnico rapido

Entradas principales:

- `main.py`
- `presupuestos_satelite_main.py`

Archivos sensibles:

- `ui/main_window.py`
  - sigue siendo el archivo mas grande y delicado
  - tamano actual aproximado: `11217` lineas
- `database/models.py`
  - tamano aproximado: `1386` lineas

Capas importantes:

- `database/`
  - conexion, modelos y preflight
- `ui/views/`
  - tabs y construccion visual
- `ui/dialogs/`
  - dialogs operativos
- `ui/helpers/`
  - presentation helpers, estados visibles, feedback y shape de tablas
- `services/`
  - reglas y bloques extraidos
- `utils/`
  - QR, etiquetas, config, formatos y soporte de build
- `scripts/`
  - salud de arranque, backup, restore, build Windows y helpers operativos
- `tests/`
  - bateria unitaria y de helpers/servicios

Servicios ya muy usados para sacar logica de `main_window.py`:

- `services/sale_*`
- `services/layaway_*`
- `services/history_snapshot_service.py`
- `services/search_filter_service.py`
- `services/inventory_label_service.py`
- `services/cash_session_action_service.py`
- `services/settings_*`

## 5. Que ya esta bastante estabilizado

Segun la documentacion y checkpoints ya registrados:

- Fase 4 se considera cerrada desde `2026-03-20` con `validated-manual`
- la logica de descuentos, promo manual, notas de venta, bloqueo de descuento y cliente escaneado ya fue extraida en buena parte
- dialogs de cobro ya viven fuera de `ui/main_window.py`
- ticket y comprobantes ya tienen servicios dedicados de texto y totales
- el arranque tiene precheck reutilizable
- hay suite de pruebas ya establecida
- el build de Windows tuvo una ronda importante de endurecimiento
- QR y etiquetas ya tuvieron una ronda fuerte de estabilizacion
- el satelite de presupuestos ya es un flujo real, pero controlado

Punto importante:

- aunque mucho ya esta extraido, `ui/main_window.py` sigue siendo el mayor riesgo tecnico del sistema

## 6. Estado real del repo al momento del handoff

Rama actual:

- `codex/etiquetas-windows`

HEAD actual:

- `63dd698` `Mejorar conteo fisico y acceso rapido a etiquetas`

Ultimos commits visibles:

- `63dd698` `Mejorar conteo fisico y acceso rapido a etiquetas`
- `e5ba7a6` `Evitar cierre con enter en conteo fisico`
- `6b03b8e` `Pulir conteo libre y cliente rapido en presupuestos`
- `6c7ac3c` `Agregar lista lateral al presupuesto satelite`
- `a611dd9` `Agregar accesos rapidos al guiado satelite`
- `f86d808` `Ajustar estados de botones en satelite`
- `2edaa9c` `Mostrar presupuesto emitido en satelite`

Working tree con cambios sin consolidar:

- modificado:
  - `docs/hoja_ruta_mejoras.md`
- nuevos sin trackear:
  - `docs/conteo_por_sku_y_recordatorios.md`
  - `docs/satelite_consulta_y_cache_local.md`
  - `scripts/build_presupuestos_satelite_hoy_windows.bat`
  - `scripts/windows_launch_presupuestos_satelite.ps1`

Esto importa porque el estado actual mezcla:

- codigo ya consolidado en commits anteriores
- decisiones de producto/documentacion aun no cerradas en git
- scripts operativos nuevos para Windows/satelite

## 7. Trabajo reciente que SI conviene entender antes de seguir

### 7.1 Conteo fisico

En `historial_refactors` quedaron varias mejoras recientes:

- `Conteo fisico` V2 permite iniciar desde seleccion multiple en Inventario
- si no hay lote previo, el flujo sigue funcionando por escaneo acumulado
- se hizo mas explicito el modo `uno a uno`
- hay boton rapido `Restar 1`
- se corrigio cierre accidental con `Enter`

Estado:

- tecnicamente estable a nivel pruebas
- validacion manual en Windows sigue siendo importante

### 7.2 Caja: agregar sin codigo

Se abrio una `V1` para venta rapida:

- popup minimo
- `Precio` obligatorio
- `Nombre rapido` opcional
- entra como `SIN-CODIGO` / `Venta manual`
- no toca inventario

Estado:

- checkpoint `validated-tests`
- validacion manual pendiente

### 7.3 Inventario y etiquetas

Quedaron avances importantes:

- seleccion multiple mas clara
- impresion por lote de etiquetas con dialogo especifico
- restauracion de seleccion despues de refresh mas robusta
- referencia Windows ya alineada al flujo real de impresora Brother

Documento clave:

- `docs/etiquetas_windows.md`

Punto operativo importante:

- en Windows la impresion de etiquetas intenta usar `win32print`, `win32ui` y `PIL.ImageWin`
- no se quiere mandar a `Microsoft Print to PDF`
- para la Brother QL-800 se requiere driver oficial

### 7.4 Satelite de presupuestos

La app satelite ya es un frente real de producto, pero con limites claros:

- consulta precios y catalogo reales
- arma presupuestos
- depende de la PC principal y de PostgreSQL por red local
- no debe abrirse como modulo de cobro/offline general

Documento nuevo clave:

- `docs/satelite_consulta_y_cache_local.md`

Decision actual documentada:

- la siguiente evolucion razonable NO es replica completa
- la siguiente mejora razonable es cache local de lectura
- luego, solo si el uso real lo justifica, evaluar borradores offline

Tambien hay dos anotaciones UX que no conviene perder:

- el boton `Agregar al presupuesto` necesita mas protagonismo visual
- para kiosko/tactil conviene evaluar scroll por arrastre mas natural

### 7.5 Conteo por SKU como frente futuro

Documento nuevo clave:

- `docs/conteo_por_sku_y_recordatorios.md`

Decision de producto ya tomada:

- el seguimiento de reconteos futuros debe ser por `SKU`
- no por zona como eje principal
- los recordatorios deben ser discretos
- no se quieren popups invasivos

Esto todavia NO esta implementado.

## 8. Que falta hacer de verdad

Lo pendiente no es una sola cosa; son varios frentes con distinto nivel de madurez.

### Pendiente tecnico-operativo inmediato

- validacion manual en Windows de:
  - conteo fisico
  - `Agregar sin codigo`
  - impresion por lote de etiquetas
  - bundle Windows real
  - satelite en uso de piso

### Pendiente de consolidacion en git

- decidir si los documentos nuevos de satelite/cache y conteo por SKU ya deben entrar a git
- decidir si los scripts nuevos de Windows/satelite ya son el flujo oficial o solo utilidades locales

### Pendiente de producto/arquitectura proxima

- seguir `Fase 5. Optimizacion fina`
- cerrar polish y estabilidad puntual sin reabrir una refactorizacion gigante
- despues de Fase 5, abrir el modulo de:
  - `Empleadas`
  - atribucion comercial
  - comisiones

## 9. Siguiente paso recomendado

Si Claude retoma desde aqui, la ruta mas sana seria:

1. Leer:
   - `docs/plan_estabilizacion.md`
   - `docs/protocolo_cambios.md`
   - `docs/historial_refactors.md`
   - `docs/hoja_ruta_mejoras.md`
   - este handoff
2. Revisar `git status` para no perder los archivos nuevos no trackeados.
3. Asumir que `ui/main_window.py` no debe recibir nueva logica densa salvo integracion minima.
4. Si el siguiente trabajo es satelite:
   - tomar como base `docs/satelite_consulta_y_cache_local.md`
   - confirmar si se quiere solo documentar, pulir UX o ya implementar cache
5. Si el siguiente trabajo es inventario/conteo:
   - tomar como base `historial_refactors.md` + `docs/conteo_por_sku_y_recordatorios.md`
   - separar claramente lo ya implementado vs lo conceptual
6. Si el siguiente trabajo es Windows:
   - validar primero si los scripts nuevos deben quedar oficiales
   - probar bundle y periféricos reales antes de seguir agregando complejidad

## 10. Comandos utiles

Checks minimos recomendados por el proyecto:

```bash
./.venv/bin/python scripts/check_startup_health.py
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Setup rapido:

```bash
python scripts/setup_dev_env.py
```

Arranque local del POS:

```bash
python -m pos_uniformes.main
```

Migraciones:

```bash
python -m alembic upgrade head
```

Build Windows final:

```powershell
scripts\build_windows_bundle.ps1
```

## 11. Advertencias para no perder tiempo

- No asumir que todo lo documentado ya esta implementado.
- No asumir que `pending-manual` significa problema tecnico; muchas veces solo falta correrlo en Windows o en piso.
- No meter una mejora nueva grande dentro de `ui/main_window.py`.
- No abrir a la vez satelite offline, caja, inventario y etiquetas; mejor un frente por vez.
- No confundir la app satelite con una segunda caja.

## 12. Resumen corto para pegarle a Claude

Trabajamos en `pos_uniformes`, un POS Python con una app satelite de presupuestos. La forma de trabajo ha sido de estabilizacion incremental: sacar logica de `ui/main_window.py` hacia `services/`, `ui/helpers/` y `ui/dialogs/`, documentar cada checkpoint en `docs/historial_refactors.md` y no mezclar refactors grandes con features grandes. La fase tecnica actual es `Fase 5. Optimizacion fina`. Los documentos que primero debe leer Claude son `docs/plan_estabilizacion.md`, `docs/protocolo_cambios.md`, `docs/historial_refactors.md`, `docs/hoja_ruta_mejoras.md`, `docs/mapa_modulos.md` y este handoff.

El repo esta en la rama `codex/etiquetas-windows`, con `HEAD` en `63dd698`. Hay cambios sin consolidar: `docs/hoja_ruta_mejoras.md` modificado y nuevos `docs/conteo_por_sku_y_recordatorios.md`, `docs/satelite_consulta_y_cache_local.md`, `scripts/build_presupuestos_satelite_hoy_windows.bat` y `scripts/windows_launch_presupuestos_satelite.ps1`. Lo ultimo fuerte del proyecto fue conteo fisico, venta `sin codigo`, impresion de etiquetas y pulido del satelite. Lo pendiente real es validar en Windows varias mejoras recientes, decidir si esos docs/scripts ya se consolidan, y continuar Fase 5 sin volver a meter logica grande en `main_window.py`. Despues de Fase 5, la iniciativa grande prevista es `Empleadas / atribucion / comisiones`.
