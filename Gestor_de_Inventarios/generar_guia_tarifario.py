#!/usr/bin/env python3
"""Guía de uso del Tarifario General — material de capacitación para el personal.

Documento estático (no consulta la DB) con el mismo diseño del tarifario para
que el personal asocie los colores y secciones. Los precios de los ejemplos
son reales al 2026-07; si cambian mucho, actualizar los ejemplos.
"""
import generar_tarifarios_db as G
import generar_tarifarios_html as base

OUT = G.OUT_HTML / "Guia_Tarifario_General.html"

CSS_GUIA = """
@page { size: A4 portrait; margin: 0; }
.page { width: 210mm; min-height: 297mm; position: relative; }
@media print {
  .page { min-height: 0; height: auto; zoom: 1; width: 210mm; }
}
.pagina-num {
  position: absolute; bottom: 10px; right: 20px;
  font-size: 10px; font-weight: 700; color: #94A3B8;
}
body { font-size: 14px; }
.guia p, .guia li { font-size: 13.5px; line-height: 1.55; color: #1F2937; }
.guia h3 { font-size: 15px; margin: 14px 0 6px; color: #093A54; }
.guia ol, .guia ul { margin: 4px 0 10px 22px; }
.guia li { margin-bottom: 4px; }
.paso {
  background: #F0F7FC; border-left: 4px solid #66CCF9; border-radius: 6px;
  padding: 9px 13px; margin: 8px 0; font-size: 13.5px; line-height: 1.5;
}
.ejemplo {
  border: 1.5px solid #D8E2EC; border-radius: 8px; padding: 10px 14px;
  margin: 8px 0; font-size: 13px; line-height: 1.55;
}
.ejemplo b.res { color: #0F7DB5; }
.regla {
  background: #FEF0F0; border: 2px solid #E5A3A3; border-radius: 8px;
  padding: 10px 14px; margin: 10px 0; font-size: 14px; font-weight: 600;
  color: #7F1D1D;
}
.muestra { display: inline-block; width: 13px; height: 13px; border-radius: 3px;
  margin-right: 7px; vertical-align: -2px; }
.leyenda li { list-style: none; margin-left: -18px; }
"""


def pagina(num, titulo, cuerpo):
    return f"""
<div class="page">
  <div class="page-header">
    <div class="header-left">
      <div class="header-category">Guía de uso · Capacitación</div>
      <div class="header-title">{titulo}</div>
    </div>
    <div class="header-right">
      <div class="header-date">Tarifario General 2026</div>
    </div>
  </div>
  <div class="guia">{cuerpo}</div>
  <div class="pagina-num">Página {num}</div>
</div>"""


P1 = """
<h3>¿Qué es el Tarifario General?</h3>
<p>Es el documento con <b>todos los precios de la tienda organizados por tipo de
prenda</b>: pants, chamarras, playeras, suéteres, chalecos, camisas, pantalones,
faldas y accesorios. Cada hoja es una categoría. Los precios salen directo del
sistema, así que <b>el tarifario y la caja siempre dicen lo mismo</b>.</p>

<h3>El código de colores (apréndetelo, es tu mapa)</h3>
<ul class="leyenda">
  <li><span class="muestra" style="background:#66CCF9"></span><b>Azul cielo</b> —
  título de cada tabla: el nombre de la prenda (ej. "Básico", "Manga Corta Blanca").</li>
  <li><span class="muestra" style="background:#A8D08D"></span><b>Verde</b> —
  la barra TALLAS / PRECIO de cada tabla.</li>
  <li><span class="muestra" style="background:#F8C045"></span><b>Dorado</b> —
  tablas donde el precio <b>depende del nivel escolar</b> (Preescolar, Primaria,
  Secundaria, Bachillerato). Antes de cobrar, pregunta: <i>"¿para qué escuela
  es?"</i> y ubica su nivel.</li>
  <li><span class="muestra" style="background:#F5B8FB"></span><b>Rosa</b> —
  prendas de niña: faldas, jumpers, cuello olán y suéter de botones.</li>
  <li><span class="muestra" style="background:#FDD"></span><b>ROJO</b> —
  <b>EXCEPCIONES ACTIVAS</b>: escuelas con precio especial. Siempre está
  <b>hasta arriba de la hoja</b>. Es lo primero que revisas.</li>
</ul>

<h3>Cómo leer una tabla (la "escalera")</h3>
<p>Cada tabla junta las tallas que comparten precio. Se lee: <i>"de tal talla a
tal talla, cuesta tanto"</i>.</p>
<div class="paso">Ejemplo — Suéter Básico: tallas <b>4, 6, 8</b> = $289 ·
tallas <b>10-16</b> = $299 · <b>28-34</b> = $309 · <b>36-42</b> = $315 ·
<b>44, 46</b> = $325.<br>¿Te piden un suéter básico talla 12? Buscas el renglón
donde está el 12 → <b>$299</b>. Así de simple.</div>

<h3>Las tallas</h3>
<ul>
  <li><b>Números chicos (2-16):</b> tallas de niño/niña.</li>
  <li><b>Números grandes (28-46):</b> tallas juveniles/adulto.</li>
  <li><b>Letras:</b> CH (chica), MD (mediana), GD (grande), EXG (extra grande).</li>
  <li><b>UNI:</b> unitalla (gorros, boinas, accesorios).</li>
</ul>
"""

P2 = """
<div class="regla">⭐ REGLA DE ORO: antes de dar un precio, revisa el bloque ROJO
de "Excepciones activas" (arriba de la hoja). Si la escuela del cliente aparece
ahí con esa talla, ESE precio manda. Si no aparece, usas la tabla normal.</div>

<h3>Pasos para cotizar cualquier prenda</h3>
<ol>
  <li><b>Pregunta la escuela</b> del cliente (y con eso sabes el nivel).</li>
  <li><b>Abre la hoja</b> de la prenda (Pants 3pz, Suéteres, Faldas…).</li>
  <li><b>Revisa el rojo:</b> ¿está su escuela en Excepciones con esa talla?
  → ese es el precio, fin.</li>
  <li>Si no está: ¿la tabla es <b>dorada</b>? → usa la del nivel de su escuela.
  ¿Es azul/rosa? → es precio general, solo ubica la talla.</li>
</ol>

<h3>Ejemplos resueltos (con precios reales)</h3>
<div class="ejemplo">🟢 <b>Caso 1 — sin excepción:</b> mamá de <b>Benito Juárez
(primaria)</b> quiere suéter oficial talla 10.<br>
Hoja Suéteres → Excepciones: Benito Juárez NO aparece → tabla dorada
"Oficial Primaria" → talla 10 → <b class="res">$299</b>.</div>

<div class="ejemplo">🔴 <b>Caso 2 — con excepción:</b> cliente de
<b>Telesecundaria 512</b> quiere pants 2 piezas talla 14.<br>
Hoja Pants 2 Piezas → Excepciones: ¡512 SÍ aparece! (10-16, CH-EXG) →
<b class="res">$650</b>. <i>(Sin la excepción habrías cobrado $605 — por eso
el rojo se revisa primero.)</i></div>

<div class="ejemplo">🌸 <b>Caso 3 — prenda de niña:</b> falda escocesa talla 8
para <b>Margarita Paz Paredes</b>.<br>
Hoja Faldas → Excepciones: Margarita aparece (2-8 a $239) →
<b class="res">$239</b>. Para cualquier otra escuela sería $215.</div>

<div class="ejemplo">🟡 <b>Caso 4 — mismo producto, precio por nivel:</b>
playera deportiva talla 14.<br>¿Primaria? → $209. ¿Secundaria o bachillerato? →
$229. <b>La misma playera cambia según el nivel</b> — por eso siempre se
pregunta la escuela primero.</div>
"""

P3 = """
<h3>Dónde está cada cosa (orden de las hojas)</h3>
<ol>
  <li>Pants 3 Piezas</li>
  <li>Pants 2 Piezas</li>
  <li>Chamarras</li>
  <li>Pants Suelto</li>
  <li>Playeras Deportivas</li>
  <li>Suéteres</li>
  <li>Chalecos</li>
  <li>Camisas y Playeras Manga Corta</li>
  <li>Camisas Manga Larga</li>
  <li>Pantalones</li>
  <li>Faldas · Jumper</li>
  <li>Accesorios · Malla · Bata</li>
</ol>

<h3>Preguntas frecuentes</h3>
<div class="ejemplo"><b>¿El precio del tarifario no coincide con la caja?</b><br>
La caja siempre manda. Cobra lo que diga el sistema y avísale a Daniel para
regenerar el tarifario.</div>
<div class="ejemplo"><b>¿La prenda que buscan no aparece en el tarifario?</b><br>
Algunas piezas se manejan aparte (ofertas, descontinuados). Escanéala en caja o
pregunta.</div>
<div class="ejemplo"><b>¿Una escuela pide talla más grande de lo que muestra su
nivel?</b><br>Es probable que sí exista — el tarifario muestra lo usual.
Verifícala en el sistema.</div>
<div class="ejemplo"><b>¿Qué significa "se respeta el precio mayor"?</b><br>
Si una prenda trae marcado un precio más alto que el tarifario, se respeta el
marcado. Nunca se cobra de menos sin autorización.</div>

<div class="regla" style="background:#F0F7FC;border-color:#8CC5E8;color:#093A54">
💡 Consejo: los primeros días ten la guía a la mano y resuelve cada venta con
los 4 pasos. En una semana te sabrás las excepciones de memoria.</div>
"""


def generate():
    paginas = [
        pagina(1, "Cómo leer el Tarifario", P1),
        pagina(2, "Cómo cotizar paso a paso", P2),
        pagina(3, "Mapa del documento y dudas", P3),
    ]
    html = base.HTML_WRAPPER.format(
        title="Guía del Tarifario General 2026",
        css=base.CSS + G.CSS_EXTRA + CSS_GUIA,
        body="\n".join(paginas))
    OUT.write_text(html, encoding="utf-8")
    print(f"Generado: {OUT}")


if __name__ == "__main__":
    generate()
