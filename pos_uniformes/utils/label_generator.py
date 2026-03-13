"""Generacion basica de etiquetas normal y split para presentaciones."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import textwrap

from PIL import Image, ImageDraw, ImageFont

from pos_uniformes.database.models import Variante
from pos_uniformes.utils.qr_generator import QrGenerator

LABELS_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "generated" / "labels"

STANDARD_SIZE = (992, 271)
SPLIT_SIZE = (976, 342)
SPLIT_SECTION_WIDTH = 244
QR_SIZE_STANDARD = 231
QR_SIZE_SPLIT = 231


@dataclass(frozen=True)
class LabelRenderResult:
    mode: str
    image_path: Path
    effective_copies: int
    requested_copies: int


class LabelGenerator:
    """Renderiza etiquetas basicas con los dos formatos heredados del sistema legacy."""

    @classmethod
    def output_dir(cls, mode: str) -> Path:
        directory = LABELS_OUTPUT_DIR / ("split" if mode == "split" else "standard")
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @classmethod
    def path_for_variant(cls, variante: Variante, mode: str) -> Path:
        suffix = "split" if mode == "split" else "standard"
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
        normalized_mode = "split" if str(mode).strip().lower() == "split" else "standard"
        qr_path = cls.ensure_qr(variante)
        output_path = cls.path_for_variant(variante, normalized_mode)
        if normalized_mode == "split":
            cls._render_split(variante, qr_path, output_path)
            effective_copies = max(1, math.ceil(max(1, requested_copies) / 4))
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
        label_text = cls._split_label_text(variante)
        lines = textwrap.wrap(label_text, width=20) or [label_text]
        for section in range(4):
            section_x = section * SPLIT_SECTION_WIDTH
            qr_x = section_x + (SPLIT_SECTION_WIDTH - QR_SIZE_SPLIT) // 2
            qr_y = 10
            label_image.paste(qr_image, (qr_x, qr_y))
            font = cls._fit_font(draw, label_text, QR_SIZE_SPLIT, base_size=36, min_size=16)
            text_y = qr_y + QR_SIZE_SPLIT + 6
            for line in lines:
                text_width = cls._text_width(draw, line, font)
                text_x = qr_x + (QR_SIZE_SPLIT - text_width) // 2
                draw.text((text_x, text_y), line, font=font, fill=0)
                text_y += cls._line_height(font) + 6

        output_path.parent.mkdir(parents=True, exist_ok=True)
        label_image.save(output_path, "PNG")

    @classmethod
    def _standard_fields(cls, variante: Variante) -> list[str]:
        producto = variante.producto
        escuela = getattr(getattr(producto, "escuela", None), "nombre", "") or ""
        nivel = getattr(getattr(producto, "nivel_educativo", None), "nombre", "") or ""
        title = cls._clean_name(producto.nombre, variante.talla)
        pieces: list[str] = []
        if nivel and escuela:
            pieces.append(f"{nivel} - {escuela}")
        elif escuela:
            pieces.append(escuela)
        elif nivel:
            pieces.append(nivel)
        pieces.append(cls._build_label_text(title, variante.talla))
        pieces.append(variante.sku)
        return [piece for piece in pieces if piece]

    @classmethod
    def _split_label_text(cls, variante: Variante) -> str:
        producto = variante.producto
        title = cls._clean_name(producto.nombre, variante.talla)
        return cls._build_label_text(title, variante.talla)

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
