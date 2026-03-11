"""Generacion de codigos QR para presentaciones y clientes."""

from __future__ import annotations

from pathlib import Path

import qrcode

from pos_uniformes.database.models import Cliente, Variante

QR_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "generated" / "qrs"
CLIENT_QR_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "generated" / "client_qrs"


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
        qr_image = qrcode.make(variante.sku)
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
        qr_image = qrcode.make(cliente.codigo_cliente)
        qr_image.save(output_path)
        return output_path
