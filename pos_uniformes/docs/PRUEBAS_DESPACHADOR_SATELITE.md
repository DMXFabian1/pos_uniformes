# Guía de pruebas — Despachador al satélite (Windows)

Circuito a validar: el POS/kiosko **encolan** trabajos y el satélite (la PC con las
impresoras) los **imprime/atiende**. Todo por la red local, contra la Postgres de
la PC principal.

> Rama: `feat/despachador-satelite`. Nada está mergeado a `main`.

---

## 0. Preparación (una sola vez)

**En la PC principal (la que tiene la Postgres):**
1. `git fetch && git checkout feat/despachador-satelite && git pull`
2. Aplicar migraciones: `alembic upgrade head`
   - Debe correr hasta `i2c3d4e5f6a7` (crea la tabla `trabajo`, columnas de
     reintento y el trigger de NOTIFY).
3. Confirmar que Postgres acepta conexiones de la red local (no solo localhost):
   `listen_addresses='*'` en `postgresql.conf` y una regla para la subred en
   `pg_hba.conf`. Anotar la **IP local** de esta PC (`ipconfig`).

**En la PC satélite (la de las impresoras):**
1. Mismo checkout de la rama.
2. En `pos_uniformes.env`, apuntar a la principal:
   `POS_UNIFORMES_DB_HOST=<IP de la principal>` (no `localhost`).
3. Abrir la app del satélite. Menú admin (**Ctrl+Shift+A**) → pestaña
   **🖨 Impresoras** → “Modo de impresión de esta PC” = **Imprimir local**.
   Confirmar que las impresoras de tickets y etiquetas estén elegidas.

**En la PC principal (POS/kiosko):**
1. Menú admin → “Modo de impresión de esta PC” = **Enviar al satélite**.
   Poner un “origen” reconocible (p.ej. `principal` o `kiosko`).

**Atajos en el satélite:**
- **Ctrl+Shift+Q** → panel de la cola (ver/reordenar/reimprimir/cancelar).
- **Ctrl+Shift+P** → tablero de pedidos.

> Regla de oro: con modo **Local**, el comportamiento es el de siempre (imprime
> en su impresora). El ruteo al satélite SOLO ocurre en las máquinas marcadas
> como **Enviar al satélite**.

---

## 1. Tickets de venta y apartado

En la **principal** (modo satélite):
1. Hacer una venta rápida y pulsar **Ticket Venta**.
   - Esperado: aviso “Enviado al satélite (N tickets)”. **No** imprime local.
2. En el **satélite**, el ticket sale en la impresora térmica en ≈1 s.
3. Abrir **Ctrl+Shift+Q** en el satélite: el trabajo aparece como **Impreso**,
   con su origen.
4. Repetir con **Ticket Apartado** (deben salir las 2 copias) y con una venta
   con descuento (ticket + copia de empleada).

**Qué revisar:** que el corte (autocut) separe cada ticket, y que el contenido
sea idéntico al de imprimir local.

---

## 2. Etiquetas

En la **principal** (modo satélite):
1. Abrir el diálogo de etiqueta de un producto e **Imprimir etiqueta**.
   - Esperado: aviso “Enviado al satélite (N copia(s))”.
2. En el **satélite** sale en la Brother correcta.
3. Probar los modos: **Normal**, **Split**, **Continua** y **Label (DK-1221)**.
   - Cada uno debe salir en la impresora que corresponda según la config del
     menú admin del satélite (Normal/Split/Continua → una; Label → otra).

**Qué revisar:** que el modo/tamaño sea el correcto y que la copia impresa sea
la **misma imagen** que se previsualizó en la principal (se envía la imagen ya
renderizada, no se vuelve a generar).

---

## 3. Conteo (y pedido de mercancía)

En la **principal** (modo satélite):
1. Generar hojas de conteo (o “Pedido de mercancía”) desde el panel.
   - Esperado: aviso “N hoja(s) en cola para el satélite”.
2. En el **satélite** salen todas las hojas, una por página (corte entre cada
   una).

**Qué revisar:** que salgan **todas** las hojas. Si una impresora se queda sin
papel a media tanda, el trabajo debe quedar en **Error** en el panel con el
detalle (“X de N hojas…”) para reintentarlo.

---

## 4. Tablero de pedidos (cocina)

1. En la venta rápida de la **principal**, agregar piezas y pulsar
   **Enviar a preparar**.
   - Esperado: aviso “N pieza(s) enviadas al tablero”.
2. En el **satélite**, abrir **Ctrl+Shift+P**. El pedido aparece en
   **Por preparar** con el origen.
3. Seleccionarlo → **▶ Tomar** (pasa a **Preparando**) → **✓ Marcar listo**
   (pasa a **Listos**).
4. Probar **✕ Cancelar** en otro pedido.

**Qué revisar:** que los pedidos **no** intenten imprimirse (no son impresión),
que se muevan de columna, y que el tablero se refresque solo.

---

## 5. Robustez (lo de la Fase 6)

**Reintentos automáticos:**
1. En el satélite, apagar la impresora de tickets.
2. Mandar un ticket desde la principal.
3. En el panel (Ctrl+Shift+Q): el trabajo debe reintentar (vuelve a
   **En espera**) un par de veces con pausa creciente, y tras 3 intentos quedar
   en **Error**.
4. Encender la impresora y **Reintentar** el trabajo desde el panel → debe salir.

**Latencia (NOTIFY):**
- Mandar un trabajo y cronometrar: debería salir casi al instante (no esperar
  varios segundos). Si el listener no conecta, igual sale, solo con la latencia
  del polling (~1.5 s) — no se pierde nada.

**Resiliencia de red / orden de encendido:**
1. Encender el satélite **antes** que la principal. Mandar trabajos cuando la
   principal esté lista → deben despacharse (el satélite no se cuelga si la DB
   no está al arrancar).
2. Desconectar el WiFi del satélite unos segundos y reconectar → debe seguir
   despachando después, sin reiniciar la app.

**Cola persistente:**
- Encolar trabajos con el satélite **apagado**; al encenderlo, deben imprimirse
  los que quedaron pendientes (la cola vive en la DB, no se pierden).

---

## 6. Qué anotar para ajustar

Por cada tipo (ticket / etiqueta / conteo / pedido):
- ¿Salió en la impresora correcta?
- ¿El formato/tamaño/corte es igual al de imprimir local?
- ¿La latencia es aceptable?
- ¿Algún caso quedó en **Error**? Copiar el mensaje del panel.

Con esas notas ajustamos lo que haga falta y luego mergeamos a `main`.
