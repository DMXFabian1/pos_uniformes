"""Oportunidades de ahora mismo, explicadas en palabras.

El bot ya calcula por dentro si entrar o no: compara lo que dice su modelo con lo que pide el
mercado y descuenta las comisiones. Este módulo toma esas decisiones y las convierte en algo que
se lee de un vistazo, agrupado por mercado: qué comprar, a qué precio, cuánto se gana si acierta,
y por qué.

No decide nada nuevo: traduce lo que el motor ya decidió.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from .storage import latest_markets, scan

# Cuánto vale una señal antes de considerarla vieja. Los mercados de 5 minutos se mueven rápido.
FRESCURA_S = {"updown_model": 90, "model_deviation": 300, "smart_money": 600,
              "complement_buy": 60, "complement_sell": 60, "multi_buy_all_yes": 120,
              "multi_buy_all_no": 120, "spread_capture": 180}
FRESCURA_POR_DEFECTO = 300

GRUPOS = {"crypto_updown": ("Cripto", "Ventanas de 5 y 15 minutos de Bitcoin"),
          "nba": ("NBA", "Partidos y futuros de la NBA"),
          "tennis": ("Tenis", "Partidos y torneos de tenis")}


VEREDICTOS = {
    "entrar": ("ENTRAR", "La ventaja cubre de sobra la comisión y el modelo está seguro."),
    "justa": ("AJUSTADA", "Da números, pero por poco. Si dudas, déjala pasar."),
    "pasada": ("YA PASÓ", "Se detectó hace rato: el precio ya se movió. No entres a ciegas."),
}

# Prioridad por cuánto supera la señal al edge mínimo requerido de su estrategia (medido en el
# ledger: coste de salida + selección adversa + margen). Sin ledger se usa el mínimo por defecto.
PRIORIDADES = {
    "S": "Muy por encima del mínimo y con el modelo seguro. Es de las pocas que valen la pena.",
    "A": "Cómodamente por encima del mínimo.",
    "B": "Por encima del mínimo, con poco margen.",
    "C": "Justo en el límite. Pasarla no cuesta nada.",
    "NO TRADE": "Por debajo del mínimo que esta estrategia necesita para ser rentable. No se entra.",
}
MINIMO_POR_DEFECTO = 0.01     # USD por share, mientras no haya ledger que lo mida


@dataclass
class Oportunidad:
    ts_ms: int
    grupo: str
    categoria: str
    kind: str
    condition_id: str
    mercado: str
    accion: str                 # "Comprar Up", "Comprar Lakers"…
    precio: float               # a cuánto se compra
    edge_neto: float            # ganancia esperada por share, ya sin comisiones
    edge_pct: float             # la misma ganancia, en % sobre lo invertido
    tamano: float               # shares que soporta el libro
    inversion: float            # USD que costaría
    ganancia: float             # USD esperados si el modelo acierta
    confianza: float
    fee: float
    razon: str                  # explicación en palabras
    veredicto: str = "justa"    # entrar | justa | pasada
    prioridad: str = "C"        # S | A | B | C | NO TRADE
    porque: str = ""            # por qué existe este trade, en una frase
    edge_minimo: float = MINIMO_POR_DEFECTO
    estrategia: str = ""
    contexto: list[dict[str, Any]] = field(default_factory=list)   # el partido o el mercado
    matematica: list[dict[str, Any]] = field(default_factory=list)  # de dónde sale la ventaja
    detalle: dict[str, Any] = field(default_factory=dict)

    @property
    def perdida(self) -> float:
        """Lo que se pierde si falla. En estos mercados, todo lo invertido."""
        return round(self.inversion, 2)

    @property
    def prob_acierto(self) -> float | None:
        p = self.detalle.get("p_model")
        return round(float(p), 4) if p is not None else None

    @property
    def titulo_veredicto(self) -> str:
        return VEREDICTOS[self.veredicto][0]

    @property
    def nota_prioridad(self) -> str:
        """La razón real de la prioridad: caducar y quedarse corta de ventaja no es lo mismo."""
        if not self.fresca:
            return VEREDICTOS["pasada"][1]
        return PRIORIDADES.get(self.prioridad, "")

    @property
    def veces_el_minimo(self) -> float:
        return round(self.edge_neto / self.edge_minimo, 2) if self.edge_minimo > 0 else 0.0

    @property
    def nota_veredicto(self) -> str:
        return VEREDICTOS[self.veredicto][1]

    @property
    def antiguedad_s(self) -> float:
        return max(0.0, (time.time() * 1000 - self.ts_ms) / 1000)

    @property
    def fresca(self) -> bool:
        return self.antiguedad_s <= FRESCURA_S.get(self.kind, FRESCURA_POR_DEFECTO)

    def to_dict(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in ("ts_ms", "grupo", "categoria", "kind", "condition_id", "mercado", "accion",
                                           "precio", "edge_neto", "edge_pct", "tamano", "inversion", "ganancia",
                                           "confianza", "fee", "razon", "veredicto", "contexto", "matematica",
                                           "detalle", "prioridad", "porque", "edge_minimo", "estrategia")}
        d.update(antiguedad_s=round(self.antiguedad_s, 1), fresca=self.fresca, perdida=self.perdida,
                 prob_acierto=self.prob_acierto, titulo_veredicto=self.titulo_veredicto,
                 nota_veredicto=self.nota_veredicto, nota_prioridad=self.nota_prioridad,
                 veces_el_minimo=self.veces_el_minimo)
        return d


def _pct(x: float, d: int = 0) -> str:
    return f"{x * 100:.{d}f} %"


def _explicar(kind: str, m: dict[str, Any], mercado: str, precio: float, edge: float) -> tuple[str, str]:
    """Devuelve (acción, razón) en palabras llanas."""
    lado = str(m.get("side") or "")
    p_modelo, p_mercado = m.get("p_model"), m.get("p_market")

    if kind == "updown_model":
        direccion = "suba" if lado == "up" else "baje"
        mueve = m.get("moneyness_bps")
        seg = m.get("seconds_left")
        piezas = []
        if mueve is not None:
            if abs(mueve) < 0.5:
                piezas.append("Bitcoin está justo en el precio de apertura, así que ahora mismo es una moneda al aire")
            else:
                piezas.append(f"Bitcoin va {abs(mueve):.0f} puntos básicos "
                              f"{'por encima' if mueve > 0 else 'por debajo'} del precio de apertura")
        if seg is not None:
            piezas.append(f"quedan {int(seg)} segundos de la ventana")
        if p_modelo is not None:
            piezas.append(f"el modelo calcula {_pct(p_modelo)} de que {direccion}, "
                          f"y el mercado lo vende como si fuera {_pct(precio)}")
        else:
            piezas.append(f"el mercado lo vende a {precio:.2f}")
        prev = m.get("prev_up_won")
        if prev is not None:
            piezas.append(f"la ventana anterior terminó {'arriba' if prev else 'abajo'}")
        texto = ". ".join(p[0].upper() + p[1:] if i == 0 else p for i, p in enumerate(piezas)) + "."
        return f"Comprar {'Up' if lado == 'up' else 'Down'}", texto

    if kind == "model_deviation":
        marcador = m.get("score")
        periodo = m.get("period")
        equipo = {"home": "local", "away": "visitante", "draw": "empate"}.get(lado, lado)
        piezas = [f"El modelo da {_pct(p_modelo)} al {equipo} y el mercado lo vende a {precio:.2f}"]
        if marcador:
            piezas.append(f"marcador {marcador}" + (f" en {periodo}" if periodo else ""))
        if m.get("tau") is not None:
            piezas.append(f"queda el {_pct(m['tau'])} del partido")
        return f"Comprar {equipo}", ". ".join(piezas) + "."

    if kind == "smart_money":
        nombre = m.get("wallet_name") or str(m.get("wallet", ""))[:10]
        piezas = [f"La wallet {nombre} acaba de entrar con {float(m.get('their_usd') or 0):,.0f} USD a "
                  f"{float(m.get('their_price') or 0):.2f}"]
        if m.get("wallet_n") and m.get("wallet_roi") is not None:
            piezas.append(f"su historial son {m['wallet_n']} posiciones cerradas con {_pct(m['wallet_roi'], 1)} "
                          f"de retorno")
        piezas.append(f"el precio sigue en {precio:.2f}")
        return "Seguir la entrada", ". ".join(piezas) + "."

    if kind in ("complement_buy", "complement_sell"):
        if kind == "complement_buy":
            return "Comprar ambos lados", (f"Comprando SÍ y NO a la vez el par cuesta menos de 1 USD, y siempre "
                                           f"paga 1. Ganancia asegurada de {edge:.3f} por share si se llenan las dos "
                                           f"patas.")
        return "Vender ambos lados", (f"Vender SÍ y NO a la vez da más de 1 USD, y crear el par cuesta 1. "
                                      f"Ganancia asegurada de {edge:.3f} por share si se llenan las dos patas.")

    if kind.startswith("multi_buy"):
        n = m.get("n", "varios")
        return "Comprar todas las opciones", (f"El evento tiene {n} resultados y exactamente uno gana. Comprándolos "
                                              f"todos se paga menos de lo que se cobra: {edge:.3f} por share seguro.")

    if kind == "spread_capture":
        st = m.get("spread_ticks")
        return "Poner órdenes dentro del spread", (f"El hueco entre compra y venta es de {st} ticks y hay actividad. "
                                                   f"Poniendo órdenes por dentro se cobra la diferencia sin pagar "
                                                   f"comisión, si se llenan los dos lados.")
    return "Revisar", f"Señal {kind} con ventaja de {edge:.3f} por share."


def _fila(etiqueta: str, valor: Any, tipo: str = "") -> dict[str, Any]:
    return {"etiqueta": etiqueta, "valor": valor, "tipo": tipo}


def _mmss(segundos: Any) -> str:
    try:
        s = int(float(segundos))
    except (TypeError, ValueError):
        return "–"
    return f"{s // 60}:{s % 60:02d}"


def _contexto(kind: str, m: dict[str, Any], mercado: str) -> list[dict[str, Any]]:
    """Lo que está pasando: el partido, la ventana, quién entró."""
    if kind == "updown_model":
        strike, spot = m.get("strike"), m.get("spot")
        mv = m.get("moneyness_bps")
        return [
            _fila("Activo", str(m.get("symbol") or "–").upper()),
            _fila("Precio de apertura", f"{strike:,.0f}" if strike else "–"),
            _fila("Precio ahora", f"{spot:,.0f}" if spot else "–",
                  "bueno" if (mv or 0) > 0 else "malo" if (mv or 0) < 0 else ""),
            _fila("Se movió", f"{mv:+.1f} puntos básicos" if mv is not None else "–",
                  "bueno" if (mv or 0) > 0 else "malo" if (mv or 0) < 0 else ""),
            _fila("Queda de la ventana", _mmss(m.get("seconds_left"))),
        ]
    if kind == "model_deviation":
        equipo = {"home": "local", "away": "visitante", "draw": "empate"}.get(str(m.get("side")), "–")
        return [
            _fila("Marcador", str(m.get("score") or "–")),
            _fila("Período", str(m.get("period") or "–")),
            _fila("Queda del partido", _pct(m.get("tau", 0)) if m.get("tau") is not None else "–"),
            _fila("Lado", equipo),
            _fila("Precio antes de empezar", f"{m['pregame']:.2f}" if m.get("pregame") else "–"),
        ]
    if kind == "smart_money":
        return [
            _fila("Wallet", str(m.get("wallet_name") or m.get("wallet", ""))[:24]),
            _fila("Entró con", f"{float(m.get('their_usd') or 0):,.0f} USD"),
            _fila("A precio", f"{float(m.get('their_price') or 0):.3f}"),
            _fila("Su historial", f"{m.get('wallet_n', 0)} posiciones cerradas"),
            _fila("Su retorno", _pct(m.get("wallet_roi", 0), 1),
                  "bueno" if (m.get("wallet_roi") or 0) > 0 else "malo"),
        ]
    if kind == "spread_capture":
        return [
            _fila("Hueco compra-venta", f"{m.get('spread_ticks', 0):.0f} ticks"),
            _fila("Actividad", f"{m.get('tpm', 0):.1f} trades por minuto"),
            _fila("Precio medio", f"{m.get('mid', 0):.3f}" if m.get("mid") else "–"),
        ]
    return [_fila("Tipo", "arbitraje: el resultado no importa"),
            _fila("Patas", str(m.get("n") or 2))]


def _matematica(kind: str, m: dict[str, Any], precio: float, fee: float, edge: float,
                tamano: float) -> list[dict[str, Any]]:
    """De dónde sale la ventaja, paso a paso, hasta el número final."""
    filas: list[dict[str, Any]] = []
    p_modelo = m.get("p_model")
    if kind in ("updown_model", "model_deviation") and p_modelo is not None:
        filas += [
            _fila("El modelo dice", _pct(p_modelo, 1)),
            _fila("El mercado pide", _pct(precio, 1)),
            _fila("Diferencia a favor", f"{(p_modelo - precio) * 100:+.1f} puntos", "bueno"),
        ]
    elif kind == "smart_money":
        filas += [
            _fila("Retorno histórico", _pct(m.get("wallet_roi", 0), 1)),
            _fila("Se asume la mitad", _pct((m.get("wallet_roi", 0) or 0) / 2, 1)),
        ]
    elif kind == "spread_capture":
        filas += [
            _fila("Medio hueco", f"{(m.get('spread_ticks', 0) / 2) * 0.01:.3f} por share"),
            _fila("Volatilidad reciente", f"{m.get('mid_vol', 0):.4f}", "malo"),
        ]
    filas.append(_fila("Comisión", f"−{fee:.4f} por share", "malo" if fee > 0 else ""))
    minimo = m.get("_edge_minimo")
    if minimo:
        filas.append(_fila("Mínimo que pide esta estrategia", f"{minimo:.4f} por share"))
    filas.append(_fila("Ventaja neta", f"{edge:+.4f} por share", "bueno" if edge > 0 else "malo"))
    filas.append(_fila("Por cada 100 USD", f"{edge / precio * 100:+.1f} USD" if precio else "–",
                       "bueno" if edge > 0 else "malo"))
    return filas


def _decidir(kind: str, edge: float, precio: float, confianza: float, fresca: bool, fee: float) -> str:
    """Gradúa la señal que el motor ya aprobó: fuerte, justa o caducada."""
    if not fresca:
        return "pasada"
    edge_pct = edge / precio if precio else 0
    holgada = edge > 2 * fee and edge_pct >= 0.05
    return "entrar" if (holgada and confianza >= 0.55) else "justa"


def _prioridad(edge: float, minimo: float, confianza: float, fresca: bool) -> str:
    """S/A/B/C/NO TRADE según cuántas veces la señal supera el mínimo que su estrategia necesita."""
    if not fresca:
        return "NO TRADE"
    if minimo <= 0:
        minimo = MINIMO_POR_DEFECTO
    veces = edge / minimo
    if veces < 1:
        return "NO TRADE"
    if veces >= 3 and confianza >= 0.65:
        return "S"
    if veces >= 2 and confianza >= 0.55:
        return "A"
    if veces >= 1.3:
        return "B"
    return "C"


def minimos_por_estrategia(data_dir: str | Path) -> dict[str, float]:
    """Edge mínimo requerido de cada estrategia, medido en el ledger. Vacío si aún no hay datos."""
    try:
        from .evaluacion import evaluar as evaluar_metricas
        return {e.strategy: e.edge_minimo_requerido for e in evaluar_metricas(data_dir)
                if e.edge_minimo_requerido is not None and e.n >= 20}
    except Exception:  # noqa: BLE001 - un informe roto no debe tumbar la lista de oportunidades
        return {}


def _grupo_de(categoria: str, meta: dict[str, Any]) -> tuple[str, str]:
    if categoria in GRUPOS:
        return GRUPOS[categoria][0], GRUPOS[categoria][1]
    liga = str(meta.get("league") or "")
    if liga in GRUPOS:
        return GRUPOS[liga][0], GRUPOS[liga][1]
    if meta.get("sport") == "crypto" or categoria == "crypto_updown":
        return GRUPOS["crypto_updown"]
    return categoria.capitalize() or "Otros", ""


def listar(data_dir: str | Path, minutos: float = 30, solo_frescas: bool = False,
           min_edge: float = 0.0) -> list[Oportunidad]:
    """Señales recientes convertidas en oportunidades legibles, la más jugosa primero."""
    lf = scan(data_dir, "signals")
    if lf is None:
        return []
    desde = int((time.time() - minutos * 60) * 1000)
    df = lf.filter(pl.col("ts_ms") >= desde).sort("ts_ms", descending=True).collect()
    if not df.height:
        return []
    mk = latest_markets(data_dir)
    minimos = minimos_por_estrategia(data_dir)
    info: dict[str, dict[str, Any]] = {}
    if mk is not None:
        for r in mk.to_dicts():
            info[r["condition_id"]] = r

    vistos: set[tuple[str, str]] = set()
    out: list[Oportunidad] = []
    for r in df.to_dicts():
        try:
            m = json.loads(r["meta"] or "{}")
            legs = json.loads(r["legs"] or "[]")
        except json.JSONDecodeError:
            continue
        clave = (r["condition_id"], str(m.get("side") or r["kind"]))
        if clave in vistos:                      # solo la más reciente de cada mercado y lado
            continue
        vistos.add(clave)
        edge = float(r["edge_net"])
        if edge < min_edge:
            continue
        mi = info.get(r["condition_id"], {})
        categoria = str(mi.get("category") or "")
        mercado = str(mi.get("question") or m.get("game_id") or r["condition_id"][:12])
        precio = float(m.get("entry") or (legs[0]["price"] if legs else 0) or 0)
        tam = float(r["size"])
        accion, razon = _explicar(r["kind"], m, mercado, precio, edge)
        nombre_lado = ""
        if legs and legs[0].get("outcome") and r["kind"] in ("model_deviation", "smart_money"):
            nombre_lado = str(legs[0]["outcome"])
            accion = f"Comprar {nombre_lado}"
        grupo, _sub = _grupo_de(categoria, m)
        inversion = round(precio * tam, 2) if precio else 0.0
        fee = round(float(r["fee_est"]), 4)
        op = Oportunidad(
            ts_ms=int(r["ts_ms"]), grupo=grupo, categoria=categoria, kind=r["kind"],
            condition_id=r["condition_id"], mercado=mercado, accion=accion, precio=round(precio, 4),
            edge_neto=round(edge, 4), edge_pct=round(edge / precio, 4) if precio else 0.0, tamano=tam,
            inversion=inversion, ganancia=round(edge * tam, 2), confianza=float(r["confidence"]),
            fee=fee, razon=razon, detalle=m)
        op.estrategia = str(m.get("strategy") or r["kind"])
        op.edge_minimo = round(minimos.get(op.estrategia, MINIMO_POR_DEFECTO), 5)
        op.porque = str(m.get("por_que") or "")
        op.contexto = _contexto(r["kind"], m, mercado)
        op.matematica = _matematica(r["kind"], {**m, "_edge_minimo": op.edge_minimo}, precio, fee, edge, tam)
        op.veredicto = _decidir(r["kind"], edge, precio, op.confianza, op.fresca, fee)
        op.prioridad = _prioridad(edge, op.edge_minimo, op.confianza, op.fresca)
        out.append(op)
    if solo_frescas:
        out = [o for o in out if o.fresca]
    # Lo vigente manda: una señal caducada con mucha ventaja no sirve, el precio ya cambió.
    out.sort(key=lambda o: (not o.fresca, -o.edge_pct, -o.confianza))
    return out


def por_grupo(ops: list[Oportunidad]) -> dict[str, list[Oportunidad]]:
    d: dict[str, list[Oportunidad]] = {}
    for o in ops:
        d.setdefault(o.grupo, []).append(o)
    return d


def resumen_grupo(ops: list[Oportunidad]) -> dict[str, Any]:
    """Cuántas oportunidades hay en un grupo y cuál es la mejor."""
    frescas = [o for o in ops if o.fresca]
    mejor = max(ops, key=lambda o: o.edge_pct) if ops else None
    return {"total": len(ops), "frescas": len(frescas),
            "mejor_edge_pct": mejor.edge_pct if mejor else 0.0,
            "mejor": mejor.to_dict() if mejor else None,
            "ganancia_total": round(sum(o.ganancia for o in frescas), 2)}


def formatear(ops: list[Oportunidad], ancho: int = 100) -> str:
    if not ops:
        return ("Ahora mismo el bot no ve ninguna oportunidad.\n\n"
                "Eso es normal y es buena señal: solo avisa cuando los números dan después de comisiones.\n"
                "Si el bot acaba de arrancar, dale unos minutos para que llene los libros.")
    lineas = []
    for grupo, lista in por_grupo(ops).items():
        r = resumen_grupo(lista)
        lineas.append("=" * ancho)
        lineas.append(f"  {grupo.upper()}   {r['frescas']} vigentes de {len(lista)}   ·   "
                      f"mejor ventaja {_pct(r['mejor_edge_pct'], 1)} sobre lo invertido")
        lineas.append("=" * ancho)
        for o in lista[:8]:
            etiqueta = o.prioridad if o.fresca else f"{o.titulo_veredicto}"
            lineas.append(f"\n  [{etiqueta:^8}] {o.accion.upper()}  ·  {o.mercado[:58]}")
            lineas.append(f"     {o.nota_prioridad}")
            if o.porque:
                lineas.append(f"     POR QUÉ EXISTE: {o.porque}")
            lineas.append(f"     precio {o.precio:.3f}   invertir {o.inversion:>8.2f}   "
                          f"ganar {o.ganancia:>7.2f}   perder {o.perdida:>8.2f}   "
                          f"ventaja {_pct(o.edge_pct, 1):>7}")
            lineas.append(f"     ventaja {o.edge_neto:.4f} por share, {o.veces_el_minimo:.1f}x el mínimo "
                          f"que pide {o.estrategia} ({o.edge_minimo:.4f})")
            if o.prob_acierto is not None:
                lineas.append(f"     acierta {_pct(o.prob_acierto)} de las veces según el modelo")
            lineas.append(f"     {o.razon}")
            if not o.fresca:
                lineas.append(f"     (detectada hace {o.antiguedad_s / 60:.0f} min)")
        lineas.append("")
    return "\n".join(lineas)
