# Birthday Bomb Box 🎂💣

A CircuitPython prank/surprise mechanism for a Raspberry Pi Pico (RP2040).
Hide it in a gift box: when the box is opened, an IR sensor triggers a fake
bomb countdown (CS:GO-style accelerating ticks) on an LCD, followed by an
"explosion" sound, a short silence, and then Happy Birthday plays over an
I2S speaker.

Closing the box at any point (even mid-sequence) stops all sound instantly
and resets everything back to the ready state — opening it again always
replays the full sequence from the start, so you can reset and re-trigger
the prank as many times as you want before wrapping it up.

## Demo flow

1. Box closed → LCD shows `Ready...`
2. Box opened → LCD shows `!!! BOMB !!!` with a countdown (default 8s);
   speaker ticks, getting faster and higher-pitched as it counts down
3. Countdown hits 0 → `*** BOOM ***` explosion sound
4. Short silence (1.5s)
5. `Happy Birthday` message + melody plays
6. Box closed at any point → immediate silence, back to `Ready...`, ready
   to trigger again on the next open

## Hardware

- Raspberry Pi Pico (RP2040), running **CircuitPython** (not MicroPython)
- IR obstacle/reflectance sensor (3-pin: VCC, GND, OUT), sensitivity set via
  its onboard potentiometer
- MAX98357A I2S amplifier + small speaker
- 16x2 LCD with I2C backpack (PCF8574 chip — the common "HW-61" style
  board, **not** the Adafruit MCP23008-based backpack)
- Logic level converter for the LCD's I2C bus (Pico is 3.3V, most PCF8574
  backpacks run at 5V)

### Wiring

```
IR sensor:
  VCC  -> Pico 3V3(OUT)
  GND  -> Pico GND
  OUT  -> Pico GP15

MAX98357A I2S amp:
  VIN  -> Pico VBUS (5V)
  GND  -> Pico GND
  BCLK -> Pico GP16
  LRC  -> Pico GP17
  DIN  -> Pico GP18

16x2 I2C LCD (via logic level converter):
  Pico GP0 (SDA) -> LV1 -> HV1 -> LCD SDA
  Pico GP1 (SCL) -> LV2 -> HV2 -> LCD SCL
  Pico 3V3       -> LV
  Pico VBUS (5V) -> HV
  LCD GND / level converter GND -> common GND
```

Powering everything from a single USB source (Pico's VBUS = the same 5V as
USB) means there's no special power-up sequencing to worry about between
the 3.3V and 5V sides of the level converter.

## Software setup

1. **Flash CircuitPython** (skip if already installed): hold BOOTSEL while
   plugging in the Pico, drag the latest stable UF2 for "Raspberry Pi
   Pico" from [circuitpython.org/board/raspberry_pi_pico](https://circuitpython.org/board/raspberry_pi_pico)
   onto the `RPI-RP2` drive that appears.
2. **Copy the code**: copy `code.py` and `lcd_pcf8574.py` from this repo to
   the root of the `CIRCUITPY` drive.
3. **Copy the one required library**: download the
   [CircuitPython Library Bundle](https://circuitpython.org/libraries)
   matching your CircuitPython major version, and copy the
   `adafruit_bus_device` folder into `CIRCUITPY/lib/`. That's the only
   external dependency — `synthio`, `audiobusio`, `digitalio`, `busio`,
   `board`, `random`, and `array` are all built into CircuitPython itself.

   > Note: this project does **not** use Adafruit's `adafruit_character_lcd`
   > library. That library's I2C backpack support (`character_lcd_i2c.py`)
   > is hardcoded for the MCP23008 chip, which most cheap "HW-61" style
   > PCF8574 backpacks don't use — hence the small custom `lcd_pcf8574.py`
   > driver included here.

4. **Adjust the LCD contrast** on the backpack's trimmer potentiometer if
   the text isn't visible (this is unrelated to wiring/level-shifting —
   pure contrast voltage).

## Configuration

All pins and tunables sit at the top of `code.py`:

| Constant | Purpose |
|---|---|
| `IR_SENSOR_PIN`, `I2S_*_PIN`, `I2C_*_PIN` | Pin assignments |
| `LCD_I2C_ADDR` | LCD backpack address (`0x27` or `0x3F` are common) |
| `TRIGGER_ON_LOW` | Whether "box open" reads as sensor `LOW` or `HIGH` — verify via REPL (see below) |
| `DEBOUNCE_S` | Sensor debounce time |
| `BOMB_COUNTDOWN_S` | Countdown length in seconds |
| `BOMB_START_BEEP_HZ` / `BOMB_END_BEEP_HZ` | Tick pitch range |
| `POST_EXPLOSION_PAUSE_S` | Silence between explosion and Happy Birthday |
| `HAPPY_BIRTHDAY` | The melody as `(frequency_hz, duration_s)` tuples |

## Testing the sensor before trusting the full prank

Connect to the Pico's serial REPL (Mu, `screen`, `tio`, Thonny, etc.) and
run:

```python
import board, digitalio, time
ir = digitalio.DigitalInOut(board.GP15)
ir.direction = digitalio.Direction.INPUT
while True:
    print(ir.value)
    time.sleep(0.2)
```

Note which value corresponds to "box closed" vs "box open" for your
specific sensor/mounting, then set `TRIGGER_ON_LOW` in `code.py`
accordingly (`False` if open reads `True`, `True` if open reads `False`).

## Troubleshooting

**Sensor logic flips (or stops responding) after wrapping the box in gift
paper.** Reflective/shiny wrapping paper sitting loosely right in front of
the IR sensor can itself reflect the beam, so the sensor mostly "sees" the
paper instead of the lid. Symptoms: open/closed behavior is exactly
inverted from before wrapping, and/or waving a hand in front of the sensor
from outside does nothing. Fix: re-run the sensor test above with the box
in its final wrapped state, and set `TRIGGER_ON_LOW` to match what you
measure now — if the inversion is clean and consistent, flipping this one
constant is enough. For a more robust long-term fix, cut a small slit/hole
in the paper directly in front of the sensor lens (or build a small
cardboard tunnel around it) so it points at the lid, not the paper.

## Notes / gotchas found while building this

- CircuitPython's `str` has no `.ljust()`/`.rjust()` — pad strings manually.
- Use `time.monotonic()` for timing/sleep-loop logic, not `time.time()` —
  on this board `time.time()` only has whole-second resolution, which
  made short interruptible sleeps wildly inaccurate.
- `synthio` has no built-in noise generator; the explosion sound uses a
  single-cycle array of random samples as an oscillator waveform to fake
  white noise, layered with a low sine "thump" for the bass.
