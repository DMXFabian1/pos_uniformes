"""¿De qué hora son los datos de la copia de la casa?

La copia viva de la casa (Postgres "pos-viva" en el servidor de Daniel) se
recarga desde la tienda cada 15 min y deja un COMMENT en la base, por ejemplo:

    copia pos_uniformes_20261120_141503.dump (de la tienda a las 2026-11-20 14:15), cargada 2026-11-20 14:17

De ahí sale la hora de la TIENDA (cuándo se sacó la copia), que es la que le
importa a quien consulta: "estos datos son de las 14:15".
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import text

_DE_LA_TIENDA = re.compile(r"de la tienda a las (\d{4}-\d{2}-\d{2}) (\d{1,2}:\d{2})")
_NOMBRE_DUMP = re.compile(r"_(\d{8})_(\d{2})(\d{2})\d{2}\.dump")


def hora_de_la_nota(nota: str | None) -> datetime | None:
    """La hora de la tienda escrita en el COMMENT; None si no se entiende."""
    if not nota:
        return None
    m = _DE_LA_TIENDA.search(nota)
    try:
        if m:
            return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M")
        m = _NOMBRE_DUMP.search(nota)
        if m:
            return datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}", "%Y%m%d %H:%M")
    except ValueError:
        return None
    return None


def datos_de(db) -> str | None:
    """"AAAA-MM-DDTHH:MM" (hora de la tienda) de la copia que se está leyendo,
    o None si la base no trae la nota (SQLite, base de la tienda, error)."""
    try:
        if db.get_bind().dialect.name != "postgresql":
            return None
        nota = db.execute(text(
            "SELECT shobj_description(oid, 'pg_database') FROM pg_database "
            "WHERE datname = current_database()"
        )).scalar()
    except Exception:  # noqa: BLE001 — la frescura es un extra, nunca tumba /inicio
        return None
    hora = hora_de_la_nota(nota)
    return hora.strftime("%Y-%m-%dT%H:%M") if hora else None
