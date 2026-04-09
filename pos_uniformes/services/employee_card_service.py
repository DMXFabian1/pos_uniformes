"""Renderizado de credenciales visuales para empleadas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pos_uniformes.database.models import Empleada
from pos_uniformes.services.employee_identity_service import EmployeeIdentityService
from pos_uniformes.utils.qr_generator import QrGenerator

CARD_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "generated" / "employee_cards"
CARD_SIZE = (1080, 1350)
BACKGROUND_COLOR = "#F6F0E8"
SURFACE_COLOR = "#FFFCF7"
TEXT_PRIMARY = "#191716"
TEXT_MUTED = "#6E6258"
DIVIDER_COLOR = "#DED2C4"
ACCENT_COLOR = "#111111"
ACCENT_SOFT = "#EEE8E0"


@dataclass(frozen=True)
class EmployeeCardRenderInput:
    visible_name: str
    employee_code: str
    qr_path: str


class EmployeeCardService:
    """Genera una credencial sobria para staff usando el QR EMP existente."""

    @staticmethod
    def output_dir() -> Path:
        CARD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return CARD_OUTPUT_DIR

    @classmethod
    def path_for_employee(cls, employee: Empleada) -> Path:
        return cls.output_dir() / f"{employee.codigo}_card.png"

    @classmethod
    def exists_for_employee(cls, employee: Empleada) -> bool:
        return cls.path_for_employee(employee).exists()

    @classmethod
    def build_render_input(cls, employee: Empleada) -> EmployeeCardRenderInput:
        qr_path = QrGenerator.path_for_employee(employee)
        if not qr_path.exists():
            qr_path = QrGenerator.generate_for_employee(employee)
        return EmployeeCardRenderInput(
            visible_name=EmployeeIdentityService.build_visible_employee_name(employee.nombre_completo),
            employee_code=str(employee.codigo),
            qr_path=str(qr_path),
        )

    @classmethod
    def render_for_employee(cls, employee: Empleada) -> Path:
        payload = cls.build_render_input(employee)
        output_path = cls.path_for_employee(employee)
        cls.render_card(payload, output_path)
        return output_path

    @classmethod
    def render_card(cls, payload: EmployeeCardRenderInput, output_path: str | Path) -> Path:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        canvas = Image.new("RGBA", CARD_SIZE, BACKGROUND_COLOR)
        draw = ImageDraw.Draw(canvas)

        cls._draw_background_pattern(canvas)
        cls._draw_surface_panel(draw)
        cls._draw_top_band(draw)
        cls._draw_title(draw)
        cls._draw_name_block(draw, payload.visible_name)
        cls._draw_code_badge(draw, payload.employee_code)
        cls._draw_qr_block(canvas, payload.qr_path)

        canvas.convert("RGB").save(target, format="PNG", optimize=True)
        return target

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        ]
        for candidate in candidates:
            path = Path(candidate)
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size=size)
                except Exception:
                    continue
        return ImageFont.load_default()

    @classmethod
    def _draw_background_pattern(cls, canvas: Image.Image) -> None:
        pattern = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
        pattern_draw = ImageDraw.Draw(pattern)
        rgba = (17, 17, 17, 18)
        for offset_y in range(120, CARD_SIZE[1], 220):
            for offset_x in range(90, CARD_SIZE[0], 210):
                pattern_draw.rounded_rectangle(
                    (offset_x, offset_y, offset_x + 96, offset_y + 96),
                    radius=24,
                    outline=rgba,
                    width=2,
                )
        pattern = pattern.filter(ImageFilter.GaussianBlur(radius=0.6))
        canvas.alpha_composite(pattern)

    @staticmethod
    def _draw_surface_panel(draw: ImageDraw.ImageDraw) -> None:
        draw.rounded_rectangle(
            (64, 72, 1016, 1274),
            radius=40,
            fill=SURFACE_COLOR,
            outline=DIVIDER_COLOR,
            width=2,
        )

    @staticmethod
    def _draw_top_band(draw: ImageDraw.ImageDraw) -> None:
        draw.rounded_rectangle(
            (64, 72, 1016, 148),
            radius=40,
            fill=ACCENT_COLOR,
        )
        draw.rounded_rectangle(
            (64, 120, 1016, 148),
            radius=20,
            fill=ACCENT_COLOR,
        )

    @classmethod
    def _draw_title(cls, draw: ImageDraw.ImageDraw) -> None:
        draw.text(
            (540, 214),
            "Staff",
            anchor="mm",
            font=cls._font(52, bold=True),
            fill=TEXT_PRIMARY,
        )

    @classmethod
    def _draw_name_block(cls, draw: ImageDraw.ImageDraw, visible_name: str) -> None:
        draw.text(
            (540, 356),
            visible_name,
            anchor="mm",
            font=cls._font(cls._title_font_size(visible_name), bold=True),
            fill=TEXT_PRIMARY,
        )
        draw.line((170, 428, 910, 428), fill=DIVIDER_COLOR, width=2)

    @classmethod
    def _title_font_size(cls, visible_name: str) -> int:
        normalized = " ".join((visible_name or "").split())
        if len(normalized) >= 24:
            return 64
        if len(normalized) >= 18:
            return 72
        return 80

    @classmethod
    def _draw_code_badge(cls, draw: ImageDraw.ImageDraw, employee_code: str) -> None:
        draw.rounded_rectangle(
            (350, 472, 730, 556),
            radius=30,
            fill=ACCENT_SOFT,
            outline=DIVIDER_COLOR,
            width=2,
        )
        draw.text(
            (540, 514),
            employee_code,
            anchor="mm",
            font=cls._font(34, bold=True),
            fill=ACCENT_COLOR,
        )

    @classmethod
    def _draw_qr_block(cls, canvas: Image.Image, qr_path: str) -> None:
        qr_image = Image.open(qr_path).convert("RGBA")
        qr_image = qr_image.resize((430, 430))
        qr_panel = Image.new("RGBA", (510, 510), (255, 255, 255, 0))
        qr_draw = ImageDraw.Draw(qr_panel)
        qr_draw.rounded_rectangle(
            (0, 0, 510, 510),
            radius=34,
            fill="#FFFFFF",
            outline=DIVIDER_COLOR,
            width=2,
        )
        qr_panel.alpha_composite(qr_image, (40, 40))
        canvas.alpha_composite(qr_panel, (285, 650))
