---
tags: [referencia, pos-uniformes, chuleta]
fecha: 2026-09-25
estado: vigente
---

# 41 — Chuleta: atajos y comandos

> Todo lo que se puede teclear o hacer doble clic, en un solo lugar. Daniel, 2026-09-25: *"siento que son muchos y luego los olvido"*.

---

## Teclado — POS (la PC principal)

| Tecla | Qué hace |
|---|---|
| **F2** | Vender |
| **F8** | Saltar al campo de SKU |
| **F6** | Ventas recientes |
| **Ctrl + S** | Buscar producto |
| **Ctrl + K** | Kiosko rápido (funciona incluso con una ventana encima) |
| **Ctrl + Shift + B** | Respaldo rápido de la base |

*(En Mac, `Cmd` en vez de `Ctrl` para buscar y respaldar.)*

## Teclado — Kiosko

| Tecla | Qué hace |
|---|---|
| **Ctrl + K** | Kiosko rápido (consulta de precio) |
| **Ctrl + S** | Búsqueda rápida |
| **Ctrl + ← / →** | Cambiar de sección |
| **Ctrl + P** | Imprimir etiqueta de lo seleccionado (catálogo o guiado) |
| **Escape** | Salir de lo que esté abierto |
| **Ctrl + Shift + A** | 🔧 **Admin — pide PIN.** Conexión · Impresoras · Búsqueda · Conteos · Anuncios · **Precios** · Cámaras |
| **Ctrl + Shift + C** | Cámaras |
| **Ctrl + Shift + Q** | Cola del despachador |
| **Ctrl + Shift + P** | Tablero de pedidos |
| **Ctrl + Shift + R** | Libreta: ver lo **real** (lo que de verdad se vendió, sin ajustes) |
| **Ctrl + Shift + L** | Ligar prendas generales a una escuela (dentro del guiado) |

> El PIN de administrador y los demás están en [[22 - Referencia Rápida]].

---

## Doble clic — los iconos del escritorio

| | |
|---|---|
| **POS Uniformes** | Abre el POS. Antes trae lo nuevo, migra y republica a los kioskos. **Es el único que necesitas para actualizar.** |
| **Actualizar POS** | Lo mismo, sin abrir el POS |

## Doble clic — `pos_uniformes\scripts\`

**Del día a día**

| Archivo | Qué hace |
|---|---|
| `revisar_stock_negativo.bat` | Qué tallas dicen tener menos que nada. Solo mira; `--aplicar` las sube a cero |
| `enviar_reporte.bat` | Manda a Claude lo que dijo la consola, por git |
| `diagnostico_impresora_carta.bat` | ¿Por qué no imprime la HP? Deja el reporte en `reportes\` |
| `revisar_tareas.bat` | ¿Qué tarea abre la ventana negra? Con `--arreglar` la calla |

**Cuando algo se rompe**

| Archivo | Qué hace |
|---|---|
| `reparar_satelite.bat` | El kiosko de esta PC no abre |
| `forzar_update_satelite.bat` | Forzar la actualización del kiosko de esta PC |
| `quitar_parpadeo_tareas.bat` | Quitar el parpadeo de la ventana negra |

**Instalar (una vez por PC)**

`instalar_kiosko_aqui` · `instalar_servidor_pwa` · `instalar_supervisor` · `instalar_resumen_diario` · `instalar_corte_propuesto` · `configurar_telegram` · `crear_accesos_principal` · `preparar_share_updates`

**Corren solos — no los toques**

`postactualizacion` · `corte_automatico` · `resumen_diario_telegram` · `supervisor` · `telegram_bot_vigia` · `servidor_pwa_vigia` · `enviar_snapshot_casa`

---

## Consola — lo que de verdad se usa

Todos van igual: desde `C:\Users\Pc\pos_uniformes`, con `.\pos_uniformes\.venv\Scripts\python.exe -m pos_uniformes.scripts.<nombre>`.

| Script | Para qué | Seco / aplica |
|---|---|---|
| `cambiar_precio` | `--prenda "3pz UVEG" --precio 750` · acepta `--tallas CH,MD` | `--aplicar` |
| `revisar_stock_negativo` | Las tallas en rojo, en orden de trabajo | `--aplicar` |
| `auditar_catalogo` | Inconsistencias del catálogo | solo mira |
| `fundir_productos` | `--de 529 --en 303` cuando una prenda está duplicada | `--aplicar` |
| `separar_escuela_por_nivel` | Cuando una escuela son en realidad dos planteles | `--aplicar` |
| `revisar_conteos_pendientes` | Conteos pendientes envenenados | `--descartar` |
| `generar_panel_uniformes` | Rehace el Panel a mano (se rehace solo al abrirlo) | — |
| `generar_tarifario_escuelas` | PDF, una página por escuela | — |
| `backup_database` | Respaldo manual | — |

> **PowerShell no entiende `&&` ni `cd /d`.** Usa `Set-Location <ruta>;` y separa con `;`.
> Y **no guardes reportes con `>`** desde PowerShell: los escribe en UTF-16 y los acentos llegan rotos. Para eso están los `.bat`.

### En la Mac

```
POS_UNIFORMES_DB_HOST=localhost ./pos_uniformes/.venv/bin/python -m pytest pos_uniformes/tests -q -n 6 --dist load
```

```
POS_UNIFORMES_DB_HOST=localhost ./pos_uniformes/.venv/bin/python mapas_escuelas/generar_datos_escuelas.py
```

---

## Telegram (el bot, desde el celular)

| Comando | Qué hace |
|---|---|
| `/corte` | Hace el corte ahora e imprime el ticket en la tienda |
| `/corte 5000` | El mismo corte, retirando $5,000 |
| `/corte sintarjeta` | Sin que se vean los cobros con tarjeta *(se juntan: `/corte 5000 sintarjeta`)* |
| `/nocorte` | Dejar pasar el corte propuesto de hoy |
| **`/pulso`** | **¿Está todo en pie? La tienda entera en una pantalla** (2026-10-02) |
| `/estado` | Qué hay en caja ahora |
| `/resumen` | Resumen del día |
| `/pendientes` | Lo que falta por registrar |
| `/asistencia` | Quién vino hoy, con un botón por empleada |
| **`/prenda playera justo sierra`** | **Precio y cuántas hay por talla** (2026-09-25) |
| **`/escuela conalep`** | **Cómo va esa escuela: contada, agotadas, vendido, por pedir** |
| **`/contar`** | **Qué falta contar, lo rojo primero — igual que el kiosko** |
| **`/faltas`** | **Lo que pidieron y no había en 7 días** |
| `/cortes` | Los últimos cortes, con lo que faltó o sobró y el motivo del ajuste |
| `/retiro 500 gasolina` | Saca del cajón dejando dicho para qué |
| `/pagos` · `/pagar Fanny` | A quién le toca cobrar; con «si» al final se registra |
| `/deshacerpago` | Deshace el último pago |
| `/prestamos` | Los préstamos que pidieron, para aprobar o rechazar |
| **`/aviso Junta a las 6`** | **Sale a pantalla completa en las pantallas de la tienda** (2026-10-01) |
| **`/aviso 3h Hoy cerramos temprano`** | **Igual, pero se quita solo en 3 h** *(sin plazo: 12 h; vale `30m`, `2d`)* |
| **`/aviso @caja2 Ven un momento`** | **Solo en esa pantalla** *(el @ ignora espacios: `@caja2` = «Caja 2»)* |
| **(mandarle una foto)** | **Sin comando: sale a pantalla completa. El pie de foto es el aviso** |
| **`/cartel Promoción de mochilas`** | **El que no interrumpe: rota cuando nadie está tocando la pantalla** |
| **`/avisos`** | **Los puestos, quién los vio; tocando uno: quitarlo, +3 h, +12 h, o que lo vean otra vez** |
| `/falta_Fanny` · `/descanso_Fanny` · `/vino_Fanny` | Marcar. También con espacio: `/falta Fanny` |
| `/menu` | Los botones, para no acordarse de nada |
| `/ayuda` | Esta lista, desde el bot |

---

## El celular (Libreta / PWA)

No hay comandos: todo es tocar. Lo que a veces se olvida:

- **Jalar hacia abajo** para actualizar.
- Si algo no aparece después de una actualización, **⋯ → Reinstalar** (borra el caché y recarga).
- En el inicio del dueño: **🗺 Mapa de conteos** y **🏫 Escuelas**.

---

> Creado: 2026-09-25 · Al día 2026-10-01 · Ver [[22 - Referencia Rápida]] (PINs, rutas, red) · [[39 - Brújula]]
