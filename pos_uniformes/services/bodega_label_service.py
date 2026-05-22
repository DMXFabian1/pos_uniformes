"""Genera HTML imprimible de etiqueta de caja para bodega."""

from __future__ import annotations

import base64
import io
import logging
import math
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from pos_uniformes.database.models import CATEGORIA_CAJA_LABELS, BodegaCaja
from pos_uniformes.services.bodega_service import BodegaService

logger = logging.getLogger(__name__)


def _generate_qr_data_uri(data: str) -> str:
    """Genera un QR como data URI PNG usando segno."""
    try:
        import segno
        qr = segno.make(data)
        buf = io.BytesIO()
        qr.save(buf, kind="png", scale=6, border=1)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
    except ImportError:
        logger.debug("segno no instalado, QR no disponible")
        return ""
    except Exception:
        logger.debug("Error generando QR", exc_info=True)
        return ""

CATEGORIA_COLORS: dict[str, str] = {
    "A": "#2e7d32",
    "B": "#1565c0",
    "C": "#e65100",
    "D": "#616161",
}

MAX_ROWS_PAGE_1 = 22
MAX_ROWS_CONTINUATION = 28


def _css() -> str:
    return """
  @page { size: letter landscape; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, 'Segoe UI', Arial, sans-serif;
    color: #1a1a1a;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .page {
    width: 279mm; min-height: 216mm;
    padding: 10mm 14mm 8mm;
    page-break-after: always;
    position: relative;
  }
  .page:last-child { page-break-after: auto; }

  .header {
    display: flex; align-items: flex-start; gap: 16px;
    padding-bottom: 12px; border-bottom: 3px solid #222;
  }
  .header-compact { padding-bottom: 8px; border-bottom: 2px solid #222; }
  .qr-box {
    width: 100px; height: 100px; border: 2px solid #333; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; background: white; overflow: hidden;
  }
  .qr-box img { width: 96px; height: 96px; }
  .qr-small { width: 60px; height: 60px; }
  .qr-small img { width: 56px; height: 56px; }
  .header-info { flex: 1; }
  .codigo { font-size: 48px; font-weight: 900; letter-spacing: 2px; line-height: 1; }
  .codigo-compact { font-size: 28px; }
  .categoria-badge {
    display: inline-block; padding: 4px 16px; border-radius: 20px;
    font-size: 16px; font-weight: 700; color: white; margin-top: 6px;
  }
  .categoria-badge-compact { font-size: 12px; padding: 2px 12px; margin-top: 4px; }
  .ubicacion { font-size: 18px; color: #444; margin-top: 6px; font-weight: 500; }
  .ubicacion-compact { font-size: 13px; margin-top: 2px; }

  .meta-row {
    display: flex; gap: 24px; padding: 8px 0;
    border-bottom: 1px solid #ddd; font-size: 13px; color: #555;
  }
  .meta-row span { font-weight: 600; color: #222; }

  .contenido-title { font-size: 18px; font-weight: 800; padding: 10px 0 6px; color: #222; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  thead th {
    background: #222; color: white; padding: 7px 10px; text-align: left;
    font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;
  }
  thead th:last-child, tbody td:last-child { text-align: center; }
  tbody tr { border-bottom: 1px solid #e0e0e0; }
  tbody tr:nth-child(even) { background: #f7f7f7; }
  tbody td { padding: 5px 10px; }
  .producto-row td {
    background: #eef5fb; font-weight: 700; font-size: 15px;
    padding: 8px 10px 5px; border-bottom: 2px solid #c5d9e8;
  }
  .talla-row td { padding-left: 28px; color: #333; }
  .cantidad-cell { font-weight: 800; font-size: 16px; color: #c45425; }

  .leyenda {
    margin-top: 14px; padding: 8px 14px; border: 1px solid #ddd;
    border-radius: 8px; display: flex; gap: 20px; font-size: 12px;
  }
  .leyenda-item { display: flex; align-items: center; gap: 6px; }
  .leyenda-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }

  .footer {
    padding-top: 8px; border-top: 1px solid #ddd;
    display: flex; justify-content: space-between;
    font-size: 11px; color: #888; margin-top: 10px;
  }
  .resumen-box {
    margin-top: 20px; padding: 12px 16px; background: #f5f9fc;
    border-radius: 8px; border: 1px solid #dbe6ef;
  }
  .resumen-box .title { font-size: 14px; font-weight: 700; color: #222; margin-bottom: 6px; }
  .resumen-box .body { font-size: 12px; color: #555; line-height: 1.6; }

  @media print {
    .no-print { display: none !important; }
    .page { padding: 8mm 12mm 6mm; }
  }
"""


def _leyenda_html() -> str:
    items = []
    for cat, label in CATEGORIA_CAJA_LABELS.items():
        color = CATEGORIA_COLORS[cat]
        items.append(
            f'<div class="leyenda-item">'
            f'<div class="leyenda-dot" style="background:{color}"></div> {cat} — {label}</div>'
        )
    return f'<div class="leyenda">{"".join(items)}</div>'


def _header_html(caja: BodegaCaja, *, compact: bool = False, qr_data_uri: str = "") -> str:
    cat_label = CATEGORIA_CAJA_LABELS.get(caja.categoria, caja.categoria)
    color = CATEGORIA_COLORS.get(caja.categoria, "#333")
    ub_text = caja.ubicacion.codigo if caja.ubicacion else "Sin ubicación"

    h_cls = "header header-compact" if compact else "header"
    qr_cls = "qr-box qr-small" if compact else "qr-box"
    cod_cls = "codigo codigo-compact" if compact else "codigo"
    badge_cls = "categoria-badge categoria-badge-compact" if compact else "categoria-badge"
    ub_cls = "ubicacion ubicacion-compact" if compact else "ubicacion"

    if qr_data_uri:
        qr_inner = f'<img src="{qr_data_uri}" alt="QR {caja.codigo}">'
    else:
        qr_inner = f"[ QR ]<br>{caja.codigo}"

    cont = ' <span style="font-size:16px;font-weight:500;color:#666;">— continuación</span>' if compact else ""

    return f"""
    <div class="{h_cls}">
      <div class="{qr_cls}">{qr_inner}</div>
      <div class="header-info">
        <div class="{cod_cls}">{caja.codigo}{cont}</div>
        <div class="{badge_cls}" style="background:{color}">{caja.categoria} — {cat_label}</div>
        <div class="{ub_cls}">📍 {ub_text}</div>
      </div>
    </div>"""


def _table_rows_html(desglose: list[dict], start: int, count: int) -> tuple[str, int]:
    """Render up to `count` table rows starting from flat index `start`. Returns (html, rows_rendered)."""
    flat: list[str] = []
    for grupo in desglose:
        flat.append(
            f'<tr class="producto-row"><td colspan="3">{grupo["producto"]}</td>'
            f'<td class="cantidad-cell">{grupo["total"]}</td></tr>'
        )
        for t in grupo["tallas"]:
            flat.append(
                f'<tr class="talla-row"><td></td><td>{t["talla"]}</td>'
                f'<td>{t["color"]}</td><td class="cantidad-cell">{t["cantidad"]}</td></tr>'
            )

    chunk = flat[start : start + count]
    return "\n".join(chunk), len(chunk)


def _table_wrap(body: str, title: str = "Contenido de la caja") -> str:
    return f"""
    <div class="contenido-title">{title}</div>
    <table>
      <thead><tr><th>Producto</th><th>Talla</th><th>Color</th><th>Cantidad</th></tr></thead>
      <tbody>{body}</tbody>
    </table>"""


def _total_flat_rows(desglose: list[dict]) -> int:
    total = 0
    for grupo in desglose:
        total += 1 + len(grupo["tallas"])
    return total


def generate_caja_label_html(session: Session, caja_id: int, qr_data_uri: str = "") -> str:
    caja = BodegaService.obtener_caja_detalle(session, caja_id)
    if not caja:
        return "<html><body><h1>Caja no encontrada</h1></body></html>"

    desglose = BodegaService.desglose_contenido_caja(session, caja_id)
    total_prendas = sum(g["total"] for g in desglose)
    total_productos = len(desglose)
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    flat_count = _total_flat_rows(desglose)

    if flat_count <= MAX_ROWS_PAGE_1:
        num_pages = 1
    else:
        remaining = flat_count - MAX_ROWS_PAGE_1
        num_pages = 1 + math.ceil(remaining / MAX_ROWS_CONTINUATION)

    pages: list[str] = []
    row_cursor = 0

    for page_num in range(1, num_pages + 1):
        is_first = page_num == 1
        capacity = MAX_ROWS_PAGE_1 if is_first else MAX_ROWS_CONTINUATION

        header = _header_html(caja, compact=not is_first, qr_data_uri=qr_data_uri)

        meta = ""
        if is_first:
            meta = f"""
            <div class="meta-row">
              <div>Estado: <span>{caja.estado}</span></div>
              <div>Prendas totales: <span>{total_prendas}</span></div>
              <div>Impreso: <span>{now_str}</span></div>
            </div>"""

        body_html, rendered = _table_rows_html(desglose, row_cursor, capacity)
        row_cursor += rendered

        title = "Contenido de la caja" if is_first else "Contenido de la caja (cont.)"
        table = _table_wrap(body_html, title)

        resumen = ""
        if page_num == num_pages and total_productos > 1:
            parts = " · ".join(f'{g["producto"]}: {g["total"]}' for g in desglose)
            resumen = f"""
            <div class="resumen-box">
              <div class="title">Resumen total: {total_prendas} prendas en {total_productos} productos</div>
              <div class="body">{parts}</div>
            </div>"""

        footer = f"""
        <div class="footer">
          <div>POS Uniformes · Bodega</div>
          <div>Página {page_num} de {num_pages}</div>
          <div>Generado automáticamente</div>
        </div>"""

        pages.append(f"""
        <div class="page">
          {header}
          {meta}
          {table}
          {resumen}
          {_leyenda_html()}
          {footer}
        </div>""")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Etiqueta — Caja {caja.codigo}</title>
<style>{_css()}</style>
</head>
<body>
{"".join(pages)}
</body>
</html>"""


def print_caja_label(session: Session, caja_id: int, qr_data_uri: str = "") -> Path:
    # Generar QR automáticamente si no se proporciona
    if not qr_data_uri:
        caja = session.get(BodegaCaja, caja_id)
        if caja:
            qr_data = BodegaService.generar_qr_data(caja)
            qr_data_uri = _generate_qr_data_uri(qr_data)
    html = generate_caja_label_html(session, caja_id, qr_data_uri=qr_data_uri)
    tmp = Path(tempfile.mkdtemp()) / "etiqueta_caja.html"
    tmp.write_text(html, encoding="utf-8")
    webbrowser.open(tmp.as_uri())
    return tmp
