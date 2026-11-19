"""Piezas de la skill entradas-inventario. Nada aquí escribe.

- Conexión: la de `alta-productos/scripts/_comun.py` (--env-file / --db-url, solo lectura).
- Existencia por partes como la ve el POS: total (`stock_actual`) = tienda + bodega + piso.
  El conteo del POS mide SOLO la tienda (lo que no está en cajas); aquí igual.
- Resolver un renglón del plan a UNA talla (por SKU, id o texto), sin adivinar.
- La cuenta del conteo: lo que había al contar + lo que se movió desde entonces.
"""
from __future__ import annotations

import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "alta-productos" / "scripts"))
import _comun  # noqa: E402,F401  (pone la raíz del repo en sys.path)

from sqlalchemy import text  # noqa: E402

ZONA = ZoneInfo("America/Mexico_City")
DUENO = "VEND-1"


def sin_acentos(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def parse_cuando(valor: str | None) -> datetime:
    """«2026-11-19 18:30»: la hora REAL en que se contó (hora de la tienda), nunca en el futuro.

    No se acepta «ahora»: el plan se aplica minutos u horas después de contar, y lo que se
    vendió en medio debe restarse; con «ahora» se perdería.
    """
    ahora = datetime.now(ZONA)
    if not valor or str(valor).strip().lower() == "ahora":
        raise SystemExit("ERROR: conteo «contado»: pon la hora en que se contó (AAAA-MM-DD HH:MM), no «ahora».")
    try:
        momento = datetime.fromisoformat(str(valor).strip())
    except ValueError:
        raise SystemExit(f"ERROR: conteo «contado»: hora inválida {valor!r} (formato AAAA-MM-DD HH:MM).")
    momento = momento if momento.tzinfo else momento.replace(tzinfo=ZONA)
    if momento > ahora:
        raise SystemExit(f"ERROR: la hora del conteo está en el futuro: {momento:%Y-%m-%d %H:%M}.")
    return momento


def objetivo_tienda(hay: int, desde_conteo: int, entra_a_tienda: int, incluye_entradas: bool) -> int:
    """Lo que debe quedar en TIENDA al aplicar el conteo.

    - `hay`: lo que Daniel contó en tienda (sin cajas de bodega) a la hora del conteo.
    - `desde_conteo`: suma de movimientos de esa talla DESPUÉS del conteo y antes de
      aplicar (ventas −, entradas +). Si contó a las 18:30 y a las 19:00 se vendieron 2,
      hoy hay 2 menos de lo que contó.
    - `entra_a_tienda`: lo que este mismo plan mete a la tienda (entrada sin lo que va a caja).
      Si el conteo se hizo DESPUÉS de acomodar la mercancía (`incluye_entradas`), ya está
      en `hay` y no se suma otra vez.
    """
    return int(hay) + int(desde_conteo) + (0 if incluye_entradas else int(entra_a_tienda))


# ── Lecturas ────────────────────────────────────────────────────────────────

_SQL_FILAS = """
with cajas as (
    select bc.variante_id,
           coalesce(sum(bc.cantidad) filter (where upper(u.rack) <> 'PISO'), 0) as bodega,
           coalesce(sum(bc.cantidad) filter (where upper(u.rack) = 'PISO'), 0) as piso
    from bodega_contenido bc
    join bodega_caja c on c.id = bc.caja_id
    join bodega_ubicacion u on u.id = c.ubicacion_id
    group by bc.variante_id
), ventas as (
    select variante_id, -sum(cantidad) as vendidas_30d, max(created_at) as ultima_venta
    from movimiento_inventario
    where tipo_movimiento = 'SALIDA_VENTA' and created_at > now() - interval '30 days'
    group by variante_id
)
select v.id, v.sku, p.id as producto_id, p.nombre as producto, v.talla, v.color,
       coalesce(e.nombre, '') as escuela, v.stock_actual,
       coalesce(cj.bodega, 0) as bodega, coalesce(cj.piso, 0) as piso,
       v.costo_referencia, v.precio_venta, v.ultimo_conteo_at,
       coalesce(vt.vendidas_30d, 0) as vendidas_30d, vt.ultima_venta,
       exists(select 1 from conjunto_componente k where k.conjunto_id = p.id) as es_conjunto,
       v.activo and p.activo as activo
from variante v
join producto p on p.id = v.producto_id
left join escuela e on e.id = p.escuela_id
left join cajas cj on cj.variante_id = v.id
left join ventas vt on vt.variante_id = v.id
where {where}
order by {orden}
"""


def filas(conn, where: str, params: dict | None = None, orden: str = "v.stock_actual, p.nombre, v.id") -> list[dict]:
    """Tallas con su existencia por partes. `where` usa los alias v, p, e."""
    rs = conn.execute(text(_SQL_FILAS.format(where=where, orden=orden)), params or {})
    out = []
    for r in rs.mappings():
        d = dict(r)
        d["tienda"] = int(d["stock_actual"]) - int(d["bodega"]) - int(d["piso"])
        out.append(d)
    return out


def buscar_texto(conn, texto: str, *, escuela: str | None = None, talla: str | None = None,
                 solo_activas: bool = True, limite: int = 40) -> list[dict]:
    """Todas las palabras del texto en nombre+color+escuela (sin acentos)."""
    condiciones = ["true"]
    params: dict = {}
    if solo_activas:
        condiciones.append("v.activo and p.activo")
    for i, palabra in enumerate(sin_acentos(texto).split()):
        condiciones.append(
            f"translate(lower(p.nombre || ' ' || coalesce(v.color,'') || ' ' || coalesce(e.nombre,'')),"
            f" 'áéíóúüñ', 'aeiouun') like :w{i}")
        params[f"w{i}"] = f"%{palabra}%"
    if escuela:
        condiciones.append("translate(lower(coalesce(e.nombre,'')), 'áéíóúüñ', 'aeiouun') like :esc")
        params["esc"] = f"%{sin_acentos(escuela)}%"
    if talla:
        condiciones.append("lower(v.talla) = lower(:talla)")
        params["talla"] = str(talla).strip()
    res = filas(conn, " and ".join(condiciones), params, orden="p.nombre, v.talla, v.id")
    return res[:limite]


def resolver(conn, item: dict, donde: str) -> dict:
    """Un renglón del plan → UNA talla. Por `sku`, `variante_id` o `buscar` (+`talla`, `escuela`)."""
    if item.get("variante_id") is not None:
        r = filas(conn, "v.id = :id", {"id": int(item["variante_id"])})
    elif item.get("sku"):
        r = filas(conn, "upper(v.sku) = upper(:sku)", {"sku": str(item["sku"]).strip()})
    elif item.get("buscar"):
        r = buscar_texto(conn, item["buscar"], escuela=item.get("escuela"), talla=item.get("talla"), limite=12)
    else:
        raise SystemExit(f"ERROR: {donde}: cada renglón necesita «sku», «variante_id» o «buscar».")
    if not r:
        raise SystemExit(f"ERROR: {donde}: no encontré {item.get('sku') or item.get('buscar') or item.get('variante_id')!r}.")
    if len(r) > 1:
        opciones = "\n".join(f"    {f['sku']}  {f['producto']} · {f['talla']} · {f['escuela'] or 'general'}" for f in r[:8])
        raise SystemExit(f"ERROR: {donde}: «{item.get('buscar')}» es ambiguo ({len(r)}). Usa el SKU:\n{opciones}")
    fila = r[0]
    if not fila["activo"]:
        print(f"   ⚠ {donde}: {fila['sku']} {fila['producto']} está INACTIVA.")
    return fila


def nombre_talla(f: dict) -> str:
    esc = f" · {f['escuela']}" if f.get("escuela") and f["escuela"].lower() not in f["producto"].lower() else ""
    return f"{f['producto']} {f['talla']}{esc}"


def cifra(n: int) -> str:
    return f"−{abs(int(n))}" if int(n) < 0 else str(int(n))
