"""Demanda no atendida: lo que pidieron y no se pudo vender.

La Libreta dice qué SÍ había. Nadie guarda qué faltó, y ese es el dato que
sirve para decidir qué pedir. Aquí se junta **sin pedirle nada a la
empleada**: se deduce de lo que ella ya hace.

    busqueda_vacia  buscó y el catálogo no devolvió nada
    talla_agotada   tocó una talla que está en cero
    carrito_vacio   armó una venta y la canceló sin cobrar

Reglas de diseño:

1. **Anotar nunca falla y nunca tarda.** Va a un JSON local, igual que la
   Libreta. Si no hay red, no importa. Si el archivo está corrupto, tampoco.
2. **La inteligencia va en el drenado, no en la captura.** Teclear "cami" y
   luego "camisa" dispara dos búsquedas vacías; `colapsar` se queda con la
   última de la cadena. Así la UI puede ser tonta y el dato sale limpio.
3. **Una señal suelta es ruido.** Los agregados existen para ver repetición:
   la misma talla pedida cinco veces en la semana es una orden de compra.
"""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

BUSQUEDA_VACIA = "busqueda_vacia"
TALLA_AGOTADA = "talla_agotada"
CARRITO_VACIO = "carrito_vacio"

# Menos de esto es un teclazo, no una búsqueda.
LARGO_MINIMO = 3
# Dentro de esta ventana, "cami" y "camisa" son la misma persona escribiendo.
VENTANA_TECLEO = timedelta(seconds=90)
_QUEUE_FILENAME = "demanda_pendiente.json"
_LOCK = threading.Lock()


def _queue_path():
    from pos_uniformes.utils.config import satellite_data_dir

    return satellite_data_dir() / "data" / _QUEUE_FILENAME


def _load_raw() -> list[dict]:
    try:
        path = _queue_path()
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — jamás estorbar al mostrador
        return []
    return payload if isinstance(payload, list) else []


def _save_raw(entries: list[dict]) -> None:
    path = _queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def anotar(
    tipo: str,
    *,
    texto: str = "",
    sku: str = "",
    producto: str = "",
    talla: str = "",
    piezas: int = 1,
    employee_code: str = "",
    origen: str = "",
    momento: datetime | None = None,
) -> None:
    """Deja la señal en la cola local. No lanza excepciones nunca."""
    try:
        entrada = {
            "tipo": str(tipo),
            "texto": str(texto or "").strip()[:120],
            "sku": str(sku or "").strip()[:40],
            "producto": str(producto or "").strip()[:160],
            "talla": str(talla or "").strip()[:30],
            "piezas": max(1, int(piezas or 1)),
            "employee_code": str(employee_code or "").upper()[:40],
            "origen": str(origen or "")[:60],
            "created_at": (momento or datetime.now()).isoformat(),
        }
        with _LOCK:
            entries = _load_raw()
            entries.append(entrada)
            _save_raw(entries)
    except Exception:  # noqa: BLE001 — una señal perdida no vale una venta
        pass


def pendientes() -> list[dict]:
    with _LOCK:
        return _load_raw()


def _momento(entrada: dict) -> datetime:
    try:
        return datetime.fromisoformat(str(entrada.get("created_at")))
    except (TypeError, ValueError):
        return datetime.min


def colapsar(entradas: list[dict]) -> list[dict]:
    """Limpia el ruido de teclear (puro).

    Tira las búsquedas cortas y, de una cadena como cami → camis → camisa
    hecha por la misma empleada dentro de la ventana, deja solo la última.
    Todo lo que no es búsqueda pasa intacto.
    """
    busquedas, otras = [], []
    for e in entradas or []:
        (busquedas if e.get("tipo") == BUSQUEDA_VACIA else otras).append(e)

    busquedas = [b for b in busquedas if len(str(b.get("texto", "")).strip()) >= LARGO_MINIMO]
    busquedas.sort(key=_momento)

    limpias: list[dict] = []
    for actual in busquedas:
        texto = str(actual.get("texto", "")).strip().lower()
        reemplazo = False
        for indice in range(len(limpias) - 1, -1, -1):
            previo = limpias[indice]
            if previo.get("employee_code") != actual.get("employee_code"):
                continue
            if _momento(actual) - _momento(previo) > VENTANA_TECLEO:
                break
            anterior = str(previo.get("texto", "")).strip().lower()
            if texto.startswith(anterior) or anterior.startswith(texto):
                # La cadena crece: nos quedamos con la palabra más completa.
                limpias[indice] = actual if len(texto) >= len(anterior) else previo
                reemplazo = True
                break
        if not reemplazo:
            limpias.append(actual)
    return otras + limpias


def drenar(session) -> int:
    """Sube las señales pendientes ya colapsadas. Devuelve cuántas subió."""
    from pos_uniformes.database.models import DemandaNoAtendida

    with _LOCK:
        entradas = _load_raw()
        if not entradas:
            return 0
        limpias = colapsar(entradas)
        for e in limpias:
            session.add(
                DemandaNoAtendida(
                    tipo=str(e.get("tipo", "")),
                    texto=str(e.get("texto", "")),
                    sku=str(e.get("sku", "")),
                    producto=str(e.get("producto", "")),
                    talla=str(e.get("talla", "")),
                    piezas=int(e.get("piezas", 1) or 1),
                    employee_code=str(e.get("employee_code", "")),
                    origen=str(e.get("origen", "")),
                    created_at=_momento(e),
                )
            )
        session.commit()
        _save_raw([])
        return len(limpias)


# ─── Lectura ─────────────────────────────────────────────────────────────
def listar(session, desde, hasta, *, tipo: str | None = None) -> list:
    from sqlalchemy import select

    from pos_uniformes.database.models import DemandaNoAtendida

    stmt = select(DemandaNoAtendida).where(
        DemandaNoAtendida.created_at >= desde, DemandaNoAtendida.created_at <= hasta
    )
    if tipo:
        stmt = stmt.where(DemandaNoAtendida.tipo == tipo)
    return list(session.scalars(stmt.order_by(DemandaNoAtendida.created_at)).all())


@dataclass(frozen=True)
class Falta:
    clave: str
    veces: int
    piezas: int
    ultima: datetime | None

    @property
    def urgente(self) -> bool:
        """Repetido de verdad: ya no es ruido, es que falta producto."""
        return self.veces >= 3


def _agrupar(filas, clave) -> list[Falta]:
    acc: dict[str, list] = defaultdict(lambda: [0, 0, None])
    for f in filas:
        k = (clave(f) or "").strip()
        if not k:
            continue
        acc[k][0] += 1
        acc[k][1] += int(getattr(f, "piezas", 1) or 1)
        momento = getattr(f, "created_at", None)
        if momento and (acc[k][2] is None or momento > acc[k][2]):
            acc[k][2] = momento
    faltas = [Falta(k, v[0], v[1], v[2]) for k, v in acc.items()]
    return sorted(faltas, key=lambda x: (-x.veces, -x.piezas, x.clave))


def por_producto_talla(filas) -> list[Falta]:
    """Lo que se tocó estando agotado: la lista de qué pedir."""
    return _agrupar(
        [f for f in filas if getattr(f, "tipo", "") == TALLA_AGOTADA],
        lambda f: f"{f.producto} · {f.talla}".strip(" ·"),
    )


def por_texto(filas) -> list[Falta]:
    """Lo que buscaron y no existe: puede ser catálogo incompleto o sinónimo."""
    return _agrupar(
        [f for f in filas if getattr(f, "tipo", "") == BUSQUEDA_VACIA],
        lambda f: str(f.texto).lower(),
    )


@dataclass(frozen=True)
class ResumenDemanda:
    busquedas_vacias: int
    tallas_agotadas: int
    carritos_vacios: int
    piezas_perdidas: int


def resumen(filas) -> ResumenDemanda:
    def cuenta(tipo):
        return sum(1 for f in filas if getattr(f, "tipo", "") == tipo)

    return ResumenDemanda(
        busquedas_vacias=cuenta(BUSQUEDA_VACIA),
        tallas_agotadas=cuenta(TALLA_AGOTADA),
        carritos_vacios=cuenta(CARRITO_VACIO),
        piezas_perdidas=sum(
            int(getattr(f, "piezas", 1) or 1)
            for f in filas
            if getattr(f, "tipo", "") == TALLA_AGOTADA
        ),
    )
