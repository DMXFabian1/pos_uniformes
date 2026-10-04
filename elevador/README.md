# Elevador de 3 pisos (Arduino Nano + L298N)

Sketch: `elevador/elevador.ino`. Abrir la carpeta `elevador/` con el IDE de Arduino, placa **Arduino Nano**, procesador ATmega328P (Old Bootloader si no sube).

## Conexiones (ajustables al inicio del .ino)

| Función                  | Pin Nano |
|--------------------------|----------|
| L298N ENA (PWM)          | D10      |
| L298N IN1                | D11      |
| L298N IN2                | D12      |
| Botón piso 1 / 2 / 3     | D9 / D8 / D7 (otro lado a GND) |
| Switch piso 1 / 2 / 3    | D6 / D5 / D4 (otro lado a GND) |
| Display a b c d e f g    | D3 D2 A0 A1 A2 A3 A4 (con resistencia 220-330 Ω) |
| Display común            | GND (cátodo común) |

Alimentación: 12V al L298N, jumper 5V del L298N puesto, salida 5V del L298N al pin **5V** del Nano, GND común.

## Notas
- El motor es de 3-6V: `VELOCIDAD_PWM = 110` deja ~5V efectivos. No subirlo a 255.
- Si al subir baja, poner `INVERTIR_MOTOR = true`.
- Si el display está encendido "al revés" (ánodo común), invertir `HIGH`/`LOW` en `mostrar()`.
- Cualquier botón saca del estado de error (display "E" parpadeando).
