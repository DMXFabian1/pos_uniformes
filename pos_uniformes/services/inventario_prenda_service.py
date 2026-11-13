"""Vista «Por prenda» de Inventario (tanda 4, 2026-11-13): reglas puras.

Cada fila es una PRENDA + COLOR (`producto_id` + color): así se surte y se
cuenta en la tienda, y la escalera de tallas de un mismo color se lee de un
vistazo («4·3  6·0  8·5  10·2  12·−1»). El color va en la fila, no en la
escalera: una prenda en dos colores son dos filas.

Se agrupa SOLO lo que pasó los filtros, el buscador y la tarjeta: una prenda
aparece si alguna de sus tallas pasa, y su escalera enseña solo esas tallas
(con «En negativo» prendida, cada prenda enseña solo sus negativos). Los
conjuntos y virtuales salen igual que en «Por talla» (en la escalera, con su
número sin tono), pero no suman piezas: ya están contados en sus piezas.

Sin Qt ni base: la vista (`ui/helpers/inventario_prendas_vista.py`) solo pinta.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping, Sequence

from pos_uniformes.services.inventario_donde_service import MARCA_DESCUADRE, SEPARADOR, TIENDA, VACIO, repartir
from pos_uniformes.services.inventario_existencia_service import cifra_existencia, es_fila_virtual, tono_cifra
from pos_uniformes.services.inventario_precio_service import LLAVE_PRECIO, LLAVE_TIPO, precio_efectivo
from pos_uniformes.services.rebaja_service import ETIQUETAS as ETIQUETAS_REBAJA, fmt_corto
from pos_uniformes.services.talla_orden_service import clave_talla

#: Columnas de la vista «Por prenda». En las filas hijas (las tallas) la
#: primera dice el código, «Tallas» dice la talla y el resto es igual que en
#: «Por talla»: así una talla desplegada se lee como en la otra vista.
COLUMNAS_PRENDA = ("Prenda", "Tallas", "Hay", "Dónde", "Precio", "Contada")
#: Columnas que ordenan al tocar el encabezado (la escalera no ordena).
ORDEN_PRENDA = ("Prenda", "Hay", "Dónde", "Precio", "Contada")

#: Etiqueta cuando las tallas de una prenda traen Oferta y Liquidación a la vez.
REBAJA_MEZCLADA = "Rebaja"

#: Separador entre fichas de la escalera en el texto plano (aviso y pruebas).
SEPARADOR_ESCALERA = "  "


@dataclass(frozen=True)
class TallaEscalera:
    """Una ficha de la escalera: «10·2» con el tono de su número."""

    variante_id: object
    talla: str
    existencia: int
    tono: str  # danger | warning | muted | "" (el de la columna «Hay» de «Por talla»)
    activa: bool
    virtual: bool

    @property
    def cifra(self) -> str:
        return cifra_existencia(self.existencia)

    @property
    def texto(self) -> str:
        return f"{self.talla or '—'}·{self.cifra}"


@dataclass(frozen=True)
class GrupoPrenda:
    llave: tuple
    producto_id: object
    prenda: str
    color: str
    filas: tuple  # las filas del snapshot, ya en orden de talla
    escalera: tuple[TallaEscalera, ...]
    piezas: int  # suma de lo positivo, sin conjuntos/virtuales
    piezas_conjunto: int  # lo que se puede armar si TODA la prenda es conjunto
    es_conjunto: bool
    precio_min: Decimal | None
    precio_max: Decimal | None
    rebaja: str  # «Oferta» / «Liquidación»; «Rebaja» si sus tallas traen las dos
    tallas_con_rebaja: int
    contada_mas_vieja: datetime | None
    nunca_contada: bool  # alguna talla nunca se contó
    bodega: int
    piso: int
    #: Lo que está a la venta sin caja (suma de la «Tienda» de cada talla).
    tienda: int = 0
    #: Piezas que hay en cajas de más contra el total, sumadas talla por talla.
    descuadre: int = 0
    #: Tallas con descuadre (en cajas hay más de lo que dice su total).
    tallas_descuadre: int = 0
    #: Cuántas tallas trae cada tipo de rebaja, en orden: (("Oferta", 2), ("Liquidación", 1)).
    rebajas: tuple = ()

    @property
    def variante_ids(self) -> tuple:
        return tuple(talla.variante_id for talla in self.escalera)

    @property
    def tallas(self) -> int:
        return len(self.escalera)

    @property
    def texto_escalera(self) -> str:
        return texto_escalera(self.escalera)

    @property
    def texto_hay(self) -> str:
        return f"{(self.piezas_conjunto if self.es_conjunto else self.piezas):,}"

    @property
    def texto_precio(self) -> str:
        return texto_rango_precio(self.precio_min, self.precio_max, rebaja=self.rebaja)

    @property
    def aviso_precio(self) -> str | None:
        if not self.rebaja:
            return None
        if len(self.rebajas) > 1:
            # Tipos mezclados: cuántas de cada uno («Oferta en 2 · Liquidación en 1 de 3 tallas»).
            cuentas = SEPARADOR.join(f"{tipo} en {n}" for tipo, n in self.rebajas)
            return f"{cuentas} de {self.tallas} tallas"
        if self.tallas_con_rebaja >= self.tallas:
            return f"{self.rebaja} en todas sus tallas"
        return f"{self.rebaja} en {self.tallas_con_rebaja} de {self.tallas} tallas"

    @property
    def texto_donde(self) -> str:
        """Lo que hay en cajas sumado: «Bodega 12 · Piso 2»; si nada, «Tienda» o «—».

        Si alguna talla tiene descuadre (en cajas más de lo que dice su total)
        lleva la misma marca «⚠» que en «Por talla»."""
        if self.es_conjunto:
            return VACIO
        partes = [f"{nombre} {n:,}" for nombre, n in (("Bodega", self.bodega), ("Piso", self.piso)) if n > 0]
        if partes:
            return SEPARADOR.join(partes) + (MARCA_DESCUADRE if self.descuadre else "")
        return TIENDA if self.piezas > 0 else VACIO

    @property
    def aviso_donde(self) -> str | None:
        """Reparto completo para el aviso: «Tienda 4 · Bodega 6 · Piso 2» y, si
        hay descuadre, en cuántas tallas."""
        if self.es_conjunto:
            return "Se arma con sus piezas: no se guarda aparte."
        partes = [f"{nombre} {n:,}" for nombre, n in ((TIENDA, self.tienda), ("Bodega", self.bodega), ("Piso", self.piso)) if n > 0]
        texto = SEPARADOR.join(partes) if partes else "No hay"
        if self.descuadre:
            tallas = "1 talla" if self.tallas_descuadre == 1 else f"{self.tallas_descuadre} tallas"
            texto += f". Ojo: en {tallas} hay en cajas {self.descuadre:,} de más contra su total"
        return texto


def texto_escalera(escalera: Iterable[TallaEscalera]) -> str:
    """«4·3  6·0  8·5  10·2  12·−1» (para el aviso al pasar el mouse)."""
    return SEPARADOR_ESCALERA.join(talla.texto for talla in escalera)


def texto_rango_precio(minimo: Decimal | None, maximo: Decimal | None, *, rebaja: str = "") -> str:
    """«$250», «$250–$265» y, con alguna talla rebajada, «Oferta $175–$289»."""
    if minimo is None or maximo is None:
        return "—"
    texto = fmt_corto(minimo) if minimo == maximo else f"{fmt_corto(minimo)}–{fmt_corto(maximo)}"
    return f"{rebaja} {texto}" if rebaja else texto


def texto_contada_grupo(grupo: GrupoPrenda, *, ahora: datetime) -> str:
    """La talla contada hace más tiempo manda: «Nunca» si alguna nunca se contó;
    si no, «Hoy», «Ayer» o «Hace 52d» (como la columna de «Por talla»)."""
    if grupo.nunca_contada or grupo.contada_mas_vieja is None:
        return "Nunca"
    dias = max(0, (_utc(ahora) - _utc(grupo.contada_mas_vieja)).days)
    if dias == 0:
        return "Hoy"
    if dias == 1:
        return "Ayer"
    return f"Hace {dias}d"


# ── Agrupar ──────────────────────────────────────────────────────────────


def llave_prenda(fila: Mapping[str, object]) -> tuple:
    """Prenda + color. Sin `producto_id` (no debería pasar), el nombre de la prenda."""
    producto = fila.get("producto_id")
    if producto is None:
        producto = _normal(fila.get("producto_nombre_base") or fila.get("producto_nombre"))
    return (producto, _normal(fila.get("color")))


def agrupar_por_prenda(filas: Iterable[Mapping[str, object]]) -> list[GrupoPrenda]:
    """Junta las tallas por prenda + color, en el orden en que aparece cada prenda.

    Dentro de cada prenda, las tallas van en orden de talla (`clave_talla`) y,
    si se repite la talla, por código. Una sola pasada sobre las filas: con
    ~5,200 tallas tarda unos milisegundos.
    """
    cubetas: dict[tuple, list[Mapping[str, object]]] = {}
    for fila in filas:
        llave = llave_prenda(fila)
        cubeta = cubetas.get(llave)
        if cubeta is None:
            cubetas[llave] = [fila]
        else:
            cubeta.append(fila)
    return [_grupo(llave, cubeta) for llave, cubeta in cubetas.items()]


def _grupo(llave: tuple, filas: list[Mapping[str, object]]) -> GrupoPrenda:
    if len(filas) > 1:
        filas = sorted(filas, key=lambda f: (clave_talla(f.get("talla")), str(f.get("sku") or "")))
    primera = filas[0]
    escalera = []
    piezas = piezas_conjunto = bodega = piso = tienda = descuadre = tallas_descuadre = 0
    todas_virtuales = True
    precio_min = precio_max = None
    tipos_rebaja: dict[str, int] = {}
    con_rebaja = 0
    mas_vieja: datetime | None = None
    nunca = False
    for fila in filas:
        stock = _entero(fila.get("stock_actual"))
        virtual = es_fila_virtual(fila)
        activa = bool(fila.get("variante_activa", True))
        minimo = fila.get("stock_minimo")
        tono = tono_cifra(stock, stock_minimo=_entero(minimo) if minimo is not None else None, virtual=virtual)
        escalera.append(
            TallaEscalera(
                variante_id=fila.get("variante_id"),
                talla=str(fila.get("talla") or "").strip(),
                existencia=stock,
                tono=tono if activa else "muted",
                activa=activa,
                virtual=virtual,
            )
        )
        if virtual:
            piezas_conjunto += max(0, stock)
        else:
            todas_virtuales = False
            piezas += max(0, stock)
            reparto = repartir(stock, _entero(fila.get("stock_bodega")), _entero(fila.get("stock_piso")))
            bodega += reparto.bodega
            piso += reparto.piso
            tienda += reparto.tienda
            if reparto.descuadre:
                descuadre += reparto.descuadre
                tallas_descuadre += 1
        precio = _decimal(precio_efectivo(fila))
        if precio is not None:
            precio_min = precio if precio_min is None or precio < precio_min else precio_min
            precio_max = precio if precio_max is None or precio > precio_max else precio_max
        tipo = fila.get(LLAVE_TIPO)
        if tipo and fila.get(LLAVE_PRECIO) is not None:
            con_rebaja += 1
            etiqueta = ETIQUETAS_REBAJA.get(str(tipo), str(tipo))
            tipos_rebaja[etiqueta] = tipos_rebaja.get(etiqueta, 0) + 1
        conteo = fila.get("ultimo_conteo_at")
        if isinstance(conteo, datetime):
            if mas_vieja is None or _utc(conteo) < _utc(mas_vieja):
                mas_vieja = conteo
        else:
            nunca = True
    if len(tipos_rebaja) > 1:
        rebaja = REBAJA_MEZCLADA
    else:
        rebaja = next(iter(tipos_rebaja), "")
    return GrupoPrenda(
        llave=llave,
        producto_id=primera.get("producto_id"),
        prenda=str(primera.get("producto_nombre_base") or primera.get("producto_nombre") or "").strip(),
        color=str(primera.get("color") or "").strip(),
        filas=tuple(filas),
        escalera=tuple(escalera),
        piezas=piezas,
        piezas_conjunto=piezas_conjunto,
        es_conjunto=todas_virtuales,
        precio_min=precio_min,
        precio_max=precio_max,
        rebaja=rebaja,
        tallas_con_rebaja=con_rebaja,
        contada_mas_vieja=mas_vieja,
        nunca_contada=nunca,
        bodega=bodega,
        piso=piso,
        tienda=tienda,
        descuadre=descuadre,
        tallas_descuadre=tallas_descuadre,
        rebajas=tuple(tipos_rebaja.items()),
    )


def filas_en_orden(grupos: Iterable[GrupoPrenda]) -> list:
    """Las tallas de todas las prendas, prenda tras prenda y en orden de talla."""
    return [fila for grupo in grupos for fila in grupo.filas]


def resumen_prendas(grupos: Sequence[GrupoPrenda]) -> str:
    """«12 prendas · 340 piezas» (sin piezas si no hay ninguna a la vista)."""
    n = len(grupos)
    piezas = sum(grupo.piezas for grupo in grupos)
    prendas = f"{n:,} {'prenda' if n == 1 else 'prendas'}"
    if piezas == 0 and n > 0:
        return prendas
    return f"{prendas} · {piezas:,} {'pieza' if piezas == 1 else 'piezas'}"


# ── Orden al tocar el encabezado ─────────────────────────────────────────


def _clave_grupo(columna: str, grupo: GrupoPrenda) -> tuple:
    if columna == "Prenda":
        return (_normal(grupo.prenda), _normal(grupo.color))
    if columna == "Hay":
        return (grupo.piezas_conjunto if grupo.es_conjunto else grupo.piezas,)
    if columna == "Dónde":
        return (grupo.bodega + grupo.piso,)
    if columna == "Precio":
        return (grupo.precio_min if grupo.precio_min is not None else Decimal(0),)
    if columna == "Contada":
        # Nunca contada primero (lo más viejo), luego de la más vieja a la más nueva.
        if grupo.nunca_contada or grupo.contada_mas_vieja is None:
            return (0, 0.0)
        return (1, _utc(grupo.contada_mas_vieja).timestamp())
    return ()


def ordenar_grupos(grupos: Sequence[GrupoPrenda], columna: str | None, *, descendente: bool = False) -> list[GrupoPrenda]:
    """Sin columna (o una que no ordena) deja el orden de siempre. Estable."""
    if not columna or columna not in ORDEN_PRENDA:
        return list(grupos)
    return sorted(grupos, key=lambda grupo: _clave_grupo(columna, grupo), reverse=descendente)


def siguiente_orden_prenda(actual: tuple[str | None, bool], columna: str) -> tuple[str | None, bool]:
    """1.º ascendente, 2.º descendente, 3.º vuelve al orden de siempre."""
    columna_actual, descendente = actual
    if columna not in ORDEN_PRENDA:
        return actual
    if columna_actual != columna:
        return (columna, False)
    if not descendente:
        return (columna, True)
    return (None, False)


# ── Páginas por prenda ───────────────────────────────────────────────────


@dataclass(frozen=True)
class PaginaPrendas:
    grupos: tuple[GrupoPrenda, ...]
    pagina: int
    paginas: int
    total: int  # prendas en todas las páginas
    inicio: int  # número de la primera prenda de la página (1…); 0 si no hay
    fin: int


def indice_de_variante(grupos: Sequence[GrupoPrenda], variante_id: object) -> int | None:
    """En qué prenda (índice) está esa talla."""
    if variante_id is None:
        return None
    for indice, grupo in enumerate(grupos):
        if variante_id in grupo.variante_ids:
            return indice
    return None


def paginar_prendas(
    grupos: Sequence[GrupoPrenda], pagina: int, tamano: int, *, variante_id: object = None
) -> PaginaPrendas:
    """La paginación cuenta PRENDAS (cada una con todas sus tallas en la misma
    página). Con `variante_id`, salta a la página de la prenda de esa talla."""
    if tamano <= 0:
        raise ValueError("tamano debe ser mayor a cero.")
    indice = indice_de_variante(grupos, variante_id)
    if indice is not None:
        pagina = indice // tamano
    total = len(grupos)
    paginas = max(1, (total + tamano - 1) // tamano)
    pagina = min(max(pagina, 0), paginas - 1)
    inicio = pagina * tamano
    visibles = tuple(grupos[inicio : inicio + tamano])
    return PaginaPrendas(
        grupos=visibles,
        pagina=pagina,
        paginas=paginas,
        total=total,
        inicio=inicio + 1 if visibles else 0,
        fin=inicio + len(visibles),
    )


def texto_paginacion_prendas(pagina: PaginaPrendas) -> str:
    """«Mostrando 12 prendas» o «Mostrando 1–100 de 340 prendas»."""
    if pagina.total <= 0:
        return "Sin prendas con estos filtros"
    if pagina.inicio == 1 and pagina.fin == pagina.total:
        return f"Mostrando {pagina.total:,} {'prenda' if pagina.total == 1 else 'prendas'}"
    return f"Mostrando {pagina.inicio:,}–{pagina.fin:,} de {pagina.total:,} prendas"


# ── Utilidades ───────────────────────────────────────────────────────────


def _normal(valor: object) -> str:
    texto = unicodedata.normalize("NFD", str(valor or "").strip())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").casefold()


def _entero(valor: object) -> int:
    try:
        return int(valor or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _decimal(valor: object) -> Decimal | None:
    if valor in (None, ""):
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


def _utc(momento: datetime) -> datetime:
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)
