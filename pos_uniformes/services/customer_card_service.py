"""Renderizado de credenciales visuales para clientes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import Cliente
from pos_uniformes.services.business_settings_service import BusinessSettingsService
from pos_uniformes.services.loyalty_service import LoyaltyService
from pos_uniformes.utils.qr_generator import QrGenerator

CARD_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "generated" / "client_cards"
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "assets" / "customer_card_template"
TEMPLATE_HTML_PATH = TEMPLATE_DIR / "customer-card.html"
TEMPLATE_CSS_PATH = TEMPLATE_DIR / "customer-card.css"
BRAND_DIR = TEMPLATE_DIR / "brand"
CARD_SIZE = (1080, 1350)
BACKGROUND_COLOR = "#F8F4EE"
SURFACE_COLOR = "#FFFDFC"
TEXT_PRIMARY = "#1F1A17"
TEXT_MUTED = "#7A716B"
DIVIDER_COLOR = "#E8DED4"
SPANISH_MONTHS = (
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)


@dataclass(frozen=True)
class CustomerCardRenderInput:
    business_name: str | None
    logo_path: str | None
    full_name: str
    customer_since: datetime
    loyalty_level: str
    level_label: str
    primary_color: str
    secondary_color: str
    qr_path: str


class CustomerCardService:
    """Genera la credencial PNG del cliente con un layout sobrio y vertical."""

    @staticmethod
    def default_logo_path() -> Path | None:
        configured_logo = CustomerCardService._configured_logo_path()
        if configured_logo is not None:
            return configured_logo
        candidates = [
            Path(__file__).resolve().parents[1] / "assets" / "logo.png",
            Path(__file__).resolve().parents[1] / "assets" / "logo.jpg",
            Path(__file__).resolve().parents[1] / "assets" / "logo.jpeg",
            TEMPLATE_DIR / "brand" / "store-logo.PNG",
            TEMPLATE_DIR / "brand" / "store-logo.png",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _configured_logo_path() -> Path | None:
        try:
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                if not (config.logo_path or "").strip():
                    return None
                candidate = Path(str(config.logo_path)).expanduser()
                if candidate.exists():
                    return candidate
        except Exception:
            return None
        return None

    @staticmethod
    def _business_name() -> str:
        try:
            with get_session() as session:
                config = BusinessSettingsService.get_or_create(session)
                if (config.nombre_negocio or "").strip():
                    return str(config.nombre_negocio).strip()
        except Exception:
            return "POS Uniformes"
        return "POS Uniformes"

    @staticmethod
    def install_logo_asset(source_path: str | Path) -> Path:
        source = Path(source_path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(f"No se encontro el logo: {source}")
        BRAND_DIR.mkdir(parents=True, exist_ok=True)
        normalized_suffix = source.suffix.lower() if source.suffix else ".png"
        target = BRAND_DIR / f"business-logo{normalized_suffix}"
        shutil.copy2(source, target)
        return target

    @staticmethod
    def output_dir() -> Path:
        CARD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return CARD_OUTPUT_DIR

    @staticmethod
    def preview_dir() -> Path:
        preview_dir = TEMPLATE_DIR / "preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        return preview_dir

    @classmethod
    def path_for_client(cls, cliente: Cliente) -> Path:
        return cls.output_dir() / f"{cliente.codigo_cliente}_card.png"

    @classmethod
    def demo_output_path(cls) -> Path:
        return cls.preview_dir() / "business-card-demo.png"

    @classmethod
    def exists_for_client(cls, cliente: Cliente) -> bool:
        return cls.path_for_client(cliente).exists()

    @classmethod
    def build_render_input(
        cls,
        cliente: Cliente,
        *,
        logo_path: str | Path | None = None,
    ) -> CustomerCardRenderInput:
        qr_path = QrGenerator.path_for_client(cliente)
        if not qr_path.exists():
            qr_path = QrGenerator.generate_for_client(cliente)
        visual = LoyaltyService.visual_spec(cliente.nivel_lealtad)
        customer_since = cliente.cliente_desde or cliente.created_at or datetime.now()
        return CustomerCardRenderInput(
            business_name=cls._business_name(),
            logo_path=str(logo_path) if logo_path else None,
            full_name=cliente.nombre,
            customer_since=customer_since,
            loyalty_level=visual.level.value,
            level_label=visual.label,
            primary_color=visual.primary_color,
            secondary_color=visual.secondary_color,
            qr_path=str(qr_path),
        )

    @classmethod
    def render_for_client(
        cls,
        cliente: Cliente,
        *,
        logo_path: str | Path | None = None,
    ) -> Path:
        resolved_logo = logo_path or cls.default_logo_path()
        payload = cls.build_render_input(cliente, logo_path=resolved_logo)
        output_path = cls.path_for_client(cliente)
        cls.render_card(payload, output_path)
        return output_path

    @classmethod
    def render_and_attach(
        cls,
        cliente: Cliente,
        *,
        logo_path: str | Path | None = None,
    ) -> Path:
        output_path = cls.render_for_client(cliente, logo_path=logo_path)
        cliente.card_image_path = str(output_path)
        return output_path

    @classmethod
    def render_card(cls, payload: CustomerCardRenderInput, output_path: str | Path) -> Path:
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
                    "No se pudo renderizar la credencial ni con HTML ni con PIL."
                ) from pil_error
            raise

    @classmethod
    def _render_card_from_html(cls, payload: CustomerCardRenderInput, output_path: Path) -> Path:
        template_html = TEMPLATE_HTML_PATH.read_text(encoding="utf-8")
        template_css = TEMPLATE_CSS_PATH.read_text(encoding="utf-8")
        html_document = cls._build_html_document(payload, template_html, template_css)
        browser_path = cls._resolve_browser_executable()
        if browser_path is None:
            raise FileNotFoundError("No se encontro un browser compatible para render headless.")

        with tempfile.TemporaryDirectory(prefix="customer-card-") as temp_dir:
            temp_html = Path(temp_dir) / "customer-card.html"
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
        payload: CustomerCardRenderInput,
        template_html: str,
        template_css: str,
    ) -> str:
        replacements = {
            "{{ primary_color }}": payload.primary_color,
            "{{ secondary_color }}": payload.secondary_color,
            "{{ name_size }}": cls._name_size_variant(payload.full_name),
            "{{ logo_path }}": cls._asset_src(
                payload.logo_path,
                fallback=cls._fallback_logo_data_uri(payload.primary_color, payload.business_name),
            ),
            "{{ full_name }}": escape(payload.full_name),
            "{{ customer_since }}": escape(cls._format_customer_since(payload.customer_since)),
            "{{ loyalty_level }}": escape(payload.loyalty_level),
            "{{ level_label }}": escape(payload.level_label),
            "{{ qr_path }}": cls._asset_src(payload.qr_path),
        }
        document = template_html.replace(
            '<link rel="stylesheet" href="./customer-card.css" />',
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
    def _format_customer_since(value: datetime) -> str:
        month_name = SPANISH_MONTHS[value.month]
        return f"{value.day} {month_name} {value.year}"

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

    @staticmethod
    def _fallback_logo_data_uri(primary_color: str, business_name: str | None = None) -> str:
        resolved_business_name = (business_name or CustomerCardService._business_name()).strip() or "POS Uniformes"
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" width="720" height="220" viewBox="0 0 720 220">
          <rect width="720" height="220" fill="white" fill-opacity="0"/>
          <text x="360" y="122" text-anchor="middle" font-family="Baskerville, serif" font-size="58" font-weight="700" fill="{primary_color}">{escape(resolved_business_name)}</text>
        </svg>
        """.strip()
        return f"data:image/svg+xml;charset=utf-8,{quote(svg)}"

    @staticmethod
    def _resolve_browser_executable() -> str | None:
        candidates = [
            Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path("/Applications/Arc.app/Contents/MacOS/Arc"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        for executable in ("brave-browser", "brave", "google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
            resolved = shutil.which(executable)
            if resolved:
                return resolved
        return None

    @classmethod
    def _render_card_with_pil(cls, payload: CustomerCardRenderInput, target: Path) -> Path:
        canvas = Image.new("RGBA", CARD_SIZE, BACKGROUND_COLOR)
        draw = ImageDraw.Draw(canvas)

        cls._draw_background_pattern(canvas, payload.primary_color)
        cls._draw_surface_panel(draw)
        cls._draw_top_band(draw, payload.primary_color)
        cls._draw_logo_block(canvas, payload.logo_path, payload.primary_color, payload.business_name)
        cls._draw_title_block(draw, payload)
        cls._draw_level_badge(draw, payload)
        cls._draw_qr_block(canvas, payload)
        cls._draw_footer(draw, payload)

        canvas.convert("RGB").save(target, format="PNG", optimize=True)
        return target

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
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
    def _draw_background_pattern(cls, canvas: Image.Image, primary_color: str) -> None:
        pattern = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
        pattern_draw = ImageDraw.Draw(pattern)
        rgba = cls._hex_to_rgba(primary_color, 22)
        for offset_y in range(110, CARD_SIZE[1], 240):
            for offset_x in range(80, CARD_SIZE[0], 220):
                pattern_draw.rounded_rectangle(
                    (offset_x, offset_y, offset_x + 88, offset_y + 88),
                    radius=24,
                    outline=rgba,
                    width=2,
                )
                pattern_draw.text(
                    (offset_x + 20, offset_y + 10),
                    "M",
                    font=cls._font(42, bold=True),
                    fill=rgba,
                )
        pattern = pattern.filter(ImageFilter.GaussianBlur(radius=0.4))
        canvas.alpha_composite(pattern)

    @staticmethod
    def _draw_surface_panel(draw: ImageDraw.ImageDraw) -> None:
        draw.rounded_rectangle(
            (64, 74, 1016, 1274),
            radius=40,
            fill=SURFACE_COLOR,
            outline=DIVIDER_COLOR,
            width=2,
        )

    @classmethod
    def _draw_top_band(cls, draw: ImageDraw.ImageDraw, primary_color: str) -> None:
        draw.rounded_rectangle(
            (64, 74, 1016, 148),
            radius=40,
            fill=primary_color,
        )
        draw.rounded_rectangle(
            (64, 122, 1016, 148),
            radius=20,
            fill=primary_color,
        )

    @classmethod
    def _draw_logo_block(
        cls,
        canvas: Image.Image,
        logo_path: str | None,
        primary_color: str,
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
            (business_name or cls._business_name()).strip() or "POS Uniformes",
            anchor="mm",
            font=cls._font(42, bold=True),
            fill=primary_color,
        )
        draw.text(
            (CARD_SIZE[0] // 2, 258),
            "Credencial de cliente",
            anchor="mm",
            font=cls._font(24),
            fill=TEXT_MUTED,
        )

    @classmethod
    def _draw_title_block(cls, draw: ImageDraw.ImageDraw, payload: CustomerCardRenderInput) -> None:
        title_font_size = cls._title_font_size(payload.full_name)
        draw.text(
            (120, 352),
            payload.full_name,
            font=cls._font(title_font_size, bold=True),
            fill=TEXT_PRIMARY,
        )
        draw.text(
            (120, 440),
            f"Cliente desde {payload.customer_since.strftime('%d/%m/%Y')}",
            font=cls._font(28),
            fill=TEXT_MUTED,
        )
        draw.line((120, 490, 960, 490), fill=DIVIDER_COLOR, width=2)

    @classmethod
    def _title_font_size(cls, full_name: str) -> int:
        variant = cls._name_size_variant(full_name)
        if variant == "dense":
            return 42
        if variant == "compact":
            return 50
        if variant == "medium":
            return 58
        return 64

    @classmethod
    def _draw_level_badge(cls, draw: ImageDraw.ImageDraw, payload: CustomerCardRenderInput) -> None:
        badge_fill = cls._hex_to_rgba(payload.secondary_color, 255)
        badge_outline = cls._hex_to_rgba(payload.primary_color, 255)
        draw.rounded_rectangle(
            (120, 540, 430, 620),
            radius=26,
            fill=badge_fill,
            outline=badge_outline,
            width=2,
        )
        draw.text(
            (150, 557),
            "Nivel de lealtad",
            font=cls._font(20),
            fill=payload.primary_color,
        )
        draw.text(
            (150, 582),
            payload.level_label.upper(),
            font=cls._font(30, bold=True),
            fill=payload.primary_color,
        )

    @classmethod
    def _draw_qr_block(cls, canvas: Image.Image, payload: CustomerCardRenderInput) -> None:
        qr_image = Image.open(payload.qr_path).convert("RGBA")
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
        canvas.alpha_composite(qr_panel, (330, 640))

    @classmethod
    def _draw_footer(cls, draw: ImageDraw.ImageDraw, payload: CustomerCardRenderInput) -> None:
        draw.text(
            (CARD_SIZE[0] // 2, 1100),
            "Presenta este codigo al visitarnos",
            anchor="mm",
            font=cls._font(24),
            fill=TEXT_MUTED,
        )
        draw.text(
            (CARD_SIZE[0] // 2, 1140),
            payload.loyalty_level,
            anchor="mm",
            font=cls._font(22, bold=True),
            fill=payload.primary_color,
        )
        draw.text(
            (CARD_SIZE[0] // 2, 1190),
            "Imagen lista para compartir por WhatsApp",
            anchor="mm",
            font=cls._font(20),
            fill=TEXT_MUTED,
        )

    @staticmethod
    def _hex_to_rgba(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
        cleaned = hex_color.lstrip("#")
        if len(cleaned) != 6:
            return (58, 58, 58, alpha)
        return (
            int(cleaned[0:2], 16),
            int(cleaned[2:4], 16),
            int(cleaned[4:6], 16),
            alpha,
        )
