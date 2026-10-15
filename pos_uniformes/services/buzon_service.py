"""Buzón entre las PCs: mandar un texto de una pantalla a otra.

Existe para pasar comandos y respuestas entre la Mac, la PC principal y los
kioskos sin WhatsApp (Daniel, 2026-10-15). Se escribe en una PC, se lee y se
copia en otra. Va por la base porque todas las PCs ya hablan con ella, y porque
así Claude puede dejar un script desde la Mac y leer lo que le contesten.

No ejecuta nada: solo lleva texto. Quien lo recibe decide si lo copia y lo
corre (Daniel escogió eso sobre un botón «Ejecutar»).

Convención del repo: estas funciones mutan la Session pero NO hacen commit.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import BuzonMensaje

#: Lo que se ve en la ventana. Lo viejo sigue en la base, solo no estorba.
LIMITE = 60
#: Un mensaje es para leer y copiar, no para guardar un archivo entero.
MAXIMO_CARACTERES = 20_000


class NoSePuede(Exception):
    """Algo impide mandar el mensaje, dicho para enseñarlo en pantalla."""


def mi_nombre() -> str:
    """Cómo se firma esta PC: el nombre que tiene en el menú admin."""
    try:
        from pos_uniformes.services.satellite_identity_service import get_satellite_name

        nombre = (get_satellite_name() or "").strip()
        if nombre:
            return nombre[:60]
    except Exception:  # noqa: BLE001 — sin identidad, el nombre de la máquina
        pass
    import platform

    return (platform.node() or "PC")[:60]


def enviar(session: Session, texto: str, *, de: str, para: str | None = None) -> BuzonMensaje:
    """Deja un mensaje. `para` vacío = a todas las PCs."""
    texto = (texto or "").rstrip()
    if not texto.strip():
        raise NoSePuede("El mensaje está vacío.")
    if len(texto) > MAXIMO_CARACTERES:
        raise NoSePuede(
            f"Es muy largo ({len(texto):,} caracteres). El máximo es {MAXIMO_CARACTERES:,}."
        )
    mensaje = BuzonMensaje(
        de=(de or "PC").strip()[:60],
        para=((para or "").strip()[:60] or None),
        texto=texto,
    )
    session.add(mensaje)
    session.flush()
    return mensaje


def recientes(session: Session, *, yo: str | None = None, limite: int = LIMITE) -> list[BuzonMensaje]:
    """Los últimos mensajes que le tocan a `yo`, del más viejo al más nuevo.

    Le tocan los que son para todas, los que son para ella y los que ella
    mandó. Sin `yo`, todos."""
    stmt = select(BuzonMensaje)
    if yo:
        stmt = stmt.where(
            or_(BuzonMensaje.para.is_(None), BuzonMensaje.para == yo, BuzonMensaje.de == yo)
        )
    filas = list(session.scalars(stmt.order_by(BuzonMensaje.id.desc()).limit(limite)).all())
    filas.reverse()
    return filas


def destinos(session: Session, *, yo: str | None = None) -> list[str]:
    """A quién se le puede escribir: las PCs que se conocen, menos esta."""
    from pos_uniformes.database.models import Satelite

    nombres = {
        str(n).strip()
        for n in session.scalars(select(Satelite.nombre)).all()
        if n and str(n).strip()
    }
    # También quien ya escribió alguna vez (la PC principal, la Mac, Claude).
    nombres |= {
        str(n).strip() for n in session.scalars(select(BuzonMensaje.de).distinct()).all() if n
    }
    nombres.discard(yo or "")
    return sorted(nombres, key=str.lower)
