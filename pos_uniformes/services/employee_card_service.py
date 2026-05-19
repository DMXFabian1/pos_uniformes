"""Renderizado de credenciales visuales para empleadas."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pos_uniformes.database.models import Empleada
from pos_uniformes.services.employee_identity_service import EmployeeIdentityService
from pos_uniformes.utils.headless_browser_helper import resolve_headless_browser_executable
from pos_uniformes.utils.qr_generator import QrGenerator

CARD_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "generated" / "employee_cards"
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "assets" / "employee_card_template"
TEMPLATE_HTML_PATH = TEMPLATE_DIR / "employee-card.html"
TEMPLATE_CSS_PATH = TEMPLATE_DIR / "employee-card.css"
CARD_SIZE = (1080, 1350)
BACKGROUND_COLOR = "#F6F0E8"
SURFACE_COLOR = "#FFFCF7"
TEXT_PRIMARY = "#191716"
TEXT_MUTED = "#6E6258"
DIVIDER_COLOR = "#DED2C4"
ACCENT_COLOR = "#111111"
ACCENT_SOFT = "#EEE8E0"
SECONDARY_COLOR = "#E8DDD2"


@dataclass(frozen=True)
class EmployeeCardRenderInput:
    business_name: str | None
    logo_path: str | None
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

    @staticmethod
    def _business_name() -> str:
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services.business_settings_service import BusinessSettingsService
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                if (config.nombre_negocio or "").strip():
                    return str(config.nombre_negocio).strip()
        except Exception:
            return "POS Uniformes"
        return "POS Uniformes"

    @staticmethod
    def default_logo_path() -> Path | None:
        try:
            from pos_uniformes.database.connection import get_session
            from pos_uniformes.services.business_settings_service import BusinessSettingsService
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                if (config.logo_path or "").strip():
                    candidate = Path(str(config.logo_path)).expanduser()
                    if candidate.exists():
                        return candidate
        except Exception:
            pass
        candidates = [
            Path(__file__).resolve().parents[1] / "assets" / "logo.png",
            Path(__file__).resolve().parents[1] / "assets" / "logo.jpg",
            Path(__file__).resolve().parents[1] / "assets" / "logo.jpeg",
            Path(__file__).resolve().parents[1] / "assets" / "customer_card_template" / "brand" / "store-logo.PNG",
            Path(__file__).resolve().parents[1] / "assets" / "customer_card_template" / "brand" / "store-logo.png",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    @classmethod
    def build_render_input(cls, employee: Empleada) -> EmployeeCardRenderInput:
        qr_path = QrGenerator.path_for_employee(employee)
        if not qr_path.exists():
            qr_path = QrGenerator.generate_for_employee(employee)
        logo = cls.default_logo_path()
        return EmployeeCardRenderInput(
            business_name=cls._business_name(),
            logo_path=str(logo) if logo else None,
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
        html_error: Exception | None = None

        try:
            return cls._render_card_from_html(payload, target)
        except Exception as exc:
            html_error = exc

        try:
            return cls._render_card_with_pil(payload, target)
        except Exception as pil_error:
            if html_error is not None:
                raise RuntimeError(
                    "No se pudo renderizar la credencial de staff ni con HTML ni con PIL."
                ) from pil_error
            raise

    @classmethod
    def _render_card_from_html(cls, payload: EmployeeCardRenderInput, output_path: Path) -> Path:
        template_html = TEMPLATE_HTML_PATH.read_text(encoding="utf-8")
        template_css = TEMPLATE_CSS_PATH.read_text(encoding="utf-8")
        html_document = cls._build_html_document(payload, template_html, template_css)
        browser_path = resolve_headless_browser_executable()
        if browser_path is None:
            raise FileNotFoundError("No se encontro un browser compatible para render headless.")

        with tempfile.TemporaryDirectory(prefix="employee-card-") as temp_dir:
            temp_html = Path(temp_dir) / "employee-card.html"
            temp_html.write_text(html_document, encoding="utf-8")
            command = [
                browser_path,
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                f"--window-size={CARD_SIZE[0]},{CARD_SIZE[1]}",
                f"--screenshot={str(output_path)}",
                "--allow-file-access-from-files",
                temp_html.as_uri(),
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
        return output_path

    @classmethod
    def _build_html_document(
        cls,
        payload: EmployeeCardRenderInput,
        template_html: str,
        template_css: str,
    ) -> str:
        replacements = {
            "{{ primary_color }}": ACCENT_COLOR,
            "{{ secondary_color }}": SECONDARY_COLOR,
            "{{ name_size }}": cls._name_size_variant(payload.visible_name),
            "{{ logo_path }}": cls._asset_src(
                payload.logo_path,
                fallback=cls._fallback_logo_data_uri(payload.business_name),
            ),
            "{{ visible_name }}": escape(payload.visible_name),
            "{{ employee_code }}": escape(payload.employee_code),
            "{{ qr_path }}": cls._asset_src(payload.qr_path),
        }
        document = template_html.replace(
            '<link rel="stylesheet" href="./employee-card.css" />',
            f"<style>\n{template_css}\n</style>",
        )
        for placeholder, value in replacements.items():
            document = document.replace(placeholder, value)
        return document

    @staticmethod
    def _asset_src(path_value: str | None, *, fallback: str = "") -> str:
        if path_value:
            path = Path(path_value)
            if path.exists():
                return path.resolve().as_uri()
        return fallback

    @staticmethod
    def _fallback_logo_data_uri(business_name: str | None = None) -> str:
        resolved = (business_name or "POS Uniformes").strip() or "POS Uniformes"
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" width="720" height="220" viewBox="0 0 720 220">
          <rect width="720" height="220" fill="white" fill-opacity="0"/>
          <text x="360" y="122" text-anchor="middle" font-family="Baskerville, serif" font-size="58" font-weight="700" fill="{ACCENT_COLOR}">{escape(resolved)}</text>
        </svg>
        """.strip()
        return f"data:image/svg+xml;charset=utf-8,{quote(svg)}"

    @staticmethod
    def _name_size_variant(full_name: str) -> str:
        normalized = " ".join((full_name or "").split())
        if len(normalized) >= 28 or len(normalized.split()) >= 4:
            return "dense"
        if len(normalized) >= 22:
            return "compact"
        if len(normalized) >= 15 or len(normalized.split()) >= 3:
            return "medium"
        return "default"

    @classmethod
    def _render_card_with_pil(cls, payload: EmployeeCardRenderInput, target: Path) -> Path:
        canvas = Image.new("RGBA", CARD_SIZE, BACKGROUND_COLOR)
        draw = ImageDraw.Draw(canvas)

        cls._draw_background_pattern(canvas)
        cls._draw_surface_panel(draw)
        cls._draw_top_band(draw)
        cls._draw_logo_block(canvas, payload.logo_path, payload.business_name)
        cls._draw_name_block(draw, payload.visible_name)
        cls._draw_code_badge(draw, payload.employee_code)
        cls._draw_qr_block(canvas, payload.qr_path)
        cls._draw_footer(draw)

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
    def _draw_logo_block(
        cls,
        canvas: Image.Image,
        logo_path: str | None,
        business_name: str | None = None,
    ) -> None:
        if logo_path:
            path = Path(logo_path)
            if path.exists():
                try:
                    logo = Image.open(path).convert("RGBA")
                    logo.thumbnail((240, 120))
                    pos_x = (CARD_SIZE[0] - logo.width) // 2
                    canvas.alpha_composite(logo, (pos_x, 190))
                    return
                except Exception:
                    pass
        draw = ImageDraw.Draw(canvas)
        draw.text(
            (CARD_SIZE[0] // 2, 210),
            (business_name or "POS Uniformes").strip() or "POS Uniformes",
            anchor="mm",
            font=cls._font(42, bold=True),
            fill=ACCENT_COLOR,
        )
        draw.text(
            (CARD_SIZE[0] // 2, 258),
            "Credencial de staff",
            anchor="mm",
            font=cls._font(24),
            fill=TEXT_MUTED,
        )

    @classmethod
    def _draw_name_block(cls, draw: ImageDraw.ImageDraw, visible_name: str) -> None:
        draw.text(
            (120, 352),
            visible_name,
            font=cls._font(cls._title_font_size(visible_name), bold=True),
            fill=TEXT_PRIMARY,
        )
        draw.line((120, 428, 960, 428), fill=DIVIDER_COLOR, width=2)

    @classmethod
    def _title_font_size(cls, visible_name: str) -> int:
        variant = cls._name_size_variant(visible_name)
        if variant == "dense":
            return 42
        if variant == "compact":
            return 50
        if variant == "medium":
            return 58
        return 64

    @classmethod
    def _draw_code_badge(cls, draw: ImageDraw.ImageDraw, employee_code: str) -> None:
        draw.rounded_rectangle(
            (120, 472, 430, 552),
            radius=26,
            fill=ACCENT_SOFT,
            outline=DIVIDER_COLOR,
            width=2,
        )
        draw.text(
            (150, 489),
            "Codigo",
            font=cls._font(20),
            fill=TEXT_MUTED,
        )
        draw.text(
            (150, 514),
            employee_code,
            font=cls._font(30, bold=True),
            fill=ACCENT_COLOR,
        )

    @classmethod
    def _draw_qr_block(cls, canvas: Image.Image, qr_path: str) -> None:
        qr_image = Image.open(qr_path).convert("RGBA")
        qr_image = qr_image.resize((360, 360))
        qr_panel = Image.new("RGBA", (420, 420), (255, 255, 255, 0))
        qr_draw = ImageDraw.Draw(qr_panel)
        qr_draw.rounded_rectangle(
            (0, 0, 420, 420),
            radius=34,
            fill="#FFFFFF",
            outline=DIVIDER_COLOR,
            width=2,
        )
        qr_panel.alpha_composite(qr_image, (30, 30))
        canvas.alpha_composite(qr_panel, (330, 620))

    @classmethod
    def _draw_footer(cls, draw: ImageDraw.ImageDraw) -> None:
        draw.text(
            (CARD_SIZE[0] // 2, 1100),
            "Escanea para identificar responsable",
            anchor="mm",
            font=cls._font(24),
            fill=TEXT_MUTED,
        )
        draw.text(
            (CARD_SIZE[0] // 2, 1190),
            "Credencial interna para registro de ventas y comisiones",
            anchor="mm",
            font=cls._font(20),
            fill=TEXT_MUTED,
        )
