import logging

from PIL import Image, ImageWin
import win32con
import win32gui
import win32print
import win32ui

logger = logging.getLogger(__name__)

PRINT_BW_THRESHOLD = 180


def _best_fit_scale(image_size, printable_size):
    image_width, image_height = image_size
    printable_width, printable_height = printable_size
    if image_width <= 0 or image_height <= 0:
        return 0
    return min(printable_width / image_width, printable_height / image_height)


def _centered_draw_rect(image_size, printable_size, offsets):
    image_width, image_height = image_size
    printable_width, printable_height = printable_size
    offset_x, offset_y = offsets
    left = offset_x + max((printable_width - image_width) // 2, 0)
    top = offset_y + max((printable_height - image_height) // 2, 0)
    return (left, top, left + image_width, top + image_height)


def create_landscape_printer_dc(printer_name):
    """
    Crea un device context de impresora forzando orientación horizontal.
    """
    hprinter = win32print.OpenPrinter(printer_name)
    try:
        printer_info = win32print.GetPrinter(hprinter, 2)
        devmode = printer_info.get("pDevMode")
        if devmode is not None:
            devmode.Fields |= win32con.DM_ORIENTATION
            devmode.Orientation = win32con.DMORIENT_LANDSCAPE
            paper_width = int(getattr(devmode, "PaperWidth", 0) or 0)
            paper_length = int(getattr(devmode, "PaperLength", 0) or 0)
            if paper_width > 0 and paper_length > 0 and paper_width < paper_length:
                devmode.Fields |= win32con.DM_PAPERWIDTH | win32con.DM_PAPERLENGTH
                devmode.PaperWidth = paper_length
                devmode.PaperLength = paper_width
                logger.debug(
                    "Dimensiones del papel intercambiadas para landscape en %s: %s x %s",
                    printer_name,
                    devmode.PaperWidth,
                    devmode.PaperLength,
                )
            try:
                win32print.DocumentProperties(
                    0,
                    hprinter,
                    printer_name,
                    devmode,
                    devmode,
                    win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER,
                )
            except Exception as exc:
                logger.warning(
                    "No se pudo confirmar orientación landscape con el driver de %s: %s",
                    printer_name,
                    exc,
                )
        dc_handle = win32gui.CreateDC("WINSPOOL", printer_name, devmode)
        hdc = win32ui.CreateDCFromHandle(dc_handle)
        logger.debug("DC creado para %s con orientación landscape", printer_name)
        return hprinter, hdc
    except Exception:
        try:
            win32print.ClosePrinter(hprinter)
        except Exception:
            pass
        raise


def prepare_label_image_for_printer(label_path, hdc):
    """
    Prepara una etiqueta para imprimirse con el área real reportada por la impresora.
    """
    printable_width = hdc.GetDeviceCaps(win32con.HORZRES)
    printable_height = hdc.GetDeviceCaps(win32con.VERTRES)
    offset_x = hdc.GetDeviceCaps(win32con.PHYSICALOFFSETX)
    offset_y = hdc.GetDeviceCaps(win32con.PHYSICALOFFSETY)

    image = Image.open(label_path).convert("L")

    scale = _best_fit_scale(image.size, (printable_width, printable_height))
    if 0 < scale < 1:
        resized_size = (
            max(1, int(round(image.width * scale))),
            max(1, int(round(image.height * scale))),
        )
        logger.debug(
            "Etiqueta redimensionada para evitar reescalado del driver: %sx%s -> %sx%s",
            image.width,
            image.height,
            resized_size[0],
            resized_size[1],
        )
        image = image.resize(resized_size, Image.Resampling.LANCZOS)

    prepared_image = image.point(lambda x: 0 if x < PRINT_BW_THRESHOLD else 255, "1")
    draw_rect = _centered_draw_rect(
        prepared_image.size,
        (printable_width, printable_height),
        (offset_x, offset_y),
    )

    logger.debug(
        "Preparación de impresión: imagen=%sx%s, área imprimible=%sx%s, offsets=(%s,%s), rect=%s",
        prepared_image.width,
        prepared_image.height,
        printable_width,
        printable_height,
        offset_x,
        offset_y,
        draw_rect,
    )

    return prepared_image, draw_rect


def draw_prepared_label(hdc, image, draw_rect):
    """
    Dibuja una etiqueta ya preparada en el contexto de impresión.
    """
    dib = ImageWin.Dib(image)
    dib.draw(hdc.GetHandleOutput(), draw_rect)
