"""Contador de afluencia: personas que entran a la tienda, por hora, desde el DVR.

Corre en la PC servidor (o en la Mac para probar) con su propio entorno
(`afluencia/requirements.txt`: ultralytics + opencv + psycopg). Por cada cámara
de `afluencia.json` abre el stream principal del DVR, detecta personas con
YOLOv8n, las sigue con ByteTrack y:

  - modo "linea": cuenta cruces de la línea de la puerta (entra / sale).
  - modo "paso":  cuenta personas distintas vistas (quienes pasan por fuera).

Cada minuto suma lo acumulado en la tabla `afluencia_hora` de Postgres
(upsert aditivo por cámara y hora). Sin base (`--sin-db`) solo imprime.

Uso:
    python contador_afluencia.py                 # corre indefinidamente
    python contador_afluencia.py --calibrar      # guarda un cuadro por cámara con cuadrícula y línea
    python contador_afluencia.py --sin-db --duracion 120 --debug-frames ./eventos
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from conteo import AcumuladorHora, ContadorLinea, ContadorPaso, Linea, pies

AQUI = Path(__file__).resolve().parent
RAIZ_POS = AQUI.parent
log = logging.getLogger("afluencia")


# --- configuración -------------------------------------------------------------

def _leer_env_file(path: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    if not path.exists():
        return valores
    for linea in path.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        valores[k.strip()] = v.strip().strip('"').strip("'")
    return valores


def _env(nombre: str, default: str = "") -> str:
    valor = os.getenv(nombre)
    if valor is not None:
        return valor.strip()
    return _leer_env_file(RAIZ_POS / "pos_uniformes.env").get(nombre, default).strip()


def credenciales_dvr() -> tuple[str, int, str, str]:
    """(host, puerto rtsp, usuario, contraseña) desde data/dvr_settings.json o el env."""
    host = _env("POS_UNIFORMES_DVR_HOST")
    user = _env("POS_UNIFORMES_DVR_USER")
    password = _env("POS_UNIFORMES_DVR_PASSWORD")
    puerto = 554
    # El kiosko instalado (exe) guarda su config en %APPDATA%\PresupuestosSatelite;
    # en desarrollo (Mac) queda junto al código. Se toma la primera que exista.
    candidatos = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidatos.append(Path(appdata) / "PresupuestosSatelite" / "data" / "dvr_settings.json")
    candidatos.append(RAIZ_POS / "data" / "dvr_settings.json")
    for ajustes in candidatos:
        if not ajustes.exists():
            continue
        try:
            data = json.loads(ajustes.read_text(encoding="utf-8"))
            host = data.get("host") or host
            user = data.get("user") or user
            password = data.get("password") or password
            puerto = int(data.get("rtsp_port") or puerto)
            log.info("DVR tomado de %s", ajustes)
            break
        except Exception as exc:  # noqa: BLE001
            log.warning("%s ilegible: %s", ajustes, exc)
    if not host or not user:
        raise SystemExit("Falta la configuración del DVR (data/dvr_settings.json o POS_UNIFORMES_DVR_*).")
    return host, puerto, user, password


def url_rtsp(host: str, puerto: int, user: str, password: str, canal: int) -> str:
    return (
        f"rtsp://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{puerto}"
        f"/cam/realmonitor?channel={canal}&subtype=0"
    )


def cargar_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"No existe {path}. Copia afluencia.json.example y ajusta las líneas.")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg.setdefault("fps_proceso", 4)
    cfg.setdefault("modelo", "yolov8n.pt")
    cfg.setdefault("imgsz", 416)
    cfg.setdefault("conf", 0.35)
    cfg.setdefault("intervalo_guardado_s", 60)
    if not cfg.get("camaras"):
        raise SystemExit("afluencia.json no tiene cámaras.")
    return cfg


# --- almacenamiento ------------------------------------------------------------

class AlmacenPostgres:
    """Upsert aditivo en afluencia_hora. Reconecta solo si la conexión se cae."""

    def __init__(self) -> None:
        self._conn = None

    def _dsn(self) -> str:
        return (
            f"host={_env('POS_UNIFORMES_DB_HOST', 'localhost')} "
            f"port={_env('POS_UNIFORMES_DB_PORT', '5432')} "
            f"dbname={_env('POS_UNIFORMES_DB_NAME', 'pos_uniformes')} "
            f"user={_env('POS_UNIFORMES_DB_USER', 'postgres')} "
            f"password={_env('POS_UNIFORMES_DB_PASSWORD', 'postgres')} "
            "connect_timeout=5"
        )

    def _conectar(self):
        import psycopg

        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self._dsn(), autocommit=True)
        return self._conn

    def guardar(self, filas: list[tuple[str, datetime, int, int, int]]) -> None:
        if not filas:
            return
        sql = (
            "INSERT INTO afluencia_hora (camara, hora, entradas, salidas, pasan, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, now()) "
            "ON CONFLICT (camara, hora) DO UPDATE SET "
            "entradas = afluencia_hora.entradas + EXCLUDED.entradas, "
            "salidas = afluencia_hora.salidas + EXCLUDED.salidas, "
            "pasan = afluencia_hora.pasan + EXCLUDED.pasan, "
            "updated_at = now()"
        )
        try:
            conn = self._conectar()
            with conn.cursor() as cur:
                for camara, hora, e, s, p in filas:
                    cur.execute(sql, (camara, hora.astimezone(), e, s, p))
        except Exception as exc:  # noqa: BLE001
            log.error("No se pudo guardar en Postgres: %s", exc)
            self._conn = None
            raise


class AlmacenConsola:
    def guardar(self, filas) -> None:
        for camara, hora, e, s, p in filas:
            log.info("[%s %s] entradas=%s salidas=%s pasan=%s", camara, hora.strftime("%H:%M"), e, s, p)


# --- hilo por cámara -----------------------------------------------------------

class HiloCamara(threading.Thread):
    def __init__(self, cam: dict, url: str, cfg: dict, acumulador: AcumuladorHora, lock: threading.Lock, parar: threading.Event, debug_dir: Path | None) -> None:
        super().__init__(daemon=True, name=f"cam-{cam['nombre']}")
        self.cam = cam
        self.url = url
        self.cfg = cfg
        self.acumulador = acumulador
        self.lock = lock
        self.parar = parar
        self.debug_dir = debug_dir
        self.modo = cam.get("modo", "linea")
        if self.modo == "linea":
            x1, y1, x2, y2 = cam["linea"]
            self.contador_linea = ContadorLinea(Linea(x1, y1, x2, y2, cam.get("lado_dentro", "abajo")))
        else:
            self.contador_paso = ContadorPaso()

    def run(self) -> None:
        import cv2
        from ultralytics import YOLO

        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        modelo = YOLO(self.cfg["modelo"])
        nombre = self.cam["nombre"]
        while not self.parar.is_set():
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                log.warning("%s: no abre el stream, reintento en 10 s", nombre)
                self.parar.wait(10)
                continue
            log.info("%s: stream abierto (modo %s)", nombre, self.modo)
            fps_fuente = cap.get(cv2.CAP_PROP_FPS) or 15
            salto = max(1, int(round(fps_fuente / float(self.cfg["fps_proceso"]))))
            n = 0
            fallos = 0
            while not self.parar.is_set():
                ok, frame = cap.read()
                if not ok:
                    fallos += 1
                    if fallos > 30:
                        log.warning("%s: stream caído, reconectando", nombre)
                        break
                    continue
                fallos = 0
                n += 1
                if n % salto:
                    continue
                self._procesar(modelo, frame, nombre)
            cap.release()

    def _procesar(self, modelo, frame, nombre: str) -> None:
        alto, ancho = frame.shape[:2]
        res = modelo.track(
            frame,
            persist=True,
            classes=[0],
            conf=float(self.cfg["conf"]),
            imgsz=int(self.cfg["imgsz"]),
            tracker="bytetrack.yaml",
            verbose=False,
        )[0]
        if res.boxes is None or res.boxes.id is None:
            ids: list[int] = []
            puntos: list[tuple[int, float, float]] = []
        else:
            ids = [int(i) for i in res.boxes.id.tolist()]
            cajas = res.boxes.xyxy.tolist()
            puntos = [(tid, *pies(tuple(c), ancho, alto)) for tid, c in zip(ids, cajas)]
        ahora = datetime.now()
        if self.modo == "linea":
            eventos = self.contador_linea.actualizar(puntos)
            self.contador_linea.olvidar_ausentes(set(ids))
            if eventos:
                entradas = sum(1 for _, e in eventos if e == "entra")
                salidas = len(eventos) - entradas
                with self.lock:
                    self.acumulador.agregar(nombre, ahora, entradas=entradas, salidas=salidas)
                log.info("%s: %s", nombre, ", ".join(f"#{tid} {e}" for tid, e in eventos))
                self._debug(res, frame, nombre, eventos)
        else:
            nuevos = self.contador_paso.actualizar(ids)
            if nuevos:
                with self.lock:
                    self.acumulador.agregar(nombre, ahora, pasan=nuevos)

    def _debug(self, res, frame, nombre: str, eventos) -> None:
        if self.debug_dir is None:
            return
        import cv2

        img = res.plot()
        alto, ancho = img.shape[:2]
        if self.modo == "linea":
            ln = self.contador_linea.linea
            cv2.line(img, (int(ln.x1 * ancho), int(ln.y1 * alto)), (int(ln.x2 * ancho), int(ln.y2 * alto)), (0, 255, 255), 3)
        texto = " ".join(f"{e}" for _, e in eventos)
        cv2.putText(img, texto, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(self.debug_dir / f"{nombre}_{datetime.now():%H%M%S}_{texto.replace(' ', '_')}.jpg"), img)


# --- calibración ---------------------------------------------------------------

def calibrar(cfg: dict, urls: dict[str, str], salida: Path) -> None:
    import cv2

    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    salida.mkdir(parents=True, exist_ok=True)
    for cam in cfg["camaras"]:
        nombre = cam["nombre"]
        cap = cv2.VideoCapture(urls[nombre], cv2.CAP_FFMPEG)
        frame = None
        for _ in range(40):
            ok, f = cap.read()
            if ok:
                frame = f
        cap.release()
        if frame is None:
            log.warning("%s: sin cuadro", nombre)
            continue
        frame = cv2.resize(frame, (1280, 720))
        h, w = frame.shape[:2]
        for i in range(1, 10):
            x, y = int(w * i / 10), int(h * i / 10)
            cv2.line(frame, (x, 0), (x, h), (0, 255, 255), 1)
            cv2.line(frame, (0, y), (w, y), (0, 255, 255), 1)
            cv2.putText(frame, f"{i/10:.1f}", (x + 3, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(frame, f"{i/10:.1f}", (3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        if cam.get("modo", "linea") == "linea":
            x1, y1, x2, y2 = cam["linea"]
            cv2.line(frame, (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h)), (0, 0, 255), 4)
            cv2.putText(frame, f"dentro = {cam.get('lado_dentro', 'abajo')}", (20, h - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        cv2.putText(frame, f"{nombre} ({cam.get('modo', 'linea')})", (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
        destino = salida / f"{nombre}.jpg"
        cv2.imwrite(str(destino), frame)
        log.info("calibración guardada: %s", destino)


# --- main ----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Contador de afluencia con las cámaras del DVR")
    parser.add_argument("--config", default=str(AQUI / "afluencia.json"))
    parser.add_argument("--calibrar", action="store_true", help="guarda un cuadro por cámara con cuadrícula y línea, y sale")
    parser.add_argument("--sin-db", action="store_true", help="no escribe en Postgres, solo imprime")
    parser.add_argument("--duracion", type=int, default=0, help="segundos a correr (0 = indefinido)")
    parser.add_argument("--debug-frames", default="", help="carpeta donde guardar un cuadro por cada entra/sale")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    cfg = cargar_config(Path(args.config))
    host, puerto, user, password = credenciales_dvr()
    urls = {cam["nombre"]: url_rtsp(host, puerto, user, password, int(cam["canal"])) for cam in cfg["camaras"]}

    if args.calibrar:
        calibrar(cfg, urls, AQUI / "calibracion")
        return 0

    # Descarga/carga el modelo una sola vez antes de lanzar los hilos (si cada
    # hilo lo hiciera a la vez, se pisarían al bajar el archivo).
    from ultralytics import YOLO

    YOLO(cfg["modelo"])

    almacen = AlmacenConsola() if args.sin_db else AlmacenPostgres()
    acumulador = AcumuladorHora()
    lock = threading.Lock()
    parar = threading.Event()
    debug_dir = Path(args.debug_frames) if args.debug_frames else None
    hilos = [HiloCamara(cam, urls[cam["nombre"]], cfg, acumulador, lock, parar, debug_dir) for cam in cfg["camaras"]]
    for h in hilos:
        h.start()

    inicio = time.time()
    ultimo_guardado = time.time()
    try:
        while not parar.is_set():
            time.sleep(1)
            if time.time() - ultimo_guardado >= cfg["intervalo_guardado_s"]:
                ultimo_guardado = time.time()
                with lock:
                    filas = acumulador.vaciar()
                if filas:
                    try:
                        almacen.guardar(filas)
                    except Exception:  # noqa: BLE001
                        # No perder lo contado: vuelve al acumulador y se reintenta.
                        with lock:
                            for camara, hora, e, s, p in filas:
                                acumulador.agregar(camara, hora, entradas=e, salidas=s, pasan=p)
            if args.duracion and time.time() - inicio >= args.duracion:
                parar.set()
    except KeyboardInterrupt:
        parar.set()
    for h in hilos:
        h.join(timeout=5)
    with lock:
        filas = acumulador.vaciar()
    if filas:
        try:
            almacen.guardar(filas)
        except Exception:  # noqa: BLE001
            log.error("Se perdieron %d filas al cerrar", len(filas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
