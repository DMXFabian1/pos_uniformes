# Arquitectura de impresión — Servidor / Estación

Entorno con **varias estaciones de trabajo** (cajas, kioskos) y **una sola PC con
impresoras**. La impresión está **centralizada**: las estaciones no tocan hardware;
solo mandan la solicitud al servidor, que imprime.

## Roles (ajuste por PC)

Cada PC elige su rol en el admin del satélite (**Ctrl+Shift+A** → pestaña
🖨 Impresoras). Es un ajuste **local por máquina** (`print_routing.json` en
`satellite_data_dir()/data/`), no en la base compartida.

| Rol (UI) | En código | Qué hace |
|---|---|---|
| **🖨 Servidor de impresión** | `MODO_LOCAL` | Tiene las impresoras. Imprime lo suyo **y** drena la cola de las estaciones. Único en la red. |
| **📡 Estación** | `MODO_SATELITE` | No tiene impresoras. Encola todo (tickets, etiquetas, conteo) al servidor. **No detecta ni configura impresoras** (la config se oculta). |

> Motivo de ocultar la config en estaciones: antes intentaban autodetectar
> impresoras Brother que no tienen conectadas y fallaban.

## Transporte: cola durable en la base

```
Estación  ──encola trabajo──►  tabla `trabajo` (Postgres compartido)  ──►  Servidor de impresión
(sin impresoras)                    cola durable, auditable                 despachador → impresoras
```

- **`trabajo`**: cola persistente (tipos `TICKET`, `ETIQUETA`, `CONTEO`, `PEDIDO`).
- **Despachador** (`services/trabajo_dispatcher.py`): corre **solo en el Servidor**.
  Reclama, imprime, marca estado; reintentos con backoff; LISTEN/NOTIFY para baja
  latencia (fallback a polling ~1.5 s).
- **Handlers físicos** (`ui/helpers/trabajo_print_handlers.py`): lo que toca hardware.

**Por qué cola en DB y no un microservicio HTTP:** durabilidad gratis (si el
servidor está ocupado o reiniciando, el trabajo espera en la cola y sale al
volver), reusa la Postgres que ya se usa (cero puertos/servicios nuevos), es
auditable y ya tiene panel (Ctrl+Shift+Q). Un POST HTTP se perdería si el
servidor no está, y terminarías reconstruyendo… una cola. Compartir impresoras de
Windows es peor: driver por estación + los mismos problemas de autodetect + el
render ESC/POS y de etiquetas QL necesitaría el driver correcto en cada PC.

## Ruteo en el código

Todo flujo de impresión térmica pasa por un helper de ruteo que decide, según el
rol de la PC, imprimir local o encolar:

| Tipo | Helper |
|---|---|
| Tickets de venta / presupuestos | `ui/helpers/ticket_routing_helper.route_tickets` |
| Etiquetas | `ui/helpers/label_routing_helper.maybe_route_label_to_satellite` |
| Hojas de conteo | `ui/helpers/conteo_routing_helper.maybe_route_conteo_to_satellite` |

`ui/dialogs/printable_text_dialog.open_printable_text_dialog` (presupuestos y
ticket de venta de la satélite) también pasa por `route_tickets`.

> **Regla:** nunca llamar directo a `_print_ticket_job` / `open_tickets_print_dialog`
> / impresión de etiqueta desde un flujo de negocio. Siempre vía un helper de
> ruteo, para que las estaciones encolen en vez de imprimir local.

## Setup (una vez por PC)

1. La PC con impresoras → rol **Servidor de impresión**; ahí se eligen las
   impresoras de tickets y etiquetas.
2. Las demás → rol **Estación** (ya no ven config de impresoras).
3. Todas apuntan a la misma Postgres (`POS_UNIFORMES_DB_HOST`).

Pruebas de extremo a extremo: ver [`PRUEBAS_DESPACHADOR_SATELITE.md`](PRUEBAS_DESPACHADOR_SATELITE.md).

## Pendiente

- El autodetect de impresoras Brother ahora solo importa en la PC **Servidor**.
  Si ahí falla, falta agregar un **selector manual de impresora** como respaldo.
