"""Generacion basica de etiquetas normal y split para presentaciones."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

from PIL import Image, ImageDraw, ImageFont

from pos_uniformes.database.models import Variante
from pos_uniformes.utils.inventory_label_content_helper import resolve_inventory_label_profile
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
QR_MODULO_DK1221 = 5  # puntos por módulo en la cuadrada: 0.42 mm a 300 dpi (probado en la tienda)
QR_SIZE_DK1221 = 21 * QR_MODULO_DK1221  # 105: un QR de 21 módulos, sin marco

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
class SmallLabelContent:
    """Lo que dicen las etiquetas chicas (tira de 4, rollo continuo y cuadrada)."""

    encabezado: str     # la escuela (y el color), en chico; vacío en ropa normal
    nombre: str         # en negrita
    talla: str          # en caja negra; vacío si es unitalla en ropa normal
    precio: str         # "$179"; vacío en uniformes


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
            cls._render_dk1221(variante, qr_path, output_path, show_price=show_price)
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
        """Quita del nombre de la prenda el nombre de su escuela, que ya va arriba.

        Se compara palabra por palabra, sin acentos, mayúsculas ni signos: la
        escuela «Álvaro Obregón (El Carretón)» aparece en sus prendas como
        «…Álvaro Obregón El Carretón», sin paréntesis, y comparando el texto
        tal cual no se encontraba — la etiqueta repetía la escuela (2026-11-05).
        """
        import re
        import unicodedata

        def llave(palabra: str) -> str:
            sin = unicodedata.normalize("NFKD", palabra)
            return re.sub(r"[^a-z0-9]", "", "".join(c for c in sin if not unicodedata.combining(c)).casefold())

        palabras = str(titulo or "").split()
        llaves = [llave(p) for p in palabras]
        buscadas = [k for k in (llave(p) for p in str(escuela or "").split()) if k]
        if not buscadas or len(buscadas) > len(palabras):
            return titulo
        # Todas las apariciones: hay prendas con la escuela escrita dos veces
        # («Pants 2pz Deportivo Estv 154 ESTV 154»).
        i = len(palabras) - len(buscadas)
        while i >= 0:
            if llaves[i:i + len(buscadas)] == buscadas:
                del palabras[i:i + len(buscadas)], llaves[i:i + len(buscadas)]
                i = min(i, len(palabras) - len(buscadas))
            else:
                i -= 1
        limpio = " ".join(palabras).strip(" -|·")
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
    def _pastilla(
        cls, draw: ImageDraw.ImageDraw, texto: str, x: int, y: int, alto: int, *, max_width: int, centro: int | None = None,
    ) -> int:
        """Texto blanco en caja negra redondeada. Devuelve la x donde termina.
        Con `centro`, la caja se centra en esa x en vez de arrancar en `x`."""
        fuente = cls._fit_font(draw, texto, max(40, max_width - 36), base_size=int(alto * 0.62), min_size=14, bold=True)
        caja = draw.textbbox((0, 0), texto, font=fuente)
        ancho = (caja[2] - caja[0]) + 36
        if centro is not None:
            x = centro - ancho // 2
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
        prefiere_uno_desde: int = 44,
    ) -> tuple[ImageFont.ImageFont, list[str]]:
        """La negrita más grande con la que `text` cabe, en uno o dos renglones.

        Un renglón se prefiere mientras la letra no baje de `prefiere_uno_desde`: un nombre partido
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
        if uno is not None and (uno[0] >= prefiere_uno_desde or dos is None or dos[0] < uno[0] * 1.25):
            return uno[1], [entero]
        if dos is not None:
            return dos[1], dos[2]
        return cls._load_font(min_size, bold=True), [entero]

    @classmethod
    def _render_split(cls, variante: Variante, qr_path: Path, output_path: Path, *, show_price: bool | None = None) -> None:
        """La tira de 4: el mismo trato que la Label (2026-11-05). Antes era el
        nombre con «T: 6» pegado, todo del mismo tamaño y partido cada 20 letras."""
        label_image = Image.new("1", SPLIT_SIZE, 1)
        draw = ImageDraw.Draw(label_image)
        qr_image = Image.open(qr_path).convert("1").resize((QR_SIZE_SPLIT, QR_SIZE_SPLIT))
        contenido = cls.small_content(variante, show_price=show_price)
        qr_y = 6
        texto_y = qr_y + QR_SIZE_SPLIT + 4
        ancho_texto = SPLIT_SECTION_WIDTH - 16
        piezas = cls._piezas_chicas(draw, contenido, ancho_texto, SPLIT_SIZE[1] - 6 - texto_y)
        for section in range(4):
            section_x = section * SPLIT_SECTION_WIDTH
            label_image.paste(qr_image, (section_x + (SPLIT_SECTION_WIDTH - QR_SIZE_SPLIT) // 2, qr_y))
            cls._pintar_chicas(draw, piezas, section_x + SPLIT_SECTION_WIDTH // 2, texto_y)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        label_image.save(output_path, "PNG")

    @classmethod
    def _render_continuous(cls, variante: Variante, qr_path: Path, output_path: Path, *, show_price: bool | None = None) -> None:
        """Rollo continuo: el alto sale de lo que haya que decir."""
        draw_temp = ImageDraw.Draw(Image.new("1", (1, 1), 1))
        contenido = cls.small_content(variante, show_price=show_price)
        ancho_texto = CONTINUOUS_SIZE[0] - 16
        piezas = cls._piezas_chicas(draw_temp, contenido, ancho_texto, 230)
        margin, gap = 5, 6
        label_height = margin + QR_SIZE_CONTINUOUS + gap + sum(alto for *_resto, alto in piezas) + margin
        size = (CONTINUOUS_SIZE[0], label_height)

        label_image = Image.new("1", size, 1)
        draw = ImageDraw.Draw(label_image)
        qr_image = Image.open(qr_path).convert("1").resize((QR_SIZE_CONTINUOUS, QR_SIZE_CONTINUOUS))
        label_image.paste(qr_image, ((size[0] - QR_SIZE_CONTINUOUS) // 2, margin))
        cls._pintar_chicas(draw, piezas, size[0] // 2, margin + QR_SIZE_CONTINUOUS + gap)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        label_image.save(output_path, "PNG")

    @classmethod
    def _render_dk1221(cls, variante: Variante, qr_path: Path, output_path: Path, *, show_price: bool | None = None) -> None:
        """La cuadrada de 23 mm, que se volvió la de todos los días (2026-11-05).

        Son 202 puntos por lado a 300 dpi: 17 mm imprimibles, con ~3 mm de
        orilla en blanco que la Brother no toca. Antes casi todo era QR y el
        nombre iba abajo a 8 puntos, ilegible. Ahora:

            ┌──────────┬─────────┐
            │          │  TALLA  │   uniforme: la talla, enorme
            │    QR    │    6    │   ropa: el precio ($ arriba, la cifra grande)
            │          │         │         y la talla debajo si no es unitalla
            ├──────────┴─────────┤
            │ Pants 3pz          │   el nombre en negrita, hasta tres renglones
            │ Deportivo          │
            └────────────────────┘

        El QR va SIN su marco blanco y pegado a la esquina: arriba y a la
        izquierda el marco ya lo pone la orilla de la etiqueta, y a la derecha
        y abajo se dejan dos módulos antes del texto. Así los módulos miden lo
        mismo que en la versión que se probó en la tienda (5 puntos, 0.42 mm) y
        se gana un 30 % de lugar para letras. Tampoco lleva el ícono del
        centro: a 2 mm no se distingue, y le quita corrección de errores al lector.
        """
        size = DK1221_SIZE
        label_image = Image.new("1", (size, size), 1)
        draw = ImageDraw.Draw(label_image)
        qr_image = cls._qr_sin_icono(variante, qr_path)
        qr_lado = qr_image.size[0]
        label_image.paste(qr_image, (0, 0))
        aire = 2 * QR_MODULO_DK1221                     # dos módulos de blanco antes del texto

        c = cls.small_content(variante, show_price=show_price)
        col_x = qr_lado + aire
        col_w = size - col_x - 1
        col_cx = col_x + col_w // 2
        col_y0, col_y1 = 2, qr_lado - 2

        def centrado(texto: str, fuente, y: int) -> int:
            caja = draw.textbbox((0, 0), texto, font=fuente)
            draw.text((col_cx - (caja[2] - caja[0]) // 2 - caja[0], y - caja[1]), texto, font=fuente, fill=0)
            return caja[3] - caja[1]

        talla_abajo = ""        # una talla que no cabe grande en la columna baja al pie
        if c.precio:
            cifra = c.precio.lstrip("$")
            f_peso = cls._load_font(24, bold=True)
            f_talla = cls._fit_font(draw, c.talla, col_w, base_size=24, min_size=12, bold=True) if c.talla else None
            alto_talla = (cls._line_height(f_talla) + 8) if f_talla else 0
            f_cifra = cls._fit_font(draw, cifra, col_w, base_size=62, min_size=16, bold=True)
            caja_cifra = draw.textbbox((0, 0), cifra, font=f_cifra)
            alto_bloque = 18 + 4 + (caja_cifra[3] - caja_cifra[1]) + alto_talla
            y = col_y0 + max(0, ((col_y1 - col_y0) - alto_bloque) // 2)
            y += centrado("$", f_peso, y) + 4
            y += centrado(cifra, f_cifra, y) + 8
            if f_talla:
                centrado(cls._recortar(draw, c.talla, f_talla, col_w), f_talla, y)
        elif c.talla:
            f_talla = cls._fit_font(draw, c.talla, col_w, base_size=84, min_size=10, bold=True)
            if getattr(f_talla, "size", 10) >= 22:
                f_rot = cls._fit_font(draw, "TALLA", col_w, base_size=18, min_size=10)
                caja = draw.textbbox((0, 0), c.talla, font=f_talla)
                alto_bloque = 14 + 6 + (caja[3] - caja[1])
                y = col_y0 + max(0, ((col_y1 - col_y0) - alto_bloque) // 2)
                y += centrado("TALLA", f_rot, y) + 6
                centrado(c.talla, f_talla, y)
            else:
                talla_abajo = c.talla       # «Unitalla», «Infantil»… no caben grandes aquí

        # El nombre, abajo, a todo lo ancho: la letra más grande que quepa en 1 a 3 renglones.
        y0 = qr_lado + aire - 2
        alto = size - y0 - 1
        nombre = f"{c.nombre} · {talla_abajo}" if talla_abajo else c.nombre
        f_nom, renglones = cls._fit_lines(draw, nombre, size - 4, alto, base_size=40, min_size=14, max_renglones=3)
        paso = cls._alto_real(f_nom)
        y = y0 + max(0, (alto - len(renglones) * paso) // 2)
        for renglon in renglones:
            draw.text((2, y), renglon, font=f_nom, fill=0)
            y += paso
        output_path.parent.mkdir(parents=True, exist_ok=True)
        label_image.save(output_path, "PNG")

    @classmethod
    def _fit_lines(
        cls, draw: ImageDraw.ImageDraw, text: str, max_width: int, max_height: int, *,
        base_size: int, min_size: int, max_renglones: int,
    ) -> tuple[ImageFont.ImageFont, list[str]]:
        """La negrita más grande con la que `text` cabe partido por palabras en
        hasta `max_renglones`. Lo que ni así cabe se recorta con «…»."""
        palabras = str(text or "").split() or [""]
        for size in range(base_size, min_size - 1, -1):
            fuente = cls._load_font(size, bold=True)
            renglones: list[str] = []
            actual = ""
            cabe = True
            for palabra in palabras:
                intento = f"{actual} {palabra}".strip()
                if cls._text_width(draw, intento, fuente) <= max_width:
                    actual = intento
                    continue
                if not actual:                      # una sola palabra más ancha que la etiqueta
                    cabe = False
                    break
                renglones.append(actual)
                actual = palabra
                if cls._text_width(draw, actual, fuente) > max_width:
                    cabe = False
                    break
            if not cabe:
                continue
            renglones.append(actual)
            if len(renglones) <= max_renglones and len(renglones) * cls._alto_real(fuente) <= max_height:
                return fuente, renglones
        fuente = cls._load_font(min_size, bold=True)
        return fuente, [cls._recortar(draw, " ".join(palabras), fuente, max_width)]

    @staticmethod
    def _qr_sin_icono(variante: Variante, qr_path: Path) -> Image.Image:
        """El QR del SKU, limpio: sin ícono, sin marco, 5 puntos exactos por módulo.
        Si no se pudiera generar, el de archivo (con ícono), a su tamaño equivalente."""
        try:
            import qrcode
            from qrcode.constants import ERROR_CORRECT_H

            qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H, box_size=QR_MODULO_DK1221, border=0)
            qr.add_data(str(variante.sku))
            qr.make(fit=True)
            return qr.make_image(fill_color="black", back_color="white").convert("1")
        except Exception:  # noqa: BLE001 — una etiqueta con ícono es mejor que ninguna
            return Image.open(qr_path).convert("1").resize((QR_SIZE_DK1221, QR_SIZE_DK1221), Image.Resampling.NEAREST)

    @classmethod
    def small_content(cls, variante: Variante, *, show_price: bool | None = None) -> SmallLabelContent:
        """Qué dicen las etiquetas chicas: lo mismo que la Label, con menos lugar."""
        c = cls.standard_content(variante, show_price=show_price)
        if c.familia == "uniforme":
            escuela = getattr(getattr(variante.producto, "escuela", None), "nombre", "") or ""
            encabezado = " · ".join(p for p in (escuela, c.color) if p).upper()
            return SmallLabelContent(encabezado, c.nombre, c.talla, "")
        return SmallLabelContent("", c.nombre, c.talla, c.precio)

    @classmethod
    def _recortar(cls, draw: ImageDraw.ImageDraw, texto: str, fuente: ImageFont.ImageFont, ancho: int) -> str:
        """Si ni con la letra más chica cabe, se corta con «…»: nunca se sale ni se encima."""
        if cls._text_width(draw, texto, fuente) <= ancho:
            return texto
        while len(texto) > 2 and cls._text_width(draw, texto.rstrip(" ·") + "…", fuente) > ancho:
            texto = texto[:-1]
        return texto.rstrip(" ·") + "…"

    @classmethod
    def _piezas_chicas(
        cls, draw: ImageDraw.ImageDraw, c: SmallLabelContent, ancho: int, alto_max: int,
    ) -> list[tuple[str, str, ImageFont.ImageFont | None, int]]:
        """El bloque de texto de una etiqueta chica, de arriba abajo:
        (tipo, texto, fuente, alto). El nombre toma lo que dejen los demás."""
        piezas: list[tuple[str, str, ImageFont.ImageFont | None, int]] = []
        fijo = 0
        if c.encabezado:
            f_enc = cls._fit_font(draw, c.encabezado, ancho, base_size=19, min_size=13)
            piezas.append(("texto", cls._recortar(draw, c.encabezado, f_enc, ancho), f_enc, cls._line_height(f_enc) + 9))
            fijo += piezas[-1][3]
        abajo: list[tuple[str, str, ImageFont.ImageFont | None, int]] = []
        if c.precio:
            f_pre = cls._fit_font(draw, c.precio, ancho, base_size=56, min_size=30, bold=True)
            abajo.append(("texto", c.precio, f_pre, cls._alto_real(f_pre) + (2 if c.talla else -4)))
        if c.talla:
            abajo.append(("pastilla", f"TALLA {c.talla}", None, (34 if c.precio else 46) + 6))
        fijo += sum(alto for *_r, alto in abajo)
        f_nom, renglones = cls._fit_wrapped(
            draw, c.nombre, ancho, max(30, alto_max - fijo - 4), base_size=32, min_size=15, prefiere_uno_desde=26,
        )
        for renglon in renglones:
            piezas.append(("texto", renglon, f_nom, cls._alto_real(f_nom)))
        piezas[-1] = (*piezas[-1][:3], piezas[-1][3] + 4)
        return piezas + abajo

    @classmethod
    def _pintar_chicas(cls, draw: ImageDraw.ImageDraw, piezas, centro_x: int, y: int) -> int:
        for tipo, texto, fuente, alto in piezas:
            if tipo == "pastilla":
                cls._pastilla(draw, texto, 0, y, alto - 6, max_width=SPLIT_SECTION_WIDTH - 16, centro=centro_x)
            else:
                caja = draw.textbbox((0, 0), texto, font=fuente)
                draw.text((centro_x - (caja[2] - caja[0]) // 2 - caja[0], y), texto, font=fuente, fill=0)
            y += alto
        return y

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
            # La talla solo se quita si es una palabra aparte: «Telesecundaria
            # 512» en talla 12 quedaba «Telesecundaria 5» (2026-11-05).
            suffixes = [
                f"| {size_value}",
                f"- {size_value}",
                f" {size_value}",
            ]
            for suffix in suffixes:
                if cleaned.endswith(suffix):
                    cleaned = cleaned[: -len(suffix)].strip(" |-")
        return cleaned or str(nombre or "").strip()

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
