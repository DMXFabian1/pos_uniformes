#!/usr/bin/env python3
"""Reto Tarifario — juego de capacitación estilo Kahoot para el personal.

Genera un HTML autocontenido (funciona offline) con:
- Un banco GRANDE de preguntas de precios construido automáticamente desde las
  escaleras reales de la DB/cache (una pregunta por peldaño de cada familia)
- Preguntas de excepciones por escuela y de concepto
- 3 modos: Rápido (10), Completo (20) y Práctica (sin reloj)
- Cronómetro, puntos por velocidad, racha con bono escalado, explicación con la
  escalera completa, repaso de falladas al final y tabla de récords local
- Sonidos, cuenta regresiva, confeti en partida perfecta y teclado 1-4
- Las preguntas no se repiten entre partidas hasta agotar el banco

Regenerar cuando cambien precios: preguntas y distractores se actualizan solos.
"""
import json
import random

import generar_tarifarios_db as G

OUT = G.OUT_HTML / "Reto_Tarifario.html"

filas = G.cargar_filas()
F = G.Filas(filas)

PREGUNTAS = []


def preg(texto, opciones, correcta, exp, cat="Concepto"):
    PREGUNTAS.append({"q": texto, "ops": opciones, "ok": correcta, "exp": exp, "cat": cat})


def opciones_precio(correcto, pool):
    """4 opciones: el correcto + 3 distractores creíbles (misma escalera)."""
    ops = {correcto}
    cerca = sorted((p for p in pool if p != correcto), key=lambda p: abs(p - correcto))
    for p in cerca:
        if len(ops) >= 4:
            break
        ops.add(p)
    delta = 10
    while len(ops) < 4:
        for c in (correcto - delta, correcto + delta):
            if c > 0 and len(ops) < 4:
                ops.add(c)
        delta += 10
    return [f"${v:,.0f}" for v in sorted(ops)]


def escalera_txt(rows):
    return " · ".join(f"{t} = {p}" for t, p in rows)


def preguntas_familia(etiqueta, fn, exp_extra="", max_preguntas=3):
    """Genera hasta N preguntas (peldaños distintos) de una familia."""
    sel = F.sel(fn)
    if not sel:
        return
    rows, _ = G.escalera(sel)
    if not rows:
        return
    pool = sorted({float(p.replace("$", "").replace(",", "")) for _, p in rows})
    if len(rows) == 1:
        indices = [0]
    elif len(rows) == 2:
        indices = [0, 1]
    else:
        indices = sorted(random.sample(range(len(rows)), min(max_preguntas, len(rows))))
    exp = f"Escalera — {etiqueta}: {escalera_txt(rows)}." + (f" {exp_extra}" if exp_extra else "")
    for i in indices:
        tallas, precio_s = rows[i]
        talla = random.choice([t.strip() for t in tallas.split(",")])
        correcto = float(precio_s.replace("$", "").replace(",", ""))
        ops = opciones_precio(correcto, pool)
        preg(f"{etiqueta}, talla {talla}: ¿precio?", ops,
             ops.index(f"${correcto:,.0f}"), exp, cat="Precio")


def pregunta_excepcion(texto, fn, talla, exp, pool_fn):
    vals = {float(pr) for _, _, t, pr in F.sel(fn) if G.talla_norm(t) == G.talla_norm(talla)}
    if len(vals) != 1:
        return
    correcto = vals.pop()
    pool = sorted({float(pr) for _, _, _, pr in F.sel(pool_fn)})
    ops = opciones_precio(correcto, pool)
    preg(texto, ops, ops.index(f"${correcto:,.0f}"), exp, cat="Excepción")


random.seed(20260724)

# ── Concepto ─────────────────────────────────────────────────────────────────
preg("¿Qué es LO PRIMERO que revisas en una hoja del tarifario antes de dar un precio?",
     ["El bloque rojo de Excepciones activas", "La tabla más grande",
      "El precio más barato", "La fecha de actualización"], 0,
     "Regla de oro: si la escuela del cliente está en el bloque rojo, ese precio manda.")
preg("¿Qué significa una tabla con encabezado DORADO?",
     ["Que está en oferta", "Que el precio depende del nivel escolar",
      "Que es prenda de niña", "Que es precio de mayoreo"], 1,
     "Dorado = por nivel: pregunta la escuela y ubica si es preescolar, primaria, secundaria o bachillerato.")
preg("¿Qué prendas van en tablas ROSAS?",
     ["Las más caras", "Las de temporada",
      "Las de niña: faldas, jumpers, cuello olán y suéter de botones", "Las de preescolar"], 2,
     "El rosa te ayuda a ubicar rápido el uniforme de niña.")
preg("¿Qué es lo primero que le preguntas al cliente?",
     ["Su nombre", "¿Para qué escuela es?", "¿Cuánto quiere gastar?", "La talla"], 1,
     "La escuela define nivel, precios especiales y prendas correctas.")
preg("La etiqueta de una prenda marca MÁS que el tarifario. ¿Qué cobras?",
     ["El del tarifario", "El precio marcado en la prenda",
      "El promedio", "Le pregunto al cliente"], 1,
     "Se respeta el precio mayor marcado. Nunca se cobra de menos sin autorización.")
preg("¿Qué significa la talla EXG?",
     ["Extra grande", "Extra género", "Exclusivo general", "Escolar general"], 0,
     "CH chica · MD mediana · GD grande · EXG extra grande.")
preg("El precio del tarifario no coincide con el de la caja. ¿Qué haces?",
     ["Cobro el del tarifario", "Cobro el de la caja y aviso a Daniel",
      "No vendo la prenda", "Invento un precio intermedio"], 1,
     "La caja siempre manda; el tarifario se regenera para volver a coincidir.")
preg("¿Qué significa la talla UNI?",
     ["Uniforme", "Unitalla", "Único color", "Universitario"], 1,
     "UNI = unitalla: boinas, guantes, corbatas y accesorios.")
preg("En el suéter de botones, ¿para quién es normalmente?",
     ["Para niña", "Para niño", "Unisex en todas las escuelas", "Solo maestras"], 0,
     "El de botones es de niña (tabla rosa) — salvo Margarita Paz Paredes y SABES, donde es unisex.")

# ── Familias (escaleras completas, preguntas automáticas) ────────────────────
FAMILIAS = [
    ("Suéter BÁSICO (sin escuela)", lambda b_, p, e_, n: b_.startswith("sueter claudia"), ""),
    ("Suéter OFICIAL de Preescolar", lambda b_, p, e_, n: n == "Preescolar" and b_.startswith("sueter")
        and "oficial" in p and "margarita" not in b_, "Margarita es excepción a $315."),
    ("Suéter OFICIAL de Primaria", lambda b_, p, e_, n: n == "Primaria" and b_.startswith("sueter")
        and "oficial" in p and "claudia" not in b_, ""),
    ("Suéter OFICIAL de Secundaria", lambda b_, p, e_, n: n == "Secundaria" and b_.startswith("sueter")
        and "oficial" in p, ""),
    ("Suéter OFICIAL de Bachillerato", lambda b_, p, e_, n: n == "Bachillerato" and b_.startswith("sueter")
        and "oficial" in p, ""),
    ("Playera deportiva de Preescolar", lambda b_, p, e_, n: n == "Preescolar" and b_.startswith("playera")
        and "deportiv" in p, ""),
    ("Playera deportiva de Primaria", lambda b_, p, e_, n: n == "Primaria" and b_.startswith("playera")
        and "deportiv" in p and "motolinea" not in b_, "Motolinea es excepción: $235 parejo."),
    ("Playera deportiva de Secundaria", lambda b_, p, e_, n: n == "Secundaria" and b_.startswith("playera")
        and "deportiv" in p, ""),
    ("Playera Polo Blanca", lambda b_, p, e_, n: b_ == "playera polo blanca", ""),
    ("Chamarra BÁSICA Liso", lambda b_, p, e_, n: b_.startswith("chamarra liso"), ""),
    ("Chamarra BÁSICA Punto", lambda b_, p, e_, n: b_.startswith("chamarra punto"), ""),
    ("Chamarra deportiva de Primaria", lambda b_, p, e_, n: n == "Primaria" and b_.startswith("chamarra")
        and "deportivo" in p, ""),
    ("Chaleco BÁSICO (sin escuela)", lambda b_, p, e_, n: b_.startswith("chaleco claudia"), ""),
    ("Chaleco OFICIAL (con escudo)", lambda b_, p, e_, n: b_.startswith("chaleco") and "oficial" in p, ""),
    ("Camisa Manga Corta Blanca", lambda b_, p, e_, n: b_ == "camisa manga corta blanca", ""),
    ("Camisa Prowear Manga Corta", lambda b_, p, e_, n: b_.startswith("camisa prowear"), ""),
    ("Camisa Manga Larga H Blanca", lambda b_, p, e_, n: b_ == "camisa manga larga h blanca", ""),
    ("Camisa Manga Larga M Blanca", lambda b_, p, e_, n: b_ == "camisa manga larga m blanca", ""),
    ("Camisa Cuello Olán (preescolar)", lambda b_, p, e_, n: b_.startswith("camisa cuello olan"), ""),
    ("Pants 2 piezas LISO", lambda b_, p, e_, n: b_.startswith("pants 2pz liso") and "deportivo" not in p
        and not any(c in b_ for c in ("azul marino", "azul rey", "rojo", "verde", "vino")),
        "Ojo: Az. Marino, Az. Rey, Rojo, Verde y Vino andan en oferta ($175/$190 en 2-16)."),
    ("Pants 2 piezas PUNTO", lambda b_, p, e_, n: b_.startswith("pants 2pz punto") and "deportivo" not in p, ""),
    ("Pants 2pz deportivo de Preescolar", lambda b_, p, e_, n: n == "Preescolar" and b_.startswith("pants 2pz")
        and "deportivo" in p, ""),
    ("Pants 2pz deportivo de Primaria", lambda b_, p, e_, n: n == "Primaria" and b_.startswith("pants 2pz")
        and "deportivo" in p and "motolinea" not in b_, "Motolinea es excepción ($595-$650)."),
    ("Pants 2pz deportivo de Secundaria", lambda b_, p, e_, n: n == "Secundaria" and b_.startswith("pants 2pz")
        and "deportivo" in p and "telesecundaria" not in b_, "Telesec. 454 y 512 son excepción: $650."),
    ("Pants 3pz deportivo de Preescolar", lambda b_, p, e_, n: n == "Preescolar" and b_.startswith("pants 3pz")
        and "deportivo" in p, ""),
    ("Pants 3pz deportivo de Primaria", lambda b_, p, e_, n: n == "Primaria" and b_.startswith("pants 3pz")
        and "deportivo" in p and "motolinea" not in b_, "Motolinea es excepción ($695-$750)."),
    ("Pants 3pz deportivo de Secundaria", lambda b_, p, e_, n: n == "Secundaria" and b_.startswith("pants 3pz")
        and "deportivo" in p and "telesecundaria" not in b_, "Telesec. 454 y 512 son excepción: $750."),
    ("Pants SUELTO Liso", lambda b_, p, e_, n: b_.startswith("pants suelto liso"), ""),
    ("Pants SUELTO Punto", lambda b_, p, e_, n: b_.startswith("pants suelto punto"), ""),
    ("Pants suelto deportivo de Primaria", lambda b_, p, e_, n: n == "Primaria" and b_.startswith("pants suelto")
        and "deportivo" in p, ""),
    ("Pantalón de vestir (colores estándar)", lambda b_, p, e_, n: b_.startswith("pantalon vestir")
        and "gris claro" not in b_ and "gris obscuro" not in b_ and "pata de gallo" not in b_
        and "mujer" not in b_, ""),
    ("Pantalón de vestir Gris (claro/obscuro)", lambda b_, p, e_, n:
        b_.startswith("pantalon vestir gris claro") or b_.startswith("pantalon vestir gris obscuro"), ""),
    ("Pantalón Gales", lambda b_, p, e_, n: b_.startswith("pantalon gales"), ""),
    ("Pantalón Escocés (genérico)", lambda b_, p, e_, n: b_ == "pantalon escoces",
        "Margarita es excepción: 2-8 a $239."),
    ("Falda Gales", lambda b_, p, e_, n: b_.startswith("falda gales"), ""),
    ("Falda Escocesa (genérica)", lambda b_, p, e_, n: b_ == "falda escoces",
        "Margarita es excepción: 2-8 a $239."),
    ("Falda Gris (clara/obscura)", lambda b_, p, e_, n: b_.startswith("falda gris"), ""),
    ("Falda Cuatro Tablas / Tableada / Azul Marino / Vino", lambda b_, p, e_, n:
        b_.startswith("falda cuatro tablas") or b_.startswith("falda tableada")
        or b_ == "falda escolar azul marino" or b_ == "falda vino", "Las 4 comparten escalera."),
    ("Jumper", lambda b_, p, e_, n: b_.startswith("jumper"), ""),
    ("Malla Escolar", lambda b_, p, e_, n: b_.startswith("malla escolar"), ""),
    ("Bata Manga Corta", lambda b_, p, e_, n: b_.startswith("bata manga corta"), ""),
    ("Bata Manga Larga", lambda b_, p, e_, n: b_.startswith("bata manga larga"), ""),
    ("Calceta Escolar", lambda b_, p, e_, n: b_.startswith("calceta escolar"), ""),
    ("Corbata (genérica)", lambda b_, p, e_, n: b_.startswith("corbata") and not e_,
        "La de Conalep es excepción: $125."),
    ("Boina Escolta", lambda b_, p, e_, n: b_.startswith("boina escolta"), ""),
]
for etiqueta, fn, extra in FAMILIAS:
    preguntas_familia(etiqueta, fn, extra)

# ── Excepciones por escuela (las trampas clásicas) ───────────────────────────
pregunta_excepcion(
    "Cliente de TELESECUNDARIA 512 pide pants 2 piezas talla 14: ¿precio?",
    lambda b_, p, e_, n: b_.startswith("pants 2pz") and "telesecundaria 512" in b_, "14",
    "¡Excepción! Telesec. 512 va a $650 parejo. Sin revisar el rojo habrías cobrado $605.",
    lambda b_, p, e_, n: n == "Secundaria" and b_.startswith("pants 2pz") and "deportivo" in p)
pregunta_excepcion(
    "Cliente de UVEG pide pants 3 piezas talla CH: ¿precio?",
    lambda b_, p, e_, n: b_.startswith("pants 3pz") and "uveg" in b_, "CH",
    "¡Excepción! UVEG paga $790 en 3pz. El estándar de bachillerato es $750.",
    lambda b_, p, e_, n: n == "Bachillerato" and b_.startswith("pants 3pz") and "deportivo" in p)
pregunta_excepcion(
    "Cliente de CBTIS 148 pide pants 2 piezas talla CH: ¿precio?",
    lambda b_, p, e_, n: b_.startswith("pants 2pz") and "cbtis" in b_, "CH",
    "¡Excepción! CBTIS y SABES van a $615; Conalep/CECYTE a $650 y UVEG a $690.",
    lambda b_, p, e_, n: n == "Bachillerato" and b_.startswith("pants 2pz") and "deportivo" in p)
pregunta_excepcion(
    "Cliente de MARGARITA PAZ PAREDES pide falda escocesa talla 8: ¿precio?",
    lambda b_, p, e_, n: b_.startswith("falda escoces margarita"), "8",
    "¡Excepción! Margarita paga $239 en 2-8. La genérica sería $215.",
    lambda b_, p, e_, n: b_ == "falda escoces")
pregunta_excepcion(
    "Cliente de MARGARITA PAZ PAREDES (preescolar) pide suéter oficial talla 8: ¿precio?",
    lambda b_, p, e_, n: b_.startswith("sueter") and "margarita" in b_ and "oficial" in p, "8",
    "¡Excepción! Margarita paga $315 en su suéter oficial. El estándar de preescolar es $299.",
    lambda b_, p, e_, n: n == "Preescolar" and b_.startswith("sueter") and "oficial" in p)
pregunta_excepcion(
    "Cliente de COLEGIO MOTOLINEA pide pants 2 piezas talla 8: ¿precio?",
    lambda b_, p, e_, n: b_.startswith("pants 2pz") and "motolinea" in b_, "8",
    "¡Excepción! Motolinea paga $595 en tallas chicas. El estándar de primaria es $485.",
    lambda b_, p, e_, n: n == "Primaria" and b_.startswith("pants 2pz") and "deportivo" in p)
pregunta_excepcion(
    "Cliente de FRANCISCO VILLA pide camisa oficial talla 14: ¿precio?",
    lambda b_, p, e_, n: b_.startswith("camisa") and "francisco villa" in b_, "14",
    "¡Excepción! Francisco Villa: 4-10 $215 · 12-16 $225 · 18-38 $245. La línea oficial estándar es $265.",
    lambda b_, p, e_, n: b_.startswith("camisa") and "oficial" in p and "cuello olan" not in b_)
pregunta_excepcion(
    "Cliente de CONALEP pide corbata: ¿precio?",
    lambda b_, p, e_, n: b_.startswith("corbata") and "conalep" in b_, "UNI",
    "¡Excepción! La corbata (y corbatín) de Conalep cuesta $125. Las genéricas van a $70.",
    lambda b_, p, e_, n: b_.startswith("corbata"))

random.shuffle(PREGUNTAS)

HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reto Tarifario 2026</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, 'Segoe UI', sans-serif;
  background: linear-gradient(135deg, #1B3557, #0F7DB5);
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  color: #fff; padding: 18px;
}
.card {
  position: relative; width: 100%; max-width: 720px; background: rgba(255,255,255,.07);
  border-radius: 18px; padding: 28px; backdrop-filter: blur(6px);
  box-shadow: 0 10px 40px rgba(0,0,0,.35);
}
h1 { font-size: 30px; margin-bottom: 6px; }
.sub { opacity: .85; margin-bottom: 20px; font-size: 15px; }
#btnMudo {
  position: absolute; top: 16px; right: 16px; border: none; border-radius: 8px;
  background: rgba(255,255,255,.15); color: #fff; font-size: 18px;
  padding: 6px 10px; cursor: pointer;
}
input[type=text] {
  width: 100%; padding: 13px 15px; border-radius: 10px; border: none;
  font-size: 17px; margin-bottom: 14px;
}
.modos { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 14px; }
.modo {
  padding: 11px 8px; border: 2px solid transparent; border-radius: 10px;
  background: rgba(255,255,255,.12); color: #fff; font-weight: 700;
  font-size: 14px; cursor: pointer; line-height: 1.35;
}
.modo small { display: block; font-weight: 400; opacity: .75; font-size: 11.5px; }
.modo.sel { border-color: #F8C045; background: rgba(248,192,69,.18); }
button.big {
  width: 100%; padding: 15px; border: none; border-radius: 10px;
  background: #F8C045; color: #4A3500; font-size: 19px; font-weight: 800;
  cursor: pointer; transition: transform .1s;
}
button.big:hover { transform: scale(1.02); }
.top { display: flex; justify-content: space-between; font-size: 14px;
  font-weight: 700; margin-bottom: 12px; opacity: .9; }
.chip {
  display: inline-block; padding: 3px 11px; border-radius: 99px; font-size: 12px;
  font-weight: 800; margin-bottom: 10px; text-transform: uppercase; letter-spacing: .5px;
}
.chip.c-con { background: #1368CE; }
.chip.c-pre { background: #26890C; }
.chip.c-exc { background: #E21B3C; }
.timerbar { height: 10px; background: rgba(255,255,255,.2); border-radius: 5px;
  overflow: hidden; margin-bottom: 18px; }
.timerbar div { height: 100%; background: #F8C045; width: 100%;
  transition: width .1s linear, background .3s; }
.timerbar div.low { background: #E21B3C; }
.pregunta { font-size: 21px; font-weight: 700; line-height: 1.4;
  margin-bottom: 20px; min-height: 60px; }
.ops { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.op {
  padding: 17px 15px; border: none; border-radius: 12px; font-size: 16.5px;
  font-weight: 700; color: #fff; cursor: pointer; text-align: left;
  transition: transform .1s, opacity .2s; line-height: 1.3;
}
.op:hover { transform: scale(1.02); }
.op:nth-child(1) { background: #E21B3C; }
.op:nth-child(2) { background: #1368CE; }
.op:nth-child(3) { background: #D89E00; }
.op:nth-child(4) { background: #26890C; }
.op .fig { font-size: 19px; margin-right: 9px; }
.op.mal { opacity: .25; }
.op.bien { outline: 4px solid #fff; }
.feedback { border-radius: 12px; padding: 15px 18px; margin-top: 16px;
  font-size: 15.5px; line-height: 1.55; }
.feedback.ok { background: #26890C; }
.feedback.err { background: #E21B3C; }
.feedback b { display: block; font-size: 18px; margin-bottom: 6px; }
button.sig {
  margin-top: 14px; width: 100%; padding: 13px; border: none;
  border-radius: 10px; background: #fff; color: #1B3557; font-size: 17px;
  font-weight: 800; cursor: pointer;
}
button.sig:hover { transform: scale(1.01); }
.resultado { text-align: center; }
.resultado .medalla { font-size: 74px; margin: 8px 0; }
.resultado .pts { font-size: 42px; font-weight: 900; color: #F8C045; }
table.tabla { width: 100%; margin: 16px 0; border-collapse: collapse; }
table.tabla td, table.tabla th { padding: 8px 10px; text-align: left;
  border-bottom: 1px solid rgba(255,255,255,.2); font-size: 15px; }
table.tabla th { opacity: .7; font-size: 12.5px; text-transform: uppercase; }
.fallos { text-align: left; margin: 18px 0; }
.fallos h3 { font-size: 17px; margin-bottom: 10px; }
.fallo { background: rgba(0,0,0,.22); border-left: 4px solid #E21B3C;
  border-radius: 8px; padding: 11px 13px; margin-bottom: 9px; }
.fallo .fq { font-weight: 700; font-size: 14.5px; margin-bottom: 4px; }
.fallo .fa { color: #7CE87C; font-weight: 800; font-size: 14px; margin-bottom: 4px; }
.fallo .fe { font-size: 13px; opacity: .85; line-height: 1.45; }
#cuenta {
  position: fixed; inset: 0; display: flex; align-items: center;
  justify-content: center; font-size: 130px; font-weight: 900;
  background: rgba(12,32,58,.8); z-index: 50;
}
.confeti {
  position: fixed; top: -20px; width: 10px; height: 14px; z-index: 99;
  pointer-events: none; animation-name: caer;
  animation-timing-function: linear; animation-fill-mode: forwards;
}
@keyframes caer { to { transform: translateY(108vh) rotate(720deg); } }
.atajos { margin-top: 12px; font-size: 12.5px; opacity: .55; text-align: center; }
.oculto { display: none !important; }
</style>
</head>
<body>
<div class="card">
  <button id="btnMudo" onclick="toggleMudo()" title="Sonido">🔊</button>

  <div id="inicio">
    <h1>🎯 Reto Tarifario</h1>
    <p class="sub">Contra reloj · puntos por velocidad · racha con bono.<br>
    Banco de <b id="nbanco"></b> preguntas — no se repiten hasta agotar el banco.</p>
    <input type="text" id="nombre" placeholder="Tu nombre" maxlength="18">
    <div class="modos">
      <button class="modo" data-m="rapido" onclick="setModo('rapido')">⚡ Rápido<small>10 preguntas · 20s</small></button>
      <button class="modo" data-m="completo" onclick="setModo('completo')">🎓 Completo<small>20 preguntas · 20s</small></button>
      <button class="modo" data-m="practica" onclick="setModo('practica')">🧘 Práctica<small>10 preguntas · sin reloj</small></button>
    </div>
    <button class="big" onclick="empezar()">¡JUGAR!</button>
    <div class="atajos">Teclado: 1-4 para responder · Enter para seguir</div>
    <div id="records"></div>
  </div>

  <div id="juego" class="oculto">
    <div class="top">
      <span id="progreso"></span>
      <span id="rachaTxt"></span>
      <span id="puntosTxt">0 pts</span>
    </div>
    <div class="timerbar" id="timerwrap"><div id="barra"></div></div>
    <div><span class="chip" id="chip"></span></div>
    <div class="pregunta" id="ptexto"></div>
    <div class="ops" id="ops"></div>
    <div id="fb"></div>
  </div>

  <div id="fin" class="oculto resultado"></div>
</div>

<div id="cuenta" class="oculto"></div>

<script>
const BANCO = __PREGUNTAS__;
const FIGS = ['▲','◆','●','■'];
const CLASES = {'Concepto': 'c-con', 'Precio': 'c-pre', 'Excepción': 'c-exc'};
const MODOS = {
  rapido:   {n: 10, t: 20, emoji: '⚡'},
  completo: {n: 20, t: 20, emoji: '🎓'},
  practica: {n: 10, t: 0,  emoji: '🧘'}
};

let modo = localStorage.getItem('reto_modo') in MODOS ? localStorage.getItem('reto_modo') : 'rapido';
let mudo = localStorage.getItem('reto_mudo') === '1';
let jugador = '', qs = [], idx = 0, puntos = 0, racha = 0, aciertos = 0, fallos = [];
let timer = null, t0 = 0, restante = 0, respondible = false, lastTick = null;

// ── Sonidos (WebAudio, sin archivos) ─────────────────────────────
let AC = null;
function actx() { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); return AC; }
function tono(f, d, tipo, vol, delay) {
  if (mudo) return;
  try {
    const c = actx(), o = c.createOscillator(), g = c.createGain();
    o.type = tipo || 'sine'; o.frequency.value = f;
    o.connect(g); g.connect(c.destination);
    const s = c.currentTime + (delay || 0);
    g.gain.setValueAtTime(vol || .15, s);
    g.gain.exponentialRampToValueAtTime(.001, s + d);
    o.start(s); o.stop(s + d);
  } catch (e) {}
}
function sndOk()       { tono(660, .12); tono(880, .22, 'sine', .15, .12); }
function sndMal()      { tono(190, .35, 'sawtooth', .1); }
function sndTick()     { tono(1250, .05, 'square', .05); }
function sndCuenta()   { tono(520, .12, 'square', .1); }
function sndGo()       { tono(820, .25, 'square', .12); }
function sndFin()      { tono(523, .15); tono(784, .3, 'sine', .15, .16); }
function sndPerfecto() { [523, 659, 784, 1047].forEach((f, i) => tono(f, .22, 'sine', .16, i * .14)); }

function toggleMudo() {
  mudo = !mudo;
  localStorage.setItem('reto_mudo', mudo ? '1' : '0');
  pintarMudo();
}
function pintarMudo() { document.getElementById('btnMudo').textContent = mudo ? '🔇' : '🔊'; }

function setModo(m) {
  modo = m;
  localStorage.setItem('reto_modo', m);
  document.querySelectorAll('.modo').forEach(b => b.classList.toggle('sel', b.dataset.m === m));
}

function barajar(a) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ── Preguntas sin repetir entre partidas ─────────────────────────
function elegirPreguntas(n) {
  let vistas = new Set(JSON.parse(localStorage.getItem('reto_vistas') || '[]'));
  if (localStorage.getItem('reto_banco') !== String(BANCO.length)) vistas = new Set();
  const ids = [...BANCO.keys()];
  let nuevas = barajar(ids.filter(i => !vistas.has(i)));
  if (nuevas.length < n) { vistas = new Set(); nuevas = barajar([...ids]); }
  const sel = nuevas.slice(0, n);
  sel.forEach(i => vistas.add(i));
  localStorage.setItem('reto_vistas', JSON.stringify([...vistas]));
  localStorage.setItem('reto_banco', String(BANCO.length));
  return sel.map(i => BANCO[i]);
}

function empezar() {
  jugador = document.getElementById('nombre').value.trim() || 'Anónimo';
  const cfg = MODOS[modo];
  qs = elegirPreguntas(cfg.n).map(q => {
    const orden = barajar([...Array(q.ops.length).keys()]);
    return { q: q.q, exp: q.exp, cat: q.cat,
             ops: orden.map(i => q.ops[i]),
             ok: orden.indexOf(q.ok) };
  });
  idx = 0; puntos = 0; racha = 0; aciertos = 0; fallos = [];
  document.getElementById('inicio').classList.add('oculto');
  document.getElementById('fin').classList.add('oculto');
  document.getElementById('timerwrap').classList.toggle('oculto', !cfg.t);
  cuentaRegresiva(() => {
    document.getElementById('juego').classList.remove('oculto');
    mostrar();
  });
}

function cuentaRegresiva(cb) {
  const el = document.getElementById('cuenta');
  el.classList.remove('oculto');
  let n = 3;
  el.textContent = n; sndCuenta();
  const iv = setInterval(() => {
    n -= 1;
    if (n > 0) { el.textContent = n; sndCuenta(); }
    else {
      clearInterval(iv);
      el.classList.add('oculto');
      sndGo();
      cb();
    }
  }, 700);
}

function mostrar() {
  const q = qs[idx], cfg = MODOS[modo];
  document.getElementById('progreso').textContent = `Pregunta ${idx+1} / ${qs.length}`;
  document.getElementById('puntosTxt').textContent = `${puntos} pts`;
  document.getElementById('rachaTxt').textContent = racha >= 2 ? `🔥 racha x${racha}` : '';
  const chip = document.getElementById('chip');
  chip.textContent = q.cat;
  chip.className = 'chip ' + (CLASES[q.cat] || 'c-con');
  document.getElementById('ptexto').textContent = q.q;
  document.getElementById('fb').innerHTML = '';
  const cont = document.getElementById('ops');
  cont.innerHTML = '';
  q.ops.forEach((op, i) => {
    const b = document.createElement('button');
    b.className = 'op';
    b.innerHTML = `<span class="fig">${FIGS[i]}</span>${op}`;
    b.onclick = () => responder(i);
    cont.appendChild(b);
  });
  respondible = true;
  clearInterval(timer);
  if (cfg.t) {
    restante = cfg.t; t0 = Date.now(); lastTick = null;
    const barra = document.getElementById('barra');
    barra.classList.remove('low');
    barra.style.width = '100%';
    timer = setInterval(() => {
      restante = cfg.t - (Date.now() - t0) / 1000;
      barra.style.width = Math.max(0, restante / cfg.t * 100) + '%';
      if (restante <= 5) {
        barra.classList.add('low');
        const s = Math.ceil(restante);
        if (s > 0 && s !== lastTick) { lastTick = s; sndTick(); }
      }
      if (restante <= 0) responder(-1);
    }, 100);
  }
}

function responder(i) {
  if (!respondible) return;
  respondible = false;
  clearInterval(timer);
  const q = qs[idx], cfg = MODOS[modo];
  document.querySelectorAll('.op').forEach((b, j) => {
    b.onclick = null;
    if (j === q.ok) b.classList.add('bien');
    else b.classList.add('mal');
  });
  const fb = document.getElementById('fb');
  let bloque;
  if (i === q.ok) {
    const bono = cfg.t ? Math.round(500 * Math.max(0, restante) / cfg.t) : 0;
    const extra = racha >= 1 ? Math.min(racha, 5) * 50 : 0;
    const gan = 500 + bono + extra;
    puntos += gan;
    racha += 1; aciertos += 1;
    sndOk();
    bloque = `<div class="feedback ok"><b>✅ ¡Correcto! +${gan} pts${extra ? ` (🔥 +${extra} por racha)` : ''}</b>${q.exp}</div>`;
  } else {
    racha = 0;
    fallos.push(q);
    sndMal();
    const cual = i === -1 ? '⏰ ¡Se acabó el tiempo!' : '❌ Incorrecto';
    bloque = `<div class="feedback err"><b>${cual}</b>La respuesta era: <u>${q.ops[q.ok]}</u>.<br>${q.exp}</div>`;
  }
  // sin prisa: cada quien avanza cuando termina de leer
  bloque += `<button class="sig" onclick="siguiente()">${idx + 1 < qs.length ? 'SIGUIENTE →' : 'VER RESULTADO 🏁'}</button>`;
  fb.innerHTML = bloque;
  document.getElementById('puntosTxt').textContent = `${puntos} pts`;
  document.querySelector('.sig').focus();
}

function siguiente() {
  idx += 1;
  if (idx < qs.length) mostrar();
  else terminar();
}

function medalla(pct) {
  if (pct === 1)   return ['🏆', '¡PERFECTO! Dominas el tarifario.'];
  if (pct >= .8)   return ['🥇', '¡Excelente! Ya casi te lo sabes de memoria.'];
  if (pct >= .6)   return ['🥈', 'Muy bien, sigue practicando las excepciones.'];
  if (pct >= .4)   return ['🥉', 'Vas bien — repasa la guía y vuelve a intentar.'];
  return ['📖', 'Repasa la guía con calma y vuelve a jugar.'];
}

function confeti() {
  const cols = ['#F8C045', '#E21B3C', '#1368CE', '#26890C', '#fff'];
  for (let i = 0; i < 90; i++) {
    const d = document.createElement('div');
    d.className = 'confeti';
    d.style.left = Math.random() * 100 + 'vw';
    d.style.background = cols[i % cols.length];
    d.style.animationDuration = (2 + Math.random() * 2.5) + 's';
    d.style.animationDelay = (Math.random() * .8) + 's';
    document.body.appendChild(d);
    setTimeout(() => d.remove(), 6000);
  }
}

function fallosHtml() {
  if (!fallos.length) return '';
  const items = fallos.map(q =>
    `<div class="fallo"><div class="fq">${q.q}</div><div class="fa">✔ ${q.ops[q.ok]}</div><div class="fe">${q.exp}</div></div>`).join('');
  return `<div class="fallos"><h3>📝 Para repasar (${fallos.length})</h3>${items}</div>`;
}

function terminar() {
  document.getElementById('juego').classList.add('oculto');
  const pct = aciertos / qs.length;
  const [m, msg] = medalla(pct);
  if (pct === 1) { confeti(); sndPerfecto(); } else sndFin();
  const tabla = JSON.parse(localStorage.getItem('reto_tarifario_records') || '[]');
  tabla.push({ n: jugador, p: puntos, f: new Date().toLocaleDateString('es-MX'), m: modo });
  tabla.sort((a, b) => b.p - a.p);
  localStorage.setItem('reto_tarifario_records', JSON.stringify(tabla.slice(0, 10)));
  const fin = document.getElementById('fin');
  fin.classList.remove('oculto');
  fin.innerHTML = `
    <h1>${jugador}</h1>
    <div class="medalla">${m}</div>
    <div class="pts">${puntos} pts</div>
    <p class="sub">${aciertos} de ${qs.length} correctas · ${msg}</p>
    ${fallosHtml()}
    ${tablaRecords()}
    <button class="big" onclick="reiniciar()">JUGAR OTRA VEZ</button>`;
}

function tablaRecords() {
  const tabla = JSON.parse(localStorage.getItem('reto_tarifario_records') || '[]');
  if (!tabla.length) return '';
  const filas = tabla.map((r, i) =>
    `<tr><td>${['🥇','🥈','🥉'][i] || (i+1)}</td><td>${r.n}</td><td>${(MODOS[r.m] || {}).emoji || ''}</td><td>${r.p} pts</td><td>${r.f}</td></tr>`).join('');
  return `<table class="tabla"><tr><th></th><th>Nombre</th><th>Modo</th><th>Puntos</th><th>Fecha</th></tr>${filas}</table>`;
}

function reiniciar() {
  document.getElementById('fin').classList.add('oculto');
  document.getElementById('inicio').classList.remove('oculto');
  document.getElementById('records').innerHTML = tablaRecords();
}

// ── Teclado: 1-4 responde, Enter avanza ──────────────────────────
document.addEventListener('keydown', e => {
  if (document.getElementById('juego').classList.contains('oculto')) return;
  if (respondible && ['1', '2', '3', '4'].includes(e.key)) {
    const n = +e.key - 1;
    if (n < qs[idx].ops.length) responder(n);
  }
});

document.getElementById('nbanco').textContent = BANCO.length;
document.getElementById('records').innerHTML = tablaRecords();
setModo(modo);
pintarMudo();
document.getElementById('nombre').addEventListener('keydown', e => {
  if (e.key === 'Enter') empezar();
});
</script>
</body>
</html>"""


def generate():
    html = HTML.replace("__PREGUNTAS__", json.dumps(PREGUNTAS, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8")
    print(f"Generado: {OUT} ({len(PREGUNTAS)} preguntas en el banco)")


if __name__ == "__main__":
    generate()
