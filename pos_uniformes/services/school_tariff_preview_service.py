"""Genera HTML rico para la vista previa del tarifario en el kiosco."""

from __future__ import annotations

from decimal import Decimal
from html import escape


# ── Colores por tipo de pieza (sincronizados con generar_tarifario_escuelas.py) ──

# Cada entrada: (accent_bar_hex, header_bg_hex, row_alt_hex, title_hex, border_hex)
_PIEZA_COLORS: dict[str, tuple[str, str, str, str, str]] = {
    # Pants — teal
    "Pants 3pz":     ("#0F766E", "#DFF5F2", "#EFFAF8", "#0A5A54", "#B4DCD7"),
    "Pants 2pz":     ("#0F766E", "#DFF5F2", "#EFFAF8", "#0A5A54", "#B4DCD7"),
    "Pants Suelto":  ("#0F766E", "#DFF5F2", "#EFFAF8", "#0A5A54", "#B4DCD7"),
    # Chamarra — teal profundo
    "Chamarra":      ("#115E59", "#CCFBF1", "#E4FDF8", "#0C4844", "#A8D8D0"),
    # Playera — azul
    "Playera":       ("#2563EB", "#E8F1FF", "#F4F8FF", "#1C4CBC", "#C3D2EE"),
    "Playera Polo":  ("#2563EB", "#E8F1FF", "#F4F8FF", "#1C4CBC", "#C3D2EE"),
    # Camisa — sky
    "Camisa":        ("#0284C7", "#E0F2FE", "#F0F9FE", "#02669B", "#B9D2E6"),
    # Suéter — púrpura
    "Suéter":        ("#9333EA", "#F3E8FF", "#F9F4FF", "#7326B9", "#CDC3E1"),
    # Chaleco — violeta
    "Chaleco":       ("#7C3AED", "#EDE9FE", "#F4F2FE", "#602CBC", "#C8C3DE"),
    # Pantalón — slate
    "Pantalón":      ("#475569", "#E2E8F0", "#F0F3F8", "#364152", "#BEC6D2"),
    # Falda / Jumper — terracota
    "Falda":         ("#7C2D12", "#FDE7E7", "#FEF3F3", "#62220C", "#D7C3C3"),
    "Jumper":        ("#7C2D12", "#FDE7E7", "#FEF3F3", "#62220C", "#D7C3C3"),
    # Blusa — rosa
    "Blusa":         ("#7C2D12", "#FDE7E7", "#FEF3F3", "#62220C", "#D7C3C3"),
    # Corbata, accesorios — ámbar
    "Corbata":       ("#A16207", "#FEF3C7", "#FEF9E2", "#804C05", "#D7CDAA"),
    "Corbatín":      ("#A16207", "#FEF3C7", "#FEF9E2", "#804C05", "#D7CDAA"),
    "Moño":          ("#A16207", "#FEF3C7", "#FEF9E2", "#804C05", "#D7CDAA"),
    "Mascada":       ("#A16207", "#FEF3C7", "#FEF9E2", "#804C05", "#D7CDAA"),
    # Calceta / Short — gris
    "Calceta":       ("#6B7280", "#F3F4F6", "#F9FAFB", "#525864", "#CDD0D4"),
    "Short":         ("#6B7280", "#F3F4F6", "#F9FAFB", "#525864", "#CDD0D4"),
}

_DEFAULT_COLORS = ("#2563EB", "#E8F1FF", "#F4F8FF", "#1C4CBC", "#C3D2EE")


def _colors_for(tipo_pieza: str) -> tuple[str, str, str, str, str]:
    """Retorna (accent, header_bg, row_alt, title_color, border_color)."""
    return _PIEZA_COLORS.get(tipo_pieza.strip(), _DEFAULT_COLORS)


def build_school_tariff_html(
    *,
    tariff: dict,
    business_name: str = "MAXIMODA",
    business_phone: str = "",
) -> str:
    """Genera HTML para mostrar el tarifario como tabla moderna en QTextEdit."""
    escuela = tariff.get("escuela_nombre", "")
    productos = tariff.get("productos", [])

    phone_line = f' · Tel: {escape(business_phone)}' if business_phone else ""

    parts: list[str] = []
    parts.append(f"""<html><head><meta charset="utf-8"><style>
body {{
    background: #faf6f2; font-family: Arial, Helvetica, sans-serif;
    margin: 0; padding: 16px; color: #2A1505;
}}
</style></head><body>
""")

    # Header
    parts.append(f"""
<table width="100%" cellpadding="0" cellspacing="0" style="background:#7B2D14;margin-bottom:16px;">
<tr>
<td style="padding:18px 22px;">
  <div style="color:#fff;font-size:17px;font-weight:bold;">{escape(business_name)}</div>
  <div style="color:#f0c8a8;font-size:11px;margin-top:3px;">Lista de precios{phone_line}</div>
</td>
<td style="padding:18px 22px;text-align:right;">
  <div style="color:#fff;font-size:15px;font-weight:bold;">{escape(escuela)}</div>
</td>
</tr></table>
""")

    if not productos:
        parts.append(
            '<p style="color:#A07060;text-align:center;padding:40px;">'
            'Sin productos para esta escuela.</p>'
        )
        parts.append("</body></html>")
        return "".join(parts)

    # Group by section (tipo_prenda)
    sections = _group_by_section(productos)
    show_headers = len(sections) > 1

    for sec_name, sec_prods in sections:
        if show_headers:
            label = escape(sec_name.upper() if sec_name else "OTROS")
            parts.append(f"""
<table width="100%" cellpadding="0" cellspacing="0" style="margin:14px 0 8px;">
<tr><td style="background:#f0e0d8;color:#7B2D14;font-size:11px;font-weight:bold;
  letter-spacing:2px;text-transform:uppercase;padding:8px 14px;
  border-left:3px solid #C96030;">{label}</td></tr>
</table>""")

        # 2-column grid using table (QTextEdit compat)
        parts.append('<table width="100%" cellspacing="5" cellpadding="0">')
        col = 0
        for prod in sec_prods:
            nombre = prod.get("nombre", "")
            tallas = prod.get("tallas", [])
            if not tallas:
                continue

            # Colores por tipo de pieza
            tipo_pieza = prod.get("tipo_pieza", "")
            accent, header_bg, row_alt, title_color, border_color = _colors_for(tipo_pieza)

            # Detalles del producto: género y colores de variante
            genero = prod.get("genero", "")
            colores = prod.get("colores", [])
            detail_parts: list[str] = []
            if genero:
                g_label = "Niño" if genero == "NIÑO" else "Niña" if genero == "NIÑA" else genero.title()
                detail_parts.append(
                    f'<span style="color:{accent};font-weight:bold;">{escape(g_label)}</span>'
                )
            if colores:
                detail_parts.append(escape(", ".join(colores)))

            detail_html = ""
            if detail_parts:
                detail_line = " · ".join(detail_parts)
                detail_html = (
                    f'<tr><td colspan="2" style="padding:3px 14px;font-size:11px;'
                    f'color:#666;background:{header_bg};border-bottom:1px solid {border_color};">'
                    f'{detail_line}</td></tr>'
                )

            price_groups = _group_by_price(tallas)

            rows_html: list[str] = []
            for idx, (precio, group_tallas) in enumerate(price_groups):
                bg = row_alt if idx % 2 == 0 else "#fff"
                talla_str = escape(_compact_range(group_tallas))
                price_str = f"${precio:,.2f}"
                rows_html.append(
                    f'<tr style="background:{bg};">'
                    f'<td style="padding:5px 14px;color:#555;font-size:12px;">{talla_str}</td>'
                    f'<td align="right" style="padding:5px 14px;font-weight:bold;'
                    f'color:{title_color};font-size:12px;">{price_str}</td>'
                    f'</tr>'
                )

            card = (
                f'<table width="100%" cellpadding="0" cellspacing="0" '
                f'style="background:#fff;border:1px solid {border_color};'
                f'border-left:4px solid {accent};">'
                # Name
                f'<tr><td colspan="2" style="background:{header_bg};padding:9px 14px;'
                f'font-weight:bold;font-size:12px;color:{title_color};'
                f'border-bottom:1px solid {border_color};">{escape(nombre)}</td></tr>'
                # Detail row (gender + colors)
                f'{detail_html}'
                # Price rows
                f'{"".join(rows_html)}'
                f'</table>'
            )

            if col == 0:
                parts.append(f'<tr><td width="50%" valign="top">{card}</td>')
                col = 1
            else:
                parts.append(f'<td width="50%" valign="top">{card}</td></tr>')
                col = 0

        if col == 1:
            parts.append('<td width="50%"></td></tr>')
        parts.append('</table>')

    # Footer
    parts.append("""
<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;border-top:1px solid #e2c9be;">
<tr><td style="color:#A07060;font-size:10px;text-align:center;padding-top:10px;">
  Tallas en n&uacute;meros pares (4, 6, 8, 10&hellip;) &middot;
  Precios sujetos a cambio sin previo aviso.
</td></tr></table>
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
