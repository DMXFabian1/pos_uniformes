"""La pantalla nueva de «Revisar conteo» (tanda 3, 2026-11-15), sin Qt.

`ConteoRevisionDialog` solo pinta lo que sale de aquí:

- **Encabezado**: la prenda (con su color una vez) o la escuela si la jornada
  abarca varias prendas; «Contó Stayce · lun 5 oct · hace 41 días · 15 tallas».
- **Franja de chips** en una línea: primero el ajuste («Corrige 4 tallas ·
  faltan 7 · sobran 0 · −$1,385» o «Todo cuadra») y luego Urgente, Pedir y
  Surtir con su conteo. Un chip en 0 va gris y sin relleno. Surtir va siempre
  en gris con la nota de las cajas (no se recuentan desde el 16-jul): se ve,
  pero no se prende como acción. Tocar un chip filtra; tocarlo otra vez, no.
- **Tabla**: una fila por talla (TALLA · EL SISTEMA DECÍA · CONTÓ · DIF ·
  VENDIDAS DESDE · QUEDA HOY · QUÉ HACER · PEDIR), sin columna Prenda. Con
  varias prendas, una fila de grupo por prenda (nombre + color una vez). Las
  tallas con diferencia van primero dentro de cada prenda y luego el separador
  «sin diferencia (N)»; «en su orden» deja el orden de la hoja.
- **Botones**: «Corregir inventario (4 tallas, −7 pz)» o «Marcar como
  revisado»; «Hoja de pedido» solo con algo pedido; ya revisada, sin Corregir
  ni No usar.
- **Listo**: el texto después de corregir o de no usar, y cuál es la
  siguiente jornada por revisar.

No cambia ninguna regla: `revision_service.sugerir` decide el estado y
`conteo_resumen_service` la diferencia; esto solo las acomoda y las cuenta.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from pos_uniformes.services.conteo_revision_vista_service import (
    _MENOS,
    cuando_se_conto,
    etiqueta_sin_ritmo,
    fecha_tienda,
    dia_mes,
    pesos,
    que_hacer,
)
from pos_uniformes.services.revision_service import (
    NO_SE_MUEVE,
    PEDIR,
    SIN_DATOS,
    SURTIR,
    URGENTE,
)

# --- chips ---------------------------------------------------------------------------

CHIP_AJUSTE = "AJUSTE"
CHIP_URGENTE = URGENTE
CHIP_PEDIR = PEDIR
CHIP_SURTIR = SURTIR
CHIPS = (CHIP_AJUSTE, CHIP_URGENTE, CHIP_PEDIR, CHIP_SURTIR)

# Tonos (los pinta conteo_revision_styles): el de cada chip con algo, y «cero».
TONO_AJUSTE = "ajuste"
TONO_PELIGRO = "peligro"
TONO_ADVERTENCIA = "advertencia"
TONO_NEUTRO = "neutro"
TONO_CERO = "cero"

#: Las 31 cajas no se recuentan desde el 16-jul: «en cajas» no está verificado.
NOTA_CAJAS = "cajas sin recontar desde el 16-jul"

_NOMBRE_CHIP = {CHIP_URGENTE: "Urgente", CHIP_PEDIR: "Pedir", CHIP_SURTIR: "Surtir"}
_SIN_COLOR = ("", "UNICO", "ÚNICO", "SIN COLOR")


@dataclass(frozen=True)
class Chip:
    clave: str
    texto: str
    n: int              # cuántas tallas trae el filtro
    tono: str
    tocable: bool       # con 0 no filtra nada
    nota: str = ""


def _tallas(n: int) -> str:
    return "1 talla" if n == 1 else f"{n} tallas"


def _con_diferencia(t) -> bool:
    return t is not None and int(t.diferencia) != 0


def en_grupo(clave: str, linea, talla_ajuste=None) -> bool:
    """¿La talla entra en el filtro de ese chip?"""
    if clave == CHIP_AJUSTE:
        return _con_diferencia(talla_ajuste)
    return linea.estado == clave


def texto_chip_ajuste(ajuste, *, ya_revisada: bool = False, aplicada: bool = True) -> str:
    """«Corrige 4 tallas · faltan 7 · sobran 0 · −$1,385» o «Todo cuadra».

    Ya revisada: lo que se corrigió («Corrigió 4 tallas · faltaban 7 · sobraban 0»)
    o, si no se usó, cuántas traían diferencia."""
    if ajuste is None:
        return "Sin resumen del ajuste"
    con_dif = [t for t in ajuste.tallas if _con_diferencia(t)]
    if not con_dif:
        return "Todo cuadra"
    if ya_revisada:
        faltan = -sum(t.diferencia for t in con_dif if t.diferencia < 0)
        sobran = sum(t.diferencia for t in con_dif if t.diferencia > 0)
        if not aplicada:
            return f"{_tallas(len(con_dif))} con diferencia · no se usó"
        return f"Corrigió {_tallas(len(con_dif))} · faltaban {faltan} · sobraban {sobran}"
    n = ajuste.tallas_a_corregir
    if n == 0:
        return "Todo cuadra"
    return f"Corrige {_tallas(n)} · faltan {ajuste.salen} · sobran {ajuste.entran} · {pesos(ajuste.valor, signo=True)}"


def chips(lineas: Iterable, ajuste=None, *, ya_revisada: bool = False, aplicada: bool = True) -> list[Chip]:
    """La franja: el ajuste primero y luego Urgente, Pedir y Surtir."""
    lineas = list(lineas)
    por_id = tallas_por_id(ajuste)
    n_ajuste = sum(1 for l in lineas if _con_diferencia(por_id.get(l.conteo_id)))
    salida = [Chip(
        CHIP_AJUSTE, texto_chip_ajuste(ajuste, ya_revisada=ya_revisada, aplicada=aplicada), n_ajuste,
        TONO_AJUSTE if n_ajuste else TONO_CERO, n_ajuste > 0,
    )]
    for clave, tono in ((CHIP_URGENTE, TONO_PELIGRO), (CHIP_PEDIR, TONO_ADVERTENCIA), (CHIP_SURTIR, TONO_NEUTRO)):
        n = sum(1 for l in lineas if l.estado == clave)
        nota = NOTA_CAJAS if clave == CHIP_SURTIR else ""
        salida.append(Chip(clave, f"{_NOMBRE_CHIP[clave]} {n}", n, tono if n else TONO_CERO, n > 0, nota))
    return salida


def tocar_chip(activo: str | None, clave: str) -> str | None:
    """El filtro después de tocar un chip: lo prende, o lo quita si ya estaba."""
    return None if activo == clave else clave


# --- encabezado ----------------------------------------------------------------------

def _limpio(producto: str, titulo: str) -> str:
    from pos_uniformes.services.conteo_hoja_carta_service import nombre_para_hoja

    return nombre_para_hoja(producto, titulo)


def _colores(lineas) -> list[str]:
    vistos: list[str] = []
    for l in lineas:
        color = str(getattr(l, "color", "") or "").strip()
        if color.upper() in _SIN_COLOR:
            continue
        if color.lower() not in [c.lower() for c in vistos]:
            vistos.append(color)
    return vistos


def _bonito(color: str) -> str:
    """'AZUL MARINO' → 'Azul Marino'; lo que ya trae minúsculas se queda."""
    return color.title() if color.isupper() else color


def nombre_prenda(producto: str, lineas, titulo: str) -> str:
    """El nombre de la prenda con su color una vez («Prenda 0 · Azul»); sin el
    color si ya viene en el nombre o si la prenda trae varios colores."""
    nombre = _limpio(producto, titulo)
    colores = _colores(lineas)
    if len(colores) == 1 and colores[0].lower() not in nombre.lower():
        return f"{nombre} · {_bonito(colores[0])}"
    return nombre


def talla_texto(linea, *, varios_colores: bool) -> str:
    """La talla sola; con el color solo si la prenda trae varios."""
    color = str(getattr(linea, "color", "") or "").strip()
    if varios_colores and color.upper() not in _SIN_COLOR:
        return f"{linea.talla} {_bonito(color)}"
    return str(linea.talla)


def prendas(lineas: Iterable) -> list[tuple[str, list]]:
    """[(producto, tallas)] en el orden en que llegan (el de la hoja)."""
    grupos: dict[str, list] = {}
    for l in lineas:
        grupos.setdefault(l.producto, []).append(l)
    return list(grupos.items())


def titulo_encabezado(lineas: Iterable, titulo_jornada: str) -> str:
    """Una prenda: «Playera Chazarilla · Azul Marino · Básicos». Varias: la escuela."""
    grupos = prendas(lineas)
    titulo_jornada = str(titulo_jornada or "")
    if len(grupos) != 1:
        return titulo_jornada
    producto, tallas = grupos[0]
    nombre = nombre_prenda(producto, tallas, titulo_jornada)
    contexto = titulo_jornada.split(" · ")[0].strip()
    if contexto and contexto.lower() not in nombre.lower():
        return f"{nombre} · {contexto}"
    return nombre


def subtitulo_encabezado(*, quien: str, contado, lineas: Iterable, hoy=None) -> str:
    """«Contó Stayce Chavarria · lun 5 oct · hace 41 días · 15 tallas» (+ «· 4 prendas»)."""
    lineas = list(lineas)
    partes = [f"Contó {quien}" if quien else "Contó (sin nombre)"]
    cuando = cuando_se_conto(contado, hoy)
    if cuando:
        partes.append(cuando)
    partes.append(_tallas(len(lineas)))
    n_prendas = len(prendas(lineas))
    if n_prendas > 1:
        partes.append(f"{n_prendas} prendas")
    return " · ".join(partes)


def texto_pedido(pedidos: Mapping[int, int | None]) -> str:
    """«Tu pedido: 21 piezas en 1 talla» o '' si no hay nada pedido."""
    piezas = sum(p for p in pedidos.values() if p)
    tallas = sum(1 for p in pedidos.values() if p)
    if not piezas:
        return ""
    return f"Tu pedido: <b>{piezas}</b> piezas en {_tallas(tallas)}"


# --- tabla ---------------------------------------------------------------------------

COLUMNAS = ("TALLA", "EL SISTEMA DECÍA", "CONTÓ", "DIF", "VENDIDAS DESDE", "QUEDA HOY", "QUÉ HACER", "PEDIR")
COL_TALLA, COL_SISTEMA, COL_CONTO, COL_DIF, COL_VENDIDAS, COL_QUEDA, COL_QUE, COL_PEDIDO = range(len(COLUMNAS))

FILA_PRENDA = "prenda"
FILA_SEPARADOR = "separador"
FILA_TALLA = "talla"

# Tonos de celda (solo la letra; los pinta la UI).
DIF_FALTAN = "faltan"
DIF_SOBRAN = "sobran"
DIF_CUADRA = "cuadra"
QUE_URGENTE = "urgente"
QUE_PEDIR = "pedir"
QUE_GRIS = "gris"
QUE_OJO = "ojo"


@dataclass(frozen=True)
class Fila:
    tipo: str                         # prenda | separador | talla
    texto: str = ""                   # prenda y separador
    conteo_id: int | None = None
    celdas: tuple[str, ...] = ()      # talla: una por columna (la de PEDIR = lo pedido)
    tono_dif: str = ""
    tono_queda: str = ""
    tono_que: str = ""
    tono_conto: str = ""              # «0» en rojo
    ayuda_que: str = ""               # tooltip de «qué hacer» (las cajas)
    ojo: str = ""                     # «otro ajuste el 20 oct»: la marca ⚠ va en DIF (tooltip)


def tallas_por_id(ajuste) -> dict:
    return {} if ajuste is None else {t.conteo_id: t for t in ajuste.tallas}


def con_signo(n: int) -> str:
    """'−4' / '+2' / '·' (cuadra)."""
    n = int(n)
    if n == 0:
        return "·"
    return f"{_MENOS}{-n}" if n < 0 else f"+{n}"


def queda_texto(n: int) -> str:
    """'4' o, si sale negativo, '−1 · recontar'."""
    n = int(n)
    return f"{_MENOS}{-n} · recontar" if n < 0 else str(n)


#: La marca corta del otro ajuste; va pegada a la diferencia, no en «qué hacer».
MARCA_OJO = "⚠"


def texto_ojo(t) -> str:
    """«otro ajuste el 20 oct» si la talla tuvo otro ajuste que Corregir no toca; '' si no."""
    if t is None or t.ajuste_posterior is None or t.ajustado:
        return ""
    return f"otro ajuste el {dia_mes(fecha_tienda(t.ajuste_posterior))}"


def _que_hacer_talla(linea, t) -> tuple[str, str, str]:
    """(texto, tono, ayuda) de «qué hacer»: el motivo real de la tanda 1 y las
    cajas en gris (sin recontar). Solo la acción: el ⚠ del otro ajuste va en
    DIF (con la fecha en el tooltip y en el «por qué») para que no la corte."""
    texto = que_hacer(linea)
    if linea.estado == URGENTE:
        tono = QUE_URGENTE
    elif linea.estado == PEDIR:
        tono = QUE_PEDIR
    elif linea.estado in (SURTIR, NO_SE_MUEVE, SIN_DATOS) or etiqueta_sin_ritmo(linea):
        tono = QUE_GRIS
    else:
        tono = ""
    ayuda = ""
    if getattr(linea, "en_cajas", 0):
        detalle = " · ".join(f"{codigo} ×{n}" for codigo, n in (linea.cajas or ()))
        ayuda = f"En cajas: {detalle or linea.en_cajas} ({NOTA_CAJAS})"
        if linea.estado == SURTIR:
            texto = f"{texto} de cajas*"
        elif not linea.surtir:
            texto = f"{texto} · +{linea.en_cajas} en cajas*"
    return texto, tono, ayuda


def fila_talla(linea, t, pedido: int | None, *, varios_colores: bool = False, ya_revisada: bool = False) -> Fila:
    """Una talla con sus 8 celdas. `t` es su `TallaResumen` (None si no hubo resumen)."""
    if t is not None:
        sistema = str(t.stock_sistema)
        dif = con_signo(t.diferencia)
        tono_dif = DIF_CUADRA if t.diferencia == 0 else (DIF_FALTAN if t.diferencia < 0 else DIF_SOBRAN)
        vendidas = str(t.vendidas_desde)
        # Ya revisada (aplicada o no usada) no se va a corregir: queda lo de hoy.
        queda_n = t.tienda_hoy if (ya_revisada or t.ajustado) else t.queda_hoy
        queda = queda_texto(queda_n)
        tono_queda = "recontar" if queda_n < 0 else ""
    else:
        sistema = dif = vendidas = queda = "—"
        tono_dif = tono_queda = ""
    que, tono_que, ayuda = _que_hacer_talla(linea, t)
    ojo = texto_ojo(t)
    if ojo:
        dif = f"{dif} {MARCA_OJO}"
    celdas = (
        talla_texto(linea, varios_colores=varios_colores), sistema, str(linea.conto), dif, vendidas, queda, que,
        "" if pedido is None else str(pedido),
    )
    return Fila(
        FILA_TALLA, conteo_id=linea.conteo_id, celdas=celdas, tono_dif=tono_dif, tono_queda=tono_queda,
        tono_que=tono_que, tono_conto="cero" if linea.conto == 0 else "", ayuda_que=ayuda, ojo=ojo,
    )


def _resumen_prenda(tallas, por_id, pedidos: Mapping[int, int | None]) -> str:
    """«2 con diferencia · pedir 6» para la fila de grupo. «pedir» es lo que
    está escrito en PEDIR (lo que va a la hoja), no lo sugerido."""
    partes = []
    n_dif = sum(1 for l in tallas if _con_diferencia(por_id.get(l.conteo_id)))
    if n_dif:
        partes.append(f"{n_dif} con diferencia")
    pedido = sum(pedidos.get(l.conteo_id) or 0 for l in tallas)
    if pedido:
        partes.append(f"pedir {pedido}")
    if any(l.estado == URGENTE for l in tallas):
        partes.append("¡urgente!")
    return " · ".join(partes)


def grupos_tabla(lineas: Iterable, titulo: str = "") -> list[tuple[str, list]]:
    """[(nombre del grupo, tallas)] en el orden de la hoja: uno por prenda y,
    si la prenda trae varios colores, uno por prenda y color («Chamarra ·
    Negro»). Así la talla va sola en su celda y no se corta («10 Azul …»)."""
    salida: list[tuple[str, list]] = []
    for producto, tallas in prendas(lineas):
        colores = _colores(tallas)
        if len(colores) <= 1:
            salida.append((nombre_prenda(producto, tallas, titulo), tallas))
            continue
        nombre = _limpio(producto, titulo)
        por_color: dict[str, list] = {}
        for l in tallas:
            color = str(getattr(l, "color", "") or "").strip()
            clave = "" if color.upper() in _SIN_COLOR else color.lower()
            por_color.setdefault(clave, []).append(l)
        for clave, del_color in por_color.items():
            color = _colores(del_color)
            if color and color[0].lower() not in nombre.lower():
                salida.append((f"{nombre} · {_bonito(color[0])}", del_color))
            else:
                salida.append((nombre, del_color))
    return salida


def filas_tabla(
    lineas: Iterable, ajuste=None, pedidos: Mapping[int, int | None] | None = None, *,
    titulo: str = "", filtro: str | None = None, en_su_orden: bool = False, ya_revisada: bool = False,
) -> list[Fila]:
    """Las filas de la tabla, ya ordenadas y agrupadas.

    - Varias prendas (o una de varios colores): una fila de grupo por prenda
      y color (nombre + color una vez); la talla va sola.
    - Dentro de cada grupo, las tallas con diferencia primero y luego el
      separador «sin diferencia (N)» (solo si hay de las dos). Con
      `en_su_orden`, el orden de la hoja y sin separador.
    - Con `filtro` (la clave de un chip), solo las tallas de ese grupo.
    - La fila de grupo dice «pedir N» con lo escrito en PEDIR (`pedidos`)."""
    pedidos = pedidos or {}
    por_id = tallas_por_id(ajuste)
    grupos = grupos_tabla(lineas, titulo)
    varios = len(grupos) > 1
    filas: list[Fila] = []
    for nombre, tallas in grupos:
        visibles = [l for l in tallas if filtro is None or en_grupo(filtro, l, por_id.get(l.conteo_id))]
        if not visibles:
            continue
        if varios:
            resumen = _resumen_prenda(visibles, por_id, pedidos)
            filas.append(Fila(FILA_PRENDA, texto=nombre + (f"   —   {resumen}" if resumen else "")))
        if en_su_orden:
            primero, despues = visibles, []
        else:
            primero = [l for l in visibles if _con_diferencia(por_id.get(l.conteo_id))]
            despues = [l for l in visibles if not _con_diferencia(por_id.get(l.conteo_id))]
            if not primero:   # nada con diferencia: sin separador
                primero, despues = despues, []

        def _fila(l):
            return fila_talla(l, por_id.get(l.conteo_id), pedidos.get(l.conteo_id), ya_revisada=ya_revisada)

        filas.extend(_fila(l) for l in primero)
        if despues:
            filas.append(Fila(FILA_SEPARADOR, texto=f"sin diferencia ({len(despues)})"))
            filas.extend(_fila(l) for l in despues)
    return filas


def texto_orden(en_su_orden: bool) -> str:
    """El botón que cambia el orden dice a dónde lleva."""
    return "↕ Diferencias primero" if en_su_orden else "↕ En su orden"


# --- «Ver todas las columnas» (diálogo aparte con scroll) ----------------------------

COLUMNAS_TODAS = (
    "Prenda", "Talla", "El sistema decía", "Contó", "Dif", "Vendidas desde", "Queda hoy",
    "En cajas", "Vendidas", "Ritmo/sem", "Alcanza", "Pidieron", "Hoja", "Surtir", "Sugerido", "Pedido",
    "La vez pasada",
)


def la_vez_pasada(linea) -> str:
    """«pediste 6 el 12/09, vendiste 4» / «había 5 el 12/09» / «primer conteo»."""
    if linea.pedido_anterior is not None:
        cuando = linea.pedido_anterior_at.strftime("%d/%m") if linea.pedido_anterior_at else ""
        vendio = f", vendiste {linea.vendidas_desde_pedido}" if linea.vendidas_desde_pedido is not None else ""
        return f"pediste {linea.pedido_anterior} el {cuando}{vendio}"
    if linea.anterior is not None:
        return f"había {linea.anterior} el {linea.anterior_at.strftime('%d/%m')}"
    return "primer conteo"


def fila_todas(linea, t, pedido: int | None, *, titulo: str = "", ya_revisada: bool = False) -> tuple[str, ...]:
    """Una talla con todas las columnas (las de la tanda 2 y las de antes)."""
    corta = fila_talla(linea, t, pedido, varios_colores=True, ya_revisada=ya_revisada).celdas
    vendidas = f"{linea.vendidas} en {linea.dias_observados} d" if linea.dias_observados else "—"
    if linea.semanas_cubiertas is None:
        alcanza = "—"
    else:
        alcanza = f"{linea.semanas_cubiertas:g} sem" if linea.semanas_cubiertas < 99 else "+"
    if linea.estado in (SIN_DATOS, NO_SE_MUEVE):
        sugerido = etiqueta_sin_ritmo(linea)
    elif linea.estado == URGENTE:
        sugerido = f"{linea.sugerido}  ¡urgente!"
    else:
        sugerido = str(linea.sugerido) if linea.sugerido else "bien"
    return (
        _limpio(linea.producto, titulo), corta[COL_TALLA], corta[COL_SISTEMA], corta[COL_CONTO], corta[COL_DIF],
        corta[COL_VENDIDAS], corta[COL_QUEDA],
        str(linea.en_cajas) if linea.en_cajas else "—", vendidas,
        f"{linea.ritmo_semana:.1f}" if linea.ritmo_semana else "—", alcanza,
        str(linea.pidieron) if linea.pidieron else "—",
        str(linea.ellas_sugieren) if linea.ellas_sugieren is not None else "—",
        str(linea.surtir) if linea.surtir else "—", sugerido,
        "" if pedido is None else str(pedido), la_vez_pasada(linea),
    )


# --- botones y estado ----------------------------------------------------------------

TEXTO_MARCAR_REVISADO = "Marcar como revisado"


def texto_boton_corregir(ajuste) -> str:
    """«Corregir inventario (4 tallas, −7 pz)» o «Marcar como revisado» sin diferencias."""
    if ajuste is None or ajuste.tallas_a_corregir == 0:
        return TEXTO_MARCAR_REVISADO
    netas = ajuste.piezas_netas
    pz = "0" if netas == 0 else con_signo(netas)
    return f"Corregir inventario ({_tallas(ajuste.tallas_a_corregir)}, {pz} pz)"


@dataclass(frozen=True)
class Acciones:
    corregir: bool
    no_usar: bool
    hoja: bool


def acciones(*, ya_revisada: bool, pedidos: Mapping[int, int | None]) -> Acciones:
    """Ya revisada: sin Corregir ni No usar (el pedido y la hoja siguen).
    La hoja de pedido solo si hay algo pedido."""
    hay_pedido = any(p for p in pedidos.values())
    return Acciones(corregir=not ya_revisada, no_usar=not ya_revisada, hoja=hay_pedido)


def texto_listo(resultado: str, ajuste=None) -> str:
    """Lo que dice «✓ Listo» después de corregir o de no usar el conteo."""
    if resultado == "descartada":
        return "No se usó este conteo: el inventario no cambió."
    if ajuste is None or ajuste.tallas_a_corregir == 0:
        return "Quedó revisado: ninguna talla cambió."
    verbo = "Se corrigió" if ajuste.tallas_a_corregir == 1 else "Se corrigieron"
    return (
        f"{verbo} {_tallas(ajuste.tallas_a_corregir)}: faltaban {ajuste.salen}, sobraban {ajuste.entran} "
        f"({pesos(ajuste.valor, signo=True)} a precio de venta)."
    )


def texto_quedan(n: int) -> str:
    """«Queda 1 conteo por revisar.» / «Quedan 3 …» / «No queda ninguno por revisar.»"""
    if n <= 0:
        return "No queda ningún conteo por revisar."
    return "Queda 1 conteo por revisar." if n == 1 else f"Quedan {n} conteos por revisar."


def siguiente_por_revisar(ids_por_revisar: Iterable[int], actual: int) -> int | None:
    """La siguiente jornada por revisar (en el orden de la tarjeta POR REVISAR), sin la actual."""
    return next((int(i) for i in ids_por_revisar if int(i) != int(actual)), None)
