#!/usr/bin/env python3
"""Índices del Tarifario por Escuela (horizontal) en un solo documento.

Genera un HTML/PDF apaisado (carta horizontal, mismo formato que
Tarifario_Escuelas_2026) con:
  1. Índice · Contenido general — las hojas que van ANTES de Preescolar
     (tarifario general + básicos), con su número de página en el documento.
  2. Los índices de Preescolar, Primaria, Secundaria y Bachillerato,
     idénticos a los del documento por escuela.

Los números de página son los del Tarifario_Escuelas_2026 vigente. El
documento principal ya no trae las hojas de índice pero sí reserva su
número, así que estas hojas se imprimen aparte y se intercalan en su lugar
sin mover ninguna página.
"""
import subprocess

import generar_tarifario_escuelas_db as E
import generar_tarifarios_db as G
import generar_tarifarios_html as base

OUT_HTML = G.OUT_HTML / "Indices_Tarifario_2026.html"
OUT_PDF = "/Users/danielfabian/Downloads/Indices_Tarifario_2026.pdf"
BRAVE = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"


def generate():
    G.DOC_NOMBRE = "Tarifario por Escuela"
    filas = G.cargar_filas()
    numerada = E.secuencia_numerada(filas)

    paginas = []

    # 1) Índice del contenido general (todo lo anterior a Preescolar)
    rows = [[tit, str(num)] for num, tipo, cat, tit, _ in numerada
            if tipo == "pagina" and cat not in E.CON_INDICE + ("Otros",)]
    items = [("divider", "Índice"),
             ("grid", 2, [("Contenido general", ["Contenido", "Página"], rows)])]
    paginas.append(G.html_page("General", "Índice · Contenido general", items))

    # 2) Índices por nivel, cada uno con su número reservado en el documento
    for num, tipo, nivel, titulo, _ in numerada:
        if tipo != "indice":
            continue
        rows = [[t2, str(n2)] for n2, tp2, nv2, t2, _ in numerada
                if tp2 == "pagina" and nv2 == nivel]
        items = [("divider", "Índice"),
                 ("grid", 2, [(f"Escuelas de {nivel}", ["Escuela", "Página"], rows)])]
        paginas.append(E.con_numero(G.html_page(nivel, titulo, items), num))

    html = base.HTML_WRAPPER.format(
        title="Índices · Tarifario por Escuela 2026",
        css=base.CSS + G.CSS_EXTRA + E.CSS_LOCAL,
        body="\n".join(paginas) + E.AUTOFIT_JS)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Generado: {OUT_HTML} ({len(paginas)} hojas)")

    subprocess.run([
        BRAVE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
        f"--print-to-pdf={OUT_PDF}",
        OUT_HTML.resolve().as_uri()], check=True)
    print(f"PDF: {OUT_PDF}")


if __name__ == "__main__":
    generate()
