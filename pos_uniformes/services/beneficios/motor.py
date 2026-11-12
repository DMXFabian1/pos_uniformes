"""Motor central de beneficios: cálculo puro (T1, M1a).

`calcular(EntradaVenta) -> Calculo` decide, en un solo lugar y una sola vez,
el precio de cada línea, su descuento, su consumo del tope, su parte del
redondeo y del saldo, su base de Monedero y de Leal, y la comisión de
tarjeta. Cada decisión deja su motivo (`motivos.py`).

Puro: sin base de datos, sin Qt, sin impresoras, sin red, sin reloj y sin
azar. La misma entrada da siempre el mismo resultado, sin importar el orden
de las líneas (I5, D1, C8, Q6).

Orden de las reglas (§2.4 del diseño):
1. Rebaja (E7, C7): cobra el precio rebajado y nada más.
2. Candidatos de descuento: mayoreo (C4, sin 3pz), empleada con su nivel y
   el máximo de uniforme, «otra persona» al 5 % parejo (R2).
3. Tope de empleada por pieza (C8, C9, P4): primero el mayor precio de lista.
   La pieza que cabe consume el tope aunque luego gane el mayoreo (A3).
4. Gana el mayor; un descuento de $0 respeta la modalidad (C4).
5. Redondeo R1 del ticket, repartido entre las líneas (I8, D2).
6. Saldo (C2), repartido en proporción (Q2).
7. Base y abono de Monedero (C2, C4, T9, D1 del código).
8. Base de Leal (C1, C2).
9. Comisión de tarjeta, una sola vez (T4).

Un mismo SKU con categorías distintas se rechaza (A2, `contrato.py`).

No incluye devoluciones (M4/M5) ni H1–H8.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal

from pos_uniformes.services.beneficios import motivos as M
from pos_uniformes.services.beneficios.contrato import (
    CERO,
    CIEN,
    MEDIO_EFECTIVO,
    MEDIO_MONEDERO,
    MEDIO_TARJETA,
    MODALIDAD_DESCUENTO,
    ORIGEN_KIOSKO_SIN_CONEXION,
    Calculo,
    Descuento,
    EntradaInvalida,
    EntradaVenta,
    LineaCalculo,
    LineaEntrada,
    MonederoCalculo,
    Pago,
    validar,
)
from pos_uniformes.services.beneficios.reparto import (
    CENT,
    clave_orden,
    mayor_residuo,
    redondeo_tienda,
    repartir_redondeo,
)

VERSION_MOTOR = "M1a-2026-11-11"

FUENTE_MAYOREO = "mayoreo"
FUENTE_EMPLEADA = "empleada"
FUENTE_OTRA_PERSONA = "otra_persona"


def _q(valor: Decimal) -> Decimal:
    """Al centavo como hoy (`quantize` con el contexto por omisión: mitad al par)."""
    return valor.quantize(CENT, rounding=ROUND_HALF_EVEN)


# ─── Agrupación (Q6, P3, D1) ─────────────────────────────────────────────


@dataclass
class _Grupo:
    linea_uid: str
    origenes: list[tuple[str, int]]
    base: LineaEntrada
    cantidad: int
    motivos: list[str] = field(default_factory=list)

    @property
    def clave(self) -> tuple[str, str]:
        return clave_orden(self.base.sku, self.linea_uid)

    @property
    def rebajada(self) -> bool:
        return self.base.rebaja is not None

    @property
    def es_3pz(self) -> bool:
        return bool(self.base.promo_3pz)

    @property
    def precio_unitario(self) -> Decimal:
        return self.base.rebaja.precio if self.base.rebaja is not None else self.base.precio_lista

    @property
    def importe(self) -> Decimal:
        return (self.precio_unitario * self.cantidad).quantize(CENT)

    @property
    def importe_lista(self) -> Decimal:
        return (self.base.precio_lista * self.cantidad).quantize(CENT)


def _llave_q6(linea: LineaEntrada):
    """Condiciones económicas y de beneficios que deben ser idénticas para agrupar."""
    rebaja = None if linea.rebaja is None else (linea.rebaja.tipo, linea.rebaja.precio)
    return (linea.sku, linea.precio_lista, rebaja, bool(linea.promo_3pz), linea.categoria)


def _agrupar(lineas: tuple[LineaEntrada, ...]) -> list[_Grupo]:
    """Q6: junta las líneas con condiciones idénticas; sin SKU no se agrupa.

    La línea agrupada toma el menor `linea_uid` y conserva todos (D1, P3).
    El resultado sale ordenado por `clave_orden`, no por orden de captura."""
    por_llave: dict = {}
    sueltas: list[_Grupo] = []
    for linea in lineas:
        if linea.sku is None:
            sueltas.append(_Grupo(linea.linea_uid, [(linea.linea_uid, linea.cantidad)], linea, linea.cantidad))
            continue
        por_llave.setdefault(_llave_q6(linea), []).append(linea)
    grupos = list(sueltas)
    for miembros in por_llave.values():
        miembros = sorted(miembros, key=lambda l: l.linea_uid)
        g = _Grupo(
            linea_uid=miembros[0].linea_uid,
            origenes=[(m.linea_uid, m.cantidad) for m in miembros],
            base=miembros[0],
            cantidad=sum(m.cantidad for m in miembros),
        )
        if len(miembros) > 1:
            g.motivos.append(M.LINEAS_AGRUPADAS)
        grupos.append(g)
    return sorted(grupos, key=lambda g: g.clave)


# ─── Descuentos (pasos 1 a 4) ────────────────────────────────────────────


@dataclass
class _Desc:
    pct: Decimal = Decimal("0")
    importe: Decimal = CERO
    fuente: str | None = None
    piezas_nivel: int = 0
    piezas_base: int = 0       # piezas con el % parejo de empleada (no las que ganó el mayoreo)
    consumo_tope: Decimal = CERO


def _es_uniforme(linea: LineaEntrada, entrada: EntradaVenta) -> bool:
    categoria = " ".join(str(linea.categoria or "").split()).lower()
    return categoria not in entrada.reglas.categorias_no_uniforme


def _pct_y_fuente(pct_empleada: Decimal, pct_mayoreo: Decimal, fuente_empleada: str) -> tuple[Decimal, str | None]:
    """Gana el mayor. En empate gana el mayoreo (es la modalidad elegida)."""
    if pct_mayoreo > 0 and pct_mayoreo >= pct_empleada:
        return pct_mayoreo, FUENTE_MAYOREO
    if pct_empleada > 0:
        return pct_empleada, fuente_empleada
    return Decimal("0"), None


def _descuentos(grupos: list[_Grupo], entrada: EntradaVenta, motivos_ticket: list[str]) -> dict[str, _Desc]:
    r = entrada.reglas
    base = r.pct_base_empleada
    sin_conexion = entrada.origen_calculo == ORIGEN_KIOSKO_SIN_CONEXION

    # Mayoreo (C4, C12)
    pct_may = Decimal("0")
    if entrada.modalidad_mayorista == MODALIDAD_DESCUENTO:
        if sin_conexion:
            motivos_ticket.append(M.SIN_CONEXION_SIN_MAYOREO)
        else:
            c = entrada.cliente
            if c is None or not c.pct_mayoreo or c.pct_mayoreo <= 0:
                raise EntradaInvalida("modalidad «descuento» sin un % de mayoreo del cliente")
            pct_may = c.pct_mayoreo

    resultado = {g.linea_uid: _Desc() for g in grupos}

    def pct_mayoreo_de(g: _Grupo) -> Decimal:
        if g.rebajada or pct_may <= 0:
            return Decimal("0")
        if g.es_3pz:
            if M.TRES_PZ_SIN_MAYOREO not in g.motivos:
                g.motivos.append(M.TRES_PZ_SIN_MAYOREO)
            return Decimal("0")
        return pct_may

    for g in grupos:
        if g.rebajada:
            g.motivos.append(M.REBAJA_SIN_OTRO_BENEFICIO)

    # Empleada
    modo_ticket = False
    # Líneas que van al % parejo de empleada. El motivo EMPLEADA_BASE se pone al
    # final, solo si el mayoreo no les gana (auditoría M1a: antes salía aunque
    # la pieza se cobrara con mayoreo).
    al_base: set[str] = set()
    pct_empleada: dict[str, tuple[Decimal, Decimal, int]] = {}  # uid -> (pct nivel, pct resto, piezas al nivel)
    fuente_emp = FUENTE_EMPLEADA
    if entrada.descuento_empleada:
        comp = entrada.compradora
        nivel = comp.pct_nivel if comp is not None else None
        con_nivel = comp is not None and nivel is not None and nivel > base
        if con_nivel and sin_conexion:
            con_nivel = False
            motivos_ticket.append(M.SIN_CONEXION_EMPLEADA_BASE)
        if comp is None:
            fuente_emp = FUENTE_OTRA_PERSONA
            motivos_ticket.append(M.OTRA_PERSONA_5)
        if con_nivel:
            # C8, C9, P4: por pieza, primero el mayor precio de lista; desempata la clave de I5.
            candidatas = []
            for g in grupos:
                if g.rebajada:
                    continue
                if g.es_3pz:
                    g.motivos.append(M.TRES_PZ_EMPLEADA_BASE)
                    pct_empleada[g.linea_uid] = (base, base, 0)
                    continue
                pct_linea = nivel
                if _es_uniforme(g.base, entrada) and pct_linea > r.tope_pct_uniforme:
                    pct_linea = r.tope_pct_uniforme
                    g.motivos.append(M.TOPE_UNIFORME_10)
                # A3 (Daniel, 11/11): la pieza que cabe consume el tope aunque luego
                # gane el mayoreo, como hoy (`incentivo_empleada_service.repartir`).
                if pct_linea <= base:
                    al_base.add(g.linea_uid)
                    pct_empleada[g.linea_uid] = (base, base, 0)
                    continue
                candidatas.append((g, pct_linea))
            queda = comp.restante_tope
            for g, pct_linea in sorted(candidatas, key=lambda t: (-t[0].base.precio_lista, t[0].clave)):
                precio = g.base.precio_lista
                if queda is None or precio <= 0:
                    caben = g.cantidad
                else:
                    caben = min(g.cantidad, int(max(queda, CERO) // precio))
                    queda -= precio * caben
                pct_empleada[g.linea_uid] = (pct_linea, base, caben)
                if caben:
                    # Gana el mayor; en empate, el mayoreo (`_pct_y_fuente`).
                    gana_mayoreo = pct_mayoreo_de(g) >= pct_linea
                    g.motivos.append(M.TOPE_CONSUMIDO_CON_MAYOREO if gana_mayoreo else M.EMPLEADA_NIVEL)
                else:
                    g.motivos.append(M.TOPE_MES_AGOTADO)
                if 0 < caben < g.cantidad:
                    g.motivos.append(M.TOPE_MES_AGOTADO)
        else:
            pct_parejo = r.pct_otra_persona if comp is None else base
            hay_rebajadas = any(g.rebajada for g in grupos)
            if not hay_rebajadas and pct_may <= 0:
                modo_ticket = True  # como hoy: el % sobre el subtotal, repartido entre las líneas
            for g in grupos:
                if not g.rebajada:
                    pct_empleada[g.linea_uid] = (pct_parejo, pct_parejo, 0)
                    if comp is not None:
                        al_base.add(g.linea_uid)

    if modo_ticket:
        pct = r.pct_otra_persona if entrada.compradora is None else base
        con_desc = [g for g in grupos if not g.rebajada]
        total_desc = _q(sum((g.importe for g in con_desc), CERO) * pct / CIEN)
        partes = mayor_residuo(total_desc, [g.importe for g in con_desc], [g.clave for g in con_desc]) if con_desc else []
        motivos_ticket.append(M.DESCUENTO_TICKET_REPARTIDO)
        for g, parte in zip(con_desc, partes):
            if g.linea_uid in al_base:
                g.motivos.append(M.EMPLEADA_BASE)
            resultado[g.linea_uid] = _Desc(pct=pct, importe=parte, fuente=fuente_emp, piezas_base=g.cantidad)
        return resultado

    for g in grupos:
        if g.rebajada:
            continue
        pmay = pct_mayoreo_de(g)
        p_nivel, p_resto, caben = pct_empleada.get(g.linea_uid, (Decimal("0"), Decimal("0"), 0))
        resto = g.cantidad - caben
        pct_a, fuente_a = _pct_y_fuente(p_nivel, pmay, fuente_emp)
        pct_b, fuente_b = _pct_y_fuente(p_resto, pmay, fuente_emp)
        importe = CERO
        if caben and resto and pct_a == pct_b:
            # Mismo % en toda la línea (con A3, el mayoreo gana las piezas dentro y
            # fuera del tope): un solo redondeo, como hoy `dps.descuento` por renglón.
            importe = _q(g.precio_unitario * g.cantidad * pct_a / CIEN)
        else:
            if caben:
                importe += _q(g.precio_unitario * caben * pct_a / CIEN)
            if resto:
                importe += _q(g.precio_unitario * resto * pct_b / CIEN)
        con_nivel_real = caben if fuente_a == fuente_emp and caben else 0
        piezas_base = resto if resto and fuente_b == fuente_emp else 0
        if g.linea_uid in al_base and piezas_base:
            g.motivos.append(M.EMPLEADA_BASE)
        fuente = fuente_a if caben else fuente_b
        if caben and resto and fuente_a != fuente_b:
            fuente = fuente_emp if fuente_emp in (fuente_a, fuente_b) else fuente_a
        if fuente == FUENTE_MAYOREO:
            g.motivos.append(M.MAYOREO)
            if pct_empleada.get(g.linea_uid):
                g.motivos.append(M.GANA_MAYOREO)
        elif fuente is not None and pmay > 0:
            g.motivos.append(M.GANA_EMPLEADA)
        resultado[g.linea_uid] = _Desc(
            pct=pct_a if caben else pct_b,
            importe=importe,
            fuente=fuente,
            piezas_nivel=con_nivel_real,
            piezas_base=piezas_base,
            # A3: consume el tope toda pieza que cupo, la haya ganado el nivel o el mayoreo.
            consumo_tope=(g.base.precio_lista * caben).quantize(CENT),
        )
    return resultado


# ─── Saldo y comisión ────────────────────────────────────────────────────


def _al_medio_peso_hacia_arriba(monto: Decimal) -> Decimal:
    medios = (monto * 2).to_integral_value(rounding="ROUND_CEILING")
    return (medios / 2).quantize(CENT)


def canje_ajustado(total: Decimal, disponible: Decimal, deseado: Decimal | None = None) -> Decimal:
    """El saldo que se puede usar: el mismo cálculo de hoy (`monedero_service`)."""
    tope = min(disponible, total)
    if deseado is not None:
        tope = min(tope, deseado)
    if tope <= 0:
        return CERO
    if tope >= total:
        return total.quantize(CENT)
    resto = _al_medio_peso_hacia_arriba(total - tope)
    canje = (total - resto).quantize(CENT)
    return canje if canje > 0 else CERO


def neto_con_comision(monto: Decimal, pct_comision: Decimal) -> Decimal:
    """Lo que deja la terminal: el monto menos su %, con la regla R1 (como hoy)."""
    con_comision = _q(monto * (CIEN - pct_comision) / CIEN)
    return redondeo_tienda(con_comision)


def base_monedero_con_comision(base: Decimal, pagado: Decimal, comision: Decimal) -> Decimal:
    """Regla B (Daniel, 2026-11-12): con tarjeta, el Monedero se gana sobre lo
    que de verdad entra. A la base se le quita la parte de la comisión que le
    toca (comisión × base / lo pagado con dinero), truncado al centavo.

    Pago de $1,000 con tarjeta → comisión $45 → base $955. Sin comisión, la
    base no cambia. La usan el motor y el abono del servidor, para que el
    ticket y el Monedero digan lo mismo."""
    if base <= 0:
        return CERO
    if comision <= 0 or pagado <= 0:
        return base.quantize(CENT)
    quitar = comision if base >= pagado else comision * base / pagado
    resto = (base - quitar).quantize(CENT, rounding=ROUND_DOWN)
    return resto if resto > 0 else CERO


# ─── Cálculo ─────────────────────────────────────────────────────────────


def calcular(entrada: EntradaVenta) -> Calculo:
    validar(entrada)
    r = entrada.reglas
    sin_conexion = entrada.origen_calculo == ORIGEN_KIOSKO_SIN_CONEXION
    motivos_ticket: list[str] = []

    grupos = _agrupar(entrada.lineas)
    descuentos = _descuentos(grupos, entrada, motivos_ticket)

    # C4: la modalidad elegida se respeta aunque el descuento salga en $0.
    modalidad = entrada.modalidad_mayorista
    descuento_aplicado = any(
        d.fuente == FUENTE_MAYOREO and d.importe > 0 for d in descuentos.values()
    )
    if modalidad == MODALIDAD_DESCUENTO and not sin_conexion and not descuento_aplicado:
        motivos_ticket.append(M.MAYOREO_SIN_LINEAS_ELEGIBLES)

    # Paso 5: redondeo R1 repartido (I8, D2).
    cobrados_pre = [g.importe - descuentos[g.linea_uid].importe for g in grupos]
    total_pre = sum(cobrados_pre, CERO).quantize(CENT)
    total = redondeo_tienda(total_pre)
    ajuste = (total - total_pre).quantize(CENT)
    red = repartir_redondeo(ajuste, cobrados_pre, [g.importe_lista for g in grupos], [g.clave for g in grupos])
    cobrados = [(c + p).quantize(CENT) for c, p in zip(cobrados_pre, red.partes)]
    if sum(cobrados, CERO) != total:
        raise AssertionError("I8: las líneas no suman el total del ticket")
    for i, g in enumerate(grupos):
        if red.partes[i] != 0:
            g.motivos.append(M.REDONDEO_REPARTIDO)
        if i in red.excepcion_d2:
            g.motivos.append(M.REDONDEO_EXCEPCION_D2)
    if red.excepcion_d2:
        motivos_ticket.append(M.REDONDEO_EXCEPCION_D2)

    # Paso 6: saldo (C2, C12).
    cliente = entrada.cliente
    canje = CERO
    if entrada.saldo_a_usar > 0:
        if sin_conexion:
            motivos_ticket.append(M.SIN_CONEXION_SIN_SALDO)
        elif cliente is None or not cliente.activo:
            raise EntradaInvalida("Se pidió usar saldo sin un cliente activo")
        else:
            canje = canje_ajustado(total, entrada.saldo_disponible, entrada.saldo_a_usar)
    claves = [g.clave for g in grupos]
    partes_saldo = mayor_residuo(canje, cobrados, claves) if canje > 0 else [CERO] * len(grupos)
    if canje > 0:
        for g, p in zip(grupos, partes_saldo):
            if p > 0:
                g.motivos.append(M.SALDO_REPARTIDO)

    # Paso 9 (va antes del Monedero por la regla B): pagos y comisión (T4, D6).
    por_cobrar = (total - canje).quantize(CENT)
    if entrada.pagos:
        if any(p.medio == MEDIO_MONEDERO for p in entrada.pagos):
            raise EntradaInvalida("pagos: el saldo lo decide el motor; no se manda como pago")
        if sum((p.importe for p in entrada.pagos), CERO) != por_cobrar:
            raise EntradaInvalida(f"pagos: no suman lo que queda por cobrar ({por_cobrar})")
        pagos = [p for p in entrada.pagos if p.importe > 0]
    else:
        medio = MEDIO_TARJETA if entrada.pago_tarjeta else MEDIO_EFECTIVO
        pagos = [Pago(medio, por_cobrar)] if por_cobrar > 0 else []
    if canje > 0:
        pagos.append(Pago(MEDIO_MONEDERO, canje))
    con_tarjeta = sum((p.importe for p in pagos if p.medio == MEDIO_TARJETA), CERO)
    comision = CERO
    if con_tarjeta > 0:
        comision = max(con_tarjeta - neto_con_comision(con_tarjeta, r.pct_comision_tarjeta), CERO)
        motivos_ticket.append(M.COMISION_UNICA)
    pagado_dinero = [(c - p).quantize(CENT) for c, p in zip(cobrados, partes_saldo)]
    comisiones = mayor_residuo(comision, pagado_dinero, claves) if comision > 0 else [CERO] * len(grupos)
    neto = (por_cobrar - comision).quantize(CENT)

    # Paso 7: Monedero (C2, C4, T9; con descuento de empleada no hay Monedero).
    tasa = cliente.tasa_monedero if cliente is not None and cliente.tasa_monedero else None
    bloqueo = None
    if tasa is None or tasa <= 0:
        bloqueo = M.SIN_PROGRAMA
    elif not cliente.activo:
        bloqueo = M.CLIENTE_INACTIVO
    elif modalidad == MODALIDAD_DESCUENTO and not sin_conexion:
        bloqueo = M.MAYOREO_SIN_MONEDERO
    elif entrada.descuento_empleada:
        bloqueo = M.EMPLEADA_SIN_MONEDERO
    if bloqueo:
        motivos_ticket.append(bloqueo)
    bases_mon = []
    for g, cobrado, parte in zip(grupos, cobrados, partes_saldo):
        bases_mon.append(CERO if (bloqueo or g.rebajada) else (cobrado - parte).quantize(CENT))
    monedero = None
    abonos = [CERO] * len(grupos)
    if not bloqueo:
        base_total = sum(bases_mon, CERO).quantize(CENT)
        # Regla B: con tarjeta, se gana sobre lo que deja la terminal.
        base_neta = base_monedero_con_comision(base_total, sum(pagado_dinero, CERO), comision)
        if base_neta != base_total:
            menos = mayor_residuo(base_total - base_neta, bases_mon, claves)
            bases_mon = [(b - m).quantize(CENT) for b, m in zip(bases_mon, menos)]
            base_total = base_neta
            motivos_ticket.append(M.MONEDERO_SIN_COMISION)
        abono = (base_total * tasa / CIEN).quantize(CENT, rounding=ROUND_DOWN) if base_total > 0 else CERO
        if abono > 0:
            abonos = mayor_residuo(abono, bases_mon, claves)
        monedero = MonederoCalculo(tasa=tasa, base=base_total, abono=abono)

    # Paso 8: Leal (C1, C2).
    bases_leal = []
    for g, cobrado, parte in zip(grupos, cobrados, partes_saldo):
        if entrada.descuento_empleada:
            bases_leal.append(CERO)
        elif g.rebajada:
            g.motivos.append(M.REBAJA_SIN_LEAL)
            bases_leal.append(CERO)
        else:
            bases_leal.append((cobrado - parte).quantize(CENT))
    if entrada.descuento_empleada:
        motivos_ticket.append(M.EMPLEADA_SIN_LEAL)

    # Armar el resultado.
    lineas = []
    for i, g in enumerate(grupos):
        d = descuentos[g.linea_uid]
        if g.rebajada:
            clasif = g.base.rebaja.tipo
        elif g.es_3pz:
            clasif = "3pz"
        else:
            clasif = "normal"
        lineas.append(LineaCalculo(
            linea_uid=g.linea_uid,
            lineas_origen=tuple(g.origenes),
            sku=g.base.sku,
            cantidad=g.cantidad,
            precio_lista=g.base.precio_lista,
            precio_unitario=g.precio_unitario,
            importe=g.importe,
            clasificacion_al_vender=clasif,
            piezas_con_nivel=d.piezas_nivel,
            piezas_al_base=d.piezas_base,
            descuento=Descuento(pct=d.pct, importe=d.importe, fuente=d.fuente),
            cobrado_antes_redondeo=cobrados_pre[i],
            parte_redondeo=red.partes[i],
            cobrado=cobrados[i],
            consumo_tope=d.consumo_tope,
            parte_saldo=partes_saldo[i],
            base_monedero=bases_mon[i],
            abono_linea=abonos[i],
            base_leal=bases_leal[i],
            comision_linea=comisiones[i],
            motivos=tuple(dict.fromkeys(g.motivos)),
        ))

    descuento_total = sum((l.descuento.importe for l in lineas), CERO).quantize(CENT)
    return Calculo(
        version_motor=VERSION_MOTOR,
        version_reglas=r.version,
        origen_calculo=entrada.origen_calculo,
        fecha_venta=entrada.fecha_venta,
        vendedora=entrada.vendedora,
        lineas=tuple(lineas),
        subtotal_lista=sum((g.importe_lista for g in grupos), CERO).quantize(CENT),
        subtotal=sum((g.importe for g in grupos), CERO).quantize(CENT),
        descuento_total=descuento_total,
        ahorro_rebajas=sum((g.importe_lista - g.importe for g in grupos if g.rebajada), CERO).quantize(CENT),
        total_antes_redondeo=total_pre,
        redondeo=ajuste,
        redondeo_rondas=red.rondas,
        redondeo_excepcion_d2=red.importe_excepcion,
        total=total,
        saldo_usado=canje,
        por_cobrar=por_cobrar,
        pagos=tuple(pagos),
        comision_tarjeta=comision,
        neto_tienda=neto,
        modalidad_mayorista_elegida=modalidad,
        descuento_aplicado=descuento_aplicado,
        descuento_empleada=entrada.descuento_empleada,
        monedero=monedero,
        base_leal_total=sum(bases_leal, CERO).quantize(CENT),
        consumo_tope_total=sum((l.consumo_tope for l in lineas), CERO).quantize(CENT),
        motivos_ticket=tuple(dict.fromkeys(motivos_ticket)),
    )
