import logging
import os

from PIL import Image

logger = logging.getLogger(__name__)

BROTHER_QL_MODEL = "QL-800"
BROTHER_QL_BACKEND = "pyusb"
BROTHER_QL_LABEL_SIZE = "62"
BROTHER_QL_TARGET_WIDTH = 696
BROTHER_QL_THRESHOLD = 180
BROTHER_QL_ROTATE = (os.getenv("BROTHER_QL_ROTATE", "90") or "90").strip()


def _load_brother_ql_modules():
    try:
        from brother_ql import BrotherQLRaster  # type: ignore
        from brother_ql.backends.helpers import discover, send  # type: ignore
        from brother_ql.conversion import convert  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Faltan dependencias para impresión directa Brother. "
            "Instala brother_ql, pyusb, packbits y attrs."
        ) from exc

    return BrotherQLRaster, convert, discover, send


def _resolve_printer_identifier(discover):
    configured_identifier = os.getenv("BROTHER_QL_PRINTER", "").strip()
    if configured_identifier:
        return configured_identifier

    devices = discover(backend_identifier=BROTHER_QL_BACKEND)
    if not devices:
        raise ValueError(
            "No se encontró una Brother QL por USB. "
            "Si estás en Windows, instala el filtro libusb-win32 para la QL-800."
        )

    identifier = str(devices[0].get("identifier") or "").strip()
    if not identifier:
        raise ValueError("Se detectó una Brother QL, pero no fue posible obtener su identificador USB.")
    logger.debug("Brother QL detectada para impresión nativa: %s", identifier)
    return identifier


def _prepare_image_for_brother(label_path):
    image = Image.open(label_path).convert("L")
    image = image.point(lambda x: 0 if x < BROTHER_QL_THRESHOLD else 255, "1")

    current_short_side = min(image.width, image.height)
    if current_short_side != BROTHER_QL_TARGET_WIDTH:
        scale = BROTHER_QL_TARGET_WIDTH / max(1, current_short_side)
        resized_size = (
            max(1, int(round(image.width * scale))),
            max(1, int(round(image.height * scale))),
        )
        image = image.resize(resized_size, Image.Resampling.NEAREST)

    logger.debug(
        "Imagen preparada para Brother QL: %sx%s desde %s (rotate=%s)",
        image.width,
        image.height,
        label_path,
        BROTHER_QL_ROTATE,
    )
    return image


def try_print_brother_ql(label_path, copies=1):
    """
    Intenta imprimir una etiqueta directamente a la Brother QL-800 usando raster nativo.
    """
    BrotherQLRaster, convert, discover, send = _load_brother_ql_modules()
    printer_identifier = _resolve_printer_identifier(discover)
    image = _prepare_image_for_brother(label_path)
    image_count = max(1, int(copies))

    qlr = BrotherQLRaster(BROTHER_QL_MODEL)
    qlr.exception_on_warning = True
    instructions = convert(
        qlr=qlr,
        images=[image] * image_count,
        label=BROTHER_QL_LABEL_SIZE,
        rotate=BROTHER_QL_ROTATE,
        threshold=70.0,
        dither=False,
        compress=True,
        red=False,
        dpi_600=False,
        hq=True,
        cut=True,
    )
    status = send(
        instructions=instructions,
        printer_identifier=printer_identifier,
        backend_identifier=BROTHER_QL_BACKEND,
        blocking=True,
    )
    logger.debug(
        "Resultado de impresión nativa Brother (%s copias): %s",
        image_count,
        status,
    )
    if status.get("outcome") == "error":
        raise ValueError("La Brother reportó un error al imprimir la etiqueta.")
    return True
