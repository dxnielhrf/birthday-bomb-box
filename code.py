"""
Birthday Box surprise trigger.
Pico watches IR sensor; on box-open transition, plays Happy Birthday
over I2S amp and shows a message on the I2C LCD. Fires once per boot.
"""

import time
import random
import array
import board
import digitalio
import busio
import audiobusio
import synthio
from lcd_pcf8574 import LCD_PCF8574

# ---------------------------------------------------------------------------
# PIN / CONFIG CONSTANTS — edit here only
# ---------------------------------------------------------------------------
IR_SENSOR_PIN = board.GP15

I2S_BCLK_PIN = board.GP16   # BCLK
I2S_LRCLK_PIN = board.GP17  # LRC / LRCLK
I2S_DATA_PIN = board.GP18   # DIN

I2C_SDA_PIN = board.GP0
I2C_SCL_PIN = board.GP1
LCD_I2C_ADDR = 0x27   # common PCF8574 backpack address; try 0x3F if this fails
LCD_COLUMNS = 16
LCD_ROWS = 2

DEBOUNCE_S = 0.08          # 80ms debounce for the initial open trigger
CLOSE_CONFIRM_SAMPLES = 6  # how many samples must all read "closed" before
CLOSE_CONFIRM_INTERVAL_S = 0.06   # ...believing it (glitchy sensor tolerance:
                                    # 6*0.06s = 360ms sustained close required)
TRIGGER_ON_LOW = True      # gift wrap in front of sensor inverted the reading:
                            # now True=closed, False=open (re-measure via REPL
                            # if you unwrap/rewrap and it acts backwards again)

SAMPLE_RATE = 22050

BOMB_COUNTDOWN_S = 8   # prank countdown length in seconds, edit freely
BOMB_START_BEEP_HZ = 700   # tick pitch at countdown start
BOMB_END_BEEP_HZ = 1500    # tick pitch just before "explosion" (higher/faster = tenser)
POST_EXPLOSION_PAUSE_S = 1.5   # silent beat between explosion and Happy Birthday

# ---------------------------------------------------------------------------
# HAPPY BIRTHDAY NOTE LIST — (frequency_hz, duration_s). Edit freely for tempo/melody.
# ---------------------------------------------------------------------------
REST = 0  # frequency 0 = silent gap

HAPPY_BIRTHDAY = [
    (392.00, 0.3), (392.00, 0.15), (440.00, 0.45), (392.00, 0.45), (523.25, 0.45), (493.88, 0.9),
    (REST, 0.05),
    (392.00, 0.3), (392.00, 0.15), (440.00, 0.45), (392.00, 0.45), (587.33, 0.45), (523.25, 0.9),
    (REST, 0.05),
    (392.00, 0.3), (392.00, 0.15), (783.99, 0.45), (659.25, 0.45), (523.25, 0.45), (493.88, 0.45), (440.00, 0.6),
    (REST, 0.05),
    (698.46, 0.3), (698.46, 0.15), (659.25, 0.45), (523.25, 0.45), (587.33, 0.45), (523.25, 0.9),
]

# ---------------------------------------------------------------------------
# INIT
# ---------------------------------------------------------------------------
ir = digitalio.DigitalInOut(IR_SENSOR_PIN)
ir.direction = digitalio.Direction.INPUT

i2c = busio.I2C(I2C_SCL_PIN, I2C_SDA_PIN)
lcd = LCD_PCF8574(i2c, address=LCD_I2C_ADDR, columns=LCD_COLUMNS, rows=LCD_ROWS)
lcd.clear()

audio = audiobusio.I2SOut(I2S_BCLK_PIN, I2S_LRCLK_PIN, I2S_DATA_PIN)
synth = synthio.Synthesizer(sample_rate=SAMPLE_RATE)

# single-cycle random waveform, reused as an oscillator table to fake white
# noise for the explosion sound (synthio has no built-in noise generator)
NOISE_WAVEFORM = array.array("h", [random.randint(-28000, 28000) for _ in range(256)])


def show(line1, line2=""):
    lcd.write_line(line1, 0)
    lcd.write_line(line2, 1)


def sensor_triggered(value):
    return (not value) if TRIGGER_ON_LOW else value


def box_is_open():
    return sensor_triggered(ir.value)


def box_confirmed_closed():
    """Debounced close check: a single closed reading can be electrical
    noise (e.g. a current blip from the I2S amp on a shared 3.3V rail, or a
    generally marginal/noisy sensor), so require CLOSE_CONFIRM_SAMPLES
    consecutive closed readings, spread over CLOSE_CONFIRM_INTERVAL_S each,
    before believing it's a real close."""
    for _ in range(CLOSE_CONFIRM_SAMPLES):
        if box_is_open():
            return False
        time.sleep(CLOSE_CONFIRM_INTERVAL_S)
    return True


def interruptible_sleep(duration):
    """Sleep in small steps, polling the sensor so a mid-sequence box-close
    aborts immediately instead of waiting out the full sleep. Returns False
    once a real (debounced) close is seen, True once the full duration
    elapsed open."""
    # time.monotonic() (not time.time()) — CircuitPython's time.time() only
    # has whole-second resolution on this board, which made durations wildly
    # inaccurate here.
    end = time.monotonic() + duration
    while time.monotonic() < end:
        if not box_is_open() and box_confirmed_closed():
            return False
        time.sleep(0.02)
    return True


def play_melody(notes):
    audio.play(synth)
    for freq, dur in notes:
        if freq > 0:
            note = synthio.Note(frequency=freq)
            synth.press(note)
            if not interruptible_sleep(dur):
                synth.release(note)
                audio.stop()
                return False
            synth.release(note)
        else:
            if not interruptible_sleep(dur):
                audio.stop()
                return False
        if not interruptible_sleep(0.02):  # tiny gap between notes
            audio.stop()
            return False
    audio.stop()
    return True


def play_countdown():
    """CS:GO-style bomb tick: fixed 1 beep per displayed second, but pitch
    rises and beep duration shortens toward zero for rising tension."""
    audio.play(synth)
    for remaining in range(BOMB_COUNTDOWN_S, 0, -1):
        show("!!! BOMB !!!", "  {:02d} sec left".format(remaining))
        progress = 1 - (remaining / BOMB_COUNTDOWN_S)   # 0.0 -> 1.0
        beep_freq = BOMB_START_BEEP_HZ + progress * (BOMB_END_BEEP_HZ - BOMB_START_BEEP_HZ)
        beep_len = 0.12 - progress * 0.07               # 0.12s -> 0.05s
        note = synthio.Note(frequency=beep_freq)
        synth.press(note)
        if not interruptible_sleep(beep_len):
            synth.release(note)
            audio.stop()
            return False
        synth.release(note)
        if not interruptible_sleep(1.0 - beep_len):
            audio.stop()
            return False
    audio.stop()
    return True


def play_explosion():
    """Layered bass thump + noise-waveform notes with a sharp attack and
    long decay to fake an explosion through the I2S amp."""
    boom_env = synthio.Envelope(attack_time=0.001, decay_time=0.4, sustain_level=0.3, release_time=0.6)
    bass = synthio.Note(frequency=55, envelope=boom_env)
    noise1 = synthio.Note(frequency=180, waveform=NOISE_WAVEFORM, envelope=boom_env)
    noise2 = synthio.Note(frequency=90, waveform=NOISE_WAVEFORM, envelope=boom_env)
    notes = (bass, noise1, noise2)

    show("*** BOOM ***", "")
    audio.play(synth)
    synth.press(notes)
    if not interruptible_sleep(0.05):
        synth.release(notes)
        audio.stop()
        return False
    synth.release(notes)
    if not interruptible_sleep(1.0):   # let release tail ring out
        audio.stop()
        return False
    audio.stop()
    return True


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
show("Ready...")

last_state = sensor_triggered(ir.value)

while True:
    raw = sensor_triggered(ir.value)

    if raw != last_state:
        time.sleep(DEBOUNCE_S)          # debounce: re-check after settle time
        raw_confirmed = sensor_triggered(ir.value)
        if raw_confirmed == raw:
            last_state = raw_confirmed
            if raw_confirmed:
                # fires on every close->open transition; closing the box
                # mid-sequence aborts immediately (interruptible_sleep) and
                # falls through to the reset below
                completed = play_countdown() and play_explosion()
                if completed:
                    completed = interruptible_sleep(POST_EXPLOSION_PAUSE_S)
                if completed:
                    show("Happy Birthday", "du Gooner!")
                    completed = play_melody(HAPPY_BIRTHDAY)
                    if completed:
                        show("Happy Birthday", "du Gooner!")  # keep message after song ends

                if not completed:
                    # box was closed mid-sequence: force back to the fresh
                    # ready state so the next open re-triggers cleanly
                    last_state = False
                    show("Ready...")
            else:
                show("Ready...")

    time.sleep(0.05)
