"""
Servidor HTTP minimalista para ESP32/ESP8266 (MicroPython).
Sirve la PWA en / y expone la API en /api/*.
"""

import network
import socket
import ujson
import time
import os

# Estado compartido entre el servidor (hilo 2) y el loop de LEDs (hilo 1)
state = {
    "effect":     "rainbow",
    "r": 255, "g": 0, "b": 0,
    "brightness": 0.6,
    "speed":      30,
    "off":        False,
    "changed":    True,
}

# Referencia al objeto WS2812B; se asigna desde main.py
led_ref = None

_MANIFEST = ujson.dumps({
    "name": "LED Control",
    "short_name": "LEDs",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#09090f",
    "theme_color": "#09090f",
    "icons": [],
})


# ── WiFi ─────────────────────────────────────────────────────────────────────

def setup_wifi(mode, ap_ssid, ap_pass, sta_ssid="", sta_pass=""):
    if mode == "AP":
        return _start_ap(ap_ssid, ap_pass)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(sta_ssid, sta_pass)
    deadline = time.ticks_add(time.ticks_ms(), 20000)
    while not wlan.isconnected():
        if time.ticks_diff(deadline, time.ticks_ms()) < 0:
            print("No pude conectar al WiFi. Iniciando AP de respaldo...")
            return _start_ap(ap_ssid, ap_pass)
        time.sleep_ms(500)
    ip = wlan.ifconfig()[0]
    _print_url(sta_ssid, ip)
    return ip


def _start_ap(ssid, password):
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=ssid, password=password, authmode=3)
    deadline = time.ticks_add(time.ticks_ms(), 10000)
    while not ap.active():
        if time.ticks_diff(deadline, time.ticks_ms()) < 0:
            break
        time.sleep_ms(200)
    ip = ap.ifconfig()[0]
    _print_url(ssid, ip)
    return ip


def _print_url(ssid, ip):
    print("\n╔══════════════════════════════╗")
    print("║  LED Control listo           ║")
    print("║  WiFi : {}".format(ssid).ljust(31) + "║")
    print("║  URL  : http://{}".format(ip).ljust(31) + "║")
    print("╚══════════════════════════════╝\n")


# ── HTTP ─────────────────────────────────────────────────────────────────────

def start_server(port=80):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", port))
    s.listen(3)
    s.settimeout(0.05)   # timeout corto para no bloquear
    return s


def handle(conn):
    try:
        conn.settimeout(3.0)
        raw = _recv(conn)
        if not raw:
            return

        text = raw.decode("utf-8", "ignore")
        first = text.split("\r\n")[0].split(" ")
        if len(first) < 2:
            return
        method, path = first[0], first[1].split("?")[0]

        body = text.split("\r\n\r\n", 1)[1].strip() if "\r\n\r\n" in text else ""

        if method == "GET" and path == "/":
            _serve_file(conn, "index.html", "text/html; charset=utf-8")

        elif method == "GET" and path == "/manifest.json":
            _send_json(conn, _MANIFEST)

        elif method == "GET" and path == "/api/status":
            _send_json(conn, ujson.dumps(state))

        elif method == "POST" and path == "/api/cmd":
            _handle_cmd(conn, body)

        else:
            conn.send(b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n")

    except Exception as e:
        print("HTTP err:", e)
    finally:
        try:
            conn.close()
        except:
            pass


def _recv(conn):
    data = b""
    try:
        while True:
            chunk = conn.recv(512)
            if not chunk:
                break
            data += chunk
            if len(chunk) < 512:
                break
    except OSError:
        pass
    return data


def _serve_file(conn, path, ctype):
    try:
        size = os.stat(path)[6]
        header = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: {}\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n\r\n"
        ).format(ctype, size)
        conn.send(header.encode())
        with open(path, "rb") as f:
            while True:
                chunk = f.read(512)
                if not chunk:
                    break
                conn.write(chunk)
    except OSError:
        conn.send(b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\nFile not found")


def _send_json(conn, body):
    h = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: application/json\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "Content-Length: {}\r\n"
        "Connection: close\r\n\r\n"
    ).format(len(body))
    conn.send((h + body).encode())


def _handle_cmd(conn, body):
    try:
        cmd = ujson.loads(body)
        ct = cmd.get("cmd", "")

        if ct == "effect":
            state["effect"] = cmd.get("name", "rainbow")
            state["off"] = False
        elif ct == "color":
            state["r"] = int(cmd.get("r", 255))
            state["g"] = int(cmd.get("g", 0))
            state["b"] = int(cmd.get("b", 0))
            state["effect"] = "solid"
            state["off"] = False
        elif ct == "brightness":
            state["brightness"] = max(0.0, min(1.0, float(cmd.get("value", 0.6))))
        elif ct == "speed":
            state["speed"] = max(5, min(200, int(cmd.get("value", 30))))
        elif ct == "off":
            state["off"] = True

        state["changed"] = True
        # Interrumpir el efecto en curso para aplicar el cambio de inmediato
        if led_ref is not None:
            led_ref.stop_flag = True

        _send_json(conn, ujson.dumps({"ok": True, "effect": state["effect"]}))
    except Exception as e:
        print("cmd err:", e)
        conn.send(b"HTTP/1.1 400 Bad Request\r\n\r\n")
