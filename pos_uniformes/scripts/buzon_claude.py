"""El buzón desde la Mac, como Claude: leer (y dejar las dos palomitas), mandar.

    python -m pos_uniformes.scripts.buzon_claude chats
    python -m pos_uniformes.scripts.buzon_claude leer "PC principal" [cuantos]
    python -m pos_uniformes.scripts.buzon_claude mandar "PC principal" "texto"

Antes Claude leía con un `bz.conversacion(...)` a mano y nunca anotaba lo
leído: del otro lado los mensajes se quedaban con una sola palomita (Daniel,
2026-11-07). `leer` anota hasta el último mensaje que enseñó.
"""

from __future__ import annotations

import sys

YO = "Claude"


def _leidos(session) -> dict[str, int]:
    from sqlalchemy import select

    from pos_uniformes.database.models import BuzonLeido

    return {
        f.chat: int(f.hasta_id or 0)
        for f in session.scalars(select(BuzonLeido).where(BuzonLeido.lector == YO)).all()
    }


def chats(session) -> list[str]:
    from pos_uniformes.services import buzon_service as bz

    renglones = []
    for c in bz.chats(session, yo=YO, leidos=_leidos(session)):
        pendientes = f"  ({c.no_leidos} sin leer)" if c.no_leidos else ""
        renglones.append(f"{c.nombre}{pendientes}: {c.ultimo_texto[:80]}")
    return renglones


def leer(session, con: str, cuantos: int = 20) -> list[str]:
    """La conversación con `con` (o «*» para todas) y la deja leída."""
    from pos_uniformes.services import buzon_service as bz

    mensajes = bz.conversacion(session, yo=YO, con=con, limite=cuantos)
    renglones = []
    for m in mensajes:
        hora = m.created_at.astimezone().strftime("%d/%m %H:%M") if m.created_at else ""
        cita = f" ↩{m.responde_a}" if m.responde_a else ""
        estado = f" [{m.estado}]" if m.estado else ""
        texto = bz.vista_previa(m) if (m.borrado_at or m.adjunto) else m.texto
        renglones.append(f"#{m.id} {hora} {m.de}{cita}{estado}:\n{texto}\n")
    if mensajes:
        bz.anotar_leido(session, lector=YO, chat=con, hasta_id=mensajes[-1].id)
        session.commit()
    return renglones


def mandar(session, para: str, texto: str) -> int:
    from pos_uniformes.services import buzon_service as bz

    m = bz.enviar(session, texto, de=YO, para=None if para == bz.GRUPO else para)
    session.commit()
    return m.id


def main(argv: list[str] | None = None) -> int:
    from pos_uniformes.database.connection import get_session

    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("chats", "leer", "mandar"):
        print(__doc__)
        return 2
    with get_session() as session:
        if argv[0] == "chats":
            print("\n".join(chats(session)))
        elif argv[0] == "leer":
            print("\n".join(leer(session, argv[1], int(argv[2]) if len(argv) > 2 else 20)))
        else:
            print(f"Mandado: #{mandar(session, argv[1], argv[2])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
