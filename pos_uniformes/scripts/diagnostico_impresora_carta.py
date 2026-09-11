"""¿Por qué no imprime la hoja carta? Diagnóstico que deja reporte en reportes/.

Hace tres cosas y escribe todo en `reportes/impresora_carta.txt`:

1. Lista las impresoras como las ve **Qt** (nombre, si es la predeterminada,
   estado, si es válida) — que es exactamente lo que ve el diálogo de imprimir.
2. Lista las impresoras como las ve **Windows** (puerto, si está fuera de
   línea, estado) — para cruzar: una HP puede aparecer dos veces (WSD + IP)
   y una de las dos estar muerta.
3. Manda una hoja de prueba chica a CADA impresora cuyo nombre diga "HP",
   sin diálogo, y anota si Qt la aceptó y qué estado quedó.

Uso: scripts\\diagnostico_impresora_carta.bat   (luego scripts\\enviar_reporte.bat)
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen" if platform.system() != "Windows" else "windows")

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
REPORTE = RAIZ / "reportes" / "impresora_carta.txt"

_ESTADOS = {
    QPrinter.PrinterState.Idle: "lista (Idle)",
    QPrinter.PrinterState.Active: "imprimiendo (Active)",
    QPrinter.PrinterState.Aborted: "abortada (Aborted)",
    QPrinter.PrinterState.Error: "ERROR",
}


def _linea(f, texto: str = "") -> None:
    print(texto)
    f.write(texto + "\n")


def _windows_printers() -> str:
    if platform.system() != "Windows":
        return "(no es Windows)"
    ps = (
        "Get-Printer | Select-Object Name,PortName,DriverName,PrinterStatus,WorkOffline,Shared "
        "| Format-Table -AutoSize | Out-String -Width 200"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30
        )
        return (out.stdout or "") + (out.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return f"(no se pudo consultar PowerShell: {exc})"


def _prueba(nombre: str, f) -> None:
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize, QTextDocument

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPrinterName(nombre)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
    printer.setPageOrientation(QPageLayout.Orientation.Portrait)
    printer.setPageMargins(QMarginsF(14.0, 12.0, 14.0, 12.0), QPageLayout.Unit.Millimeter)
    _linea(f, f"   printerName() que quedó: {printer.printerName()!r}")
    _linea(f, f"   isValid(): {printer.isValid()}")
    if not printer.isValid():
        _linea(f, "   -> Qt NO acepta esta impresora: el nombre no coincide o el driver no responde.")
        return
    doc = QTextDocument()
    doc.setHtml(
        f"<h2>Prueba de impresión — POS Uniformes</h2>"
        f"<p>Impresora: <b>{nombre}</b><br>Hora: {datetime.now():%d/%m/%Y %H:%M:%S}</p>"
        "<p>Si ves esta hoja, la hoja de conteo sale por aquí.</p>"
    )
    try:
        doc.print(printer)
        _linea(f, f"   print(): enviado. Estado después: {_ESTADOS.get(printer.printerState(), printer.printerState())}")
    except Exception as exc:  # noqa: BLE001
        _linea(f, f"   print(): EXCEPCIÓN {type(exc).__name__}: {exc}")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    REPORTE.parent.mkdir(parents=True, exist_ok=True)
    with REPORTE.open("w", encoding="utf-8") as f:
        _linea(f, f"=== Diagnóstico impresora carta · {datetime.now():%d/%m/%Y %H:%M} · {platform.node()} ===")
        _linea(f)
        _linea(f, "--- 1. Impresoras como las ve Qt (lo mismo que el diálogo de imprimir) ---")
        infos = QPrinterInfo.availablePrinters()
        predet = QPrinterInfo.defaultPrinterName()
        _linea(f, f"predeterminada de Windows: {predet!r}")
        if not infos:
            _linea(f, "¡Qt no ve NINGUNA impresora!")
        for info in infos:
            marca = "  <- predeterminada" if info.isDefault() else ""
            _linea(
                f,
                f" · {info.printerName()!r}  estado={_ESTADOS.get(info.state(), info.state())}"
                f"  modelo={info.makeAndModel()!r}  ubicación={info.location()!r}{marca}",
            )
        _linea(f)
        _linea(f, "--- 2. Impresoras como las ve Windows ---")
        _linea(f, _windows_printers().rstrip())
        _linea(f)
        _linea(f, "--- 3. Hoja de prueba a cada impresora con 'HP' en el nombre (sin diálogo) ---")
        hps = [i.printerName() for i in infos if "hp" in i.printerName().lower()]
        if not hps:
            _linea(f, "Ninguna impresora se llama HP: Qt no la ve. Hay que instalarla o revisar el nombre.")
        for nombre in hps:
            _linea(f, f"\n>> {nombre}")
            _prueba(nombre, f)
        _linea(f)
        _linea(f, "Fin. Si alguna hoja de prueba salió físicamente, ESA es la impresora buena;")
        _linea(f, "si ninguna salió pero print() dijo 'enviado', el trabajo está atorado en la cola de Windows.")
    print(f"\nReporte guardado en {REPORTE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
