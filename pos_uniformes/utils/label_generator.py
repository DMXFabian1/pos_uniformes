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
CONTINUOUS_SIZE = (244, 342)
QR_SIZE_STANDARD = 231
QR_SIZE_SPLIT = 231

_CONTINUOUS_MODES = {"continuous"}
_SPLIT_MODES = {"split"}


@dataclass(frozen=True)
class LabelRenderResult:
    mode: str
    image_path: Path
    effective_copies: int
    requested_copies: int


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
        return "standard"

    @classmethod
    def output_dir(cls, mode: str) -> Path:
        folder = "split" if mode == "split" else ("continuous" if mode == "continuous" else "standard")
        directory = LABELS_OUTPUT_DIR / folder
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @classmethod
    def path_for_variant(cls, variante: Variante, mode: str) -> Path:
        suffix = mode if mode in {"split", "continuous"} else "standard"
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
    ) -> LabelRenderResult:
        normalized_mode = cls._normalize_mode(mode)
        qr_path = cls.ensure_qr(variante)
        output_path = cls.path_for_variant(variante, normalized_mode)
        if normalized_mode == "split":
            cls._render_split(variante, qr_path, output_path)
            effective_copies = max(1, math.ceil(max(1, requested_copies) / 4))
        elif normalized_mode == "continuous":
            cls._render_continuous(variante, qr_path, output_path)
            effective_copies = max(1, requested_copies)
        else:
            cls._render_standard(variante, qr_path, output_path)
            effective_copies = max(1, requested_copies)
        return LabelRenderResult(
            mode=normalized_mode,
            image_path=output_path,
            effective_copies=effective_copies,
            requested_copies=max(1, requested_copies),
        )

    @classmethod
    def _render_standard(cls, variante: Variante, qr_path: Path, output_path: Path) -> None:
        label_image = Image.new("1", STANDARD_SIZE, 1)
        draw = ImageDraw.Draw(label_image)
        qr_image = Image.open(qr_path).convert("1").resize((QR_SIZE_STANDARD, QR_SIZE_STANDARD))
        qr_x = STANDARD_SIZE[0] - QR_SIZE_STANDARD - 20
        qr_y = (STANDARD_SIZE[1] - QR_SIZE_STANDARD) // 2
        label_image.paste(qr_image, (qr_x, qr_y))

        text_x = 20
        max_text_width = qr_x - 40
        fields = cls._standard_fields(variante)
        total_height = cls._measure_lines(draw, fields, max_text_width, base_size=30, min_size=18)
        text_y = (STANDARD_SIZE[1] - total_height) // 2
        for field in fields:
            font = cls._fit_font(draw, field, max_text_width, base_size=30, min_size=18)
            draw.text((text_x, text_y), field, font=font, fill=0)
            line_height = cls._line_height(font)
            text_y += line_height + 10

        output_path.parent.mkdir(parents=True, exist_ok=True)
        label_image.save(output_path, "PNG")

    @classmethod
    def _render_split(cls, variante: Variante, qr_path: Path, output_path: Path) -> None:
        label_image = Image.new("1", SPLIT_SIZE, 1)
        draw = ImageDraw.Draw(label_image)
        qr_image = Image.open(qr_path).convert("1").resize((QR_SIZE_SPLIT, QR_SIZE_SPLIT))
        label_lines = cls._split_label_lines(variante)
        for section in range(4):
            section_x = section * SPLIT_SECTION_WIDTH
            qr_x = section_x + (SPLIT_SECTION_WIDTH - QR_SIZE_SPLIT) // 2
            qr_y = 10
            label_image.paste(qr_image, (qr_x, qr_y))
            text_area_x = section_x + 10
            text_area_width = SPLIT_SECTION_WIDTH - 20
            text_area_y = qr_y + QR_SIZE_SPLIT + 8
            text_area_height = SPLIT_SIZE[1] - text_area_y - 10
            text_y = text_area_y + max(
                (text_area_height - cls._measure_split_lines(draw, label_lines, text_area_width)) // 2,
                0,
            )
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
    def _render_continuous(cls, variante: Variante, qr_path: Path, output_path: Path) -> None:
        label_image = Image.new("1", CONTINUOUS_SIZE, 1)
        draw = ImageDraw.Draw(label_image)
        qr_image = Image.open(qr_path).convert("1").resize((QR_SIZE_SPLIT, QR_SIZE_SPLIT))
        qr_x = (CONTINUOUS_SIZE[0] - QR_SIZE_SPLIT) // 2
        qr_y = 10
        label_image.paste(qr_image, (qr_x, qr_y))
        text_area_x = 10
        text_area_width = CONTINUOUS_SIZE[0] - 20
        text_area_y = qr_y + QR_SIZE_SPLIT + 8
        text_area_height = CONTINUOUS_SIZE[1] - text_area_y - 10
        label_lines = cls._split_label_lines(variante)
        text_y = text_area_y + max(
            (text_area_height - cls._measure_split_lines(draw, label_lines, text_area_width)) // 2,
            0,
        )
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
    def _standard_fields(cls, variante: Variante) -> list[str]:
        producto = variante.producto
        profile = resolve_inventory_label_profile(variante)
        escuela = getattr(getattr(producto, "escuela", None), "nombre", "") or ""
        nivel = getattr(getattr(producto, "nivel_educativo", None), "nombre", "") or ""
        title = cls._label_title(variante)
        pieces: list[str] = []
        if nivel and escuela:
            pieces.append(f"{nivel} - {escuela}")
        elif escuela:
            pieces.append(escuela)
        elif nivel:
            pieces.append(nivel)
        pieces.append(cls._build_label_text(title, variante.talla))
        pieces.append(variante.sku)
        if profile.show_price:
            pieces.append(build_inventory_label_price_line(variante))
        return [piece for piece in pieces if piece]

    @classmethod
    def _split_label_lines(cls, variante: Variante) -> list[SplitLabelLine]:
        producto = variante.producto
        profile = resolve_inventory_label_profile(variante)
        title = cls._label_title(variante)
        if profile.family == "ropa_normal":
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
        if profile.show_price:
            lines.append(build_inventory_label_price_line(variante))
        return [SplitLabelLine(text=line, base_size=34, min_size=16, gap_after=6) for line in lines]

    @classmethod
    def _label_title(cls, variante: Variante) -> str:
        producto = variante.producto
        preferred_name = getattr(producto, "nombre_base", "") or getattr(producto, "nombre", "")
        title = cls._clean_name(preferred_name, variante.talla)
        if title:
            return title
        return cls._clean_name(getattr(producto, "nombre", ""), variante.talla)

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

    @classmethod
    def _fit_font(
        cls,
        draw: ImageDraw.ImageDraw,
        text: str,
        max_width: int,
        *,
        base_size: int,
        min_size: int,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for font_size in range(base_size, min_size - 1, -2):
            font = cls._load_font(font_size)
            if cls._text_width(draw, text, font) <= max_width:
                return font
        return cls._load_font(min_size)

    @classmethod
    def _load_font(cls, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for candidate in cls._font_candidates():
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
