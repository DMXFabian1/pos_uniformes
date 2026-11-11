"""Códigos de motivo del motor de beneficios (T1).

Cada decisión del motor deja un código que explica por qué una línea llevó
(o no) un descuento, un abono o un ajuste. Los códigos son estables: la
fotografía de la venta (T2) los guarda y la sombra de M1b los compara.
"""

from __future__ import annotations

# ─── Rebajas (E7, C7, C13) ───
REBAJA_SIN_OTRO_BENEFICIO = "REBAJA_SIN_OTRO_BENEFICIO"

# ─── Mayorista (C4, T9) ───
MAYOREO = "MAYOREO"
TRES_PZ_SIN_MAYOREO = "3PZ_SIN_MAYOREO"
MAYOREO_SIN_LINEAS_ELEGIBLES = "MAYOREO_SIN_LINEAS_ELEGIBLES"
MAYOREO_SIN_MONEDERO = "MAYOREO_SIN_MONEDERO"

# ─── Empleadas (C8, C9, R2, D1 del código) ───
EMPLEADA_NIVEL = "EMPLEADA_NIVEL"
TOPE_UNIFORME_10 = "TOPE_UNIFORME_10"
TRES_PZ_EMPLEADA_BASE = "3PZ_EMPLEADA_BASE"
TOPE_MES_AGOTADO = "TOPE_MES_AGOTADO"
EMPLEADA_BASE = "EMPLEADA_BASE"
OTRA_PERSONA_5 = "OTRA_PERSONA_5"
DESCUENTO_TICKET_REPARTIDO = "DESCUENTO_TICKET_REPARTIDO"
EMPLEADA_SIN_MONEDERO = "EMPLEADA_SIN_MONEDERO"
EMPLEADA_SIN_LEAL = "EMPLEADA_SIN_LEAL"

# ─── Gana el mayor ───
GANA_MAYOREO = "GANA_MAYOR(mayoreo)"
GANA_EMPLEADA = "GANA_MAYOR(empleada)"

# ─── Redondeo (R1, I8, D2) ───
REDONDEO_REPARTIDO = "REDONDEO_REPARTIDO"
REDONDEO_EXCEPCION_D2 = "REDONDEO_EXCEPCION_D2"

# ─── Monedero y Leal (C2, T9) ───
SALDO_REPARTIDO = "SALDO_REPARTIDO"
SIN_PROGRAMA = "SIN_PROGRAMA"
CLIENTE_INACTIVO = "CLIENTE_INACTIVO"
REBAJA_SIN_LEAL = "REBAJA_SIN_LEAL"

# ─── Tarjeta (T4) ───
COMISION_UNICA = "T4_COMISION_UNICA"

# ─── Sin conexión (C12) ───
SIN_CONEXION_SIN_MAYOREO = "SIN_CONEXION_SIN_MAYOREO"
SIN_CONEXION_SIN_SALDO = "SIN_CONEXION_SIN_SALDO"
SIN_CONEXION_EMPLEADA_BASE = "SIN_CONEXION_EMPLEADA_BASE"

# ─── Agrupación (Q6, P3) ───
LINEAS_AGRUPADAS = "LINEAS_AGRUPADAS_Q6"

# ─── Entrada rechazada (A2, auditoría M1a) ───
# No es un motivo de línea: es el código de `SkuConCategoriasIncompatibles`,
# para que la sombra de M1b registre la discrepancia sin tocar la venta.
SKU_CATEGORIAS_INCOMPATIBLES = "SKU_CATEGORIAS_INCOMPATIBLES"

# ─── A3 (Daniel, 11/11): mayoreo y empleada a la vez ───
# La pieza cupo en el tope y lo consumió (C8, C9, como hoy), pero el mayoreo
# le dio un % igual o mayor que el del nivel y es el que se cobró.
TOPE_CONSUMIDO_CON_MAYOREO = "TOPE_CONSUMIDO_CON_MAYOREO"
