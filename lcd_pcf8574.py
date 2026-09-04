"""
Minimal HD44780 character LCD driver for PCF8574 I2C backpacks
(the common "HW-61" style boards, same wiring as Arduino's
LiquidCrystal_I2C library). Adafruit's adafruit_character_lcd
library targets the MCP23008-based backpack instead and does not
work with this chip, hence this small standalone driver.

PCF8574 pin -> LCD signal (standard backpack wiring):
  P0 -> RS
  P1 -> RW  (tied low / unused here, always write)
  P2 -> E
  P3 -> Backlight control
  P4..P7 -> D4..D7 (4-bit mode)
"""

import time
from adafruit_bus_device.i2c_device import I2CDevice

_RS = 0x01
_RW = 0x02
_EN = 0x04
_BACKLIGHT = 0x08

_CMD_CLEAR = 0x01
_CMD_HOME = 0x02
_CMD_ENTRY_MODE = 0x04
_CMD_DISPLAY_CTRL = 0x08
_CMD_FUNCTION_SET = 0x20
_CMD_SET_DDRAM = 0x80

_ENTRY_LEFT = 0x02
_DISPLAY_ON = 0x04
_FUNCTION_4BIT_2LINE = 0x08

_ROW_OFFSETS = (0x00, 0x40, 0x14, 0x54)


class LCD_PCF8574:
    def __init__(self, i2c, address=0x27, columns=16, rows=2):
        self.device = I2CDevice(i2c, address)
        self.columns = columns
        self.rows = rows
        self.backlight = _BACKLIGHT
        time.sleep(0.05)
        # HD44780 4-bit init sequence
        self._write4(0x03)
        time.sleep(0.005)
        self._write4(0x03)
        time.sleep(0.001)
        self._write4(0x03)
        self._write4(0x02)  # switch to 4-bit mode
        self._command(_CMD_FUNCTION_SET | _FUNCTION_4BIT_2LINE)
        self._command(_CMD_DISPLAY_CTRL | _DISPLAY_ON)
        self.clear()
        self._command(_CMD_ENTRY_MODE | _ENTRY_LEFT)

    def _pulse_enable(self, data):
        self._i2c_write(data | _EN)
        time.sleep(0.0000005)
        self._i2c_write(data & ~_EN)
        time.sleep(0.00005)

    def _i2c_write(self, data):
        with self.device as i2c:
            i2c.write(bytes([data | self.backlight]))

    def _write4(self, nibble, char_mode=False):
        data = (nibble << 4) | (_RS if char_mode else 0)
        self._i2c_write(data)
        self._pulse_enable(data)

    def _command(self, value):
        self._write4((value >> 4) & 0x0F, char_mode=False)
        self._write4(value & 0x0F, char_mode=False)
        time.sleep(0.001)

    def _write_char(self, value):
        self._write4((value >> 4) & 0x0F, char_mode=True)
        self._write4(value & 0x0F, char_mode=True)
        time.sleep(0.0001)

    def clear(self):
        self._command(_CMD_CLEAR)
        time.sleep(0.002)

    def set_cursor(self, col, row):
        row = min(row, self.rows - 1)
        self._command(_CMD_SET_DDRAM | (col + _ROW_OFFSETS[row]))

    def write_line(self, text, row):
        self.set_cursor(0, row)
        text = text[: self.columns]
        text = text + " " * (self.columns - len(text))
        for ch in text:
            self._write_char(ord(ch))
