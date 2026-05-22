"""Genera PDF imprimible de etiqueta de caja para bodega."""

from __future__ import annotations

import base64
import logging
import math
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from pos_uniformes.database.models import CATEGORIA_CAJA_LABELS, BodegaCaja
from pos_uniformes.services.bodega_service import BodegaService
from pos_uniformes.utils.qr_generator import QrGenerator

logger = logging.getLogger(__name__)


def _qr_png_to_data_uri(png_path: Path) -> str:
    """Convierte un archivo PNG de QR a data URI base64."""
    try:
        data = png_path.read_bytes()
        b64 = base64.b64encode(data).decode()
        return f"data:image/png;base64,{b64}"
    except Exception:
        logger.debug("Error leyendo QR PNG", exc_info=True)
        return ""

CATEGORIA_COLORS: dict[str, str] = {
    "A": "#2e7d32",
    "B": "#1565c0",
    "C": "#e65100",
    "D": "#616161",
}

MAX_ROWS_PAGE_1 = 30
MAX_ROWS_CONTINUATION = 38


def _leyenda_html() -> str:
    cells = []
    for cat, label in CATEGORIA_CAJA_LABELS.items():
        color = CATEGORIA_COLORS.get(cat, "#333")
        cells.append(
            f'<td style="padding:4px 12px 4px 0;">'
            f'<span style="display:inline-block;width:10px;height:10px;'
            f'background:{color};border-radius:5px;margin-right:4px;">'
            f'&nbsp;</span>'
            f'<span style="font-size:10px;color:#555;">{cat} — {label}</span></td>'
        )
    return (
        f'<table cellpadding="0" cellspacing="0" '
        f'style="margin-top:12px;border:1px solid #ddd;border-radius:6px;padding:6px 10px;">'
        f'<tr>{"".join(cells)}</tr></table>'
    )


def _header_html(caja: BodegaCaja, *, compact: bool = False, qr_data_uri: str = "") -> str:
    cat_label = CATEGORIA_CAJA_LABELS.get(caja.categoria, caja.categoria)
    color = CATEGORIA_COLORS.get(caja.categoria, "#333")
    ub_text = caja.ubicacion.codigo if caja.ubicacion else "Sin ubicación"

    qr_size = 60 if compact else 90
    if qr_data_uri:
        qr_cell = f'<img src="{qr_data_uri}" width="{qr_size}" height="{qr_size}">'
    else:
        qr_cell = f'<span style="font-size:10px;color:#999;">[QR]</span>'

    cod_size = "22px" if compact else "36px"
    cont = (' <span style="font-size:13px;font-weight:normal;color:#777;">'
            '— continuación</span>') if compact else ""

    badge_pad = "2px 10px" if compact else "4px 14px"
    badge_font = "11px" if compact else "13px"

    border_w = "2px" if compact else "3px"

    return f"""
    <table cellpadding="0" cellspacing="0" width="100%"
           style="border-bottom:{border_w} solid #222;padding-bottom:8px;margin-bottom:6px;">
      <tr>
        <td width="{qr_size + 12}" valign="top" style="padding-right:12px;">
          <div style="border:2px solid #333;border-radius:6px;padding:3px;
                      width:{qr_size + 6}px;text-align:center;background:white;">
            {qr_cell}
          </div>
        </td>
        <td valign="top">
          <div style="font-size:{cod_size};font-weight:900;letter-spacing:1px;
                      line-height:1.1;color:#111;">{caja.codigo}{cont}</div>
          <div style="margin-top:5px;">
            <span style="display:inline-block;padding:{badge_pad};border-radius:14px;
                         font-size:{badge_font};font-weight:700;color:white;
                         background:{color};">{caja.categoria} — {cat_label}</span>
          </div>
          <div style="font-size:14px;color:#444;margin-top:4px;font-weight:500;">
            {ub_text}
          </div>
        </td>
      </tr>
    </table>"""


def _meta_html(caja: BodegaCaja, total_prendas: int, now_str: str) -> str:
    return f"""
    <table cellpadding="0" cellspacing="0" width="100%"
           style="border-bottom:1px solid #ddd;padding:6px 0;margin-bottom:4px;font-size:12px;color:#555;">
      <tr>
        <td>Estado: <b style="color:#222;">{caja.estado}</b></td>
        <td align="center">Prendas totales: <b style="color:#222;">{total_prendas}</b></td>
        <td align="right">Impreso: <b style="color:#222;">{now_str}</b></td>
      </tr>
    </table>"""


def _content_table_html(desglose: list[dict], start: int, count: int) -> tuple[str, int]:
    """Genera tabla HTML de contenido. Retorna (html, filas_renderizadas)."""
    flat: list[dict] = []
    for grupo in desglose:
        flat.append({"type": "product", "nombre": grupo["producto"], "total": grupo["total"]})
        for t in grupo["tallas"]:
            flat.append({
                "type": "variant",
                "talla": t["talla"],
                "color": t["color"],
                "cantidad": t["cantidad"],
            })

    chunk = flat[start: start + count]
    if not chunk:
        return "", 0

    rows_html = []
    for item in chunk:
        if item["type"] == "product":
            rows_html.append(
                f'<tr>'
                f'<td colspan="3" style="background:#e8f0f7;font-weight:700;font-size:13px;'
                f'padding:6px 10px 4px;border-bottom:2px solid #c0d4e4;">{item["nombre"]}</td>'
                f'<td align="center" style="background:#e8f0f7;font-weight:800;font-size:14px;'
                f'color:#c45425;padding:6px 10px 4px;border-bottom:2px solid #c0d4e4;">'
                f'{item["total"]}</td>'
                f'</tr>'
            )
        else:
            rows_html.append(
                f'<tr>'
                f'<td style="padding:3px 10px 3px 28px;border-bottom:1px solid #e8e8e8;">&nbsp;</td>'
                f'<td style="padding:3px 10px;border-bottom:1px solid #e8e8e8;">{item["talla"]}</td>'
                f'<td style="padding:3px 10px;border-bottom:1px solid #e8e8e8;">{item["color"]}</td>'
                f'<td align="center" style="padding:3px 10px;border-bottom:1px solid #e8e8e8;'
                f'font-weight:700;font-size:13px;color:#c45425;">{item["cantidad"]}</td>'
                f'</tr>'
            )

    return "\n".join(rows_html), len(chunk)


def _total_flat_rows(desglose: list[dict]) -> int:
    total = 0
    for grupo in desglose:
        total += 1 + len(grupo["tallas"])
    return total


def _resumen_html(desglose: list[dict], total_prendas: int, total_productos: int) -> str:
    if total_productos <= 1:
        return ""
    parts = " &middot; ".join(f'{g["producto"]}: {g["total"]}' for g in desglose)
    return f"""
    <table cellpadding="0" cellspacing="0" width="100%"
           style="margin-top:14px;background:#f0f6fb;border:1px solid #d5e2ed;
                  border-radius:6px;padding:8px 12px;">
      <tr><td>
        <div style="font-size:12px;font-weight:700;color:#222;margin-bottom:3px;">
          Resumen total: {total_prendas} prendas en {total_productos} productos
        </div>
        <div style="font-size:10px;color:#555;line-height:1.5;">{parts}</div>
      </td></tr>
    </table>"""


def _footer_html(page_num: int, num_pages: int) -> str:
    return f"""
    <table cellpadding="0" cellspacing="0" width="100%"
           style="border-top:1px solid #ddd;padding-top:6px;margin-top:10px;
                  font-size:9px;color:#999;">
      <tr>
        <td>POS Uniformes &middot; Bodega</td>
        <td align="center">Página {page_num} de {num_pages}</td>
        <td align="right">Generado automáticamente</td>
      </tr>
    </table>"""


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

        meta = _meta_html(caja, total_prendas, now_str) if is_first else ""

        title_label = "Contenido de la caja" if is_first else "Contenido de la caja (cont.)"
        title_html = (
            f'<div style="font-size:15px;font-weight:800;color:#222;'
            f'padding:8px 0 4px;">{title_label}</div>'
        )

        content_rows, rendered = _content_table_html(desglose, row_cursor, capacity)
        row_cursor += rendered

        content_table = f"""
        <table cellpadding="0" cellspacing="0" width="100%"
               style="border-collapse:collapse;">
          <tr>
            <th style="background:#222;color:white;padding:5px 10px;text-align:left;
                       font-size:10px;font-weight:700;text-transform:uppercase;
                       letter-spacing:0.5px;" width="30%">Producto</th>
            <th style="background:#222;color:white;padding:5px 10px;text-align:left;
                       font-size:10px;font-weight:700;text-transform:uppercase;" width="20%">Talla</th>
            <th style="background:#222;color:white;padding:5px 10px;text-align:left;
                       font-size:10px;font-weight:700;text-transform:uppercase;" width="25%">Color</th>
            <th style="background:#222;color:white;padding:5px 10px;text-align:center;
                       font-size:10px;font-weight:700;text-transform:uppercase;" width="25%">Cantidad</th>
          </tr>
          {content_rows}
        </table>"""

        resumen = _resumen_html(desglose, total_prendas, total_productos) if page_num == num_pages else ""
        leyenda = _leyenda_html()
        footer = _footer_html(page_num, num_pages)

        pages.append(f"""
          {header}
          {meta}
          {title_html}
          {content_table}
          {resumen}
          {leyenda}
          {footer}
        """)

    # Para múltiples páginas, QTextDocument no soporta page-break explícito,
    # pero con el contenido suficiente hará page breaks automáticos.
    body = "\n".join(pages)

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Etiqueta — Caja {caja.codigo}</title></head>
<body style="font-family: Helvetica, Arial, sans-serif; color: #1a1a1a; margin: 0; padding: 0;">
{body}
</body>
</html>"""


def _html_to_pdf(html: str, pdf_path: Path) -> None:
    """Renderiza HTML a PDF usando QTextDocument + QPrinter de PyQt6."""
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize, QTextDocument
    from PyQt6.QtPrintSupport import QPrinter

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(pdf_path))

    page_layout = QPageLayout(
        QPageSize(QPageSize.PageSizeId.Letter),
        QPageLayout.Orientation.Portrait,
        QMarginsF(12, 12, 12, 10),
        QPageLayout.Unit.Millimeter,
    )
    printer.setPageLayout(page_layout)

    doc = QTextDocument()
    doc.setHtml(html)
    doc.setPageSize(printer.pageRect(QPrinter.Unit.Point).size())
    doc.print(printer)


def print_caja_label(session: Session, caja_id: int, qr_data_uri: str = "") -> Path:
    """Genera PDF de etiqueta de caja y lo abre con el visor del sistema."""
    if not qr_data_uri:
        caja = session.get(BodegaCaja, caja_id)
        if caja:
            qr_png_path = QrGenerator.generate_for_caja(caja)
            qr_data_uri = _qr_png_to_data_uri(qr_png_path)
    html = generate_caja_label_html(session, caja_id, qr_data_uri=qr_data_uri)

    tmp_dir = Path(tempfile.mkdtemp())
    pdf_path = tmp_dir / "etiqueta_caja.pdf"
    _html_to_pdf(html, pdf_path)

    if sys.platform == "darwin":
        subprocess.Popen(["open", str(pdf_path)])
    elif sys.platform == "win32":
        subprocess.Popen(["start", "", str(pdf_path)], shell=True)
    else:
        subprocess.Popen(["xdg-open", str(pdf_path)])

    return pdf_path
