"""Todo de una escuela, en una sola pregunta.

Hasta ahora, para saber cómo va una escuela había que abrir cuatro pantallas:
el mapa para ver qué está contado, Revisar para el pedido, la Libreta para lo
vendido y Analítica para lo que pidieron y no había. Cada una sabe su parte y
ninguna sabe el todo.

Este servicio no calcula nada nuevo: le pregunta a los que ya saben y junta
las respuestas. Si una cifra de aquí no cuadra con su pantalla, el error está
en el servicio de origen, no aquí — y ese es justo el punto.

Ver la nota `39 - Brújula`: una escuela, un número, cuatro ventanas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    ConteoInventario,
    DemandaNoAtendida,
    Escuela,
    MovimientoInventario,
    Producto,
    TipoMovimientoInventario,
    Variante,
)
from pos_uniformes.services import conteo_jornada_service, conteo_mapa_service
from pos_uniformes.services import escuela_piezas_service

#: Cuánto hacia atrás se mira lo que se vendió y lo que pidieron y no había.
VENTANA_DIAS = 30


@dataclass(frozen=True)
class TallaPedida:
    """Una talla que alguien decidió pedir, y cuánto."""

    prenda: str
    talla: str
    cuantas: int
    decidido_at: datetime | None


@dataclass(frozen=True)
class FaltaSentida:
    """Algo que pidieron en el mostrador y no se pudo vender."""

    prenda: str
    talla: str
    veces: int
    piezas: int


@dataclass(frozen=True)
class EstadoDeEscuela:
    """Cómo va una escuela, de un vistazo."""

    escuela_id: int
    nombre: str
    niveles: list[str]

    # Qué tan contada está (mismo criterio del mapa: talla por talla).
    tallas: int
    al_dia: int
    viejas: int
    nunca: int
    en_rojo: int
    ultimo_conteo: object                      # UltimoConteo
    quien_en_proceso: str

    # Qué tiene y qué le falta.
    agotadas: int
    piezas_en_tienda: int

    # Qué se decidió pedir, qué se vendió y qué pidieron y no había.
    pedido: list[TallaPedida] = field(default_factory=list)
    vendido_piezas: int = 0
    faltas_sentidas: list[FaltaSentida] = field(default_factory=list)

    @property
    def faltan_de_contar(self) -> int:
        return self.viejas + self.nunca

    @property
    def pct_al_dia(self) -> int:
        return round(100 * self.al_dia / self.tallas) if self.tallas else 0

    @property
    def salud(self) -> str:
        """El semáforo, con lo más urgente mandando.

        `rojo` = se vendió sin contar, **o** nunca se ha contado ni una talla;
        `ambar` = le falta contarse; `verde` = contada y al día.

        La regla vive en `conteo_mapa_service.semaforo`, no aquí y menos en
        quien lo pinta: el mapa, el panel, el celular y el kiosko tienen que
        estar de acuerdo en cuándo una escuela está en rojo."""
        return conteo_mapa_service.semaforo(
            self.en_rojo, self.faltan_de_contar, nunca=self.nunca, tallas=self.tallas
        )

    @property
    def titular(self) -> str:
        """Una línea para decir cómo va, con lo más urgente primero."""
        if self.en_rojo:
            cuantas = "una talla" if self.en_rojo == 1 else f"{self.en_rojo} tallas"
            return f"{cuantas} en rojo: se vendió sin contar"
        if self.nunca == self.tallas and self.tallas:
            return "nunca se ha contado"
        if self.faltan_de_contar:
            return f"faltan {self.faltan_de_contar} de {self.tallas} tallas por contar"
        return f"al día · {self.agotadas} tallas agotadas"


def _ventana(dias: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=int(dias))


def _reparto(session: Session, cache: dict | None = None) -> list[tuple]:
    """El reparto de prendas por escuela, pedido una sola vez.

    Recorrerlo es caro (mira uniformes y ligas de todas las escuelas), así que
    quien pregunte por varias escuelas seguidas lo pasa en `cache` y se lee una
    vez en lugar de una por escuela."""
    if cache is not None:
        if "reparto" not in cache:
            cache["reparto"] = escuela_piezas_service.productos_por_escuela(session)
        return cache["reparto"]
    return escuela_piezas_service.productos_por_escuela(session)


def _variantes_de(session: Session, escuela_id: int, reparto) -> list[int]:
    """Las tallas que le tocan a la escuela, incluidas las generales que lleva.

    Sale del mismo reparto que usan Piezas y los tarifarios, para que "las
    prendas de esta escuela" quiera decir lo mismo en todas partes."""
    productos = {pid for eid, pid, _nivel_id, _nivel in reparto if eid == int(escuela_id)}
    if not productos:
        return []
    return [
        int(vid)
        for vid in session.scalars(
            select(Variante.id)
            .join(Producto, Producto.id == Variante.producto_id)
            .where(
                Variante.producto_id.in_(productos),
                Variante.activo.is_(True),
                Producto.activo.is_(True),
            )
        ).all()
    ]


def _pedido(session: Session, variantes: list[int], desde: datetime) -> list[TallaPedida]:
    """Lo que se decidió pedir al revisar un conteo (la decisión se guarda)."""
    if not variantes:
        return []
    filas = session.execute(
        select(
            Producto.nombre_base,
            Producto.nombre,
            Variante.talla,
            ConteoInventario.pedido,
            ConteoInventario.pedido_decidido_at,
        )
        .join(Variante, Variante.id == ConteoInventario.variante_id)
        .join(Producto, Producto.id == Variante.producto_id)
        .where(
            ConteoInventario.variante_id.in_(variantes),
            ConteoInventario.pedido.is_not(None),
            ConteoInventario.pedido > 0,
            ConteoInventario.pedido_decidido_at >= desde,
        )
        .order_by(ConteoInventario.pedido_decidido_at.desc())
    ).all()
    return [
        TallaPedida(
            prenda=str(nombre_base or nombre),
            talla=str(talla),
            cuantas=int(cuantas),
            decidido_at=decidido,
        )
        for nombre_base, nombre, talla, cuantas, decidido in filas
    ]


def _vendido(session: Session, variantes: list[int], desde: datetime) -> int:
    """Piezas que salieron por venta. Sale de los movimientos, que es lo único
    que sabe de qué escuela era cada pieza."""
    if not variantes:
        return 0
    total = session.scalar(
        select(func.coalesce(func.sum(MovimientoInventario.cantidad), 0)).where(
            MovimientoInventario.variante_id.in_(variantes),
            MovimientoInventario.tipo_movimiento == TipoMovimientoInventario.SALIDA_VENTA,
            MovimientoInventario.created_at >= desde,
        )
    )
    return abs(int(total or 0))


def _faltas_sentidas(session: Session, variantes: list[int], desde: datetime) -> list[FaltaSentida]:
    """Lo que pidieron en el mostrador y no se pudo vender, de esta escuela.

    La demanda se anota con el SKU, así que se amarra por ahí; lo que se pidió
    sin SKU (un "¿no tienen playeras rojas?") no se puede repartir por escuela
    y se queda en la vista general de Analítica."""
    if not variantes:
        return []
    skus = {
        str(sku)
        for sku in session.scalars(select(Variante.sku).where(Variante.id.in_(variantes))).all()
    }
    if not skus:
        return []
    filas = session.execute(
        select(
            DemandaNoAtendida.producto,
            DemandaNoAtendida.talla,
            func.count(DemandaNoAtendida.id),
            func.coalesce(func.sum(DemandaNoAtendida.piezas), 0),
        )
        .where(
            DemandaNoAtendida.sku.in_(skus),
            DemandaNoAtendida.created_at >= desde,
        )
        .group_by(DemandaNoAtendida.producto, DemandaNoAtendida.talla)
    ).all()
    faltas = [
        FaltaSentida(prenda=str(prenda), talla=str(talla), veces=int(veces), piezas=int(piezas))
        for prenda, talla, veces, piezas in filas
    ]
    faltas.sort(key=lambda f: (-f.veces, -f.piezas, f.prenda))
    return faltas


def estado_de(
    session: Session, escuela_id: int, *, dias: int = VENTANA_DIAS, cache: dict | None = None
) -> EstadoDeEscuela:
    """Cómo va esta escuela: contada, surtida, pedida, vendida y sentida."""
    escuela = session.get(Escuela, int(escuela_id))
    if escuela is None:
        raise ValueError(f"No existe la escuela {escuela_id}.")

    mapa = conteo_mapa_service.escuela(session, int(escuela_id))
    ultimos = conteo_jornada_service.ultimos_conteos(session)
    abiertas = conteo_jornada_service.abiertas_por_alcance(session)
    abierta = abiertas.get(conteo_jornada_service.clave_alcance(int(escuela_id)))
    # `ref` es la foto plana de una jornada que ya usa el mapa: quién la trae y
    # si imprimió hoja. No se lee el ORM a mano para no inventar otra versión.
    quien = conteo_jornada_service.ref(abierta).quien if abierta is not None else ""

    reparto = _reparto(session, cache)
    niveles = sorted({nivel for eid, _pid, _nid, nivel in reparto if eid == int(escuela_id)})

    prendas = mapa.get("prendas", [])
    tallas_detalle = [t for p in prendas for t in p.get("tallas_detalle", [])]
    agotadas = sum(1 for t in tallas_detalle if int(t.get("stock") or 0) <= 0)
    piezas = sum(max(0, int(t.get("stock") or 0)) for t in tallas_detalle)

    variantes = _variantes_de(session, int(escuela_id), reparto)
    desde = _ventana(dias)

    return EstadoDeEscuela(
        escuela_id=int(escuela_id),
        nombre=str(escuela.nombre),
        niveles=niveles,
        tallas=int(mapa.get("tallas") or 0),
        al_dia=int(mapa.get("al_dia") or 0),
        viejas=int(mapa.get("viejas") or 0),
        nunca=int(mapa.get("nunca") or 0),
        en_rojo=int(mapa.get("en_rojo") or 0),
        ultimo_conteo=conteo_jornada_service.ultimo_conteo_de(ultimos, int(escuela_id)),
        quien_en_proceso=str(quien or ""),
        agotadas=agotadas,
        piezas_en_tienda=piezas,
        pedido=_pedido(session, variantes, desde),
        vendido_piezas=_vendido(session, variantes, desde),
        faltas_sentidas=_faltas_sentidas(session, variantes, desde),
    )


def estados_de_todas(session: Session, *, dias: int = VENTANA_DIAS) -> dict[int, EstadoDeEscuela]:
    """Cómo va cada escuela activa, indexado por su id.

    Para quien pinta muchas de un jalón (el panel, el mapa). Comparte el
    reparto entre todas en vez de recalcularlo escuela por escuela."""
    cache: dict = {}
    ids = [int(e) for e in session.scalars(select(Escuela.id).where(Escuela.activo.is_(True))).all()]
    return {eid: estado_de(session, eid, dias=dias, cache=cache) for eid in ids}
