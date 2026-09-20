"""Mapa de conteos: qué está contado y qué no, de un vistazo y por capas.

Daniel (2026-09-20): "una guía visual para ver qué está contado y qué no…
como el panel de uniformes, pero estructurado para que no sea megalítico".

Tres capas, cada una un dict listo para pintar:
  1. `resumen(session)`      → escuelas (con su nivel) y tipos de básicos, cada
                                uno con cuántas tallas están al día / viejas / nunca.
  2. `escuela(session, id)`  /  `basicos(session, tipo)` → sus prendas, mismas cifras.
  3. dentro de cada prenda   → sus tallas con días desde el último conteo.

"Al día" = contada hace menos de la vigencia de esa escuela (ConfigConteoEscuela
o el default); "vieja" = contada pero ya venció; "nunca" = sin conteo.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Escuela, NivelEducativo, Producto
from pos_uniformes.services.conteo_service import (
    _TIPOS_VIRTUALES,
    _talla_sort_key,
    agrupar_variantes_por_producto,
    obtener_variantes_basicos_para_conteo,
    obtener_variantes_para_conteo_varias,
)

AL_DIA, VIEJA, NUNCA = "al_dia", "vieja", "nunca"


def estado_talla(v) -> str:
    if v.dias_desde_conteo is None:
        return NUNCA
    return VIEJA if v.requiere_conteo else AL_DIA


def _cifras(variantes) -> dict:
    c = Counter(estado_talla(v) for v in variantes)
    total = sum(c.values())
    dias = [v.dias_desde_conteo for v in variantes if v.dias_desde_conteo is not None]
    return {
        "tallas": total, "al_dia": c[AL_DIA], "viejas": c[VIEJA], "nunca": c[NUNCA],
        "pct_al_dia": round(100 * c[AL_DIA] / total) if total else 0,
        "ultimo_dias": min(dias) if dias else None,   # el conteo más reciente que la tocó
        "estado": AL_DIA if total and c[AL_DIA] == total else (NUNCA if total and c[NUNCA] == total else (VIEJA if total else NUNCA)),
    }


def _prendas(grupos) -> list[dict]:
    out = []
    for g in grupos:
        if g.get("virtual") or g["tipo_pieza"] in _TIPOS_VIRTUALES:
            continue
        vs = sorted(g["variantes"], key=_talla_sort_key)
        out.append({
            "nombre": str(g["producto_nombre"]).split("|")[0].strip(),
            "tipo_pieza": g["tipo_pieza"],
            **_cifras(vs),
            "tallas_detalle": [
                {"talla": v.talla, "color": v.color or "", "estado": estado_talla(v), "dias": v.dias_desde_conteo,
                 "stock": int(v.stock_actual)}
                for v in vs
            ],
        })
    return out


def _niveles_por_escuela(session: Session) -> dict[int, str]:
    filas = session.execute(
        select(Producto.escuela_id, NivelEducativo.nombre)
        .join(NivelEducativo, NivelEducativo.id == Producto.nivel_educativo_id)
        .where(Producto.escuela_id.is_not(None), Producto.activo.is_(True))
        .distinct()
    ).all()
    por_escuela: dict[int, set[str]] = defaultdict(set)
    for eid, nivel in filas:
        por_escuela[int(eid)].add(str(nivel))
    return {eid: (next(iter(ns)) if len(ns) == 1 else "Varios niveles") for eid, ns in por_escuela.items()}


def _jornadas_por_clave(session: Session) -> dict:
    """{clave de alcance: {"en_proceso": quién·hoja, "quien": quién terminó la última}}:
    lo que el tablero de siempre decía en sus columnas, ahora en los mosaicos."""
    from pos_uniformes.services import conteo_jornada_service as jn

    out: dict = defaultdict(dict)
    try:
        for clave, j in jn.abiertas_por_alcance(session).items():
            r = jn.ref(j)   # ORM → foto plana (quien, hoja_texto)
            out[clave]["en_proceso"] = r.quien + (f" · {r.hoja_texto}" if r.hoja_texto else "")
        for clave, u in jn.ultimos_conteos(session).items():
            if u.quien:
                out[clave]["quien"] = u.quien
    except Exception:  # noqa: BLE001 — sin jornadas el mapa sirve igual
        pass
    return out


def resumen(session: Session) -> dict:
    escuelas = list(session.scalars(select(Escuela).where(Escuela.activo.is_(True)).order_by(Escuela.nombre)).all())
    por_escuela = obtener_variantes_para_conteo_varias(session, [int(e.id) for e in escuelas])
    niveles = _niveles_por_escuela(session)
    jornadas = _jornadas_por_clave(session)
    filas = []
    for e in escuelas:
        vs = [v for v in por_escuela.get(int(e.id), []) if v.tipo_pieza not in _TIPOS_VIRTUALES]
        if not vs:
            continue
        j = jornadas.get(int(e.id), {})
        filas.append({"escuela_id": int(e.id), "nombre": str(e.nombre), "nivel": niveles.get(int(e.id), "Sin nivel"),
                      "en_proceso": j.get("en_proceso", ""), "quien": j.get("quien", ""), **_cifras(vs)})
    basicos_vs = [v for v in obtener_variantes_basicos_para_conteo(session) if v.tipo_pieza not in _TIPOS_VIRTUALES]
    por_tipo: dict[str, list] = defaultdict(list)
    for v in basicos_vs:
        por_tipo[v.tipo_pieza or "Sin tipo"].append(v)
    basicos = []
    for t, vs in sorted(por_tipo.items()):
        j = jornadas.get(("basicos", t), {})
        basicos.append({"tipo_pieza": t, "en_proceso": j.get("en_proceso", ""), "quien": j.get("quien", ""), **_cifras(vs)})
    todo = [v for vs in por_escuela.values() for v in vs if v.tipo_pieza not in _TIPOS_VIRTUALES] + basicos_vs
    return {"total": _cifras(todo), "escuelas": filas, "basicos": basicos}


def escuela(session: Session, escuela_id: int) -> dict:
    e = session.get(Escuela, int(escuela_id))
    vs = obtener_variantes_para_conteo_varias(session, [int(escuela_id)]).get(int(escuela_id), [])
    prendas = _prendas(agrupar_variantes_por_producto(vs))
    return {"titulo": str(e.nombre) if e else f"Escuela {escuela_id}", "prendas": prendas,
            **_cifras([v for v in vs if v.tipo_pieza not in _TIPOS_VIRTUALES])}


def basicos(session: Session, tipo_pieza: str) -> dict:
    vs = [v for v in obtener_variantes_basicos_para_conteo(session) if (v.tipo_pieza or "Sin tipo") == tipo_pieza]
    prendas = _prendas(agrupar_variantes_por_producto(vs))
    return {"titulo": f"Básicos · {tipo_pieza}", "prendas": prendas, **_cifras([v for v in vs if v.tipo_pieza not in _TIPOS_VIRTUALES])}


def todo(session: Session) -> dict:
    """Las tres capas de un jalón (para el kiosko, que lo pinta sin servidor)."""
    r = resumen(session)
    detalles = {
        **{f"e{e['escuela_id']}": escuela(session, e["escuela_id"]) for e in r["escuelas"]},
        **{f"b{b['tipo_pieza']}": basicos(session, b["tipo_pieza"]) for b in r["basicos"]},
    }
    return {**r, "detalles": detalles}


_HTML = """<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Mapa de conteos</title>
<style>
:root{--crema:#f4ede2;--carta:#fffdf8;--tinta:#2c2a27;--tenue:#5f594f;--acento-osc:#8a4326;--borde:#ddd0c0;--verde-bg:#d9ecd0;--verde:#3d6b2f}
*{box-sizing:border-box}body{margin:0;background:var(--crema);color:var(--tinta);font-family:"Avenir Next","Helvetica Neue",sans-serif;font-size:15px}
.app{max-width:1100px;margin:0 auto;padding:18px 22px}
h1{font-size:24px;color:var(--acento-osc);margin:6px 0 2px}.sub{color:var(--tenue);font-size:13px;margin:0 0 12px}
.card{background:var(--carta);border:1px solid var(--borde);border-radius:14px;padding:14px 16px;margin-bottom:10px}
.sem{display:flex;height:9px;border-radius:4px;overflow:hidden;background:#e6ddd0;margin-top:6px}.sem i{display:block;height:100%}
.sem .ok{background:var(--verde)}.sem .old{background:#c98a2b}.sem .no{background:#b9b0a4}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;margin-top:8px}
.tile{background:var(--carta);border:1px solid var(--borde);border-radius:14px;padding:10px 12px;cursor:pointer}.tile:hover{border-color:var(--acento-osc)}
.tile b{display:block;font-size:14px;line-height:1.2}.tile .sub{margin:2px 0 0;font-size:12px}
.tile.al_dia{border-left:5px solid var(--verde)}.tile.vieja{border-left:5px solid #c98a2b}.tile.nunca{border-left:5px solid #b9b0a4}
.tile.proceso{background:#fff4e5;border-color:#e0b27a}.tile .proc{color:#b45309;font-weight:700}
.nivel{font-size:12px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:var(--tenue);margin:16px 0 0}
.ley{display:flex;gap:14px;font-size:12px;color:var(--tenue);margin:6px 0 0}.ley i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:4px;vertical-align:-1px}
.fila{display:flex;justify-content:space-between;align-items:center;cursor:pointer}.fila b{font-size:15px}
.t{display:inline-block;border-radius:8px;padding:6px 9px;margin:6px 6px 0 0;font-weight:700;font-size:13px;border:1px solid var(--borde);background:var(--carta)}
.t.al_dia{background:var(--verde-bg);color:var(--verde);border-color:transparent}.t.vieja{background:#f6e3c6;color:#8a5a12;border-color:transparent}.t.nunca{background:#eee9e1;color:#6f675c;border-color:transparent}
.t small{display:block;font-weight:600;font-size:10px;opacity:.85}
button{border:1px solid var(--borde);background:var(--carta);color:var(--acento-osc);border-radius:12px;padding:10px 16px;font-size:15px;font-weight:700;cursor:pointer;margin:10px 0 0}
.oculto{display:none}.busca{width:100%;border:1px solid var(--borde);border-radius:12px;padding:10px 14px;font-size:16px;margin:8px 0 0;background:var(--carta)}
</style></head><body><div class="app" id="app"></div>
<script>
const D = __DATA__;
const sem = c => { const t = c.tallas || 1; return `<div class="sem"><i class="ok" style="width:${100*c.al_dia/t}%"></i><i class="old" style="width:${100*c.viejas/t}%"></i><i class="no" style="width:${100*c.nunca/t}%"></i></div>`; };
const txt = c => `${c.pct_al_dia}% al día` + (c.ultimo_dias === null ? " · nunca" : c.ultimo_dias === 0 ? " · hoy" : ` · hace ${c.ultimo_dias} d`);
const LEY = `<div class="ley"><span><i style="background:var(--verde)"></i>al día</span><span><i style="background:#c98a2b"></i>viejo</span><span><i style="background:#b9b0a4"></i>nunca</span></div>`;
const norm = s => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
const tile = (e, onclick) => `<div class="tile ${e.estado}${e.en_proceso ? " proceso" : ""}" onclick="${onclick}"><b>${esc(e.nombre)}</b>${sem(e)}<p class="sub">${txt(e)}${e.quien && !e.en_proceso ? " · " + esc(e.quien) : ""}</p>${e.en_proceso ? `<p class="sub proc">En proceso · ${esc(e.en_proceso)}</p>` : ""}</div>`;
function mapa(q) {
  q = norm(q || "");
  const t = D.total;
  let h = `<h1>🗺 Mapa de conteos</h1><p class="sub">Toca una escuela o un tipo de básicos para ver sus prendas · generado ${D.generado}</p>` +
    `<div class="card"><strong>Toda la tienda · ${t.tallas.toLocaleString()} tallas</strong>${sem(t)}<p class="sub" style="margin:6px 0 0">${t.al_dia.toLocaleString()} al día · ${t.viejas.toLocaleString()} viejas · ${t.nunca.toLocaleString()} nunca</p>${LEY}</div>` +
    `<input class="busca" placeholder="Buscar escuela…" value="${esc(q)}" oninput="mapa(this.value)">`;
  const esc_ = D.escuelas.filter(e => !q || norm(e.nombre).includes(q));
  const orden = ["Preescolar", "Primaria", "Secundaria", "Preparatoria", "Varios niveles", "Sin nivel"];
  const niveles = [...new Set(esc_.map(e => e.nivel))].sort((a, b) => (orden.indexOf(a) + 99) % 99 - (orden.indexOf(b) + 99) % 99 || a.localeCompare(b));
  for (const n of niveles) {
    const l = esc_.filter(e => e.nivel === n);
    h += `<div class="nivel">${n} · ${l.length}</div><div class="grid">` + l.map(e => tile(e, `detalle('e${e.escuela_id}')`)).join("") + `</div>`;
  }
  if (!q) h += `<div class="nivel">Básicos · ${D.basicos.length} tipos</div><div class="grid">` + D.basicos.map(b => tile({...b, nombre: b.tipo_pieza}, `detalle('b${esc(b.tipo_pieza)}')`)).join("") + `</div>`;
  document.getElementById("app").innerHTML = h; window.scrollTo(0, 0);
  const i = document.querySelector(".busca"); if (q && i) { i.focus(); i.setSelectionRange(q.length, q.length); }
}
function detalle(k) {
  const d = D.detalles[k]; if (!d) return;
  const prendas = d.prendas.map((p, i) => `<div class="card" style="padding:12px 14px"><div class="fila" onclick="document.getElementById('t${i}').classList.toggle('oculto')"><span><b>${esc(p.nombre)}</b><span class="sub" style="display:block">${p.tipo_pieza ? esc(p.tipo_pieza) + " · " : ""}${p.tallas} tallas · ${txt(p)}</span></span><span>›</span></div>${sem(p)}` +
    `<div id="t${i}" class="oculto">` + p.tallas_detalle.map(t => `<span class="t ${t.estado}">${esc(t.talla)}${t.color && !/^(sin color|unico|único)$/i.test(t.color) ? " " + esc(t.color) : ""}<small>${t.dias === null ? "nunca" : t.dias === 0 ? "hoy" : "hace " + t.dias + " d"} · ${t.stock} pz</small></span>`).join("") + `</div></div>`).join("");
  document.getElementById("app").innerHTML = `<button onclick="mapa()">‹ Mapa</button><h1>${esc(d.titulo)}</h1><p class="sub">${d.tallas} tallas · ${txt(d)}</p>${sem(d)}${LEY}<div style="margin-top:12px">${prendas || "<div class='card'>Sin prendas para contar.</div>"}</div><p class="sub">Toca una prenda para ver sus tallas.</p><button onclick="mapa()">‹ Mapa</button>`;
  window.scrollTo(0, 0);
}
mapa();
</script></body></html>
"""


def html(session: Session) -> str:
    """El mapa completo como una sola página, sin servidor ni sesión (kiosko)."""
    import json
    from datetime import datetime

    datos = todo(session)
    datos["generado"] = datetime.now().strftime("%d/%m %H:%M")
    return _HTML.replace("__DATA__", json.dumps(datos, ensure_ascii=False).replace("</", "<\\/"))
