"""
Controlador WS2812B para ESP32 / ESP8266 en MicroPython.
Todos los efectos soportan interrupción vía stop_flag
para responder inmediatamente a comandos de la PWA.
"""

import neopixel
import machine
import time
import math
import random


class WS2812B:

    def __init__(self, pin=4, count=60, brightness=0.6):
        self.pin = machine.Pin(pin)
        self.count = count
        self.brightness = min(1.0, max(0.0, float(brightness)))
        self.np = neopixel.NeoPixel(self.pin, count)
        self.stop_flag = False   # el servidor lo pone en True para interrumpir
        self.clear()

    # ── Utilidades ───────────────────────────────────────────────────────────

    def _tick(self, ms=0):
        """Espera `ms` ms y devuelve False si se debe detener el efecto."""
        if ms > 0:
            time.sleep_ms(ms)
        return not self.stop_flag

    def _dim(self, r, g, b, factor=1.0):
        f = self.brightness * factor
        return (int(r * f), int(g * f), int(b * f))

    def _set(self, i, r, g, b, factor=1.0):
        if 0 <= i < self.count:
            self.np[i] = self._dim(r, g, b, factor)

    def _blend(self, c1, c2, t):
        return (
            int(c1[0] * (1 - t) + c2[0] * t),
            int(c1[1] * (1 - t) + c2[1] * t),
            int(c1[2] * (1 - t) + c2[2] * t),
        )

    def wheel(self, pos):
        pos = int(pos) % 256
        if pos < 85:
            return (255 - pos * 3, pos * 3, 0)
        if pos < 170:
            pos -= 85
            return (0, 255 - pos * 3, pos * 3)
        pos -= 170
        return (pos * 3, 0, 255 - pos * 3)

    def clear(self):
        for i in range(self.count):
            self.np[i] = (0, 0, 0)
        self.np.write()

    def show(self):
        self.np.write()

    def fill(self, r, g, b):
        c = self._dim(r, g, b)
        for i in range(self.count):
            self.np[i] = c

    # ── Efectos ──────────────────────────────────────────────────────────────

    def solid(self, r, g, b, duration_ms=2000):
        self.fill(r, g, b)
        self.np.write()
        step = 100
        elapsed = 0
        while elapsed < duration_ms:
            if not self._tick(min(step, duration_ms - elapsed)):
                return
            elapsed += step

    def rainbow(self, speed=20, cycles=2):
        for j in range(256 * cycles):
            for i in range(self.count):
                self.np[i] = self._dim(*self.wheel((i + j) & 255))
            self.np.write()
            if not self._tick(speed):
                return

    def rainbow_chase(self, speed=60, cycles=8):
        for j in range(256 * cycles):
            for q in range(3):
                for i in range(0, self.count, 3):
                    if i + q < self.count:
                        self.np[i + q] = self._dim(*self.wheel((i + j) % 255))
                self.np.write()
                if not self._tick(speed):
                    return
                for i in range(0, self.count, 3):
                    if i + q < self.count:
                        self.np[i + q] = (0, 0, 0)

    def glitter_rainbow(self, speed=20, cycles=3):
        for j in range(256 * cycles):
            for i in range(self.count):
                if random.randint(0, 25) == 0:
                    w = int(255 * self.brightness)
                    self.np[i] = (w, w, w)
                else:
                    self.np[i] = self._dim(*self.wheel((i + j) & 255))
            self.np.write()
            if not self._tick(speed):
                return

    def breathe(self, r, g, b, speed=8, cycles=3):
        for _ in range(cycles):
            for v in range(0, 256, 3):
                c = self._dim(r, g, b, v / 255)
                for i in range(self.count):
                    self.np[i] = c
                self.np.write()
                if not self._tick(speed):
                    return
            for v in range(255, -1, -3):
                c = self._dim(r, g, b, v / 255)
                for i in range(self.count):
                    self.np[i] = c
                self.np.write()
                if not self._tick(speed):
                    return

    def heartbeat(self, r, g, b, speed=12, cycles=5):
        for _ in range(cycles):
            for v in list(range(0, 190, 8)) + list(range(190, 0, -8)):
                c = self._dim(r, g, b, v / 255)
                for i in range(self.count):
                    self.np[i] = c
                self.np.write()
                if not self._tick(speed):
                    return
            if not self._tick(70):
                return
            for v in list(range(0, 255, 8)) + list(range(255, 0, -8)):
                c = self._dim(r, g, b, v / 255)
                for i in range(self.count):
                    self.np[i] = c
                self.np.write()
                if not self._tick(speed):
                    return
            if not self._tick(350):
                return

    def color_wipe(self, r, g, b, speed=40):
        c = self._dim(r, g, b)
        for i in range(self.count):
            self.np[i] = c
            self.np.write()
            if not self._tick(speed):
                return

    def theater_chase(self, r, g, b, speed=90, cycles=10):
        c = self._dim(r, g, b)
        for _ in range(cycles):
            for q in range(3):
                for i in range(0, self.count, 3):
                    if i + q < self.count:
                        self.np[i + q] = c
                self.np.write()
                if not self._tick(speed):
                    return
                for i in range(0, self.count, 3):
                    if i + q < self.count:
                        self.np[i + q] = (0, 0, 0)

    def running_lights(self, r, g, b, speed=40, cycles=2):
        for _ in range(cycles):
            for pos in range(self.count * 2):
                for i in range(self.count):
                    val = (math.sin((i + pos) * 0.3) + 1) / 2
                    self.np[i] = self._dim(r, g, b, val)
                self.np.write()
                if not self._tick(speed):
                    return

    def scanner(self, r, g, b, eye_size=4, speed=40, cycles=3):
        for _ in range(cycles):
            for i in range(self.count - eye_size - 1):
                self.clear()
                self._set(i, r, g, b, 0.25)
                for j in range(1, eye_size + 1):
                    self._set(i + j, r, g, b)
                self._set(i + eye_size + 1, r, g, b, 0.25)
                self.np.write()
                if not self._tick(speed):
                    return
            for i in range(self.count - eye_size - 2, -1, -1):
                self.clear()
                self._set(i, r, g, b, 0.25)
                for j in range(1, eye_size + 1):
                    self._set(i + j, r, g, b)
                self._set(i + eye_size + 1, r, g, b, 0.25)
                self.np.write()
                if not self._tick(speed):
                    return

    def bounce(self, r, g, b, speed=25, cycles=4):
        for _ in range(cycles):
            for i in range(self.count):
                self.clear()
                self._set(i, r, g, b)
                self.np.write()
                if not self._tick(speed):
                    return
            for i in range(self.count - 2, 0, -1):
                self.clear()
                self._set(i, r, g, b)
                self.np.write()
                if not self._tick(speed):
                    return

    def meteor_rain(self, r, g, b, meteor_size=10, trail_decay=60, speed=25, cycles=2):
        for _ in range(cycles):
            self.clear()
            for i in range(self.count + self.count):
                for j in range(self.count):
                    rc, gc, bc = self.np[j]
                    self.np[j] = (
                        max(0, rc - (rc * trail_decay) // 256),
                        max(0, gc - (gc * trail_decay) // 256),
                        max(0, bc - (bc * trail_decay) // 256),
                    )
                for j in range(meteor_size):
                    pos = i - j
                    if 0 <= pos < self.count:
                        self.np[pos] = self._dim(r, g, b, 1.0 - (j / meteor_size) * 0.7)
                self.np.write()
                if not self._tick(speed):
                    return

    def comet(self, r, g, b, tail_length=14, speed=18, cycles=3):
        for _ in range(cycles):
            for pos in range(self.count + tail_length):
                for i in range(self.count):
                    rc, gc, bc = self.np[i]
                    self.np[i] = (max(0, rc - 18), max(0, gc - 18), max(0, bc - 18))
                if pos < self.count:
                    self.np[pos] = self._dim(r, g, b)
                self.np.write()
                if not self._tick(speed):
                    return

    def fire(self, cooling=55, sparkling=120, speed=15, frames=200):
        heat = [0] * self.count
        for _ in range(frames):
            for i in range(self.count):
                cd = random.randint(0, ((cooling * 10) // self.count) + 2)
                heat[i] = max(0, heat[i] - cd)
            for i in range(self.count - 1, 2, -1):
                heat[i] = (heat[i - 1] + heat[i - 2] + heat[i - 2]) // 3
            if random.randint(0, 255) < sparkling:
                y = random.randint(0, min(7, self.count - 1))
                heat[y] = min(255, heat[y] + random.randint(160, 255))
            for i in range(self.count):
                h = heat[self.count - 1 - i]
                if h < 85:
                    c = (h * 3, 0, 0)
                elif h < 170:
                    c = (255, (h - 85) * 3, 0)
                else:
                    c = (255, 255, (h - 170) * 3)
                self.np[i] = self._dim(c[0], c[1], c[2])
            self.np.write()
            if not self._tick(speed):
                return

    def plasma(self, speed=25, frames=200):
        t = 0.0
        for _ in range(frames):
            for i in range(self.count):
                v = (
                    math.sin(i / 5.0 + t) +
                    math.sin(10.0 + i / 3.0 * math.sin(t / 2)) +
                    math.sin(i / 2.0 + t)
                ) / 3.0
                hue = int((v + 1) * 127.5) % 256
                self.np[i] = self._dim(*self.wheel(hue))
            self.np.write()
            t += 0.08
            if not self._tick(speed):
                return

    def aurora(self, speed=35, frames=200):
        COLS = [(0, 255, 100), (0, 150, 255), (100, 0, 255), (0, 255, 220)]
        n = len(COLS)
        t = 0.0
        for _ in range(frames):
            for i in range(self.count):
                w1 = (math.sin(i * 0.25 + t) + 1) / 2
                w2 = (math.sin(i * 0.12 + t * 0.6 + 1.5) + 1) / 2
                w3 = (math.sin(i * 0.4 + t * 0.25 + 3.0) + 1) / 2
                ci = int((w1 + w2) * n / 2) % n
                cj = (ci + 1) % n
                bl = self._blend(COLS[ci], COLS[cj], w3)
                self.np[i] = self._dim(min(255, int(bl[0] * w1)),
                                       min(255, int(bl[1] * w1)),
                                       min(255, int(bl[2] * w1)))
            self.np.write()
            t += 0.04
            if not self._tick(speed):
                return

    def lava_lamp(self, speed=40, frames=200):
        positions = [random.uniform(0, self.count) for _ in range(5)]
        velocities = [random.uniform(0.05, 0.2) * random.choice([-1, 1]) for _ in range(5)]
        hues = [random.randint(0, 255) for _ in range(5)]
        for _ in range(frames):
            for i in range(self.count):
                self.np[i] = (0, 0, 0)
            for k in range(len(positions)):
                positions[k] += velocities[k]
                if positions[k] < 0 or positions[k] >= self.count:
                    velocities[k] *= -1
                    positions[k] = max(0, min(self.count - 1, positions[k]))
                center = int(positions[k])
                for j in range(-5, 6):
                    idx = center + j
                    if 0 <= idx < self.count:
                        inten = math.cos(abs(j) / 5 * math.pi / 2) ** 2
                        base = self.wheel(hues[k])
                        cr, cg, cb = self.np[idx]
                        self.np[idx] = (
                            min(255, cr + int(base[0] * inten * self.brightness)),
                            min(255, cg + int(base[1] * inten * self.brightness)),
                            min(255, cb + int(base[2] * inten * self.brightness)),
                        )
                hues[k] = (hues[k] + 1) % 256
            self.np.write()
            if not self._tick(speed):
                return

    def matrix_rain(self, speed=55, frames=150):
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
            if not self._tick(speed):
                return

    def twinkle(self, r, g, b, count=10, speed=90, cycles=20):
        for _ in range(cycles):
            chosen = []
            for _ in range(count):
                idx = random.randint(0, self.count - 1)
                chosen.append(idx)
                self.np[idx] = self._dim(r, g, b, random.random())
            self.np.write()
            if not self._tick(speed):
                return
            for idx in chosen:
                self.np[idx] = (0, 0, 0)

    def sparkle_fade(self, r, g, b, speed=18, frames=120):
        pixels = {}
        for _ in range(frames):
            if random.randint(0, 2) == 0:
                idx = random.randint(0, self.count - 1)
                pixels[idx] = 255
            done = []
            for idx, val in pixels.items():
                nv = max(0, val - random.randint(8, 25))
                if nv == 0:
                    self.np[idx] = (0, 0, 0)
                    done.append(idx)
                else:
                    self.np[idx] = self._dim(r, g, b, nv / 255)
                    pixels[idx] = nv
            for idx in done:
                del pixels[idx]
            self.np.write()
            if not self._tick(speed):
                return

    def strobe(self, r, g, b, flashes=12, speed=45):
        c = self._dim(r, g, b)
        for _ in range(flashes):
            for i in range(self.count):
                self.np[i] = c
            self.np.write()
            if not self._tick(speed):
                return
            self.clear()
            if not self._tick(speed):
                return

    def lightning(self, flashes=6, speed=25):
        for _ in range(flashes):
            start = random.randint(0, self.count // 2)
            length = random.randint(self.count // 5, self.count // 2)
            w = int(255 * self.brightness)
            for i in range(start, min(start + length, self.count)):
                self.np[i] = (w, w, w)
            self.np.write()
            if not self._tick(random.randint(speed, speed * 3)):
                return
            self.clear()
            if not self._tick(random.randint(speed, speed * 2)):
                return

    def color_shift(self, speed=60, frames=300):
        hue = 0
        for _ in range(frames):
            c = self._dim(*self.wheel(hue))
            for i in range(self.count):
                self.np[i] = c
            self.np.write()
            hue = (hue + 1) % 256
            if not self._tick(speed):
                return

    def hyperspace(self, speed=5, frames=100):
        stars = [[random.randint(0, self.count - 1), random.randint(0, 255)]
                 for _ in range(self.count // 4)]
        for frame in range(frames):
            self.clear()
            accel = max(1, frame // 15)
            for star in stars:
                pos, hue = star
                bri = min(1.0, frame / 60)
                self.np[pos % self.count] = self._dim(*self.wheel(hue), bri)
                star[0] = (pos + accel) % self.count
            self.np.write()
            if not self._tick(speed):
                return

    def demo(self):
        effects = [
            ("Rainbow",          lambda: self.rainbow(18, 1)),
            ("Glitter",          lambda: self.glitter_rainbow(18, 1)),
            ("Breathe",          lambda: self.breathe(0, 100, 255, 8, 2)),
            ("Heartbeat",        lambda: self.heartbeat(255, 0, 60, 12, 3)),
            ("Color Shift",      lambda: self.color_shift(40, 120)),
            ("Scanner",          lambda: self.scanner(255, 0, 0, 4, 35, 2)),
            ("Meteor",           lambda: self.meteor_rain(30, 120, 255, 10, 65, 22, 1)),
            ("Comet",            lambda: self.comet(0, 255, 80, 14, 18, 2)),
            ("Fire",             lambda: self.fire(55, 120, 15, 100)),
            ("Plasma",           lambda: self.plasma(22, 80)),
            ("Aurora",           lambda: self.aurora(32, 100)),
            ("Lava Lamp",        lambda: self.lava_lamp(35, 100)),
            ("Matrix",           lambda: self.matrix_rain(50, 100)),
            ("Sparkle",          lambda: self.sparkle_fade(255, 200, 50, 18, 100)),
            ("Hyperspace",       lambda: self.hyperspace(5, 80)),
        ]
        for name, fn in effects:
            print("Efecto:", name)
            self.clear()
            fn()
            if self.stop_flag:
                return
            self.clear()
            time.sleep_ms(250)
