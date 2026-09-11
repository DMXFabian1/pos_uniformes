"""Ventana de escritorio para manejar el bot sin usar la terminal.

Usa Tkinter, que viene incluido con Python: no hace falta instalar nada más. Arranca el bot y el
panel como procesos aparte y muestra su salida en vivo. Al detener, envía la misma interrupción
que Ctrl+C para que el bot guarde los datos pendientes antes de cerrar.
"""
from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable

COLOR = {
    "fondo": "#12181f", "panel": "#1a222c", "borde": "#2a3542", "texto": "#e8edf3", "suave": "#9aa7b6",
    "acento": "#3987e5", "ok": "#0ca30c", "aviso": "#fab219", "error": "#d03b3b", "log": "#0d1218",
}
PANEL_URL = "http://127.0.0.1:8787"


def _python() -> str:
    return sys.executable


def _entorno() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


class Proceso:
    """Un proceso hijo (bot o panel) cuya salida se vuelca en una cola."""

    def __init__(self, nombre: str, args: list[str], cwd: Path, salida: queue.Queue):
        self.nombre = nombre
        self.args = args
        self.cwd = cwd
        self.salida = salida
        self.proc: subprocess.Popen | None = None

    @property
    def vivo(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def iniciar(self) -> None:
        if self.vivo:
            return
        kwargs: dict[str, Any] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            [_python(), "-m", "scalper.cli", *self.args], cwd=str(self.cwd), env=_entorno(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            bufsize=1, **kwargs)
        threading.Thread(target=self._leer, daemon=True).start()
        self.salida.put((self.nombre, f"— {self.nombre} iniciado —"))

    def _leer(self) -> None:
        proc = self.proc
        if proc is None or proc.stdout is None:
            return
        for linea in proc.stdout:
            self.salida.put((self.nombre, linea.rstrip()))
        self.salida.put((self.nombre, f"— {self.nombre} detenido —"))

    def detener(self, espera: float = 25.0) -> None:
        """Pide un cierre limpio (como Ctrl+C) para que el bot vuelque los datos a disco."""
        if not self.vivo or self.proc is None:
            return
        self.salida.put((self.nombre, f"— deteniendo {self.nombre}, guardando datos… —"))
        try:
            if sys.platform == "win32":
                os.kill(self.proc.pid, signal.CTRL_BREAK_EVENT)
            else:
                self.proc.send_signal(signal.SIGINT)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.proc.wait(timeout=espera)
        except subprocess.TimeoutExpired:
            self.salida.put((self.nombre, "— no respondió a tiempo; cierre forzado —"))
            self.proc.kill()


def _dato_mas_reciente(data_dir: Path) -> float | None:
    """Momento del archivo de datos más nuevo, para saber si el bot está escribiendo."""
    mejor = None
    for tabla in ("book_deltas", "quotes", "crypto_prices"):
        d = data_dir / tabla
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.parquet"), key=lambda x: x.stat().st_mtime, reverse=True)[:1]:
            t = p.stat().st_mtime
            mejor = t if mejor is None else max(mejor, t)
    return mejor


def lanzar(proyecto: Path, config: str = "config.yaml", cerrar_tras_ms: int | None = None) -> int:
    """Abre la ventana. `cerrar_tras_ms` solo se usa en las pruebas automáticas."""
    try:
        import tkinter as tk
        from tkinter import scrolledtext, ttk
    except ImportError:
        print("Tkinter no está disponible en esta instalación de Python.\n"
              "En Windows, reinstala Python marcando 'tcl/tk and IDLE'.\n"
              "Mientras tanto puedes usar: scalper paper  y  scalper dashboard")
        return 1

    cola: queue.Queue = queue.Queue()
    bot = Proceso("bot", ["-c", config, "--log-file", "logs/bot.log", "paper"], proyecto, cola)
    panel = Proceso("panel", ["-c", config, "--log-file", "logs/panel.log", "dashboard"], proyecto, cola)
    data_dir = proyecto / "data"

    raiz = tk.Tk()
    raiz.title("Scalper Polymarket")
    raiz.geometry("1020x680")
    raiz.minsize(820, 520)
    raiz.configure(bg=COLOR["fondo"])

    estilo = ttk.Style(raiz)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass
    fuente = "Segoe UI" if sys.platform == "win32" else "Helvetica"
    estilo.configure("TFrame", background=COLOR["fondo"])
    estilo.configure("Panel.TFrame", background=COLOR["panel"])
    estilo.configure("TLabel", background=COLOR["fondo"], foreground=COLOR["texto"], font=(fuente, 10))
    estilo.configure("Suave.TLabel", background=COLOR["panel"], foreground=COLOR["suave"], font=(fuente, 9))
    estilo.configure("Dato.TLabel", background=COLOR["panel"], foreground=COLOR["texto"], font=("Consolas", 13, "bold"))
    estilo.configure("Titulo.TLabel", background=COLOR["fondo"], foreground=COLOR["texto"], font=(fuente, 15, "bold"))
    estilo.configure("TNotebook", background=COLOR["fondo"], borderwidth=0)
    estilo.configure("TNotebook.Tab", borderwidth=0)
    estilo.layout("TNotebook", [("TNotebook.client", {"sticky": "nswe"})])
    estilo.configure("TNotebook.Tab", background=COLOR["panel"], foreground=COLOR["suave"],
                     padding=(16, 7), font=(fuente, 10))
    estilo.map("TNotebook.Tab", background=[("selected", COLOR["fondo"])], foreground=[("selected", COLOR["texto"])])

    def boton(padre: tk.Widget, texto: str, orden: Callable[[], None], color: str = COLOR["acento"]) -> tk.Button:
        b = tk.Button(padre, text=texto, command=orden, bg=color, fg="#ffffff", activebackground=color,
                      activeforeground="#ffffff", relief="flat", font=(fuente, 10, "bold"), cursor="hand2",
                      padx=14, pady=8, borderwidth=0, highlightthickness=0)
        return b

    # ---------------- cabecera
    cabecera = ttk.Frame(raiz, padding=(16, 14, 16, 8))
    cabecera.pack(fill="x")
    ttk.Label(cabecera, text="Scalper Polymarket", style="Titulo.TLabel").pack(side="left")
    estado_var = tk.StringVar(value="detenido")
    punto = tk.Canvas(cabecera, width=12, height=12, bg=COLOR["fondo"], highlightthickness=0)
    circulo = punto.create_oval(2, 2, 11, 11, fill=COLOR["error"], outline="")
    punto.pack(side="left", padx=(16, 6))
    ttk.Label(cabecera, textvariable=estado_var).pack(side="left")
    ttk.Label(cabecera, text="paper trading · sin dinero real", foreground=COLOR["suave"]).pack(side="right")

    # ---------------- tarjetas de estado
    tarjetas = ttk.Frame(raiz, padding=(16, 0, 16, 10))
    tarjetas.pack(fill="x")
    valores: dict[str, tk.StringVar] = {}
    for i, (clave, etiqueta) in enumerate((("mercados", "Mercados seguidos"), ("senales", "Señales detectadas"),
                                           ("btc", "Bitcoin"), ("ventanas", "Ventanas de cripto"),
                                           ("datos", "Último dato"))):
        tarjeta = ttk.Frame(tarjetas, style="Panel.TFrame", padding=(12, 9))
        tarjeta.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
        tarjetas.columnconfigure(i, weight=1)
        valores[clave] = tk.StringVar(value="–")
        ttk.Label(tarjeta, text=etiqueta, style="Suave.TLabel").pack(anchor="w")
        ttk.Label(tarjeta, textvariable=valores[clave], style="Dato.TLabel").pack(anchor="w")

    # ---------------- botones
    barra = ttk.Frame(raiz, padding=(16, 4, 16, 10))
    barra.pack(fill="x")

    def refrescar_botones() -> None:
        if bot.vivo:
            b_bot.configure(text="Detener bot", bg=COLOR["error"], activebackground=COLOR["error"])
            estado_var.set("funcionando")
            punto.itemconfig(circulo, fill=COLOR["ok"])
        else:
            b_bot.configure(text="Iniciar bot", bg=COLOR["ok"], activebackground=COLOR["ok"])
            estado_var.set("detenido")
            punto.itemconfig(circulo, fill=COLOR["error"])
        b_panel.configure(text="Cerrar panel" if panel.vivo else "Abrir panel")

    def alternar_bot() -> None:
        if bot.vivo:
            threading.Thread(target=lambda: (bot.detener(), raiz.after(0, refrescar_botones)), daemon=True).start()
        else:
            cuaderno.select(0)
            texto_log.configure(state="normal")
            texto_log.delete("1.0", "end")
            texto_log.configure(state="disabled")
            bot.iniciar()
        refrescar_botones()

    def alternar_panel() -> None:
        if panel.vivo:
            threading.Thread(target=lambda: (panel.detener(5), raiz.after(0, refrescar_botones)), daemon=True).start()
        else:
            panel.iniciar()
            raiz.after(3000, lambda: webbrowser.open(PANEL_URL))
        refrescar_botones()

    def ver_informes() -> None:
        cuaderno.select(1)
        texto_inf.configure(state="normal")
        texto_inf.delete("1.0", "end")
        texto_inf.insert("end", "Generando informes…\n")
        texto_inf.configure(state="disabled")

        def trabajo() -> None:
            try:
                r = subprocess.run([_python(), "-m", "scalper.cli", "-c", config, "overview"], cwd=str(proyecto),
                                   env=_entorno(), capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=180)
                out = r.stdout + (("\n" + r.stderr) if r.stderr else "")
            except Exception as e:  # noqa: BLE001
                out = f"No se pudieron generar los informes: {e}"
            raiz.after(0, lambda: _pintar(texto_inf, out))

        threading.Thread(target=trabajo, daemon=True).start()

    def _pintar(widget: Any, contenido: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", contenido)
        widget.configure(state="disabled")

    def abrir_carpeta() -> None:
        d = data_dir if data_dir.exists() else proyecto
        if sys.platform == "win32":
            os.startfile(str(d))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(d)])
        else:
            subprocess.Popen(["xdg-open", str(d)])

    b_bot = boton(barra, "Iniciar bot", alternar_bot, COLOR["ok"])
    b_bot.pack(side="left")
    b_panel = boton(barra, "Abrir panel", alternar_panel)
    b_panel.pack(side="left", padx=8)
    boton(barra, "Ver informes", ver_informes, "#3c4858").pack(side="left")
    boton(barra, "Carpeta de datos", abrir_carpeta, "#3c4858").pack(side="left", padx=8)

    # ---------------- pestañas
    cuaderno = ttk.Notebook(raiz)
    cuaderno.pack(fill="both", expand=True, padx=16, pady=(0, 14))
    marco_log = ttk.Frame(cuaderno)
    marco_inf = ttk.Frame(cuaderno)
    cuaderno.add(marco_log, text="  Actividad  ")
    cuaderno.add(marco_inf, text="  Informes  ")

    def _oscurecer(st: Any) -> None:
        """Quita el marco claro que Tk dibuja por defecto y oscurece la barra de desplazamiento."""
        st.configure(highlightthickness=0, borderwidth=0, bd=0, padx=10, pady=8)
        try:                                   # ScrolledText envuelve el texto en un Frame propio
            st.master.configure(bg=COLOR["log"], borderwidth=0, highlightthickness=0)
        except tk.TclError:
            pass
        for hijo in st.master.winfo_children():
            if isinstance(hijo, tk.Scrollbar):
                hijo.configure(bg=COLOR["panel"], troughcolor=COLOR["log"], activebackground=COLOR["borde"],
                               highlightthickness=0, borderwidth=0, relief="flat", width=12)

    texto_log = scrolledtext.ScrolledText(marco_log, bg=COLOR["log"], fg=COLOR["texto"], insertbackground=COLOR["texto"],
                                          font=("Consolas", 9), relief="flat", borderwidth=0, wrap="none")
    texto_log.pack(fill="both", expand=True)
    _oscurecer(texto_log)
    texto_log.insert("end", "El bot está detenido.\n\n", "suave")
    texto_log.insert("end", "Pulsa «Iniciar bot» para empezar a recolectar y simular.\n"
                            "Aquí verás su actividad en vivo.\n\n"
                            "Nada de esto usa dinero real: el bot no firma órdenes ni maneja una wallet.\n", "suave")
    texto_log.configure(state="disabled")
    for nombre, color in (("ok", COLOR["ok"]), ("aviso", COLOR["aviso"]), ("error", COLOR["error"]),
                          ("suave", COLOR["suave"])):
        texto_log.tag_configure(nombre, foreground=color)

    texto_inf = scrolledtext.ScrolledText(marco_inf, bg=COLOR["log"], fg=COLOR["texto"], font=("Consolas", 9),
                                          relief="flat", borderwidth=0, wrap="none")
    texto_inf.pack(fill="both", expand=True)
    _oscurecer(texto_inf)
    texto_inf.tag_configure("suave", foreground=COLOR["suave"])
    texto_inf.insert("end", "Pulsa «Ver informes» para generarlos.\n\n"
                            "Incluye: qué datos hay guardados, el estudio del arrastre entre ventanas de cripto,\n"
                            "los resultados por tipo de señal, las wallets con historial, los modelos\n"
                            "aprendidos y el uso de disco.\n", "suave")
    texto_inf.configure(state="disabled")

    # ---------------- bucle de actualización
    def procesar_cola() -> None:
        pendientes = 0
        while pendientes < 200:
            try:
                origen, linea = cola.get_nowait()
            except queue.Empty:
                break
            pendientes += 1
            etiqueta = "suave"
            bajo = linea.lower()
            if "error" in bajo or "falló" in bajo or "traceback" in bajo:
                etiqueta = "error"
            elif "warning" in bajo or "aviso" in bajo or "desconect" in bajo:
                etiqueta = "aviso"
            elif "conectado" in bajo or "cierre" in bajo or "—" in linea:
                etiqueta = "ok"
            texto_log.configure(state="normal")
            texto_log.insert("end", (f"[{origen}] " if origen != "bot" else "") + linea + "\n", etiqueta)
            # no dejar crecer el buffer sin límite
            if int(texto_log.index("end-1c").split(".")[0]) > 3000:
                texto_log.delete("1.0", "1000.0")
            texto_log.see("end")
            texto_log.configure(state="disabled")
            _extraer_estado(linea)
        raiz.after(200, procesar_cola)

    def _extraer_estado(linea: str) -> None:
        if "mercados activos=" in linea:
            valores["mercados"].set(linea.split("mercados activos=")[1].split()[0])
        if "discovery:" in linea and "mercados" in linea:
            try:
                valores["mercados"].set(linea.split("discovery:")[1].split()[0])
            except IndexError:
                pass
        if "btc=" in linea:
            valores["btc"].set("$" + linea.split("btc=")[1].split()[0])
        if "updown=" in linea:
            try:
                v = linea.split("updown=")[1].split()[0]
                s = linea.split("strikes=")[1].split()[0] if "strikes=" in linea else "0"
                valores["ventanas"].set(f"{v} · {s} con apertura")
            except IndexError:
                pass
        if "'signals':" in linea:
            try:
                valores["senales"].set(linea.split("'signals':")[1].split(",")[0].strip())
            except IndexError:
                pass

    def refrescar_datos() -> None:
        t = _dato_mas_reciente(data_dir)
        if t is None:
            valores["datos"].set("sin datos")
        else:
            seg = int(time.time() - t)
            valores["datos"].set(f"hace {seg} s" if seg < 90 else f"hace {seg // 60} min")
        refrescar_botones()
        raiz.after(5000, refrescar_datos)

    def al_cerrar() -> None:
        if bot.vivo or panel.vivo:
            from tkinter import messagebox
            if not messagebox.askokcancel("Cerrar", "El bot está funcionando.\n\n"
                                                    "Se detendrá guardando los datos pendientes. ¿Cerrar?"):
                return
            estado_var.set("guardando datos…")
            raiz.update()
            panel.detener(5)
            bot.detener(25)
        raiz.destroy()

    raiz.protocol("WM_DELETE_WINDOW", al_cerrar)
    refrescar_botones()
    procesar_cola()
    refrescar_datos()
    if cerrar_tras_ms is not None:
        raiz.after(cerrar_tras_ms, raiz.destroy)
    raiz.mainloop()
    return 0
