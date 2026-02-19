"""SSD1306 OLED + 눈 표정. findee._i2c_bus 락 사용."""
from __future__ import annotations

import random
import threading
import time
from enum import IntEnum
from types import SimpleNamespace

from findee._i2c_bus import _I2C_LOCK

OLED_ADDR = 0x3C
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_PAGES = 8
OLED_BUF_SIZE = OLED_WIDTH * OLED_PAGES
_SSD1306_CMD, _SSD1306_DATA = 0x00, 0x40
_SSD1306_DISPLAYOFF = 0xAE
_SSD1306_SETDISPLAYCLOCKDIV = 0xD5
_SSD1306_SETMULTIPLEX = 0xA8
_SSD1306_SETDISPLAYOFFSET = 0xD3
_SSD1306_SETSTARTLINE = 0x40
_SSD1306_CHARGEPUMP = 0x8D
_SSD1306_SWITCHCAPVCC = 0x14
_SSD1306_MEMORYMODE = 0x20
_SSD1306_SEGREMAP = 0xA0
_SSD1306_COMSCANDEC = 0xC8
_SSD1306_SETCOMPINS = 0xDA
_SSD1306_SETCONTRAST = 0x81
_SSD1306_SETPRECHARGE = 0xD9
_SSD1306_SETVCOMDETECT = 0xDB
_SSD1306_DISPLAYALLON_RESUME = 0xA4
_SSD1306_NORMALDISPLAY = 0xA6
_SSD1306_DISPLAYON = 0xAF
_SSD1306_COLUMNADDR = 0x21
_SSD1306_PAGEADDR = 0x22

_FONT_5X7 = (
    (0x00,0x00,0x00,0x00,0x00),(0x00,0x00,0x5F,0x00,0x00),(0x00,0x07,0x00,0x07,0x00),(0x14,0x7F,0x14,0x7F,0x14),(0x24,0x2A,0x7F,0x2A,0x12),
    (0x23,0x13,0x08,0x64,0x62),(0x36,0x49,0x56,0x20,0x50),(0x00,0x08,0x07,0x03,0x00),(0x00,0x1C,0x22,0x41,0x00),(0x00,0x41,0x22,0x1C,0x00),
    (0x2A,0x1C,0x7F,0x1C,0x2A),(0x08,0x08,0x3E,0x08,0x08),(0x00,0x80,0x70,0x30,0x00),(0x08,0x08,0x08,0x08,0x08),(0x00,0x00,0x60,0x60,0x00),(0x20,0x10,0x08,0x04,0x02),
    (0x3E,0x51,0x49,0x45,0x3E),(0x00,0x42,0x7F,0x40,0x00),(0x72,0x49,0x49,0x49,0x46),(0x21,0x41,0x49,0x4D,0x33),(0x18,0x14,0x12,0x7F,0x10),(0x27,0x45,0x45,0x45,0x39),
    (0x3C,0x4A,0x49,0x49,0x31),(0x41,0x21,0x11,0x09,0x07),(0x36,0x49,0x49,0x49,0x36),(0x46,0x49,0x49,0x29,0x1E),(0x00,0x00,0x14,0x00,0x00),(0x00,0x40,0x34,0x00,0x00),
    (0x00,0x08,0x14,0x22,0x41),(0x14,0x14,0x14,0x14,0x14),(0x00,0x41,0x22,0x14,0x08),(0x02,0x01,0x59,0x09,0x06),(0x3E,0x41,0x5D,0x59,0x4E),(0x7C,0x12,0x11,0x12,0x7C),
    (0x7F,0x49,0x49,0x49,0x36),(0x3E,0x41,0x41,0x41,0x22),(0x7F,0x41,0x41,0x41,0x3E),(0x7F,0x49,0x49,0x49,0x41),(0x7F,0x09,0x09,0x09,0x01),(0x3E,0x41,0x41,0x51,0x73),
    (0x7F,0x08,0x08,0x08,0x7F),(0x00,0x41,0x7F,0x41,0x00),(0x20,0x40,0x41,0x3F,0x01),(0x7F,0x08,0x14,0x22,0x41),(0x7F,0x40,0x40,0x40,0x40),(0x7F,0x02,0x0C,0x02,0x7F),
    (0x7F,0x04,0x08,0x10,0x7F),(0x3E,0x41,0x41,0x41,0x3E),(0x7F,0x09,0x09,0x09,0x06),(0x3E,0x41,0x51,0x21,0x5E),(0x7F,0x09,0x19,0x29,0x46),(0x26,0x49,0x49,0x49,0x32),
    (0x01,0x01,0x7F,0x01,0x01),(0x3F,0x40,0x40,0x40,0x3F),(0x1F,0x20,0x40,0x20,0x1F),(0x3F,0x40,0x38,0x40,0x3F),(0x63,0x14,0x08,0x14,0x63),(0x07,0x08,0x70,0x08,0x07),(0x61,0x59,0x49,0x4D,0x43),
    (0x00,0x7F,0x41,0x41,0x41),(0x02,0x04,0x08,0x10,0x20),(0x00,0x41,0x41,0x41,0x7F),(0x04,0x02,0x01,0x02,0x04),(0x40,0x40,0x40,0x40,0x40),(0x00,0x07,0x05,0x07,0x00),
    (0x20,0x54,0x54,0x54,0x78),(0x7F,0x48,0x44,0x44,0x38),(0x38,0x44,0x44,0x44,0x20),(0x38,0x44,0x44,0x48,0x7F),(0x38,0x54,0x54,0x54,0x18),(0x08,0x7E,0x09,0x01,0x02),
    (0x18,0xA4,0xA4,0xA4,0x7C),(0x7F,0x08,0x04,0x04,0x78),(0x00,0x44,0x7D,0x40,0x00),(0x20,0x40,0x44,0x3D,0x00),(0x7F,0x10,0x28,0x44,0x00),(0x00,0x41,0x7F,0x40,0x00),
    (0x7C,0x04,0x18,0x04,0x78),(0x7C,0x08,0x04,0x04,0x78),(0x38,0x44,0x44,0x44,0x38),(0xFC,0x24,0x24,0x24,0x18),(0x18,0x24,0x24,0x18,0xFC),(0x7C,0x08,0x04,0x04,0x08),
    (0x48,0x54,0x54,0x54,0x20),(0x04,0x3F,0x44,0x40,0x20),(0x3C,0x40,0x40,0x20,0x7C),(0x1C,0x20,0x40,0x20,0x1C),(0x3C,0x40,0x30,0x40,0x3C),(0x44,0x28,0x10,0x28,0x44),(0x4C,0x50,0x50,0x50,0x3C),(0x44,0x64,0x54,0x4C,0x44),(0x00,0x08,0x36,0x41,0x00),(0x00,0x00,0x7F,0x00,0x00),(0x00,0x41,0x36,0x08,0x00),(0x08,0x04,0x08,0x10,0x08),
)


class _Animation(IntEnum):
    WAKEUP = 0
    RESET = 1
    MOVE_RIGHT_BIG = 2
    MOVE_LEFT_BIG = 3
    BLINK_LONG = 4
    BLINK_SHORT = 5
    HAPPY = 6
    SLEEP = 7
    SACCADE_RANDOM = 8


_FACE_W, _FACE_H = OLED_WIDTH, OLED_HEIGHT
_REF_EYE_H, _REF_EYE_W = 40, 40
_REF_SPACE = 10
_REF_R = 10
_CW, _CB = 1, 0
_ANIM_FRAME_DELAY = 0.025


def _safe_radius(r: int, w: int, h: int) -> int:
    if w < 2*(r+1): r = (w//2)-1
    if h < 2*(r+1): r = (h//2)-1
    return max(0, r)


class _OLED:
    """SSD1306 128x64 OLED (smbus2) + 눈 표정."""
    def __init__(self, bus, addr: int = OLED_ADDR):
        self._bus = bus
        self._addr = addr
        self._buf = bytearray(OLED_BUF_SIZE)
        self._font_first, self._font_w, self._spacing = 0x20, 5, 1
        self.left = SimpleNamespace(height=_REF_EYE_H, width=_REF_EYE_W, x=0, y=0)
        self.right = SimpleNamespace(height=_REF_EYE_H, width=_REF_EYE_W, x=0, y=0)
        self.corner_r = _REF_R

    def _cmd(self, *args: int) -> None:
        with _I2C_LOCK:
            for c in args:
                self._bus.write_byte_data(self._addr, _SSD1306_CMD, c)

    def _data(self, data: bytes) -> None:
        with _I2C_LOCK:
            for i in range(0, len(data), 32):
                block = data[i:i+32]
                self._bus.write_i2c_block_data(self._addr, _SSD1306_DATA, list(block))

    def init(self) -> None:
        self._cmd(_SSD1306_DISPLAYOFF,_SSD1306_SETDISPLAYCLOCKDIV,0x80,_SSD1306_SETMULTIPLEX,0x3F,_SSD1306_SETDISPLAYOFFSET,0x00,_SSD1306_SETSTARTLINE|0x00,_SSD1306_CHARGEPUMP,_SSD1306_SWITCHCAPVCC,_SSD1306_MEMORYMODE,0x00,_SSD1306_SEGREMAP|0x01,_SSD1306_COMSCANDEC,_SSD1306_SETCOMPINS,0x12,_SSD1306_SETCONTRAST,0xCF,_SSD1306_SETPRECHARGE,0xF1,_SSD1306_SETVCOMDETECT,0x40,_SSD1306_DISPLAYALLON_RESUME,_SSD1306_NORMALDISPLAY,_SSD1306_DISPLAYON)

    def clear(self, color: int = 0) -> None:
        fill = 0xFF if color else 0x00
        for i in range(OLED_BUF_SIZE):
            self._buf[i] = fill

    def show(self) -> None:
        with _I2C_LOCK:
            self._cmd(_SSD1306_COLUMNADDR,0,OLED_WIDTH-1,_SSD1306_PAGEADDR,0,OLED_PAGES-1)
            self._data(bytes(self._buf))

    def draw_pixel(self, x: int, y: int, color: int = 1) -> None:
        if 0 <= x < OLED_WIDTH and 0 <= y < OLED_HEIGHT:
            p, b = y // 8, y % 8
            idx = x + p * OLED_WIDTH
            if color: self._buf[idx] |= 1 << b
            else: self._buf[idx] &= ~(1 << b)

    def draw_text(self, s: str, x: int, y: int, color: int = 1) -> None:
        cx = x
        for ch in s:
            code = ord(ch)
            if code < self._font_first or code >= self._font_first + len(_FONT_5X7):
                code = self._font_first
            glyph = _FONT_5X7[code - self._font_first]
            for col in range(self._font_w):
                px = cx + col
                if px >= OLED_WIDTH: break
                byte_val = glyph[col]
                for row in range(8):
                    py = y + row
                    if py >= OLED_HEIGHT: break
                    self.draw_pixel(px, py, color if (byte_val >> row) & 1 else (1 - color))
            cx += self._font_w + self._spacing
            if cx >= OLED_WIDTH: break

    def _round_rect_simple(self, x, y, w, h, r, color):
        r = _safe_radius(r, w, h)
        cx_tl, cy_tl = x + r, y + r
        cx_tr, cy_tr = x + w - 1 - r, y + r
        cx_bl, cy_bl = x + r, y + h - 1 - r
        cx_br, cy_br = x + w - 1 - r, y + h - 1 - r
        r2 = r * r
        for py in range(y, min(y + h, _FACE_H)):
            for px in range(x, min(x + w, _FACE_W)):
                if px < cx_tl and py < cy_tl:
                    inside = (px - cx_tl)**2 + (py - cy_tl)**2 <= r2
                elif px > cx_tr and py < cy_tr:
                    inside = (px - cx_tr)**2 + (py - cy_tr)**2 <= r2
                elif px < cx_bl and py > cy_bl:
                    inside = (px - cx_bl)**2 + (py - cy_bl)**2 <= r2
                elif px > cx_br and py > cy_br:
                    inside = (px - cx_br)**2 + (py - cy_br)**2 <= r2
                else:
                    inside = True
                if inside:
                    self.draw_pixel(px, py, color)

    def _draw_eyes(self):
        rl = _safe_radius(self.corner_r, self.left.width, self.left.height)
        xl = int(self.left.x - self.left.width / 2)
        yl = int(self.left.y - self.left.height / 2)
        self._round_rect_simple(xl, yl, self.left.width, self.left.height, rl, _CW)
        rr = _safe_radius(self.corner_r, self.right.width, self.right.height)
        xr = int(self.right.x - self.right.width / 2)
        yr = int(self.right.y - self.right.height / 2)
        self._round_rect_simple(xr, yr, self.right.width, self.right.height, rr, _CW)

    def draw_frame(self):
        self.clear(0)
        self._draw_eyes()
        self.show()

    def reset_eyes(self, update: bool = True):
        self.left.height = self.right.height = _REF_EYE_H
        self.left.width = self.right.width = _REF_EYE_W
        self.left.x = _FACE_W//2 - _REF_EYE_W//2 - _REF_SPACE//2
        self.left.y = self.right.y = _FACE_H//2
        self.right.x = _FACE_W//2 + _REF_EYE_W//2 + _REF_SPACE//2
        self.corner_r = _REF_R
        if update:
            self.draw_frame()

    def blink(self, speed: int = 12):
        self.reset_eyes(update=False)
        for _ in range(3):
            self.left.height -= speed
            self.right.height -= speed
            cur = self.left.height
            self.corner_r = max(1, min((cur-4)*(_REF_R-1)//(_REF_EYE_H-4)+1, cur//2, _REF_R))
            self.left.width += 3
            self.right.width += 3
            self.draw_frame()
            time.sleep(_ANIM_FRAME_DELAY)
        for _ in range(3):
            self.left.height += speed
            self.right.height += speed
            cur = self.left.height
            self.corner_r = max(1, min((cur-4)*(_REF_R-1)//(_REF_EYE_H-4)+1, cur//2, _REF_R))
            self.left.width -= 3
            self.right.width -= 3
            self.draw_frame()
            time.sleep(_ANIM_FRAME_DELAY)
        self.reset_eyes()

    def sleep(self):
        self.reset_eyes(update=False)
        self.left.height = self.right.height = 2
        self.left.width = self.right.width = _REF_EYE_W
        self.corner_r = 0
        self.draw_frame()

    def wakeup(self):
        self.reset_eyes(update=False)
        for h in range(2, _REF_EYE_H + 1, 2):
            self.left.height = self.right.height = h
            self.corner_r = max(1, min((h-2)*(_REF_R-1)//(_REF_EYE_H-2)+1, h//2, _REF_R))
            self.draw_frame()
            time.sleep(_ANIM_FRAME_DELAY)

    def saccade(self, dx: int, dy: int):
        mx, my, bl = 8, 6, 8
        for i in range(1, 3):
            self.left.x += mx*dx
            self.right.x += mx*dx
            self.left.y += my*dy
            self.right.y += my*dy
            dh = -bl if i == 1 else bl
            self.left.height += dh
            self.right.height += dh
            self.draw_frame()
            time.sleep(_ANIM_FRAME_DELAY)

    def _draw_filled_triangle(self, x0: int, y0: int, x1: int, y1: int, x2: int, y2: int, color: int) -> None:
        xmin = max(0, min(x0, x1, x2))
        xmax = min(OLED_WIDTH - 1, max(x0, x1, x2))
        ymin = max(0, min(y0, y1, y2))
        ymax = min(OLED_HEIGHT - 1, max(y0, y1, y2))

        def sign(pax: int, pay: int, pbx: int, pby: int, pcx: int, pcy: int) -> int:
            return (pax - pcx) * (pby - pcy) - (pbx - pcx) * (pay - pcy)

        for py in range(ymin, ymax + 1):
            for px in range(xmin, xmax + 1):
                s0 = sign(x0, y0, x1, y1, px, py)
                s1 = sign(x1, y1, x2, y2, px, py)
                s2 = sign(x2, y2, x0, y0, px, py)
                if (s0 >= 0 and s1 >= 0 and s2 >= 0) or (s0 <= 0 and s1 <= 0 and s2 <= 0):
                    self.draw_pixel(px, py, color)

    def happy_eye(self) -> None:
        self.reset_eyes(update=True)
        offset = _REF_EYE_H // 2
        for _ in range(10):
            self._draw_filled_triangle(
                int(self.left.x - self.left.width / 2) - 1,
                int(self.left.y) + offset,
                int(self.left.x + self.left.width / 2) + 1,
                int(self.left.y) + 5 + offset,
                int(self.left.x - self.left.width / 2) - 1,
                int(self.left.y) + self.left.height + offset,
                _CB,
            )
            self._draw_filled_triangle(
                int(self.right.x + self.right.width / 2) + 1,
                int(self.right.y) + offset,
                int(self.right.x - self.right.width / 2) - 2,
                int(self.right.y) + 5 + offset,
                int(self.right.x + self.right.width / 2) + 1,
                int(self.right.y) + self.right.height + offset,
                _CB,
            )
            offset -= 2
            self.show()
            time.sleep(_ANIM_FRAME_DELAY)
        time.sleep(1.0)
        self.reset_eyes()

    def move_big_eye(self, direction: int):
        self.reset_eyes(update=False)
        ov, mv, bl = 1, 2, 5
        for _ in range(3):
            self.left.x += mv*direction
            self.right.x += mv*direction
            self.left.height -= bl
            self.right.height -= bl
            if direction > 0: self.right.height += ov; self.right.width += ov
            else: self.left.height += ov; self.left.width += ov
            self.draw_frame()
            time.sleep(_ANIM_FRAME_DELAY)
        for _ in range(3):
            self.left.x += mv*direction
            self.right.x += mv*direction
            self.left.height += bl
            self.right.height += bl
            if direction > 0: self.right.height += ov; self.right.width += ov
            else: self.left.height += ov; self.left.width += ov
            self.draw_frame()
            time.sleep(_ANIM_FRAME_DELAY)
        time.sleep(1.0)
        for _ in range(3):
            self.left.x -= mv*direction
            self.right.x -= mv*direction
            self.left.height -= bl
            self.right.height -= bl
            if direction > 0: self.right.height -= ov; self.right.width -= ov
            else: self.left.height -= ov; self.left.width -= ov
            self.draw_frame()
            time.sleep(_ANIM_FRAME_DELAY)
        for _ in range(3):
            self.left.x -= mv*direction
            self.right.x -= mv*direction
            self.left.height += bl
            self.right.height += bl
            if direction > 0: self.right.height -= ov; self.right.width -= ov
            else: self.left.height -= ov; self.left.width -= ov
            self.draw_frame()
            time.sleep(_ANIM_FRAME_DELAY)
        self.reset_eyes()

    def launch_animation(self, idx: int, block: bool = False):
        def _run():
            try:
                if idx == _Animation.WAKEUP:
                    self.wakeup()
                elif idx == _Animation.RESET:
                    self.reset_eyes(update=True)
                elif idx == _Animation.MOVE_RIGHT_BIG:
                    self.move_big_eye(1)
                elif idx == _Animation.MOVE_LEFT_BIG:
                    self.move_big_eye(-1)
                elif idx == _Animation.BLINK_LONG:
                    self.blink(12)
                    time.sleep(1.0)
                elif idx == _Animation.BLINK_SHORT:
                    self.blink(12)
                elif idx == _Animation.HAPPY:
                    self.happy_eye()
                elif idx == _Animation.SLEEP:
                    self.sleep()
                elif idx == _Animation.SACCADE_RANDOM:
                    self.reset_eyes(update=True)
                    for _ in range(20):
                        dx, dy = random.randint(-1, 1), random.randint(-1, 1)
                        self.saccade(dx, dy)
                        time.sleep(_ANIM_FRAME_DELAY)
                        self.saccade(-dx, -dy)
                        time.sleep(_ANIM_FRAME_DELAY)
            except Exception:
                pass
        if block:
            _run()
        else:
            threading.Thread(target=_run, daemon=True).start()
