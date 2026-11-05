"""Generacion basica de etiquetas normal y split para presentaciones."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import textwrap

from PIL import Image, ImageDraw, ImageFont

from pos_uniformes.database.models import Variante
from pos_uniformes.utils.inventory_label_content_helper import (
    build_inventory_label_price_line,
    resolve_inventory_label_profile,
)
from pos_uniformes.utils.qr_generator import QrGenerator

LABELS_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "generated" / "labels"

STANDARD_SIZE = (992, 271)
SPLIT_SIZE = (976, 342)
SPLIT_SECTION_WIDTH = 244
CONTINUOUS_SIZE = (244, 260)
DK1221_SIZE = 202  # 23mm × 23mm area imprimible (brother_ql dots_printable)
QR_SIZE_STANDARD = 231
QR_SIZE_SPLIT = 160
QR_SIZE_CONTINUOUS = 200
QR_SIZE_DK1221 = 180

_CONTINUOUS_MODES = {"continuous"}
_SPLIT_MODES = {"split"}
_DK1221_MODES = {"dk1221"}


@dataclass(frozen=True)
class LabelRenderResult:
    mode: str
    image_path: Path
    effective_copies: int
    requested_copies: int


@dataclass(frozen=True)
class StandardLabelContent:
    """Lo que dice la etiqueta Label (el formato de 29 × 90 mm)."""

    familia: str        # "uniforme" | "ropa_normal"
    encabezado: str     # renglón chico de arriba: escuela, o marca · color
    nombre: str         # lo grande
    talla: str          # en caja negra; vacío si es unitalla
    color: str          # solo en uniformes y si no va ya en el nombre
    precio: str         # "$179"; vacío en uniformes
    sku: str


@dataclass(frozen=True)
class SplitLabelLine:
    text: str
    base_size: int
    min_size: int
    gap_after: int = 6


class LabelGenerator:
    """Renderiza etiquetas basicas con los dos formatos heredados del sistema legacy."""

    @classmethod
    def _normalize_mode(cls, mode: str) -> str:
        raw = str(mode).strip().lower()
        if raw in _SPLIT_MODES:
            return "split"
        if raw in _CONTINUOUS_MODES:
            return "continuous"
        if raw in _DK1221_MODES:
            return "dk1221"
        return "standard"

    @classmethod
    def output_dir(cls, mode: str) -> Path:
        _FOLDER_MAP = {"split": "split", "continuous": "continuous", "dk1221": "dk1221"}
        folder = _FOLDER_MAP.get(mode, "standard")
        directory = LABELS_OUTPUT_DIR / folder
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @classmethod
    def path_for_variant(cls, variante: Variante, mode: str) -> Path:
        suffix = mode if mode in {"split", "continuous", "dk1221"} else "standard"
        return cls.output_dir(mode) / f"{variante.sku}_{suffix}.png"

    @classmethod
    def ensure_qr(cls, variante: Variante) -> Path:
        qr_path = QrGenerator.path_for_variant(variante)
        if not qr_path.exists():
            qr_path = QrGenerator.generate_for_variant(variante)
        return qr_path

    @classmethod
    def render_for_variant(
        cls,
        variante: Variante,
        *,
        mode: str = "standard",
        requested_copies: int = 1,
        show_price: bool | None = None,
    ) -> LabelRenderResult:
        normalized_mode = cls._normalize_mode(mode)
        qr_path = cls.ensure_qr(variante)
        output_path = cls.path_for_variant(variante, normalized_mode)
        if normalized_mode == "split":
            cls._render_split(variante, qr_path, output_path, show_price=show_price)
            effective_copies = max(1, math.ceil(max(1, requested_copies) / 4))
        elif normalized_mode == "continuous":
            cls._render_continuous(variante, qr_path, output_path, show_price=show_price)
            effective_copies = max(1, requested_copies)
        elif normalized_mode == "dk1221":
            cls._render_dk1221(variante, qr_path, output_path)
            effective_copies = max(1, requested_copies)
        else:
            cls._render_standard(variante, qr_path, output_path, show_price=show_price)
            effective_copies = max(1, requested_copies)
        return LabelRenderResult(
            mode=normalized_mode,
            image_path=output_path,
            effective_copies=effective_copies,
            requested_copies=max(1, requested_copies),
        )

    @classmethod
    def _render_standard(cls, variante: Variante, qr_path: Path, output_path: Path, *, show_price: bool | None = None) -> None:
        """La etiqueta «Label» (29 × 90 mm), rediseñada el 2026-11-05.

        Antes eran tres renglones del mismo tamaño y peso —escuela, nombre con
        «T: 6» pegado, SKU— y en la ropa normal el precio era uno más de ellos
        («Precio: $179.00»). Daniel: «que se vea mejor el nombre del producto y,
        en las prendas normales, el precio de manera clara». Ahora hay
        jerarquía:

            ENCABEZADO chico   (escuela, o marca · color)
            Nombre GRANDE      (negrita, hasta dos renglones)
            lo que decide      uniforme → [TALLA 6] en caja negra + color
                               ropa     → $179 enorme (+ talla si no es unitalla)
                               y el SKU chico a la derecha
        """
        label_image = Image.new("1", STANDARD_SIZE, 1)
        draw = ImageDraw.Draw(label_image)
        qr_image = Image.open(qr_path).convert("1").resize((QR_SIZE_STANDARD, QR_SIZE_STANDARD))
        qr_x = STANDARD_SIZE[0] - QR_SIZE_STANDARD - 20
        qr_y = (STANDARD_SIZE[1] - QR_SIZE_STANDARD) // 2
        label_image.paste(qr_image, (qr_x, qr_y))

        c = cls.standard_content(variante, show_price=show_price)
        x0, ancho = 24, qr_x - 24 - 28
        alto = STANDARD_SIZE[1]
        fila_abajo = 70                      # alto de la fila de talla / precio
        y_abajo = alto - 14 - fila_abajo

        y = 14
        if c.encabezado:
            f_enc = cls._fit_font(draw, c.encabezado, ancho, base_size=27, min_size=18)
            draw.text((x0, y), c.encabezado, font=f_enc, fill=0)
            y += cls._line_height(f_enc) + 12

        # El nombre: lo más grande que quepa entre el encabezado y la fila de abajo.
        hueco = y_abajo - 6 - y
        f_nom, renglones = cls._fit_wrapped(draw, c.nombre, ancho, hueco, base_size=66, min_size=28)
        paso = cls._alto_real(f_nom)
        y_nom = y + max(0, (hueco - len(renglones) * paso) // 2)
        for renglon in renglones:
            draw.text((x0, y_nom), renglon, font=f_nom, fill=0)
            y_nom += paso

        # SKU chico, pegado a la derecha de la fila de abajo.
        f_sku = cls._load_font(23)
        ancho_sku = cls._text_width(draw, c.sku, f_sku)
        draw.text((x0 + ancho - ancho_sku, y_abajo + fila_abajo - cls._line_height(f_sku) - 6), c.sku, font=f_sku, fill=0)
        libre = ancho - ancho_sku - 20       # lo que queda para talla / precio / color

        x = x0
        if c.precio:
            f_pre = cls._fit_font(draw, c.precio, int(libre * 0.62), base_size=86, min_size=44, bold=True)
            caja = draw.textbbox((0, 0), c.precio, font=f_pre)
            draw.text((x - caja[0], y_abajo + fila_abajo - caja[3]), c.precio, font=f_pre, fill=0)
            x += (caja[2] - caja[0]) + 26
        if c.talla:
            x = cls._pastilla(draw, f"TALLA {c.talla}", x, y_abajo + (10 if c.precio else 4), fila_abajo - (14 if c.precio else 8),
                              max_width=x0 + libre - x) + 18
        if c.color and x < x0 + libre - 60:
            f_col = cls._fit_font(draw, c.color, x0 + libre - x, base_size=30, min_size=18)
            draw.text((x, y_abajo + (fila_abajo - cls._line_height(f_col)) // 2), c.color, font=f_col, fill=0)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        label_image.save(output_path, "PNG")

    @classmethod
    def standard_content(cls, variante: Variante, *, show_price: bool | None = None) -> "StandardLabelContent":
        """Qué dice la etiqueta Label, separado de cómo se pinta (para probarlo)."""
        producto = variante.producto
        profile = resolve_inventory_label_profile(variante)
        price_visible = profile.show_price and (show_price is None or show_price)
        escuela = getattr(getattr(producto, "escuela", None), "nombre", "") or ""
        nivel = getattr(getattr(producto, "nivel_educativo", None), "nombre", "") or ""
        marca = getattr(getattr(producto, "marca", None), "nombre", "") or ""
        titulo = cls._label_title(variante)
        talla = str(variante.talla or "").strip()
        color = str(getattr(variante, "color", "") or "").strip()
        if color.casefold() in {"sin color", "n/a", "-"}:
            color = ""
        # El color ya va en el nombre cuando el producto tiene varios (Short Deportivo Rojo).
        if color and color.casefold() in titulo.casefold():
            color = ""

        if profile.family == "uniforme":
            encabezado = " · ".join(p for p in (nivel, escuela) if p).upper()
            # La escuela ya está arriba: «Pants 3pz Deportivo Vicente Guerrero» → «Pants 3pz Deportivo».
            nombre = cls._sin_escuela(titulo, escuela)
            return StandardLabelContent("uniforme", encabezado, nombre, talla, color, "", str(variante.sku))

        sin_talla = talla.casefold() in {"", "unitalla", "sin talla", "única", "unica"}
        partes = [marca if marca.casefold() not in {"", "sin marca"} else "", color, "Unitalla" if talla and sin_talla else ""]
        encabezado = " · ".join(p for p in partes if p).upper()
        precio = cls._precio_corto(variante) if price_visible else ""
        return StandardLabelContent("ropa_normal", encabezado, titulo, "" if sin_talla else talla, "", precio, str(variante.sku))

    @staticmethod
    def _sin_escuela(titulo: str, escuela: str) -> str:
        escuela = " ".join(str(escuela or "").split())
        if not escuela:
            return titulo
        bajo = titulo.casefold()
        i = bajo.find(escuela.casefold())
        if i < 0:
            return titulo
        limpio = " ".join((titulo[:i] + titulo[i + len(escuela):]).split()).strip(" -|·")
        return limpio or titulo

    @staticmethod
    def _precio_corto(variante: Variante) -> str:
        """`$179` cuando son pesos cerrados, `$179.50` cuando no."""
        from decimal import Decimal

        precio = Decimal(str(getattr(variante, "precio_venta", "0") or "0")).quantize(Decimal("0.01"))
        if precio == precio.to_integral():
            return f"${int(precio):,}"
        return f"${precio:,.2f}"

    @classmethod
    def _pastilla(cls, draw: ImageDraw.ImageDraw, texto: str, x: int, y: int, alto: int, *, max_width: int) -> int:
        """Texto blanco en caja negra redondeada. Devuelve la x donde termina."""
        fuente = cls._fit_font(draw, texto, max(40, max_width - 36), base_size=int(alto * 0.62), min_size=18, bold=True)
        caja = draw.textbbox((0, 0), texto, font=fuente)
        ancho = (caja[2] - caja[0]) + 36
        draw.rounded_rectangle((x, y, x + ancho, y + alto), radius=14, fill=0)
        draw.text((x + 18 - caja[0], y + (alto - (caja[3] - caja[1])) // 2 - caja[1]), texto, font=fuente, fill=1)
        return x + ancho

    @staticmethod
    def _alto_real(font: ImageFont.ImageFont) -> int:
        """El renglón completo (con lo que sube y lo que baja), no solo la caja de «Ag»."""
        try:
            sube, baja = font.getmetrics()
            return int(sube + baja)
        except Exception:  # noqa: BLE001 — la fuente de respaldo de PIL no tiene métricas
            caja = font.getbbox("Ág")
            return int(caja[3] - caja[1]) + 6

    @classmethod
    def _fit_wrapped(
        cls, draw: ImageDraw.ImageDraw, text: str, max_width: int, max_height: int, *, base_size: int, min_size: int,
    ) -> tuple[ImageFont.ImageFont, list[str]]:
        """La negrita más grande con la que `text` cabe, en uno o dos renglones.

        Un renglón se prefiere mientras la letra no baje de 44: un nombre partido
        en dos se lee peor que uno un poco más chico. Solo se parte cuando así
        la letra crece de verdad (un nombre largo que en un renglón quedaría
        chiquito)."""
        palabras = str(text or "").split() or [""]
        entero = " ".join(palabras)

        def en_uno() -> tuple[int, ImageFont.ImageFont] | None:
            for size in range(base_size, min_size - 1, -2):
                f = cls._load_font(size, bold=True)
                if cls._text_width(draw, entero, f) <= max_width and cls._alto_real(f) <= max_height:
                    return size, f
            return None

        def en_dos() -> tuple[int, ImageFont.ImageFont, list[str]] | None:
            if len(palabras) < 2:
                return None
            for size in range(base_size, min_size - 1, -2):
                f = cls._load_font(size, bold=True)
                if 2 * cls._alto_real(f) > max_height:
                    continue
                mejor = None
                for i in range(1, len(palabras)):
                    a, b = " ".join(palabras[:i]), " ".join(palabras[i:])
                    wa, wb = cls._text_width(draw, a, f), cls._text_width(draw, b, f)
                    if wa <= max_width and wb <= max_width and (mejor is None or max(wa, wb) < mejor[0]):
                        mejor = (max(wa, wb), [a, b])
                if mejor is not None:
                    return size, f, mejor[1]
            return None

        uno, dos = en_uno(), en_dos()
        if uno is not None and (uno[0] >= 44 or dos is None or dos[0] < uno[0] * 1.25):
            return uno[1], [entero]
        if dos is not None:
            return dos[1], dos[2]
        return cls._load_font(min_size, bold=True), [entero]

    @classmethod
    def _render_split(cls, variante: Variante, qr_path: Path, output_path: Path, *, show_price: bool | None = None) -> None:
        label_image = Image.new("1", SPLIT_SIZE, 1)
        draw = ImageDraw.Draw(label_image)
        qr_image = Image.open(qr_path).convert("1").resize((QR_SIZE_SPLIT, QR_SIZE_SPLIT))
        label_lines = cls._split_label_lines(variante, show_price=show_price)
        for section in range(4):
            section_x = section * SPLIT_SECTION_WIDTH
            qr_x = section_x + (SPLIT_SECTION_WIDTH - QR_SIZE_SPLIT) // 2
            qr_y = 6
            label_image.paste(qr_image, (qr_x, qr_y))
            text_area_x = section_x + 10
            text_area_width = SPLIT_SECTION_WIDTH - 20
            text_area_y = qr_y + QR_SIZE_SPLIT + 2
            text_y = text_area_y
            for line in label_lines:
                font = cls._fit_font(
                    draw,
                    line.text,
                    text_area_width,
                    base_size=line.base_size,
                    min_size=line.min_size,
                )
                text_width = cls._text_width(draw, line.text, font)
                text_x = text_area_x + (text_area_width - text_width) // 2
                draw.text((text_x, text_y), line.text, font=font, fill=0)
                text_y += cls._line_height(font) + line.gap_after

        output_path.parent.mkdir(parents=True, exist_ok=True)
        label_image.save(output_path, "PNG")

    @classmethod
    def _render_continuous(cls, variante: Variante, qr_path: Path, output_path: Path, *, show_price: bool | None = None) -> None:
        draw_temp = ImageDraw.Draw(Image.new("1", (1, 1), 1))
        label_lines = cls._split_label_lines(variante, show_price=show_price)
        text_area_width = CONTINUOUS_SIZE[0] - 20
        text_block_height = cls._measure_split_lines(draw_temp, label_lines, text_area_width)
        margin = 5
        gap = 6
        label_height = margin + QR_SIZE_CONTINUOUS + gap + text_block_height + margin
        size = (CONTINUOUS_SIZE[0], label_height)

        label_image = Image.new("1", size, 1)
        draw = ImageDraw.Draw(label_image)
        qr_image = Image.open(qr_path).convert("1").resize((QR_SIZE_CONTINUOUS, QR_SIZE_CONTINUOUS))
        qr_x = (size[0] - QR_SIZE_CONTINUOUS) // 2
        qr_y = margin
        label_image.paste(qr_image, (qr_x, qr_y))

        text_x_base = 10
        text_y = qr_y + QR_SIZE_CONTINUOUS + gap
        for line in label_lines:
            font = cls._fit_font(
                draw,
                line.text,
                text_area_width,
                base_size=line.base_size,
                min_size=line.min_size,
            )
            text_width = cls._text_width(draw, line.text, font)
            text_x = text_x_base + (text_area_width - text_width) // 2
            draw.text((text_x, text_y), line.text, font=font, fill=0)
            text_y += cls._line_height(font) + line.gap_after

        output_path.parent.mkdir(parents=True, exist_ok=True)
        label_image.save(output_path, "PNG")

    @classmethod
    def _render_dk1221(cls, variante: Variante, qr_path: Path, output_path: Path) -> None:
        size = DK1221_SIZE
        label_image = Image.new("1", (size, size), 1)
        draw = ImageDraw.Draw(label_image)
        qr_image = Image.open(qr_path).convert("1").resize((QR_SIZE_DK1221, QR_SIZE_DK1221))
        qr_x = (size - QR_SIZE_DK1221) // 2
        qr_y = 4
        label_image.paste(qr_image, (qr_x, qr_y))
        title = cls._label_title(variante)
        text = cls._build_label_text(title, variante.talla)
        if text:
            font = cls._fit_font(draw, text, size - 12, base_size=18, min_size=8)
            tw = cls._text_width(draw, text, font)
            tx = (size - tw) // 2
            ty = qr_y + QR_SIZE_DK1221 + 2
            draw.text((tx, ty), text, font=font, fill=0)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        label_image.save(output_path, "PNG")

    @classmethod
    def _split_label_lines(cls, variante: Variante, *, show_price: bool | None = None) -> list[SplitLabelLine]:
        producto = variante.producto
        profile = resolve_inventory_label_profile(variante)
        price_visible = profile.show_price and (show_price is None or show_price)
        title = cls._label_title(variante)
        if profile.family == "ropa_normal" and price_visible:
            return [
                SplitLabelLine(text=title, base_size=30, min_size=14, gap_after=8),
                SplitLabelLine(
                    text=build_inventory_label_price_line(variante).replace("Precio: ", ""),
                    base_size=38,
                    min_size=24,
                    gap_after=0,
                ),
            ]
        lines = textwrap.wrap(cls._build_label_text(title, variante.talla), width=20) or [title]
        if price_visible:
            lines.append(build_inventory_label_price_line(variante))
        return [SplitLabelLine(text=line, base_size=34, min_size=16, gap_after=6) for line in lines]

    @classmethod
    def _label_title(cls, variante: Variante) -> str:
        from pos_uniformes.services.nombre_con_color_service import nombre_de_variante

        producto = variante.producto
        preferred_name = getattr(producto, "nombre_base", "") or getattr(producto, "nombre", "")
        title = cls._clean_name(preferred_name, variante.talla)
        if not title:
            title = cls._clean_name(getattr(producto, "nombre", ""), variante.talla)
        # Producto de varios colores: la etiqueta dice cuál (Short Deportivo Rojo).
        return nombre_de_variante(variante, title)

    @staticmethod
    def _clean_name(nombre: str, talla: str) -> str:
        cleaned = " ".join(str(nombre or "").replace("_", " ").split())
        lowered = cleaned.casefold()
        if "talla" in lowered:
            cleaned = cleaned[: lowered.index("talla")].strip()
        size_value = str(talla or "").strip()
        if size_value:
            suffixes = [
                f"| {size_value}",
                f"- {size_value}",
                size_value,
            ]
            for suffix in suffixes:
                if cleaned.endswith(suffix):
                    cleaned = cleaned[: -len(suffix)].strip(" |-")
        return cleaned or str(nombre or "").strip()

    @staticmethod
    def _build_label_text(nombre: str, talla: str) -> str:
        size_value = str(talla or "").strip()
        if size_value and size_value.casefold() not in {"sin talla", "unitalla"}:
            return f"{nombre} T: {size_value}"
        if size_value:
            return f"{nombre} T: {size_value}"
        return nombre

    @staticmethod
    def _font_candidates() -> list[Path]:
        return [
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Helvetica.ttc"),
            Path("/Library/Fonts/Arial.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/calibri.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]

    @staticmethod
    def _bold_font_candidates() -> list[Path]:
        return [
            Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
            Path("/Library/Fonts/Arial Bold.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("C:/Windows/Fonts/calibrib.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ]

    @classmethod
    def _fit_font(
        cls,
        draw: ImageDraw.ImageDraw,
        text: str,
        max_width: int,
        *,
        base_size: int,
        min_size: int,
        bold: bool = False,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for font_size in range(base_size, min_size - 1, -2):
            font = cls._load_font(font_size, bold=bold)
            if cls._text_width(draw, text, font) <= max_width:
                return font
        return cls._load_font(min_size, bold=bold)

    @classmethod
    def _load_font(cls, size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        # Sin negrita instalada se cae a la normal: la etiqueta sale igual.
        candidatos = (cls._bold_font_candidates() if bold else []) + cls._font_candidates()
        for candidate in candidatos:
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), size)
                except OSError:
                    continue
        return ImageFont.load_default()

    @staticmethod
    def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0]

    @staticmethod
    def _line_height(font: ImageFont.ImageFont) -> int:
        box = font.getbbox("Ag")
        return box[3] - box[1]

    @classmethod
    def _measure_lines(
        cls,
        draw: ImageDraw.ImageDraw,
        lines: list[str],
        max_width: int,
        *,
        base_size: int,
        min_size: int,
    ) -> int:
        total = 0
        for line in lines:
            font = cls._fit_font(draw, line, max_width, base_size=base_size, min_size=min_size)
            total += cls._line_height(font) + 10
        return max(total - 10, 0)

    @classmethod
    def _measure_split_lines(
        cls,
        draw: ImageDraw.ImageDraw,
        lines: list[SplitLabelLine],
        max_width: int,
    ) -> int:
        total = 0
        for line in lines:
            font = cls._fit_font(
                draw,
                line.text,
                max_width,
                base_size=line.base_size,
                min_size=line.min_size,
            )
            total += cls._line_height(font) + line.gap_after
        return max(total, 0)
