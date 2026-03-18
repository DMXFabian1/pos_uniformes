# Diagrama actual de base de datos

Fuente de verdad usada para este mapa:

- `pos_uniformes/database/models.py`
- Metadata ORM cargada desde `pos_uniformes/.venv`

Estado observado hoy:

- 35 tablas en el esquema actual de `pos_uniformes`
- `variante` es el nodo mas conectado del catalogo y de las operaciones
- `cliente` y `usuario` funcionan como ejes transversales de ventas, apartados, presupuestos, caja y auditoria
- `configuracion_negocio` y `sku_sequence` son tablas aisladas de configuracion

## Vista general

```mermaid
flowchart LR
    subgraph Catalogo
        C1[categoria]
        C2[marca]
        C3[escuela]
        C4[tipo_prenda]
        C5[tipo_pieza]
        C6[nivel_educativo]
        C7[atributo_producto]
        P[producto]
        V[variante]
        A[producto_asset]
    end

    subgraph Personas
        U[usuario]
        CL[cliente]
        PR[proveedor]
    end

    subgraph Operacion
        VE[venta]
        VD[venta_detalle]
        AP[apartado]
        AD[apartado_detalle]
        AA[apartado_abono]
        PE[presupuesto]
        PD[presupuesto_detalle]
        CO[compra]
        CD[compra_detalle]
    end

    subgraph Caja
        SC[sesion_caja]
        MC[movimiento_caja]
    end

    subgraph Inventario
        MI[movimiento_inventario]
        AL[ajuste_inventario_lote]
        ALD[ajuste_inventario_lote_detalle]
    end

    subgraph Importacion_y_Auditoria
        IC[importacion_catalogo]
        ICF[importacion_catalogo_fila]
        ICI[importacion_catalogo_incidencia]
        CC[cambio_catalogo]
        CM[cambio_marketing_configuracion]
        APM[autorizacion_promocion_manual]
    end

    C1 --> P
    C2 --> P
    C3 --> P
    C4 --> P
    C5 --> P
    C6 --> P
    C7 --> P
    P --> V
    V --> A

    U --> VE
    U --> AP
    U --> PE
    U --> CO
    U --> SC
    U --> CC
    U --> CM
    U --> APM
    U --> AL

    CL --> VE
    CL --> AP
    CL --> PE
    CL --> APM
    PR --> CO

    VE --> VD
    AP --> AD
    AP --> AA
    PE --> PD
    CO --> CD

    V --> VD
    V --> AD
    V --> PD
    V --> CD
    V --> MI
    V --> ALD

    SC --> MC
    IC --> ICF
    IC --> ICI
    ICF --> ICI
    P --> ICF
    V --> ICF
    P --> ICI
    V --> ICI
```

## Catalogo

```mermaid
erDiagram
    CATEGORIA ||--o{ PRODUCTO : categoria_id
    MARCA ||--o{ PRODUCTO : marca_id
    ESCUELA ||--o{ PRODUCTO : escuela_id
    TIPO_PRENDA ||--o{ PRODUCTO : tipo_prenda_id
    TIPO_PIEZA ||--o{ PRODUCTO : tipo_pieza_id
    NIVEL_EDUCATIVO ||--o{ PRODUCTO : nivel_educativo_id
    ATRIBUTO_PRODUCTO ||--o{ PRODUCTO : atributo_id
    PRODUCTO ||--o{ VARIANTE : producto_id
    VARIANTE ||--o{ PRODUCTO_ASSET : variante_id
```

Lectura rapida:

- `producto` representa la familia o ficha base
- `variante` representa el SKU vendible con talla, color, precio y stock
- las tablas de catalogo alrededor de `producto` normalizan escuela, tipo de prenda y atributos
- `producto_asset` cuelga de `variante`, no de `producto`

## Operacion comercial

```mermaid
erDiagram
    USUARIO ||--o{ VENTA : usuario_id
    USUARIO ||--o{ VENTA : cancelado_por_id
    CLIENTE ||--o{ VENTA : cliente_id
    VENTA ||--o{ VENTA_DETALLE : venta_id
    VARIANTE ||--o{ VENTA_DETALLE : variante_id

    USUARIO ||--o{ APARTADO : usuario_id
    USUARIO ||--o{ APARTADO : cancelado_por_id
    USUARIO ||--o{ APARTADO : entregado_por_id
    CLIENTE ||--o{ APARTADO : cliente_id
    APARTADO ||--o{ APARTADO_DETALLE : apartado_id
    VARIANTE ||--o{ APARTADO_DETALLE : variante_id
    APARTADO ||--o{ APARTADO_ABONO : apartado_id
    USUARIO ||--o{ APARTADO_ABONO : usuario_id

    USUARIO ||--o{ PRESUPUESTO : usuario_id
    CLIENTE ||--o{ PRESUPUESTO : cliente_id
    PRESUPUESTO ||--o{ PRESUPUESTO_DETALLE : presupuesto_id
    VARIANTE ||--o{ PRESUPUESTO_DETALLE : variante_id

    PROVEEDOR ||--o{ COMPRA : proveedor_id
    USUARIO ||--o{ COMPRA : usuario_id
    COMPRA ||--o{ COMPRA_DETALLE : compra_id
    VARIANTE ||--o{ COMPRA_DETALLE : variante_id
```

Lectura rapida:

- ventas, apartados y presupuestos comparten el patron `cabecera -> detalle`
- `cliente` es opcional en varios flujos, pero ya esta ligado a ventas, apartados y presupuestos
- `apartado` tiene una capa extra de pagos parciales en `apartado_abono`
- compras alimentan inventario por `variante`, no directamente por `producto`

## Caja, inventario, importacion y auditoria

```mermaid
erDiagram
    USUARIO ||--o{ SESION_CAJA : abierta_por_id
    USUARIO ||--o{ SESION_CAJA : cerrada_por_id
    SESION_CAJA ||--o{ MOVIMIENTO_CAJA : sesion_caja_id
    USUARIO ||--o{ MOVIMIENTO_CAJA : usuario_id

    VARIANTE ||--o{ MOVIMIENTO_INVENTARIO : variante_id
    USUARIO ||--o{ AJUSTE_INVENTARIO_LOTE : usuario_id
    AJUSTE_INVENTARIO_LOTE ||--o{ AJUSTE_INVENTARIO_LOTE_DETALLE : lote_id
    VARIANTE ||--o{ AJUSTE_INVENTARIO_LOTE_DETALLE : variante_id

    IMPORTACION_CATALOGO ||--o{ IMPORTACION_CATALOGO_FILA : importacion_id
    PRODUCTO ||--o{ IMPORTACION_CATALOGO_FILA : producto_id
    VARIANTE ||--o{ IMPORTACION_CATALOGO_FILA : variante_id
    IMPORTACION_CATALOGO ||--o{ IMPORTACION_CATALOGO_INCIDENCIA : importacion_id
    IMPORTACION_CATALOGO_FILA ||--o{ IMPORTACION_CATALOGO_INCIDENCIA : fila_id
    PRODUCTO ||--o{ IMPORTACION_CATALOGO_INCIDENCIA : producto_id
    VARIANTE ||--o{ IMPORTACION_CATALOGO_INCIDENCIA : variante_id

    USUARIO ||--o{ CAMBIO_CATALOGO : usuario_id
    USUARIO ||--o{ CAMBIO_MARKETING_CONFIGURACION : usuario_id
    VENTA ||--o{ AUTORIZACION_PROMOCION_MANUAL : venta_id
    USUARIO ||--o{ AUTORIZACION_PROMOCION_MANUAL : usuario_id
    CLIENTE ||--o{ AUTORIZACION_PROMOCION_MANUAL : cliente_id
```

Lectura rapida:

- `sesion_caja` y `movimiento_caja` cubren apertura, cierre y movimientos manuales
- `movimiento_inventario` es el historial operativo por SKU
- los ajustes masivos tienen cabecera en `ajuste_inventario_lote` y detalle por variante
- importaciones guardan corrida, filas procesadas e incidencias separadas
- auditoria de catalogo y marketing esta modelada como historial orientado a usuario

## Tablas de soporte o configuracion

Estas tablas no son hubs relacionales fuertes, pero forman parte del esquema:

- `configuracion_negocio`
- `sku_sequence`

## Donde veo mas densidad hoy

Si queremos seguir ordenando el modelo, los centros de gravedad actuales son:

1. `variante`: inventario, compras, ventas, apartados, presupuestos, assets e importacion
2. `usuario`: ventas, apartados, compras, caja, auditoria y autorizaciones
3. `cliente`: ventas, apartados, presupuestos, promociones manuales y nivel de lealtad

## Siguiente mejora util para este mapa

Si te sirve, el siguiente paso natural es sacar una version "solo negocio" con menos tablas tecnicas, por ejemplo:

- catalogo y stock
- ventas y apartados
- clientes y lealtad
- caja

Esa version seria mejor para discutir flujo con equipo no tecnico.
