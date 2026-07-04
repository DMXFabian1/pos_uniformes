"""
Controlador WS2812B para ESP32 / ESP8266 en MicroPython
Requiere el módulo `neopixel` (incluido en MicroPython oficial).
"""

import neopixel
import machine
import time
import math
import random


class WS2812B:
    """Controlador principal con todos los efectos."""

    def __init__(self, pin=4, count=60, brightness=0.6):
        self.pin = machine.Pin(pin)
        self.count = count
        self.brightness = min(1.0, max(0.0, float(brightness)))
        self.np = neopixel.NeoPixel(self.pin, count)
        self.clear()

    # ── Utilidades internas ──────────────────────────────────────────────────

    def _dim(self, r, g, b, factor=1.0):
        """Aplica brillo global y factor adicional a un color RGB."""
        f = self.brightness * factor
        return (int(r * f), int(g * f), int(b * f))

    def _set(self, i, r, g, b, factor=1.0):
        if 0 <= i < self.count:
            self.np[i] = self._dim(r, g, b, factor)

    def _fade_pixel(self, i, amount=30):
        """Oscurece un pixel existente."""
        r, g, b = self.np[i]
        self.np[i] = (max(0, r - amount), max(0, g - amount), max(0, b - amount))

    def _blend(self, c1, c2, t):
        """Mezcla lineal entre dos colores (t: 0.0-1.0)."""
        return (
            int(c1[0] * (1 - t) + c2[0] * t),
            int(c1[1] * (1 - t) + c2[1] * t),
            int(c1[2] * (1 - t) + c2[2] * t),
        )

    def wheel(self, pos):
        """Rueda de colores del arco iris (0-255 → RGB)."""
        pos = int(pos) % 256
        if pos < 85:
            return (255 - pos * 3, pos * 3, 0)
        if pos < 170:
            pos -= 85
            return (0, 255 - pos * 3, pos * 3)
        pos -= 170
        return (pos * 3, 0, 255 - pos * 3)

    def clear(self):
        """Apaga todos los LEDs."""
        for i in range(self.count):
            self.np[i] = (0, 0, 0)
        self.np.write()

    def show(self):
        self.np.write()

    def fill(self, r, g, b):
        """Rellena toda la tira con un color (sin show)."""
        c = self._dim(r, g, b)
        for i in range(self.count):
            self.np[i] = c

    # ── Efectos ─────────────────────────────────────────────────────────────

    def solid(self, r, g, b, duration_ms=2000):
        """Color sólido durante `duration_ms` milisegundos."""
        self.fill(r, g, b)
        self.np.write()
        time.sleep_ms(duration_ms)

    # -------------------------------------------------------------------
    def rainbow(self, speed=20, cycles=2):
        """Arco iris desplazándose por toda la tira."""
        for j in range(256 * cycles):
            for i in range(self.count):
                self.np[i] = self._dim(*self.wheel((i + j) & 255))
            self.np.write()
            time.sleep_ms(speed)

    def rainbow_chase(self, speed=60, cycles=8):
        """Arco iris en patrón de perseguidor (3 en 3)."""
        for j in range(256 * cycles):
            for q in range(3):
                for i in range(0, self.count, 3):
                    if i + q < self.count:
                        self.np[i + q] = self._dim(*self.wheel((i + j) % 255))
                self.np.write()
                time.sleep_ms(speed)
                for i in range(0, self.count, 3):
                    if i + q < self.count:
                        self.np[i + q] = (0, 0, 0)

    def glitter_rainbow(self, speed=20, cycles=3):
        """Arco iris con destellos blancos aleatorios."""
        for j in range(256 * cycles):
            for i in range(self.count):
                if random.randint(0, 25) == 0:
                    w = int(255 * self.brightness)
                    self.np[i] = (w, w, w)
                else:
                    self.np[i] = self._dim(*self.wheel((i + j) & 255))
            self.np.write()
            time.sleep_ms(speed)

    # -------------------------------------------------------------------
    def breathe(self, r, g, b, speed=8, cycles=3):
        """Respiración suave: encendido y apagado gradual."""
        for _ in range(cycles):
            for v in range(0, 256, 3):
                f = v / 255
                c = self._dim(r, g, b, f)
                for i in range(self.count):
                    self.np[i] = c
                self.np.write()
                time.sleep_ms(speed)
            for v in range(255, -1, -3):
                f = v / 255
                c = self._dim(r, g, b, f)
                for i in range(self.count):
                    self.np[i] = c
                self.np.write()
                time.sleep_ms(speed)

    def heartbeat(self, r, g, b, speed=12, cycles=5):
        """Pulso de corazón doble (lub-dub)."""
        for _ in range(cycles):
            for v in list(range(0, 190, 8)) + list(range(190, 0, -8)):
                c = self._dim(r, g, b, v / 255)
                for i in range(self.count):
                    self.np[i] = c
                self.np.write()
                time.sleep_ms(speed)
            time.sleep_ms(70)
            for v in list(range(0, 255, 8)) + list(range(255, 0, -8)):
                c = self._dim(r, g, b, v / 255)
                for i in range(self.count):
                    self.np[i] = c
                self.np.write()
                time.sleep_ms(speed)
            time.sleep_ms(350)

    # -------------------------------------------------------------------
    def color_wipe(self, r, g, b, speed=40):
        """Rellena la tira LED por LED."""
        c = self._dim(r, g, b)
        for i in range(self.count):
            self.np[i] = c
            self.np.write()
            time.sleep_ms(speed)

    def theater_chase(self, r, g, b, speed=90, cycles=10):
        """Perseguidor clásico de 3 en 3."""
        c = self._dim(r, g, b)
        for _ in range(cycles):
            for q in range(3):
                for i in range(0, self.count, 3):
                    if i + q < self.count:
                        self.np[i + q] = c
                self.np.write()
                time.sleep_ms(speed)
                for i in range(0, self.count, 3):
                    if i + q < self.count:
                        self.np[i + q] = (0, 0, 0)

    def running_lights(self, r, g, b, speed=40, cycles=2):
        """Ola sinusoidal suave que corre por la tira."""
        for _ in range(cycles):
            for pos in range(self.count * 2):
                for i in range(self.count):
                    val = (math.sin((i + pos) * 0.3) + 1) / 2
                    self.np[i] = self._dim(r, g, b, val)
                self.np.write()
                time.sleep_ms(speed)

    # -------------------------------------------------------------------
    def scanner(self, r, g, b, eye_size=4, speed=40, cycles=3):
        """KITT / Cylon: ojo que rebota de extremo a extremo con halo."""
        half = r // 4, g // 4, b // 4
        full = r, g, b
        for _ in range(cycles):
            for i in range(self.count - eye_size - 1):
                self.clear()
                self._set(i, *half)
                for j in range(1, eye_size + 1):
                    self._set(i + j, *full)
                self._set(i + eye_size + 1, *half)
                self.np.write()
                time.sleep_ms(speed)
            for i in range(self.count - eye_size - 2, -1, -1):
                self.clear()
                self._set(i, *half)
                for j in range(1, eye_size + 1):
                    self._set(i + j, *full)
                self._set(i + eye_size + 1, *half)
                self.np.write()
                time.sleep_ms(speed)

    def bounce(self, r, g, b, speed=25, cycles=4):
        """Punto de luz que rebota de un extremo al otro."""
        for _ in range(cycles):
            for i in range(self.count):
                self.clear()
                self._set(i, r, g, b)
                self.np.write()
                time.sleep_ms(speed)
            for i in range(self.count - 2, 0, -1):
                self.clear()
                self._set(i, r, g, b)
                self.np.write()
                time.sleep_ms(speed)

    # -------------------------------------------------------------------
    def meteor_rain(self, r, g, b, meteor_size=10, trail_decay=60, speed=25, cycles=2):
        """Meteoro con cola que se desvanece."""
        for _ in range(cycles):
            self.clear()
            for i in range(self.count + self.count):
                # Desvanece la cola
                for j in range(self.count):
                    rc, gc, bc = self.np[j]
                    self.np[j] = (
                        max(0, rc - (rc * trail_decay) // 256),
                        max(0, gc - (gc * trail_decay) // 256),
                        max(0, bc - (bc * trail_decay) // 256),
                    )
                # Dibuja el meteoro con gradiente interno
                for j in range(meteor_size):
                    pos = i - j
                    if 0 <= pos < self.count:
                        fade = 1.0 - (j / meteor_size) * 0.7
                        self.np[pos] = self._dim(r, g, b, fade)
                self.np.write()
                time.sleep_ms(speed)

    def comet(self, r, g, b, tail_length=14, speed=18, cycles=3):
        """Cometa que cruza la tira dejando una cola que se apaga."""
        for _ in range(cycles):
            for pos in range(self.count + tail_length):
                for i in range(self.count):
                    rc, gc, bc = self.np[i]
                    self.np[i] = (max(0, rc - 18), max(0, gc - 18), max(0, bc - 18))
                if pos < self.count:
                    self.np[pos] = self._dim(r, g, b)
                self.np.write()
                time.sleep_ms(speed)

    # -------------------------------------------------------------------
    def fire(self, cooling=55, sparkling=120, speed=15, frames=200):
        """Simulación de fuego realista con calor y chispas."""
        heat = [0] * self.count
        for _ in range(frames):
            # Enfriar
            for i in range(self.count):
                cooldown = random.randint(0, ((cooling * 10) // self.count) + 2)
                heat[i] = max(0, heat[i] - cooldown)
            # Calor sube (convección)
            for i in range(self.count - 1, 2, -1):
                heat[i] = (heat[i - 1] + heat[i - 2] + heat[i - 2]) // 3
            # Chispas en la base
            if random.randint(0, 255) < sparkling:
                y = random.randint(0, min(7, self.count - 1))
                heat[y] = min(255, heat[y] + random.randint(160, 255))
            # Mapeo calor → color
            for i in range(self.count):
                h = heat[self.count - 1 - i]  # invertido: base en el índice 0
                if h < 85:
                    c = (h * 3, 0, 0)
                elif h < 170:
                    c = (255, (h - 85) * 3, 0)
                else:
                    c = (255, 255, (h - 170) * 3)
                self.np[i] = self._dim(c[0], c[1], c[2])
            self.np.write()
            time.sleep_ms(speed)

    # -------------------------------------------------------------------
    def plasma(self, speed=25, frames=200):
        """Ondas de plasma con múltiples senos superpuestos."""
        t = 0.0
        for _ in range(frames):
            for i in range(self.count):
                v = (
                    math.sin(i / 5.0 + t) +
                    math.sin(10.0 + i / 3.0 * math.sin(t / 2)) +
                    math.sin(i / 2.0 + t)
                ) / 3.0   # rango -1 a 1
                hue = int((v + 1) * 127.5) % 256
                self.np[i] = self._dim(*self.wheel(hue))
            self.np.write()
            t += 0.08
            time.sleep_ms(speed)

    def aurora(self, speed=35, frames=200):
        """Auroras boreales: ondas lentas en tonos fríos."""
        COLORS = [
            (0, 255, 100),
            (0, 150, 255),
            (100, 0, 255),
            (0, 255, 220),
        ]
        n = len(COLORS)
        t = 0.0
        for _ in range(frames):
            for i in range(self.count):
                w1 = (math.sin(i * 0.25 + t) + 1) / 2
                w2 = (math.sin(i * 0.12 + t * 0.6 + 1.5) + 1) / 2
                w3 = (math.sin(i * 0.4 + t * 0.25 + 3.0) + 1) / 2
                ci = int((w1 + w2) * n / 2) % n
                cj = (ci + 1) % n
                r = int(self._blend(COLORS[ci], COLORS[cj], w3)[0] * w1)
                g = int(self._blend(COLORS[ci], COLORS[cj], w3)[1] * w1)
                b = int(self._blend(COLORS[ci], COLORS[cj], w3)[2] * w1)
                self.np[i] = self._dim(min(255, r), min(255, g), min(255, b))
            self.np.write()
            t += 0.04
            time.sleep_ms(speed)

    # -------------------------------------------------------------------
    def matrix_rain(self, speed=55, frames=150):
        """Lluvia de Matrix: columnas de verde que caen."""
        n_drops = max(1, self.count // 8)
        drops = [random.randint(0, self.count - 1) for _ in range(n_drops)]
        for _ in range(frames):
            for i in range(self.count):
                r, g, b = self.np[i]
                self.np[i] = (max(0, r - 15), max(0, g - 25), max(0, b - 15))
            for idx in range(len(drops)):
                p = drops[idx]
                self.np[p] = self._dim(0, 255, 0)
                if p > 0:
                    self.np[p - 1] = self._dim(0, 140, 0, 0.5)
                drops[idx] = (p + 1) % self.count
                if drops[idx] == 0:
                    drops[idx] = random.randint(0, self.count // 4)
            self.np.write()
            time.sleep_ms(speed)

    # -------------------------------------------------------------------
    def twinkle(self, r, g, b, count=10, speed=90, cycles=20):
        """Destellos aleatorios que aparecen y desaparecen."""
        for _ in range(cycles):
            chosen = []
            for _ in range(count):
                idx = random.randint(0, self.count - 1)
                chosen.append(idx)
                bri = random.random()
                self.np[idx] = self._dim(r, g, b, bri)
            self.np.write()
            time.sleep_ms(speed)
            for idx in chosen:
                self.np[idx] = (0, 0, 0)

    def sparkle_fade(self, r, g, b, speed=18, frames=120):
        """Chispas que aparecen a máximo brillo y se desvanecen."""
        pixels = {}
        for _ in range(frames):
            if random.randint(0, 2) == 0:
                idx = random.randint(0, self.count - 1)
                pixels[idx] = 255
            done = []
            for idx, val in pixels.items():
                new_val = max(0, val - random.randint(8, 25))
                if new_val == 0:
                    self.np[idx] = (0, 0, 0)
                    done.append(idx)
                else:
                    self.np[idx] = self._dim(r, g, b, new_val / 255)
                    pixels[idx] = new_val
            for idx in done:
                del pixels[idx]
            self.np.write()
            time.sleep_ms(speed)

    # -------------------------------------------------------------------
    def strobe(self, r, g, b, flashes=12, speed=45):
        """Estroboscopio con destellos cortos."""
        c = self._dim(r, g, b)
        for _ in range(flashes):
            for i in range(self.count):
                self.np[i] = c
            self.np.write()
            time.sleep_ms(speed)
            self.clear()
            time.sleep_ms(speed)

    def lightning(self, flashes=6, speed=25):
        """Relámpago aleatorio que ilumina secciones de la tira."""
        for _ in range(flashes):
            start = random.randint(0, self.count // 2)
            length = random.randint(self.count // 5, self.count // 2)
            w = int(255 * self.brightness)
            for i in range(start, min(start + length, self.count)):
                self.np[i] = (w, w, w)
            self.np.write()
            time.sleep_ms(random.randint(speed, speed * 3))
            self.clear()
            time.sleep_ms(random.randint(speed, speed * 2))

    # -------------------------------------------------------------------
    def hyperspace(self, speed=5, frames=100):
        """Estrellas que aceleran como entrar en hiperespacio."""
        stars = [
            [random.randint(0, self.count - 1), random.randint(0, 255)]
            for _ in range(self.count // 4)
        ]
        for frame in range(frames):
            self.clear()
            accel = max(1, frame // 15)
            for star in stars:
                pos, hue = star
                bri = min(1.0, frame / 60)
                self.np[pos % self.count] = self._dim(*self.wheel(hue), bri)
                star[0] = (pos + accel) % self.count
            self.np.write()
            time.sleep_ms(speed)

    def lava_lamp(self, speed=40, frames=200):
        """Burbujas de color que flotan y se mezclan (lava lamp)."""
        positions = [random.uniform(0, self.count) for _ in range(5)]
        velocities = [random.uniform(0.05, 0.2) * random.choice([-1, 1]) for _ in range(5)]
        hues = [random.randint(0, 255) for _ in range(5)]
        for _ in range(frames):
            for i in range(self.count):
                self.np[i] = (0, 0, 0)
            for k in range(len(positions)):
                # Mover burbuja
                positions[k] += velocities[k]
                if positions[k] < 0 or positions[k] >= self.count:
                    velocities[k] *= -1
                    positions[k] = max(0, min(self.count - 1, positions[k]))
                # Dibujar burbuja con gradiente suave
                center = int(positions[k])
                radius = 5
                for j in range(-radius, radius + 1):
                    idx = center + j
                    if 0 <= idx < self.count:
                        dist = abs(j) / radius
                        intensity = math.cos(dist * math.pi / 2) ** 2
                        base_r, base_g, base_b = self.wheel(hues[k])
                        cr, cg, cb = self.np[idx]
                        self.np[idx] = (
                            min(255, cr + int(base_r * intensity * self.brightness)),
                            min(255, cg + int(base_g * intensity * self.brightness)),
                            min(255, cb + int(base_b * intensity * self.brightness)),
                        )
                hues[k] = (hues[k] + 1) % 256
            self.np.write()
            time.sleep_ms(speed)

    def color_shift(self, speed=60, frames=300):
        """Toda la tira cambia de color suavemente (cross-fade global)."""
        hue = 0
        for _ in range(frames):
            c = self._dim(*self.wheel(hue))
            for i in range(self.count):
                self.np[i] = c
            self.np.write()
            hue = (hue + 1) % 256
            time.sleep_ms(speed)

    # -------------------------------------------------------------------
    def demo(self):
        """Cicla por todos los efectos mostrando cada uno brevemente."""
        effects = [
            ("Solid rojo",       lambda: self.solid(255, 0, 0, 1500)),
            ("Solid cian",       lambda: self.solid(0, 255, 220, 1500)),
            ("Breathe azul",     lambda: self.breathe(0, 100, 255, 8, 2)),
            ("Heartbeat",        lambda: self.heartbeat(255, 0, 60, 12, 3)),
            ("Color shift",      lambda: self.color_shift(40, 120)),
            ("Rainbow",          lambda: self.rainbow(18, 1)),
            ("Glitter rainbow",  lambda: self.glitter_rainbow(18, 1)),
            ("Rainbow chase",    lambda: self.rainbow_chase(55, 2)),
            ("Running lights",   lambda: self.running_lights(255, 50, 200, 35, 1)),
            ("Theater chase",    lambda: self.theater_chase(255, 0, 200, 80, 6)),
            ("Scanner",          lambda: self.scanner(255, 0, 0, 4, 35, 2)),
            ("Bounce violeta",   lambda: self.bounce(160, 0, 255, 22, 3)),
            ("Meteor azul",      lambda: self.meteor_rain(30, 120, 255, 10, 65, 22, 1)),
            ("Comet verde",      lambda: self.comet(0, 255, 80, 14, 18, 2)),
            ("Fire",             lambda: self.fire(55, 120, 15, 100)),
            ("Plasma",           lambda: self.plasma(22, 80)),
            ("Aurora",           lambda: self.aurora(32, 100)),
            ("Lava lamp",        lambda: self.lava_lamp(35, 100)),
            ("Matrix",           lambda: self.matrix_rain(50, 100)),
            ("Twinkle blanco",   lambda: self.twinkle(255, 255, 255, 10, 80, 20)),
            ("Sparkle dorado",   lambda: self.sparkle_fade(255, 200, 50, 18, 100)),
            ("Lightning",        lambda: self.lightning(7, 25)),
            ("Strobe",           lambda: self.strobe(255, 255, 255, 10, 40)),
            ("Hyperspace",       lambda: self.hyperspace(5, 80)),
        ]
        for name, effect in effects:
            print("Efecto:", name)
            self.clear()
            effect()
            self.clear()
            time.sleep_ms(250)
