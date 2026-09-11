"""Imprimir la hoja de conteo en papel carta (o guardarla como PDF).

Va por `QPrinter` con diálogo, como las etiquetas del POS: quien imprime ve
la lista de impresoras y elige. Si hay una HP en la lista, ya viene
seleccionada — es la de la tienda (192.168.0.9). La tira térmica sigue viva
en el admin (Ctrl+Shift+A → Conteos) como respaldo.
"""

from __future__ import annotations

from PyQt6.QtCore import QMarginsF
from PyQt6.QtGui import QPageLayout, QPageSize, QTextDocument
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter, QPrinterInfo
from PyQt6.QtWidgets import QDialog, QWidget

PISTA_IMPRESORA = "hp"


def elegir_impresora_por_defecto(nombres: list[str], pista: str = PISTA_IMPRESORA) -> str | None:
    """La primera que se llame como la pista (puro). None si ninguna."""
    pista = pista.lower()
    for nombre in nombres:
        if pista in nombre.lower():
            return nombre
    return None


def _preparar(printer: QPrinter) -> None:
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
    printer.setPageOrientation(QPageLayout.Orientation.Portrait)
    printer.setPageMargins(QMarginsF(14.0, 12.0, 14.0, 12.0), QPageLayout.Unit.Millimeter)


def documento(html: str) -> QTextDocument:
    doc = QTextDocument()
    doc.setHtml(html)
    return doc


def guardar_pdf(html: str, ruta: str) -> None:
    """La misma hoja, a PDF. Sirve para previsualizar y para las pruebas."""
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(ruta)
    _preparar(printer)
    documento(html).print(printer)


def imprimir_hoja_carta(parent: QWidget | None, html: str, titulo: str) -> bool:
    """Abre el diálogo de impresión con la HP preseleccionada. True si se mandó."""
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    _preparar(printer)
    nombres = [p.printerName() for p in QPrinterInfo.availablePrinters()]
    preferida = elegir_impresora_por_defecto(nombres)
    if preferida:
        printer.setPrinterName(preferida)
    dialogo = QPrintDialog(printer, parent)
    dialogo.setWindowTitle(titulo)
    if dialogo.exec() != int(QDialog.DialogCode.Accepted):
        return False
    documento(html).print(printer)
    return True
