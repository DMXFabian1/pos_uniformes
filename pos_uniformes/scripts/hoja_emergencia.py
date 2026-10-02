"""La hoja que se pega junto a la caja: qué hacer si algo falla.

Daniel se va una semana (01/10) y deja la tienda a las muchachas. Lo que no
estaba escrito en ningún lado es lo más simple: qué hacer cuando algo se ve
raro y él no contesta el teléfono.

    python -m pos_uniformes.scripts.hoja_emergencia          # escribe el HTML
    python -m pos_uniformes.scripts.hoja_emergencia --abrir  # y lo abre para imprimir

Sale en `reportes/hoja_tienda.html`, de una sola página, para imprimir con
Ctrl+P. Los teléfonos van en blanco a propósito: se escriben con pluma, que es
más rápido que volver a generar la hoja y no se queda viejo en el archivo.

Está en letra grande y sin una sola palabra del programa — «base de datos»,
«servidor» o «caché» no le sirven a quien está atendiendo con un cliente
enfrente. La regla de toda la hoja es la misma: casi nada se arregla apagando
cosas, y vender nunca se detiene.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

SALIDA = "reportes/hoja_tienda.html"

#: (título, pasos). El orden es el de la probabilidad de que pase.
CASOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "La pantalla me pide mi QR y no pasa",
        (
            "Escanea el código de <b>tu</b> gafete, despacio y de frente.",
            "Si dice que no lo encuentra, avisa. <b>No uses el gafete de otra</b>: "
            "todo lo que se venda queda a nombre de quien escaneó.",
        ),
    ),
    (
        "Dice «sin conexión» o la Libreta no se actualiza",
        (
            "La computadora de atrás está apagada o se reinició.",
            "<b>Sigue vendiendo.</b> La venta rápida funciona sin ella y nada se pierde: "
            "se guarda y se acomoda solo cuando vuelve.",
            "Si puedes, préndela y espera dos minutos.",
        ),
    ),
    (
        "No sale el ticket",
        (
            "Revisa papel y que la impresora esté encendida.",
            "Dale imprimir <b>una vez más, no diez</b>: se van formando y luego salen todos.",
        ),
    ),
    (
        "Sale un aviso que tapa toda la pantalla",
        (
            "Es un recado de Daniel. Léelo y toca <b>«Enterada»</b> — así él sabe que llegó.",
            "Si estás con un cliente, toca <b>«Luego»</b>: el aviso se quita y vuelve a salir después.",
        ),
    ),
    (
        "Un precio se ve raro o no aparece una prenda",
        (
            "Avisa por WhatsApp con una foto de la pantalla.",
            "<b>No cambies precios a mano</b> ni pongas otro producto parecido.",
        ),
    ),
    (
        "Gasté dinero de la tienda (bolsas, agua, mandado)",
        (
            "Venta rápida → <b>🧾 Gasto</b>. Pon cuánto y en qué.",
            "Apúntalo <b>en el momento</b>. Si se apunta en la noche, el corte no cuadra "
            "y parece dinero perdido.",
        ),
    ),
    (
        "Necesito un préstamo de mi sueldo",
        (
            "En la Libreta, con tu gafete: <b>Pedir préstamo</b>.",
            "La pantalla te dice hasta cuánto puedes pedir. Daniel lo aprueba desde su teléfono "
            "y se descuenta en tu siguiente pago.",
        ),
    ),
    (
        "Se acabó el día",
        (
            "<b>El corte se hace solo</b> si Daniel no contestó. No tienes que hacer nada.",
            "Deja el dinero como siempre.",
        ),
    ),
    (
        "Se fue la luz",
        (
            "Cuando vuelva: primero prende la <b>computadora de atrás</b>, espera dos minutos, "
            "y después las pantallas.",
            "Si las pantallas se prenden antes, no pasa nada: se acomodan solas.",
        ),
    ),
)

NUNCA = (
    "Apagar la computadora de atrás mientras la tienda está abierta.",
    "Borrar o cambiar algo en «Cortes anteriores».",
    "Cambiar precios.",
    "Usar el gafete de otra persona.",
)

_CSS = """
@page { size: letter; margin: 12mm; }
* { box-sizing: border-box; }
body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a;
       margin: 0; font-size: 11.5pt; line-height: 1.35; }
h1 { font-size: 21pt; margin: 0 0 2px; letter-spacing: -0.3px; }
.sub { color: #6b4a3a; font-size: 10pt; margin-bottom: 10px; }
.regla { background: #7b2d14; color: #fdfaf6; padding: 8px 12px; border-radius: 6px;
         font-size: 11pt; margin-bottom: 12px; }
.casos { column-count: 2; column-gap: 16px; }
.caso { break-inside: avoid; margin-bottom: 10px; }
.caso h2 { font-size: 11.5pt; margin: 0 0 3px; color: #7b2d14; }
.caso ul { margin: 0; padding-left: 16px; }
.caso li { margin-bottom: 2px; }
.pie { margin-top: 10px; border-top: 2px solid #7b2d14; padding-top: 8px;
       display: flex; gap: 16px; }
.pie > div { flex: 1; }
.pie h2 { font-size: 11.5pt; margin: 0 0 4px; color: #7b2d14; }
.pie ul { margin: 0; padding-left: 16px; }
.nunca li { margin-bottom: 2px; }
.tel { font-size: 12pt; line-height: 2.1; }
.linea { display: inline-block; border-bottom: 1px solid #999; width: 150px; }
.fecha { margin-top: 8px; text-align: right; color: #8a7a70; font-size: 8.5pt; }
@media print { .noprint { display: none; } }
.noprint { background: #f3e9dd; padding: 8px 12px; border-radius: 6px;
           font-size: 10pt; margin-bottom: 10px; }
"""


def html(hoy: date | None = None) -> str:
    """La hoja completa. Pura: se le puede pedir el texto sin escribir nada."""
    hoy = hoy or date.today()
    casos = "\n".join(
        "<div class='caso'><h2>{t}</h2><ul>{pasos}</ul></div>".format(
            t=titulo,
            pasos="".join(f"<li>{p}</li>" for p in pasos),
        )
        for titulo, pasos in CASOS
    )
    nunca = "".join(f"<li>{n}</li>" for n in NUNCA)
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>Si algo falla — MAXIMODA</title><style>{_CSS}</style></head>
<body>
<div class="noprint">Para imprimir: <b>Ctrl + P</b>. Entra en una hoja.</div>
<h1>Si algo falla</h1>
<div class="sub">Pégala junto a la caja. No hace falta saber de computadoras.</div>
<div class="regla"><b>La regla de todo:</b> casi nada se arregla apagando cosas,
y <b>vender nunca se detiene</b>. Si algo se ve raro, manda foto por WhatsApp y sigue atendiendo.</div>
<div class="casos">{casos}</div>
<div class="pie">
  <div><h2>Esto nunca</h2><ul class="nunca">{nunca}</ul></div>
  <div><h2>A quién le hablo</h2>
    <div class="tel">
      Daniel &nbsp;<span class="linea"></span><br>
      León &nbsp;<span class="linea"></span>
    </div>
  </div>
</div>
<div class="fecha">MAXIMODA · {hoy:%d/%m/%Y}</div>
</body></html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera la hoja de «si algo falla».")
    parser.add_argument("--abrir", action="store_true", help="abrirla al terminar, para imprimir")
    parser.add_argument("--salida", default=None, help=f"dónde escribirla (default: {SALIDA})")
    args = parser.parse_args(argv)

    from pos_uniformes.utils.config import runtime_base_dir

    destino = (
        Path(args.salida).expanduser().resolve()
        if args.salida
        else (runtime_base_dir() / SALIDA)
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html(), encoding="utf-8")
    print(f"Hoja escrita en: {destino}")
    print("Ábrela y dale Ctrl+P. Entra en una hoja.")
    print("Los teléfonos van en blanco: escríbelos con pluma.")

    if args.abrir:
        import webbrowser

        webbrowser.open(destino.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
