"""Importador de catalogo legacy desde SQLite hacia PostgreSQL."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import json
import re
import sqlite3
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pos_uniformes.database.models import (
    AtributoProducto,
    Categoria,
    Escuela,
    ImportacionCatalogo,
    ImportacionCatalogoFila,
    ImportacionCatalogoIncidencia,
    Marca,
    MovimientoInventario,
    NivelEducativo,
    Producto,
    ProductoAsset,
    SkuSequence,
    TipoMovimientoInventario,
    TipoPieza,
    TipoPrenda,
    Variante,
)

SIZE_PATTERN = re.compile(r"^(?P<base>.+?)\s+Talla\s+(?P<size>.+)$", re.IGNORECASE)
LOCAL_TIMEZONE = ZoneInfo("America/Mexico_City")
LEGACY_SOURCE = "productos.db"
DEFAULT_BRAND = "Sin marca"
DEFAULT_CATEGORY = "Sin categoria"
DEFAULT_COLOR = "Sin color"


@dataclass(frozen=True)
class LegacyProductRow:
    sku: str
    nombre: str
    tipo_prenda: str
    tipo_pieza: str
    color: str
    talla: str
    marca: str
    atributo: str
    nivel_educativo: str
    genero: str
    escuela_id: int | None
    qr_path: str
    label_split_path: str
    image_path: str
    ubicacion: str
    escudo: str
    inventario: int
    precio: Decimal
    last_modified: datetime | None


@dataclass(frozen=True)
class ImportSummary:
    products_read: int
    rows_skipped_existing: int
    categories_created: int
    brands_created: int
    schools_created: int
    garment_types_created: int
    piece_types_created: int
    education_levels_created: int
    attributes_created: int
    product_families_created: int
    variants_created: int
    assets_created: int
    stock_movements_created: int
    duplicated_variant_fallbacks: int
    max_legacy_sku: int
    report_path: Path


class LegacyProductsImporter:
    """Importa productos legacy respetando SKU y metadata etiquetada."""

    def __init__(
        self,
        sqlite_path: Path,
        report_dir: Path | None = None,
        import_mode: str = "initial",
    ) -> None:
        self.sqlite_path = sqlite_path.expanduser().resolve()
        self.report_dir = (report_dir or Path(__file__).resolve().parents[1] / "exports" / "imports").resolve()
        normalized_mode = str(import_mode or "initial").strip().lower()
        if normalized_mode not in {"initial", "missing_only"}:
            raise ValueError("import_mode debe ser 'initial' o 'missing_only'.")
        self.import_mode = normalized_mode
        self._schools_by_legacy_id: dict[int, str] = {}
        self._display_name_counts: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._stats: dict[str, int] = {
            "rows_skipped_existing": 0,
            "categories_created": 0,
            "brands_created": 0,
            "schools_created": 0,
            "garment_types_created": 0,
            "piece_types_created": 0,
            "education_levels_created": 0,
            "attributes_created": 0,
            "product_families_created": 0,
            "variants_created": 0,
            "assets_created": 0,
            "stock_movements_created": 0,
            "duplicated_variant_fallbacks": 0,
        }

    def run(self, session: Session) -> ImportSummary:
        if self.import_mode == "initial":
            self._assert_safe_destination(session)

        source_rows = self._read_legacy_rows()
        self._load_legacy_schools()
        rows = source_rows
        if self.import_mode == "missing_only":
            rows = self._filter_rows_by_missing_skus(session, source_rows)
        skipped_existing = len(source_rows) - len(rows)
        self._stats["rows_skipped_existing"] = skipped_existing

        observation = "Importacion inicial desde SQLite legacy hacia POS Uniformes."
        if self.import_mode == "missing_only":
            observation = (
                "Importacion delta desde SQLite legacy hacia POS Uniformes. "
                f"Se omitieron {skipped_existing} SKUs ya existentes."
            )
        import_batch = ImportacionCatalogo(
            fuente_nombre=LEGACY_SOURCE,
            fuente_ruta=str(self.sqlite_path),
            observaciones=observation,
            filas_leidas=len(source_rows),
        )
        session.add(import_batch)
        session.flush()

        categories: dict[str, Categoria] = {}
        brands: dict[str, Marca] = {}
        schools: dict[str, Escuela] = {}
        garment_types: dict[str, TipoPrenda] = {}
        piece_types: dict[str, TipoPieza] = {}
        education_levels: dict[str, NivelEducativo] = {}
        attributes: dict[str, AtributoProducto] = {}
        products: dict[tuple[str, str, str | None, str | None, str | None, str | None, str | None, str | None], Producto] = {}
        variant_keys: set[tuple[int, str, str]] = set()
        if self.import_mode == "missing_only":
            self._prime_existing_catalog_state(
                session,
                products=products,
                variant_keys=variant_keys,
            )
        max_legacy_sku = max((self._parse_legacy_sku_number(row.sku) for row in source_rows), default=0)

        for row in rows:
            base_name, parsed_size = self._split_name_and_size(row.nombre, row.talla)
            size_value = parsed_size or row.talla
            category_name = row.tipo_prenda or DEFAULT_CATEGORY
            brand_name = row.marca or DEFAULT_BRAND
            school_name = self._schools_by_legacy_id.get(row.escuela_id) if row.escuela_id is not None else None
            color_value = row.color or DEFAULT_COLOR

            category = categories.get(category_name)
            if category is None:
                category = self._get_or_create_categoria(session, category_name)
                categories[category_name] = category
            brand = brands.get(brand_name)
            if brand is None:
                brand = self._get_or_create_marca(session, brand_name)
                brands[brand_name] = brand
            school = None
            if school_name:
                school = schools.get(school_name)
                if school is None:
                    school = self._get_or_create_escuela(session, school_name)
                    schools[school_name] = school
            garment_type = None
            if row.tipo_prenda:
                garment_type = garment_types.get(row.tipo_prenda)
                if garment_type is None:
                    garment_type = self._get_or_create_tipo_prenda(session, row.tipo_prenda)
                    garment_types[row.tipo_prenda] = garment_type
            piece_type = None
            if row.tipo_pieza:
                piece_type = piece_types.get(row.tipo_pieza)
                if piece_type is None:
                    piece_type = self._get_or_create_tipo_pieza(session, row.tipo_pieza)
                    piece_types[row.tipo_pieza] = piece_type
            education_level = None
            if row.nivel_educativo:
                education_level = education_levels.get(row.nivel_educativo)
                if education_level is None:
                    education_level = self._get_or_create_nivel_educativo(session, row.nivel_educativo)
                    education_levels[row.nivel_educativo] = education_level
            attribute = None
            if row.atributo:
                attribute = attributes.get(row.atributo)
                if attribute is None:
                    attribute = self._get_or_create_atributo(session, row.atributo)
                    attributes[row.atributo] = attribute

            family_key = (
                base_name,
                brand.nombre,
                school.nombre if school else None,
                garment_type.nombre if garment_type else None,
                piece_type.nombre if piece_type else None,
                education_level.nombre if education_level else None,
                attribute.nombre if attribute else None,
                row.genero or None,
            )
            family_key_serialized = self._serialize_family_key(family_key)
            product = products.get(family_key)
            if product is None:
                display_name = self._build_product_display_name(
                    base_name=base_name,
                    brand_name=brand.nombre,
                    school_name=school.nombre if school else None,
                    garment_type_name=garment_type.nombre if garment_type else None,
                    piece_type_name=piece_type.nombre if piece_type else None,
                )
                product = Producto(
                    categoria=category,
                    marca=brand,
                    nombre=display_name,
                    nombre_base=base_name,
                    escuela=school,
                    tipo_prenda=garment_type,
                    tipo_pieza=piece_type,
                    nivel_educativo=education_level,
                    atributo=attribute,
                    genero=row.genero or None,
                    escudo=row.escudo or None,
                    ubicacion=row.ubicacion or None,
                    descripcion=f"Importado desde {LEGACY_SOURCE}.",
                )
                session.add(product)
                session.flush()
                products[family_key] = product
                self._stats["product_families_created"] += 1

            variant_key = (int(product.id), size_value, color_value)
            fallback_product = False
            duplicate_issue_payload: dict[str, object] | None = None
            if variant_key in variant_keys:
                product = self._create_duplicate_product_fallback(
                    session=session,
                    original=product,
                    base_name=base_name,
                    brand=brand,
                    category=category,
                    school=school,
                    garment_type=garment_type,
                    piece_type=piece_type,
                    education_level=education_level,
                    attribute=attribute,
                    genero=row.genero or None,
                    escudo=row.escudo or None,
                    ubicacion=row.ubicacion or None,
                )
                variant_key = (int(product.id), size_value, color_value)
                fallback_product = True
                duplicate_issue_payload = {
                    "sku": row.sku,
                    "nombre_legacy": row.nombre,
                    "nombre_base": base_name,
                    "talla": size_value,
                    "color": color_value,
                    "clave_familia": family_key_serialized,
                    "producto_generado": product.nombre,
                }
                self._stats["duplicated_variant_fallbacks"] += 1

            variant = Variante(
                producto=product,
                sku=row.sku,
                talla=size_value,
                color=color_value,
                nombre_legacy=row.nombre,
                origen_legacy=True,
                legacy_last_modified=row.last_modified,
                precio_venta=row.precio,
                costo_referencia=None,
                stock_actual=0,
                activo=True,
            )
            session.add(variant)
            session.flush()
            variant_keys.add(variant_key)
            self._stats["variants_created"] += 1

            assets_created = self._create_variant_assets(session, variant, row)
            self._stats["assets_created"] += assets_created
            import_row = ImportacionCatalogoFila(
                importacion=import_batch,
                legacy_sku=row.sku,
                legacy_nombre=row.nombre,
                legacy_nombre_base=base_name,
                legacy_talla=size_value,
                legacy_color=color_value,
                legacy_precio=row.precio,
                legacy_inventario=row.inventario,
                legacy_last_modified=row.last_modified,
                producto_id=product.id,
                variante_id=variant.id,
                producto_fallback=fallback_product,
                clave_familia=family_key_serialized,
            )
            session.add(import_row)
            session.flush()
            if duplicate_issue_payload is not None:
                issue = ImportacionCatalogoIncidencia(
                    importacion=import_batch,
                    fila_id=import_row.id,
                    producto_id=product.id,
                    variante_id=variant.id,
                    severidad="WARNING",
                    tipo="DUPLICATE_VARIANT_FALLBACK",
                    legacy_sku=row.sku,
                    descripcion=(
                        "Se detecto una colision de talla/color dentro de la misma familia y se genero "
                        "un producto fallback para conservar el SKU legacy."
                    ),
                    detalle_json=json.dumps(duplicate_issue_payload, ensure_ascii=True, sort_keys=True),
                )
                session.add(issue)

            if row.inventario > 0:
                movement = MovimientoInventario(
                    variante=variant,
                    tipo_movimiento=TipoMovimientoInventario.AJUSTE_ENTRADA,
                    cantidad=row.inventario,
                    stock_anterior=0,
                    stock_posterior=row.inventario,
                    referencia="LEGACY-IMPORT",
                    observacion=f"Stock inicial importado desde {LEGACY_SOURCE}.",
                    creado_por="SYSTEM",
                )
                variant.stock_actual = row.inventario
                session.add(movement)
                session.add(variant)
                self._stats["stock_movements_created"] += 1

        self._sync_sku_sequence(session, max_legacy_sku)
        report_path = self._write_report(rows_count=len(source_rows), max_legacy_sku=max_legacy_sku)
        import_batch.familias_creadas = self._stats["product_families_created"]
        import_batch.variantes_creadas = self._stats["variants_created"]
        import_batch.assets_creados = self._stats["assets_created"]
        import_batch.movimientos_stock_creados = self._stats["stock_movements_created"]
        import_batch.duplicados_fallback = self._stats["duplicated_variant_fallbacks"]
        import_batch.max_sku_legacy = max_legacy_sku
        import_batch.reporte_ruta = str(report_path)
        import_batch.finished_at = datetime.now(tz=LOCAL_TIMEZONE)
        session.add(import_batch)
        session.commit()
        return ImportSummary(
            products_read=len(source_rows),
            rows_skipped_existing=skipped_existing,
            categories_created=self._stats["categories_created"],
            brands_created=self._stats["brands_created"],
            schools_created=self._stats["schools_created"],
            garment_types_created=self._stats["garment_types_created"],
            piece_types_created=self._stats["piece_types_created"],
            education_levels_created=self._stats["education_levels_created"],
            attributes_created=self._stats["attributes_created"],
            product_families_created=self._stats["product_families_created"],
            variants_created=self._stats["variants_created"],
            assets_created=self._stats["assets_created"],
            stock_movements_created=self._stats["stock_movements_created"],
            duplicated_variant_fallbacks=self._stats["duplicated_variant_fallbacks"],
            max_legacy_sku=max_legacy_sku,
            report_path=report_path,
        )

    def _assert_safe_destination(self, session: Session) -> None:
        existing_variants = session.scalar(select(Variante).limit(1))
        existing_products = session.scalar(select(Producto).limit(1))
        if existing_variants is not None or existing_products is not None:
            raise ValueError(
                "La base destino ya tiene catalogo cargado. Importa solo sobre una base vacia para evitar duplicados."
            )

    def _load_legacy_schools(self) -> None:
        connection = sqlite3.connect(str(self.sqlite_path))
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute("SELECT id, nombre FROM escuelas ORDER BY id").fetchall()
        finally:
            connection.close()

        self._schools_by_legacy_id = {int(row["id"]): str(row["nombre"]).strip() for row in rows if row["nombre"]}

    def _read_legacy_rows(self) -> list[LegacyProductRow]:
        connection = sqlite3.connect(str(self.sqlite_path))
        connection.row_factory = sqlite3.Row
        try:
            raw_rows = connection.execute(
                """
                SELECT
                    sku,
                    nombre,
                    tipo_prenda,
                    tipo_pieza,
                    color,
                    talla,
                    marca,
                    atributo,
                    nivel_educativo,
                    genero,
                    escuela_id,
                    qr_path,
                    label_split_path,
                    image_path,
                    ubicacion,
                    escudo,
                    inventario,
                    precio,
                    last_modified
                FROM productos
                ORDER BY sku
                """
            ).fetchall()
        finally:
            connection.close()

        return [
            LegacyProductRow(
                sku=self._clean_text(row["sku"]).upper(),
                nombre=self._clean_text(row["nombre"]),
                tipo_prenda=self._clean_text(row["tipo_prenda"]),
                tipo_pieza=self._clean_text(row["tipo_pieza"]),
                color=self._clean_text(row["color"]),
                talla=self._clean_text(row["talla"]),
                marca=self._clean_text(row["marca"]),
                atributo=self._clean_text(row["atributo"]),
                nivel_educativo=self._clean_text(row["nivel_educativo"]),
                genero=self._clean_text(row["genero"]),
                escuela_id=int(row["escuela_id"]) if row["escuela_id"] is not None else None,
                qr_path=self._clean_text(row["qr_path"]),
                label_split_path=self._clean_text(row["label_split_path"]),
                image_path=self._clean_text(row["image_path"]),
                ubicacion=self._clean_text(row["ubicacion"]),
                escudo=self._clean_text(row["escudo"]),
                inventario=int(row["inventario"] or 0),
                precio=Decimal(str(row["precio"] or 0)).quantize(Decimal("0.01")),
                last_modified=self._parse_datetime(row["last_modified"]),
            )
            for row in raw_rows
        ]

    @staticmethod
    def _filter_rows_by_missing_skus(session: Session, rows: list[LegacyProductRow]) -> list[LegacyProductRow]:
        existing_skus = {sku for sku in session.scalars(select(Variante.sku))}
        return [row for row in rows if row.sku not in existing_skus]

    def _prime_existing_catalog_state(
        self,
        session: Session,
        *,
        products: dict[tuple[str, str, str | None, str | None, str | None, str | None, str | None, str | None], Producto],
        variant_keys: set[tuple[int, str, str]],
    ) -> None:
        existing_products = session.scalars(
            select(Producto).options(
                selectinload(Producto.marca),
                selectinload(Producto.escuela),
                selectinload(Producto.tipo_prenda),
                selectinload(Producto.tipo_pieza),
                selectinload(Producto.nivel_educativo),
                selectinload(Producto.atributo),
                selectinload(Producto.variantes),
            )
        ).all()

        for product in existing_products:
            brand_name = product.marca.nombre
            school_name = product.escuela.nombre if product.escuela else None
            garment_type_name = product.tipo_prenda.nombre if product.tipo_prenda else None
            piece_type_name = product.tipo_pieza.nombre if product.tipo_pieza else None
            education_level_name = product.nivel_educativo.nombre if product.nivel_educativo else None
            attribute_name = product.atributo.nombre if product.atributo else None
            family_key = (
                product.nombre_base,
                brand_name,
                school_name,
                garment_type_name,
                piece_type_name,
                education_level_name,
                attribute_name,
                product.genero or None,
            )
            products.setdefault(family_key, product)
            self._display_name_counts[(brand_name, product.nombre)] += 1
            for variant in product.variantes:
                variant_keys.add((int(product.id), variant.talla, variant.color))

    @staticmethod
    def _clean_text(value: object | None) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _parse_datetime(value: object | None) -> datetime | None:
        if value in {None, ""}:
            return None
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=LOCAL_TIMEZONE)
        return parsed

    @staticmethod
    def _split_name_and_size(nombre: str, fallback_size: str) -> tuple[str, str]:
        match = SIZE_PATTERN.match(nombre.strip())
        if not match:
            return nombre.strip(), fallback_size.strip()
        return match.group("base").strip(), match.group("size").strip()

    @staticmethod
    def _parse_legacy_sku_number(sku: str) -> int:
        if sku.startswith("SKU") and sku[3:].isdigit():
            return int(sku[3:])
        return 0

    @staticmethod
    def _serialize_family_key(family_key: tuple[str, str, str | None, str | None, str | None, str | None, str | None, str | None]) -> str:
        return " | ".join(part or "-" for part in family_key)

    def _build_product_display_name(
        self,
        base_name: str,
        brand_name: str,
        school_name: str | None,
        garment_type_name: str | None,
        piece_type_name: str | None,
    ) -> str:
        suffix_parts = [part for part in (school_name, garment_type_name, piece_type_name) if part]
        display_name = f"{base_name} | {' | '.join(suffix_parts)}" if suffix_parts else base_name
        dedupe_key = (brand_name, display_name)
        count = self._display_name_counts[dedupe_key]
        self._display_name_counts[dedupe_key] += 1
        if count == 0:
            return display_name
        return f"{display_name} #{count + 1}"

    def _create_duplicate_product_fallback(
        self,
        session: Session,
        original: Producto,
        base_name: str,
        brand: Marca,
        category: Categoria,
        school: Escuela | None,
        garment_type: TipoPrenda | None,
        piece_type: TipoPieza | None,
        education_level: NivelEducativo | None,
        attribute: AtributoProducto | None,
        genero: str | None,
        escudo: str | None,
        ubicacion: str | None,
    ) -> Producto:
        display_name = self._build_product_display_name(
            base_name=base_name,
            brand_name=brand.nombre,
            school_name=school.nombre if school else None,
            garment_type_name=garment_type.nombre if garment_type else None,
            piece_type_name=piece_type.nombre if piece_type else None,
        )
        duplicate = Producto(
            categoria=category,
            marca=brand,
            nombre=display_name,
            nombre_base=base_name,
            escuela=school,
            tipo_prenda=garment_type,
            tipo_pieza=piece_type,
            nivel_educativo=education_level,
            atributo=attribute,
            genero=genero,
            escudo=escudo,
            ubicacion=ubicacion,
            descripcion=original.descripcion,
        )
        session.add(duplicate)
        session.flush()
        self._stats["product_families_created"] += 1
        return duplicate

    def _create_variant_assets(self, session: Session, variante: Variante, row: LegacyProductRow) -> int:
        count = 0
        for asset_type, path_value in (
            ("QR", row.qr_path),
            ("LABEL_SPLIT", row.label_split_path),
            ("IMAGE", row.image_path),
        ):
            if not path_value:
                continue
            asset = ProductoAsset(
                variante=variante,
                tipo=asset_type,
                ruta=path_value,
                es_legacy=True,
            )
            session.add(asset)
            count += 1
        return count

    def _sync_sku_sequence(self, session: Session, max_legacy_sku: int) -> None:
        sequence = session.scalar(select(SkuSequence).where(SkuSequence.codigo == "VARIANTE"))
        if sequence is None:
            sequence = SkuSequence(codigo="VARIANTE", prefijo="SKU", padding=6, ultimo_numero=max_legacy_sku)
        else:
            sequence.ultimo_numero = max(sequence.ultimo_numero, max_legacy_sku)
        session.add(sequence)
        session.flush()

    def _write_report(self, rows_count: int, max_legacy_sku: int) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_dir = self.report_dir / timestamp
        target_dir.mkdir(parents=True, exist_ok=True)
        report_path = target_dir / "legacy_catalog_import_summary.json"
        payload = {
            "source": str(self.sqlite_path),
            "rows_read": rows_count,
            "max_legacy_sku": max_legacy_sku,
            **self._stats,
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        return report_path

    def _get_or_create_categoria(self, session: Session, nombre: str) -> Categoria:
        existing = session.scalar(select(Categoria).where(Categoria.nombre == nombre))
        if existing is not None:
            return existing
        category = Categoria(nombre=nombre, descripcion="Importado desde catalogo legacy.")
        session.add(category)
        session.flush()
        self._stats["categories_created"] += 1
        return category

    def _get_or_create_marca(self, session: Session, nombre: str) -> Marca:
        existing = session.scalar(select(Marca).where(Marca.nombre == nombre))
        if existing is not None:
            return existing
        brand = Marca(nombre=nombre, descripcion="Importada desde catalogo legacy.")
        session.add(brand)
        session.flush()
        self._stats["brands_created"] += 1
        return brand

    def _get_or_create_escuela(self, session: Session, nombre: str) -> Escuela:
        existing = session.scalar(select(Escuela).where(Escuela.nombre == nombre))
        if existing is not None:
            return existing
        school = Escuela(nombre=nombre)
        session.add(school)
        session.flush()
        self._stats["schools_created"] += 1
        return school

    def _get_or_create_tipo_prenda(self, session: Session, nombre: str) -> TipoPrenda:
        existing = session.scalar(select(TipoPrenda).where(TipoPrenda.nombre == nombre))
        if existing is not None:
            return existing
        garment_type = TipoPrenda(nombre=nombre)
        session.add(garment_type)
        session.flush()
        self._stats["garment_types_created"] += 1
        return garment_type

    def _get_or_create_tipo_pieza(self, session: Session, nombre: str) -> TipoPieza:
        existing = session.scalar(select(TipoPieza).where(TipoPieza.nombre == nombre))
        if existing is not None:
            return existing
        piece_type = TipoPieza(nombre=nombre)
        session.add(piece_type)
        session.flush()
        self._stats["piece_types_created"] += 1
        return piece_type

    def _get_or_create_nivel_educativo(self, session: Session, nombre: str) -> NivelEducativo:
        existing = session.scalar(select(NivelEducativo).where(NivelEducativo.nombre == nombre))
        if existing is not None:
            return existing
        level = NivelEducativo(nombre=nombre)
        session.add(level)
        session.flush()
        self._stats["education_levels_created"] += 1
        return level

    def _get_or_create_atributo(self, session: Session, nombre: str) -> AtributoProducto:
        existing = session.scalar(select(AtributoProducto).where(AtributoProducto.nombre == nombre))
        if existing is not None:
            return existing
        attribute = AtributoProducto(nombre=nombre)
        session.add(attribute)
        session.flush()
        self._stats["attributes_created"] += 1
        return attribute
