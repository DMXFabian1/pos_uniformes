"""Genera HTML rico para la vista previa del tarifario en el kiosco."""

from __future__ import annotations

from decimal import Decimal
from html import escape


# ── Paleta (tema cálido del kiosco) ────────────────────────────────────────
_BG        = "#FFF8F5"
_HEADER_BG = "#7B2D14"
_CARD_BG   = "#FFFFFF"
_CARD_BORDER = "#E2C9BE"
_NAME_BG   = "#F5EDE8"
_NAME_FG   = "#4A1505"
_ROW_ALT   = "#FBF5F2"
_TALLA_FG  = "#7A4535"
_PRICE_FG  = "#1E6B1E"
_MUTED     = "#A07060"
_WHITE     = "#FFFFFF"
_ACCENT    = "#C96030"
_SEC_BG    = "#F0E0D8"
_SEC_FG    = "#7B2D14"


def build_school_tariff_html(
    *,
    tariff: dict,
    business_name: str = "MAXIMODA",
    business_phone: str = "",
) -> str:
    """Genera HTML para mostrar el tarifario como tabla moderna en QTextEdit."""
    escuela = tariff.get("escuela_nombre", "")
    productos = tariff.get("productos", [])

    parts: list[str] = []

    # ── Wrapper ──────────────────────────────────────────────────────────────
    parts.append(f"""
<html><body style="background:{_BG}; font-family:Arial,Helvetica,sans-serif;
  margin:0; padding:16px; color:#2A1505;">
""")

    # ── Encabezado ───────────────────────────────────────────────────────────
    phone_html = (
        f'<div style="color:#F0C8A8; font-size:11px; margin-top:2px;">'
        f'Tel: {escape(business_phone)}</div>'
        if business_phone else ""
    )
    parts.append(f"""
<table width="100%" cellpadding="14" cellspacing="0"
  style="background:{_HEADER_BG}; margin-bottom:14px;">
<tr>
  <td>
    <div style="color:{_WHITE}; font-size:16px; font-weight:bold; letter-spacing:1px;">
      {escape(business_name)}</div>
    <div style="color:#F0C8A8; font-size:11px; margin-top:2px;">Lista de precios</div>
    {phone_html}
  </td>
  <td align="right">
    <div style="color:{_WHITE}; font-size:15px; font-weight:bold;">
      {escape(escuela)}</div>
  </td>
</tr>
</table>
""")

    if not productos:
        parts.append(
            f'<p style="color:{_MUTED}; text-align:center; padding:24px;">Sin productos.</p>'
        )
        parts.append("</body></html>")
        return "".join(parts)

    # ── Agrupar por sección (tipo_prenda) ────────────────────────────────────
    sections = _group_by_section(productos)
    show_headers = len(sections) > 1

    parts.append('<table width="100%" cellspacing="8" cellpadding="0">')

    for sec_name, sec_prods in sections:
        # Encabezado de sección (solo cuando hay más de una)
        if show_headers:
            label = escape(sec_name.upper() if sec_name else "OTROS")
            parts.append(f"""
<tr>
  <td colspan="2" style="padding:12px 6px 5px; color:{_SEC_FG};
      font-size:11px; font-weight:bold; letter-spacing:2px;
      border-bottom:2px solid {_ACCENT};">
    {label}
  </td>
</tr>
<tr><td colspan="2" style="padding:2px;"></td></tr>""")

        col = 0
        for prod in sec_prods:
            nombre = prod.get("nombre", "")
            tallas = prod.get("tallas", [])
            if not tallas:
                continue

            price_groups = _group_by_price(tallas)
            rows_html = []
            for idx, (precio, group_tallas) in enumerate(price_groups):
                row_bg = _ROW_ALT if idx % 2 == 0 else _CARD_BG
                talla_str = escape(_compact_range(group_tallas))
                price_str = f"${precio:,.2f}"
                rows_html.append(f"""
<tr style="background:{row_bg};">
  <td style="padding:5px 12px; color:{_TALLA_FG}; font-size:12px;">{talla_str}</td>
  <td align="right"
    style="padding:5px 12px; font-weight:bold; color:{_PRICE_FG}; font-size:12px;">
    {price_str}</td>
</tr>""")

            card = f"""
<table width="100%" cellpadding="0" cellspacing="0"
  style="background:{_CARD_BG}; border:1px solid {_CARD_BORDER};">
  <tr>
    <td colspan="2"
      style="background:{_NAME_BG}; padding:8px 12px; font-weight:bold;
             color:{_NAME_FG}; font-size:12px; border-bottom:1px solid {_CARD_BORDER};">
      {escape(nombre)}</td>
  </tr>
  {"".join(rows_html)}
</table>"""

            if col == 0:
                parts.append(f'<tr><td width="50%" valign="top">{card}</td>')
                col = 1
            else:
                parts.append(f'<td width="50%" valign="top">{card}</td></tr>')
                col = 0

        # Cerrar fila incompleta de esta sección
        if col == 1:
            parts.append('<td width="50%"></td></tr>')

    parts.append("</table>")

    # ── Pie ──────────────────────────────────────────────────────────────────
    parts.append(f"""
<p style="color:{_MUTED}; font-size:10px; text-align:center; margin-top:14px;">
  Tallas en números pares (4, 6, 8, 10…) &nbsp;·&nbsp;
  Precios sujetos a cambio sin previo aviso.
</p>
""")

    parts.append("</body></html>")
    return "".join(parts)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _group_by_section(productos: list[dict]) -> list[tuple[str, list[dict]]]:
    """Agrupa productos por tipo_prenda preservando el orden de entrada."""
    groups: list[tuple[str, list[dict]]] = []
    for p in productos:
        sec = p.get("tipo_prenda", "") or ""
        if groups and groups[-1][0] == sec:
            groups[-1][1].append(p)
        else:
            groups.append((sec, [p]))
    return groups


def _group_by_price(
    tallas: list[dict],
) -> list[tuple[Decimal, list[str]]]:
    groups: list[tuple[Decimal, list[str]]] = []
    for t in tallas:
        precio = Decimal(str(t["precio"]))
        talla = str(t["talla"])
        if groups and groups[-1][0] == precio:
            groups[-1][1].append(talla)
        else:
            groups.append((precio, [talla]))
    return groups


def _compact_range(tallas: list[str]) -> str:
    if len(tallas) <= 1:
        return tallas[0] if tallas else ""
    nums = []
    for t in tallas:
        try:
            nums.append(int(t))
        except ValueError:
            nums = []
            break
    if nums and len(nums) >= 3:
        step = nums[1] - nums[0]
        if all(nums[i + 1] - nums[i] == step for i in range(len(nums) - 1)):
            return f"{tallas[0]} a {tallas[-1]}"
    if not nums and len(tallas) >= 3:
        return f"{tallas[0]} a {tallas[-1]}"
    return ", ".join(tallas)
