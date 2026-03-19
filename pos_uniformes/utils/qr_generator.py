"""Generacion de codigos QR para presentaciones y clientes."""

from __future__ import annotations

from pathlib import Path
import re
import unicodedata

from PIL import Image, ImageDraw
import qrcode
from qrcode.constants import ERROR_CORRECT_H

from pos_uniformes.database.models import Cliente, Variante

QR_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "generated" / "qrs"
CLIENT_QR_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "generated" / "client_qrs"
QR_ICON_DIR = Path(__file__).resolve().parents[1] / "assets" / "qr_icons"


class QrGenerator:
    """Genera imagenes QR PNG para identificadores del sistema."""

    @staticmethod
    def output_dir() -> Path:
        QR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return QR_OUTPUT_DIR

    @staticmethod
    def client_output_dir() -> Path:
        CLIENT_QR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return CLIENT_QR_OUTPUT_DIR

    @classmethod
    def path_for_variant(cls, variante: Variante) -> Path:
        return cls.output_dir() / f"{variante.sku}.png"

    @classmethod
    def exists_for_variant(cls, variante: Variante) -> bool:
        return cls.path_for_variant(variante).exists()

    @classmethod
    def generate_for_variant(cls, variante: Variante) -> Path:
        output_path = cls.path_for_variant(variante)
        qr_image = cls._build_qr_image(str(variante.sku))
        icon_path = cls.icon_path_for_variant(variante)
        if icon_path is not None:
            qr_image = cls._embed_center_icon(qr_image, icon_path)
        qr_image.save(output_path)
        return output_path

    @classmethod
    def sync_after_sku_change(cls, old_sku: str, variante: Variante) -> Path:
        old_path = cls.output_dir() / f"{old_sku}.png"
        new_path = cls.path_for_variant(variante)
        if old_path != new_path and old_path.exists():
            old_path.unlink()
        return cls.generate_for_variant(variante)

    @classmethod
    def generate_many(cls, variantes: list[Variante]) -> list[Path]:
        return [cls.generate_for_variant(variante) for variante in variantes]

    @classmethod
    def path_for_client(cls, cliente: Cliente) -> Path:
        return cls.client_output_dir() / f"{cliente.codigo_cliente}.png"

    @classmethod
    def exists_for_client(cls, cliente: Cliente) -> bool:
        return cls.path_for_client(cliente).exists()

    @classmethod
    def generate_for_client(cls, cliente: Cliente) -> Path:
        output_path = cls.path_for_client(cliente)
        qr_image = cls._build_qr_image(str(cliente.codigo_cliente))
        qr_image.save(output_path)
        return output_path

    @staticmethod
    def _build_qr_image(payload: str) -> Image.Image:
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_H,
            box_size=12,
            border=3,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    @classmethod
    def icon_path_for_variant(cls, variante: Variante) -> Path | None:
        if not QR_ICON_DIR.exists():
            return None

        available_icons = cls._available_icon_map()
        if not available_icons:
            return None

        for candidate in cls._variant_icon_candidates(variante):
            normalized_candidate = cls._normalize_icon_key(candidate)
            if not normalized_candidate:
                continue
            exact_icon = available_icons.get(normalized_candidate)
            if exact_icon is not None:
                return exact_icon

            for icon_key in sorted(available_icons.keys(), key=len, reverse=True):
                if icon_key == "default":
                    continue
                if icon_key in normalized_candidate:
                    return available_icons[icon_key]

        return available_icons.get("default")

    @classmethod
    def _available_icon_map(cls) -> dict[str, Path]:
        icon_map: dict[str, Path] = {}
        for icon_path in sorted(QR_ICON_DIR.glob("*.png")):
            icon_map[cls._normalize_icon_key(icon_path.stem)] = icon_path
        return icon_map

    @classmethod
    def _variant_icon_candidates(cls, variante: Variante) -> list[str]:
        producto = getattr(variante, "producto", None)
        if producto is None:
            return [str(getattr(variante, "sku", "") or "")]

        candidates = [
            getattr(getattr(producto, "tipo_prenda", None), "nombre", ""),
            getattr(getattr(producto, "categoria", None), "nombre", ""),
            getattr(getattr(producto, "tipo_pieza", None), "nombre", ""),
            getattr(getattr(producto, "atributo", None), "nombre", ""),
            getattr(producto, "nombre_base", ""),
            getattr(producto, "nombre", ""),
        ]
        return [str(candidate).strip() for candidate in candidates if str(candidate or "").strip()]

    @staticmethod
    def _normalize_icon_key(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        normalized = normalized.encode("ascii", "ignore").decode("ascii")
        normalized = normalized.casefold()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        return normalized.strip("_")

    @staticmethod
    def _embed_center_icon(qr_image: Image.Image, icon_path: Path) -> Image.Image:
        qr_canvas = qr_image.convert("RGBA")
        icon_image = Image.open(icon_path).convert("RGBA")
        qr_side = min(qr_canvas.size)
        icon_side = max(56, int(qr_side * 0.18))
        badge_side = int(icon_side * 1.42)
        icon_image = icon_image.resize((icon_side, icon_side), Image.Resampling.LANCZOS)

        badge = Image.new("RGBA", (badge_side, badge_side), (255, 255, 255, 0))
        badge_draw = ImageDraw.Draw(badge)
        badge_draw.rounded_rectangle(
            (0, 0, badge_side - 1, badge_side - 1),
            radius=max(14, badge_side // 5),
            fill=(255, 255, 255, 245),
            outline=(230, 222, 210, 255),
            width=max(2, badge_side // 24),
        )
        badge_x = (badge_side - icon_side) // 2
        badge_y = (badge_side - icon_side) // 2
        badge.alpha_composite(icon_image, (badge_x, badge_y))

        center_x = (qr_canvas.width - badge_side) // 2
        center_y = (qr_canvas.height - badge_side) // 2
        qr_canvas.alpha_composite(badge, (center_x, center_y))
        return qr_canvas
