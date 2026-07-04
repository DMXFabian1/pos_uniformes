"""Servicio de indexación y búsqueda con Meilisearch."""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.orm import Session, selectinload

from pos_uniformes.database.models import Producto, Variante

logger = logging.getLogger(__name__)

MEILI_URL = "http://127.0.0.1:7700"
MEILI_KEY = None
INDEX_NAME = "variantes"

_client = None
_client_checked_at: float = 0
_CLIENT_RETRY_INTERVAL = 30


def _get_client():
    global _client, _client_checked_at
    now = time.monotonic()
    if _client is not None:
        return _client
    if now - _client_checked_at < _CLIENT_RETRY_INTERVAL:
        return None
    _client_checked_at = now
    try:
        import meilisearch
        c = meilisearch.Client(MEILI_URL, MEILI_KEY)
        c.health()
        _client = c
        logger.info("Meilisearch conectado en %s", MEILI_URL)
        return _client
    except Exception as exc:
        logger.debug("Meilisearch no disponible: %s", exc)
        _client = None
        return None


def _get_index():
    client = _get_client()
    if client is None:
        return None
    try:
        return client.index(INDEX_NAME)
    except Exception:
        return None


def index_settings() -> dict[str, Any]:
    """Configuración del índice (separada para poder testearla)."""
    return {
            "searchableAttributes": [
                "nombre_base",
                "nombre_producto",
                "sku",
                "talla",
                "color",
                "tipo_pieza",
                "tipo_prenda",
                "categoria",
                "escuela",
                "genero",
                "marca",
            ],
            "filterableAttributes": [
                "activo",
                "escuela_id",
                "tipo_pieza_id",
                "tipo_prenda_id",
                "modo",
            ],
            "sortableAttributes": ["nombre_base", "precio_venta"],
            "typoTolerance": {
                "enabled": True,
                "minWordSizeForTypos": {"oneTypo": 3, "twoTypos": 8},
                "disableOnAttributes": ["sku"],
            },
            "rankingRules": [
                "words",
                "typo",
                "proximity",
                "attribute",
                "sort",
                "exactness",
            ],
            # ── Sinónimos ──────────────────────────────────────────
            # Género de colores (la gente busca "roja" o "rojo" indistintamente)
            # + abreviaciones comunes de prendas
            "synonyms": {
                "blanco": ["blanca"],
                "blanca": ["blanco"],
                "rojo": ["roja"],
                "roja": ["rojo"],
                "negro": ["negra"],
                "negra": ["negro"],
                "azul": ["azul marino", "azul rey"],
                "gris": ["gris oxford", "gris jaspe"],
                "cafe": ["café"],
                "café": ["cafe"],
                "pants": ["pantalón", "pantalon"],
                "pantalón": ["pants", "pantalon"],
                "pantalon": ["pants", "pantalón"],
                "playera": ["polo", "camiseta"],
                "suéter": ["sueter", "sweater"],
                "sueter": ["suéter"],
                "chamarra": ["chaqueta", "jacket"],
                "calceta": ["calcetín", "calcetin", "calcetas"],
                "calcetas": ["calceta", "calcetín"],
                "falda": ["faldas"],
                "faldas": ["falda"],
                "camisa": ["camisas"],
                "camisas": ["camisa"],
                "2pz": ["dos piezas"],
                "3pz": ["tres piezas"],
                "ch": ["chica", "small"],
                "md": ["mediana", "medium"],
                "gd": ["grande", "large"],
                "exg": ["extra grande"],
                # Niveles educativos (abreviaciones comunes)
                "sec": ["secundaria"],
                "secu": ["secundaria"],
                "prim": ["primaria"],
                "bach": ["bachillerato"],
                "prepa": ["bachillerato"],
                "kinder": ["preescolar"],
                "kínder": ["preescolar"],
                # Género (convención DB: Mujer/Hombre)
                "niña": ["mujer"],
                "nina": ["mujer"],
                "niño": ["hombre"],
                "nino": ["hombre"],
                "dama": ["mujer"],
                "caballero": ["hombre"],
                # Colores compuestos
                "marino": ["azul marino"],
                "oxford": ["gris oxford"],
                # Accesorios que se piden indistinto
                "corbatin": ["corbatín", "moño"],
                "corbatín": ["corbatin", "moño"],
                "moño": ["corbatin", "corbatín"],
            },
            # ── Stop words ─────────────────────────────────────────
            # Palabras que no aportan a la búsqueda
            "stopWords": [
                "de", "del", "la", "las", "el", "los", "en", "y", "con",
                "sin", "para", "por", "una", "un", "ad", "hoc",
            ],
            # ── Separadores ────────────────────────────────────────
            # El pipe "|" aparece en nombres de producto como separador
            "separatorTokens": ["|"],
            # ── Paginación ─────────────────────────────────────────
            "pagination": {"maxTotalHits": 5000},
    }


def configure_index() -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        client.create_index(INDEX_NAME, {"primaryKey": "id"})
    except Exception:
        # El índice puede ya existir — es el caso esperado en ejecuciones posteriores.
        logger.debug("create_index falló (índice ya existe o error menor)", exc_info=True)
    try:
        index = client.index(INDEX_NAME)
        index.update_settings(index_settings())
        return True
    except Exception as exc:
        logger.warning("No se pudo configurar el indice Meilisearch: %s", exc)
        return False


def index_from_db(session: Session) -> int:
    index = _get_index()
    if index is None:
        return 0

    productos = (
        session.query(Producto)
        .filter(Producto.activo.is_(True))
        .options(
            selectinload(Producto.variantes),
            selectinload(Producto.categoria),
            selectinload(Producto.marca),
            selectinload(Producto.escuela),
            selectinload(Producto.tipo_pieza),
            selectinload(Producto.tipo_prenda),
        )
        .all()
    )

    docs: list[dict[str, Any]] = []
    for p in productos:
        for v in p.variantes:
            if not v.activo:
                continue
            tipo_pieza_nombre = p.tipo_pieza.nombre if p.tipo_pieza else "Sin pieza"
            docs.append({
                "id": v.id,
                "sku": v.sku,
                "talla": v.talla or "",
                "color": v.color or "",
                "precio_venta": float(v.precio_venta or 0),
                "stock_actual": v.stock_actual or 0,
                "producto_id": p.id,
                "nombre_base": p.nombre_base or p.nombre or "",
                "nombre_producto": p.nombre or "",
                "categoria": p.categoria.nombre if p.categoria else "",
                "marca": p.marca.nombre if p.marca else "",
                "escuela": p.escuela.nombre if p.escuela else "",
                "escuela_id": p.escuela_id,
                "tipo_pieza": tipo_pieza_nombre,
                "tipo_pieza_id": p.tipo_pieza_id,
                "tipo_prenda": p.tipo_prenda.nombre if p.tipo_prenda else "",
                "tipo_prenda_id": p.tipo_prenda_id,
                "genero": p.genero or "",
                "family_key": f"{tipo_pieza_nombre}||{p.nombre_base or p.nombre}",
                "modo": "school" if p.escuela_id else "basics",
                "activo": True,
            })

    if not docs:
        logger.warning("index_from_db: 0 documentos generados de %d productos", len(productos))
        return 0

    try:
        task = index.delete_all_documents()
        index.wait_for_task(task.task_uid, timeout_in_ms=10_000)
        task2 = index.add_documents(docs)
        index.wait_for_task(task2.task_uid, timeout_in_ms=30_000)
        logger.info("Meilisearch indexado: %d documentos", len(docs))
        return len(docs)
    except Exception as exc:
        logger.warning("Error indexando en Meilisearch: %s", exc)
        return 0


def search(query: str, *, limit: int = 40, mode: str | None = None) -> list[dict[str, Any]]:
    index = _get_index()
    if index is None:
        return []

    opts: dict[str, Any] = {
        "limit": limit,
        # Exigir TODAS las palabras del query (con typos y sinónimos vivos).
        # Sin esto Meilisearch puede ignorar palabras ("gales verde" → azules)
        # y los consumidores tenían que re-filtrar localmente por substring,
        # lo que mataba la tolerancia a typos.
        "matchingStrategy": "all",
        "attributesToRetrieve": [
            "id", "sku", "talla", "color", "precio_venta", "stock_actual",
            "producto_id", "nombre_base", "nombre_producto", "categoria",
            "marca", "escuela", "tipo_pieza", "tipo_pieza_id", "tipo_prenda",
            "genero", "family_key", "modo",
        ],
    }

    filters = ["activo = true"]
    if mode in ("school", "basics"):
        filters.append(f'modo = "{mode}"')
    if filters:
        opts["filter"] = " AND ".join(filters)

    try:
        result = index.search(query, opts)
        return result.get("hits", [])
    except Exception as exc:
        logger.warning("Error buscando en Meilisearch: %s", exc)
        return []


def search_as_families(query: str, *, limit: int = 40, mode: str | None = None) -> list[dict[str, Any]]:
    hits = search(query, limit=limit, mode=mode)
    if not hits:
        return []

    families: dict[str, dict[str, Any]] = {}
    for hit in hits:
        fk = hit.get("family_key", "")
        if not fk:
            continue
        if fk not in families:
            families[fk] = {
                "key": fk,
                "nombre_base": hit.get("nombre_base", ""),
                "tipo_pieza": hit.get("tipo_pieza"),
                "tipo_pieza_id": hit.get("tipo_pieza_id"),
                "precio_desde": hit.get("precio_venta", 0),
                "variantes": [],
            }
        fam = families[fk]
        fam["variantes"].append({
            "id": hit["id"],
            "sku": hit["sku"],
            "talla": hit.get("talla", ""),
            "color": hit.get("color", ""),
            "precio_venta": hit.get("precio_venta", 0),
            "stock_actual": hit.get("stock_actual", 0),
        })
        if hit.get("precio_venta", 0) < fam["precio_desde"]:
            fam["precio_desde"] = hit["precio_venta"]

    return list(families.values())


def is_available() -> bool:
    return _get_client() is not None


def _ensure_vcruntime(on_progress: Any = None) -> None:
    """Instala VC++ Redistributable si VCRUNTIME140.dll no existe."""
    import ctypes.util
    import os
    import subprocess
    import urllib.request
    from pathlib import Path

    sys_dir = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32"
    if (sys_dir / "vcruntime140.dll").exists():
        return

    if on_progress:
        on_progress("Instalando Visual C++ Runtime...")

    vc_url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    tmp_path = Path(os.environ.get("TEMP", r"C:\Temp")) / "vc_redist.x64.exe"
    try:
        urllib.request.urlretrieve(vc_url, str(tmp_path))
        subprocess.run(
            [str(tmp_path), "/install", "/quiet", "/norestart"],
            timeout=120,
            check=False,
        )
    except Exception as exc:
        logger.warning("No se pudo instalar VC++ Runtime: %s", exc)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def ensure_installed(
    *,
    install_dir: str = "C:\\Meilisearch",
    version: str = "v1.14.0",
    port: int = 7700,
    on_progress: Any = None,
) -> str:
    """Descarga, instala y arranca Meilisearch si no está corriendo.

    Returns status message string.
    """
    import os
    import subprocess
    import urllib.request
    from pathlib import Path

    data_dir = Path(install_dir) / "data"
    bin_path = Path(install_dir) / "meilisearch.exe"

    if is_available():
        return "Meilisearch ya está corriendo."

    _ensure_vcruntime(on_progress)

    def _start(bin_: Path) -> bool:
        subprocess.Popen(
            [str(bin_), "--no-analytics", "--db-path", str(data_dir), "--http-addr", f"127.0.0.1:{port}"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        import time
        time.sleep(3)
        global _client, _client_checked_at
        _client = None
        _client_checked_at = 0
        return is_available()

    if bin_path.exists():
        if on_progress:
            on_progress("Iniciando Meilisearch...")
        try:
            if _start(bin_path):
                return "Meilisearch iniciado."
        except Exception as exc:
            logger.warning("No se pudo iniciar Meilisearch: %s", exc)

    if on_progress:
        on_progress("Descargando Meilisearch...")
    url = f"https://github.com/meilisearch/meilisearch/releases/download/{version}/meilisearch-windows-amd64.exe"

    os.makedirs(install_dir, exist_ok=True)
    os.makedirs(str(data_dir), exist_ok=True)

    try:
        urllib.request.urlretrieve(url, str(bin_path))
    except Exception as exc:
        return f"Error descargando: {exc}"

    if on_progress:
        on_progress("Iniciando Meilisearch...")
    try:
        if _start(bin_path):
            return "Meilisearch instalado e iniciado."
        return "Meilisearch instalado pero no responde aún. Reintenta en unos segundos."
    except Exception as exc:
        return f"Error iniciando: {exc}"


def notify_catalog_changed() -> None:
    """Re-indexa Meilisearch en un hilo aparte para no bloquear la UI."""
    import threading
    from pos_uniformes.database.connection import get_session

    def _reindex():
        try:
            global _client, _client_checked_at
            _client = None
            _client_checked_at = 0

            if _get_client() is None:
                logger.debug("notify_catalog_changed: Meilisearch no disponible, saltando")
                return

            configure_index()

            with get_session() as session:
                count = index_from_db(session)
                if count > 0:
                    logger.info("Meilisearch re-indexado OK: %d docs", count)
                else:
                    logger.warning("Meilisearch re-indexado pero 0 docs")
        except Exception as exc:
            logger.warning("Error re-indexando Meilisearch: %s", exc)

    threading.Thread(target=_reindex, daemon=True, name="meili-reindex").start()
