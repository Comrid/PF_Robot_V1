from __future__ import annotations
import gc
import math
import os
import random
import threading
import time
import atexit
import cv2
from enum import IntEnum
from types import SimpleNamespace
import smbus2
import psutil

import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('picamera2').setLevel(logging.ERROR)
os.environ['LIBCAMERA_LOG_FILE'] = '/dev/null'

import RPi.GPIO as GPIO
from picamera2 import Picamera2
import numpy as np

USE_DEBUG = False

#region OLED
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

# 5x7 폰트 ASCII 0x20~0x7E (각 문자 5바이트)
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

# 눈 표정용 상수 (control_display.ino 호환)
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


def _safe_radius(r: int, w: int, h: int) -> int:
    if w < 2*(r+1): r = (w//2)-1
    if h < 2*(r+1): r = (h//2)-1
    return max(0, r)


class _OLED:
    """SSD1306 128x64 OLED (smbus2, 단일 파일 내장) + 눈 표정."""
    def __init__(self, bus, addr: int = OLED_ADDR):
        self._bus = bus
        self._addr = addr
        self._buf = bytearray(OLED_BUF_SIZE)
        self._font_first, self._font_w, self._spacing = 0x20, 5, 1
        self.left = SimpleNamespace(height=_REF_EYE_H, width=_REF_EYE_W, x=0, y=0)
        self.right = SimpleNamespace(height=_REF_EYE_H, width=_REF_EYE_W, x=0, y=0)
        self.corner_r = _REF_R

    def _cmd(self, *args: int) -> None:
        for c in args:
            self._bus.write_byte_data(self._addr, _SSD1306_CMD, c)

    def _data(self, data: bytes) -> None:
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
            time.sleep(0.001)
        for _ in range(3):
            self.left.height += speed
            self.right.height += speed
            cur = self.left.height
            self.corner_r = max(1, min((cur-4)*(_REF_R-1)//(_REF_EYE_H-4)+1, cur//2, _REF_R))
            self.left.width -= 3
            self.right.width -= 3
            self.draw_frame()
            time.sleep(0.001)
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
            time.sleep(0.001)

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
            time.sleep(0.001)

    def _draw_filled_triangle(self, x0: int, y0: int, x1: int, y1: int, x2: int, y2: int, color: int) -> None:
        """채운 삼각형 (draw_pixel만 사용)."""
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
        """control_display.ino happy_eye: 아래쪽 검정 삼각형으로 가림, offset -= 2."""
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
            time.sleep(0.001)
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
            time.sleep(0.001)
        for _ in range(3):
            self.left.x += mv*direction
            self.right.x += mv*direction
            self.left.height += bl
            self.right.height += bl
            if direction > 0: self.right.height += ov; self.right.width += ov
            else: self.left.height += ov; self.left.width += ov
            self.draw_frame()
            time.sleep(0.001)
        time.sleep(1.0)
        for _ in range(3):
            self.left.x -= mv*direction
            self.right.x -= mv*direction
            self.left.height -= bl
            self.right.height -= bl
            if direction > 0: self.right.height -= ov; self.right.width -= ov
            else: self.left.height -= ov; self.left.width -= ov
            self.draw_frame()
            time.sleep(0.001)
        for _ in range(3):
            self.left.x -= mv*direction
            self.right.x -= mv*direction
            self.left.height += bl
            self.right.height += bl
            if direction > 0: self.right.height -= ov; self.right.width -= ov
            else: self.left.height -= ov; self.left.width -= ov
            self.draw_frame()
            time.sleep(0.001)
        self.reset_eyes()

    def launch_animation(self, idx: int, block: bool = False):
        """표정 애니메이션 재생. block=False(기본)이면 백그라운드 스레드에서 재생해 즉시 반환."""
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
                        time.sleep(0.001)
                        self.saccade(-dx, -dy)
                        time.sleep(0.001)
            except Exception:
                pass
        if block:
            _run()
        else:
            threading.Thread(target=_run, daemon=True).start()

#endregion

#region MPU6050
_MPU_ADDR = 0x68
_REG_PWR = 0x6B
_REG_SMPLRT = 0x19
_REG_CFG = 0x1A
_REG_GYRO_CFG = 0x1B
_REG_ACCEL_CFG = 0x1C
_REG_INT_PIN_CFG = 0x37
_REG_INT_ENABLE = 0x38
_REG_ACCEL_XOUT_H = 0x3B
_MPU_INT_GPIO_BCM = 4   # GY-521 INT 핀 (BCM)
_MPU_BOUNCETIME_MS = 1
_ACCEL_SCALE = 16384.0
_GYRO_SCALE = 131.0
_GRAVITY = 9.80665
_MADGWICK_BETA = 0.05


class _IMU:
    """MPU6050 + Madgwick 6DOF. Data Ready 인터럽트(GPIO 4)로 100Hz 갱신, 별도 스레드에서 update()."""
    def __init__(self, bus, addr: int = _MPU_ADDR):
        self._bus = bus
        self._addr = addr
        self._q = [1.0, 0.0, 0.0, 0.0]
        self._roll = self._pitch = self._yaw = 0.0
        self._gyro_off = (0.0, 0.0, 0.0)
        self._accel_off = (0.0, 0.0, 0.0)
        self._last_ts = None
        self._last_gyro_rad = None
        self._offset_m = (0.03, 0.0, 0.0)
        self._running = False
        self._int_occurred = False
        self._read_thread = None

    def init(self) -> None:
        self._bus.write_byte_data(self._addr, _REG_PWR, 0x00)
        time.sleep(0.1)
        self._bus.write_byte_data(self._addr, _REG_SMPLRT, 0x09)
        self._bus.write_byte_data(self._addr, _REG_CFG, 0x03)
        self._bus.write_byte_data(self._addr, _REG_GYRO_CFG, 0x00)
        self._bus.write_byte_data(self._addr, _REG_ACCEL_CFG, 0x00)
        self._bus.write_byte_data(self._addr, _REG_INT_PIN_CFG, 0x80)
        self._bus.write_byte_data(self._addr, _REG_INT_ENABLE, 0x01)
        self._last_ts = time.monotonic()
        self._q = [1.0, 0.0, 0.0, 0.0]
        self._last_gyro_rad = None

    def _on_int(self, channel):
        self._int_occurred = True

    def _read_loop(self) -> None:
        while self._running:
            if self._int_occurred:
                self._int_occurred = False
                try:
                    self.update()
                except Exception:
                    pass
            else:
                time.sleep(0.0001)

    def start(self) -> None:
        if self._running:
            return
        try:
            GPIO.remove_event_detect(_MPU_INT_GPIO_BCM)
        except (RuntimeError, ValueError):
            pass
        try:
            GPIO.cleanup(_MPU_INT_GPIO_BCM)
        except (RuntimeError, ValueError):
            pass
        GPIO.setup(_MPU_INT_GPIO_BCM, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        time.sleep(0.01)
        GPIO.add_event_detect(_MPU_INT_GPIO_BCM, GPIO.FALLING, callback=self._on_int, bouncetime=_MPU_BOUNCETIME_MS)
        self._running = True
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()

    def stop(self) -> None:
        self._running = False
        if self._read_thread is not None:
            self._read_thread.join(timeout=1.0)
        try:
            GPIO.remove_event_detect(_MPU_INT_GPIO_BCM)
        except (RuntimeError, ValueError):
            pass

    @staticmethod
    def _s16(h, l):
        v = (h << 8) | l
        return v - 65536 if v >= 32768 else v

    def _read_block(self):
        return self._bus.read_i2c_block_data(self._addr, _REG_ACCEL_XOUT_H, 14)

    def get_raw_data(self):
        b = self._read_block()
        ax = self._s16(b[0], b[1]) / _ACCEL_SCALE - self._accel_off[0]
        ay = self._s16(b[2], b[3]) / _ACCEL_SCALE - self._accel_off[1]
        az = self._s16(b[4], b[5]) / _ACCEL_SCALE - self._accel_off[2]
        gx = self._s16(b[8], b[9]) / _GYRO_SCALE - self._gyro_off[0]
        gy = self._s16(b[10], b[11]) / _GYRO_SCALE - self._gyro_off[1]
        gz = self._s16(b[12], b[13]) / _GYRO_SCALE - self._gyro_off[2]
        return ax, ay, az, gx, gy, gz

    def _lever_arm(self, ax, ay, az, gx, gy, gz, dt):
        rx, ry, rz = self._offset_m
        if rx == ry == rz == 0:
            return ax, ay, az
        deg2rad = math.pi / 180.0
        wx, wy, wz = gx * deg2rad, gy * deg2rad, gz * deg2rad
        if self._last_gyro_rad and dt > 0:
            ax_ = (wx - self._last_gyro_rad[0]) / dt
            ay_ = (wy - self._last_gyro_rad[1]) / dt
            az_ = (wz - self._last_gyro_rad[2]) / dt
        else:
            ax_, ay_, az_ = 0.0, 0.0, 0.0
        self._last_gyro_rad = (wx, wy, wz)
        def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
        om = (wx, wy, wz)
        r = (rx, ry, rz)
        tan_acc = cross((ax_, ay_, az_), r)
        cen_acc = cross(om, cross(om, r))
        c = 1.0 / _GRAVITY
        return ax - (tan_acc[0]+cen_acc[0])*c, ay - (tan_acc[1]+cen_acc[1])*c, az - (tan_acc[2]+cen_acc[2])*c

    def _madgwick(self, gx, gy, gz, ax, ay, az, dt):
        q0, q1, q2, q3 = self._q
        qd1 = 0.5 * (-q1*gx - q2*gy - q3*gz)
        qd2 = 0.5 * ( q0*gx + q2*gz - q3*gy)
        qd3 = 0.5 * ( q0*gy - q1*gz + q3*gx)
        qd4 = 0.5 * ( q0*gz + q1*gy - q2*gx)
        if not (ax == ay == az == 0.0):
            n = 1.0 / math.sqrt(ax*ax + ay*ay + az*az)
            ax, ay, az = ax*n, ay*n, az*n
            s0 = 4*q0*q2*q2 + 2*q2*ax + 4*q0*q1*q1 - 2*q1*ay
            s1 = 4*q1*q3*q3 - 2*q3*ax + 4*q0*q0*q1 - 2*q0*ay - 4*q1 + 8*q1*q1*q1 + 8*q1*q2*q2 + 4*q1*az
            s2 = 4*q0*q0*q2 + 2*q0*ax + 4*q2*q3*q3 - 2*q3*ay - 4*q2 + 8*q2*q1*q1 + 8*q2*q2*q2 + 4*q2*az
            s3 = 4*q1*q1*q3 - 2*q1*ax + 4*q2*q2*q3 - 2*q2*ay
            n = 1.0 / math.sqrt(s0*s0 + s1*s1 + s2*s2 + s3*s3)
            qd1 -= _MADGWICK_BETA * s0 * n
            qd2 -= _MADGWICK_BETA * s1 * n
            qd3 -= _MADGWICK_BETA * s2 * n
            qd4 -= _MADGWICK_BETA * s3 * n
        q0 += qd1*dt; q1 += qd2*dt; q2 += qd3*dt; q3 += qd4*dt
        n = 1.0 / math.sqrt(q0*q0 + q1*q1 + q2*q2 + q3*q3)
        self._q = [q0*n, q1*n, q2*n, q3*n]

    def _quat_to_euler(self):
        q0, q1, q2, q3 = self._q
        sinr = 2*(q0*q1 + q2*q3)
        cosr = 1 - 2*(q1*q1 + q2*q2)
        roll = math.atan2(sinr, cosr)
        sinp = 2*(q0*q2 - q3*q1)
        pitch = math.asin(max(-1, min(1, sinp))) if abs(sinp) < 1 else math.copysign(math.pi/2, sinp)
        siny = 2*(q0*q3 + q1*q2)
        cosy = 1 - 2*(q2*q2 + q3*q3)
        yaw = math.atan2(siny, cosy)
        return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)

    def update(self) -> None:
        ax, ay, az, gx, gy, gz = self.get_raw_data()
        now = time.monotonic()
        dt = now - self._last_ts if self._last_ts else 0.01
        self._last_ts = now
        ax, ay, az = self._lever_arm(ax, ay, az, gx, gy, gz, dt)
        deg2rad = math.pi / 180.0
        self._madgwick(gx*deg2rad, gy*deg2rad, gz*deg2rad, ax, ay, az, dt)
        self._roll, self._pitch, self._yaw = self._quat_to_euler()

    def calibrate(self, samples: int = 500) -> None:
        gx_s = gy_s = gz_s = ax_s = ay_s = az_s = 0.0
        for _ in range(samples):
            b = self._read_block()
            ax_s += self._s16(b[0], b[1]); ay_s += self._s16(b[2], b[3]); az_s += self._s16(b[4], b[5])
            gx_s += self._s16(b[8], b[9]); gy_s += self._s16(b[10], b[11]); gz_s += self._s16(b[12], b[13])
            time.sleep(0.002)
        n = samples
        self._gyro_off = (gx_s/n/_GYRO_SCALE, gy_s/n/_GYRO_SCALE, gz_s/n/_GYRO_SCALE)
        self._accel_off = (ax_s/n/_ACCEL_SCALE, ay_s/n/_ACCEL_SCALE, az_s/n/_ACCEL_SCALE - 1.0)

    def get_rpy(self):
        return self._roll, self._pitch, self._yaw

#endregion

#region INA219
_INA_ADDR = 0x40
_INA_REG_CFG, _INA_REG_BUS_V, _INA_REG_CURRENT, _INA_REG_CAL = 0x00, 0x02, 0x04, 0x05
_INA_RST = 1<<15
_INA_BRNG_32V = 1<<13
_INA_PGA_320 = 3<<11
_INA_ADC_12 = (3<<7)|(3<<3)
_INA_MODE_CONT = 7
_INA_BUS_LSB = 0.004
_INA_CAL_K = 0.04096
_INA_CURRENT_MAX = 32767
_INA_SHUNT_OHM = 0.1
_INA_MAX_AMP = 3.0


class _Battery:
    """INA219 전압/전류 (단일 파일 내장)."""
    def __init__(self, bus, addr: int = _INA_ADDR, shunt_ohm: float = _INA_SHUNT_OHM, max_amp: float = _INA_MAX_AMP):
        self._bus = bus
        self._addr = addr
        self._shunt = shunt_ohm
        self._current_lsb = max_amp / _INA_CURRENT_MAX
        self._cal = max(1, int(_INA_CAL_K / (self._current_lsb * shunt_ohm)))

    def init(self) -> None:
        self._w16(_INA_REG_CFG, _INA_RST)
        time.sleep(0.002)
        self._w16(_INA_REG_CFG, _INA_BRNG_32V | _INA_PGA_320 | _INA_ADC_12 | _INA_MODE_CONT)
        self._w16(_INA_REG_CAL, self._cal)

    def _w16(self, reg: int, val: int) -> None:
        self._bus.write_i2c_block_data(self._addr, reg, [(val>>8)&0xFF, val&0xFF])

    def _r16(self, reg: int) -> int:
        d = self._bus.read_i2c_block_data(self._addr, reg, 2)
        return (d[0]<<8)|d[1]

    def voltage(self) -> float:
        raw = self._r16(_INA_REG_BUS_V) >> 3
        return raw * _INA_BUS_LSB

    def current(self) -> float:
        v = self._r16(_INA_REG_CURRENT)
        v = v - 0x10000 if v >= 0x8000 else v
        return v * self._current_lsb
#endregion

def debug_decorator(func):
    def wrapper(*args, **kwargs):
        if USE_DEBUG:
            print(f"DEBUG: {func.__name__} Called")
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if USE_DEBUG:
                print(f"DEBUG: ERR:{e}")
            raise
    return wrapper

class Findee:
    default_speed: float = 50.0
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Findee, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, safe_mode: bool = False):
        if self._initialized: return
        self._initialized = True

        self.gpio_init()
        self.camera_init()
        self._code_running = False
        self._oled_stop = False
        self._oled_thread = None
        self._oled_status = ""

        self._i2c = smbus2.SMBus(1)
        self._oled = _OLED(self._i2c)
        self._imu = _IMU(self._i2c)
        self._battery = _Battery(self._i2c)

        self._oled.init()
        self._oled.clear(0)

        self._imu.init()
        self._imu.calibrate()
        self._imu.start()

        self._battery.init()

        time.sleep(5)
        self._oled_thread = threading.Thread(target=self._oled_loop, daemon=True)
        self._oled_thread.start()

        atexit.register(self.cleanup)

    def set_code_running(self, running: bool) -> None:
        """로봇 코드 실행 중이면 True. OLED 표정은 중단하고 기울기 시 배터리만 표시."""
        self._code_running = running

    def get_oled(self):
        """블록코딩/사용자 코드에서 OLED·표정 제어용. clear, draw_text, show, launch_animation 등 사용."""
        return self._oled

    def set_oled_status(self, status: str) -> None:
        """OLED 상태 문구 설정. 비어 있으면 표정/배터리 표시, 아니면 해당 문구만 표시 (예: '서버 연결 중', '대기 중')."""
        self._oled_status = (status or "").strip()

    def _battery_remaining_pct(self, voltage: float) -> float:
        """6.5V=0%, 8.1V=100%, 0~100으로 제한."""
        pct = (voltage - 6.5) / (8.1 - 6.5) * 100.0
        return max(0.0, min(100.0, pct))

    def _oled_loop(self) -> None:
        """OLED: 코드 미실행 시 표정 랜덤 반복. roll>=70° 0.5초 유지 시 배터리 정보 표시. IMU는 인터럽트 100Hz, 배터리 10Hz."""
        if self._i2c is None or not hasattr(self, '_oled'):
            return
        high_roll_start = None
        showing_battery = False
        last_battery_draw = 0.0
        last_anim_time = 0.0
        last_status_draw = 0.0
        LINE_SPACING = 14
        ROLL_THRESH = 30
        HOLD_S = 0.5

        while not getattr(self, '_oled_stop', True):
            time.sleep(0.01)
            if self._code_running:
                continue
            try:
                roll, _, _ = self._imu.get_rpy()
            except Exception:
                roll = 0.0
            if abs(roll) >= ROLL_THRESH:
                if high_roll_start is None:
                    high_roll_start = time.monotonic()
                elif time.monotonic() - high_roll_start >= HOLD_S:
                    showing_battery = True
            else:
                high_roll_start = None
                showing_battery = False
            if showing_battery:
                now = time.monotonic()
                if now - last_battery_draw >= 0.1:
                    last_battery_draw = now
                    try:
                        v = self._battery.voltage()
                        i = self._battery.current()
                        pct = self._battery_remaining_pct(v)
                        r, p, y = self._imu.get_rpy()
                        cpu_pct = int(psutil.cpu_percent()) if psutil is not None else 0
                    except Exception:
                        v, i, pct = 0.0, 0.0, 0.0
                        r, p, y = 0.0, 0.0, 0.0
                        cpu_pct = 0
                    self._oled.clear(0)
                    self._oled.draw_text("[ Battery Info ]", 0, 0)
                    i_mA = int(i * 1000)
                    self._oled.draw_text(f"V: {v:.2f} V, I: {i_mA} mA", 0, LINE_SPACING)
                    self._oled.draw_text(f"Remaining : {pct:.0f}%", 0, LINE_SPACING * 2)
                    self._oled.draw_text(f"CPU: {cpu_pct} %", 0, LINE_SPACING * 3)
                    self._oled.draw_text(f"R:{r:.1f} P:{p:.1f} Y:{y:.1f}", 0, LINE_SPACING * 4)
                    self._oled.show()
            else:
                status = getattr(self, '_oled_status', '')
                if status:
                    now = time.monotonic()
                    if now - last_status_draw >= 0.3:
                        last_status_draw = now
                        try:
                            self._oled.clear(0)
                            for i, line in enumerate(status.split('\n')):
                                self._oled.draw_text(line, 0, LINE_SPACING * i)
                            self._oled.show()
                        except Exception:
                            pass
                else:
                    now = time.monotonic()
                    if now - last_anim_time >= 2.5:
                        last_anim_time = now
                        try:
                            idx = random.choice([_Animation.HAPPY, _Animation.BLINK_SHORT, _Animation.MOVE_LEFT_BIG, _Animation.MOVE_RIGHT_BIG])
                            self._oled.launch_animation(idx)
                        except Exception:
                            pass

#region: init
    # DRV8833: 모터당 IN1, IN2 두 핀에 각각 PWM (ENA/ENB 없음)
    PWM_FREQ: int = 1000  # Hz

    @debug_decorator
    def gpio_init(self):
        # 이전 실행이 cleanup 없이 종료된 경우 핀이 점유된 상태일 수 있음 → 먼저 해제
        try:
            GPIO.cleanup()
        except Exception:
            pass
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        # DRV8833 Pin (005_Motor_test.py 기준)
        self.AIN1: int = 24  # Right Motor (A) IN1
        self.AIN2: int = 23  # Right Motor (A) IN2
        self.BIN1: int = 27  # Left Motor (B) IN1
        self.BIN2: int = 22  # Left Motor (B) IN2
        self.nSLEEP: int = 25  # DRV8833 활성화 (HIGH=활성)
        self.TRIG: int = 5   # Ultrasonic Sensor Trigger
        self.ECHO: int = 6   # Ultrasonic Sensor Echo

        # GPIO Pin Setting
        GPIO.setup((self.AIN1, self.AIN2, self.BIN1, self.BIN2, self.nSLEEP, self.TRIG),
                   GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.ECHO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.output(self.nSLEEP, GPIO.HIGH)

        # DRV8833: 모터당 2개 PWM
        self._pwm_ain1 = GPIO.PWM(self.AIN1, self.PWM_FREQ)
        self._pwm_ain2 = GPIO.PWM(self.AIN2, self.PWM_FREQ)
        self._pwm_bin1 = GPIO.PWM(self.BIN1, self.PWM_FREQ)
        self._pwm_bin2 = GPIO.PWM(self.BIN2, self.PWM_FREQ)
        self._pwm_ain1.start(0)
        self._pwm_ain2.start(0)
        self._pwm_bin1.start(0)
        self._pwm_bin2.start(0)

    @debug_decorator
    def camera_init(self):
        # Camera Init
        self.camera = Picamera2()
        self.config = self.camera.create_video_configuration(
            main={"size": (640, 480), "format": "RGB888"},
            controls={"FrameDurationLimits": (33333, 33333)},
            queue=False, buffer_count=2
        )
        self.camera.configure(self.config)
        self.camera.start()
#endregion

#region: Motor
    @staticmethod
    def constrain(value, min_value, max_value):
        return max(min(value, max_value), min_value)

    def _duty(self, speed: float) -> float:
        """speed -100~100 -> 듀티 0~100."""
        return max(0.0, min(100.0, abs(speed)))

    def _set_channel(self, speed: float, pwm1: GPIO.PWM, pwm2: GPIO.PWM, decay: str = "slow"):
        """DRV8833 한 채널(IN1, IN2) 제어. speed: -100~100, decay: 'slow' | 'fast'."""
        duty = self._duty(speed)
        fwd = speed >= 0
        if decay == "slow":
            if fwd:
                pwm1.ChangeDutyCycle(duty)
                pwm2.ChangeDutyCycle(0)
            else:
                pwm1.ChangeDutyCycle(0)
                pwm2.ChangeDutyCycle(duty)
        else:
            if fwd:
                pwm1.ChangeDutyCycle(duty)
                pwm2.ChangeDutyCycle(100 - duty)
            else:
                pwm1.ChangeDutyCycle(100 - duty)
                pwm2.ChangeDutyCycle(duty)

    def control_motors(self, left: float, right: float, decay: str = "slow") -> None:
        """DRV8833: 오른쪽=A(AIN1/AIN2), 왼쪽=B(BIN1/BIN2), 각 채널 2핀 PWM."""
        def normalize(s: float) -> float:
            return (1 if s >= 0 else -1) * self.constrain(abs(s), 20, 100) if s != 0.0 else 0.0
        self._set_channel(normalize(right), self._pwm_ain1, self._pwm_ain2, decay)
        self._set_channel(normalize(left), self._pwm_bin1, self._pwm_bin2, decay)

    # Stop
    @debug_decorator
    def stop(self):
        self.control_motors(0.0, 0.0)

    @debug_decorator
    def force_stop(self):
        """양쪽 모터 IN1·IN2 모두 HIGH로 제동(short brake) 0.5초 후 LOW로 해제."""
        self._pwm_ain1.ChangeDutyCycle(100)
        self._pwm_ain2.ChangeDutyCycle(100)
        self._pwm_bin1.ChangeDutyCycle(100)
        self._pwm_bin2.ChangeDutyCycle(100)
        time.sleep(0.5)
        self._pwm_ain1.ChangeDutyCycle(0)
        self._pwm_ain2.ChangeDutyCycle(0)
        self._pwm_bin1.ChangeDutyCycle(0)
        self._pwm_bin2.ChangeDutyCycle(0)

    # Straight, Backward
    @debug_decorator
    def move_forward(self, speed: float = default_speed, duration: float = 0.0):
        self.control_motors(speed, speed)
        self.__duration_check(duration)

    @debug_decorator
    def move_backward(self, speed: float = default_speed, duration: float = 0.0):
        self.control_motors(-speed, -speed)
        self.__duration_check(duration)

    # Rotation
    @debug_decorator
    def turn_left(self, speed: float = default_speed, duration: float = 0.0):
        self.control_motors(-speed, speed)
        self.__duration_check(duration)

    @debug_decorator
    def turn_right(self, speed: float = default_speed, duration: float = 0.0):
        self.control_motors(speed, -speed)
        self.__duration_check(duration)

    # Curvilinear
    @debug_decorator
    def curve_left(self, speed: float = default_speed, ratio: float = 0.5, duration: float = 0.0):
        self.control_motors(speed * ratio, speed)
        self.__duration_check(duration)

    @debug_decorator
    def curve_right(self, speed: float = default_speed, ratio: float = 0.5, duration: float = 0.0):
        self.control_motors(speed, speed * ratio)
        self.__duration_check(duration)

    def __duration_check(self, duration: float):
        if duration < 0.0:
            raise ValueError("Duration must be greater or equal to 0.0")
        elif duration > 0.0:
            time.sleep(duration); self.stop()
        else:
            return
#endregion

#region: Ultrasonic Sensor
    @debug_decorator
    def get_distance(self):
        # Return
        # -1 : Trig Timeout
        # -2 : Echo Timeout
        # Trigger
        GPIO.output(self.TRIG, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(self.TRIG, GPIO.LOW)

        # Measure Distance
        t1 = time.time()
        while GPIO.input(self.ECHO) is not GPIO.HIGH:
            if time.time() - t1 > 0.1: # 100ms
                return -1

        t1 = time.time()

        while GPIO.input(self.ECHO) is not GPIO.LOW:
            if time.time() - t1 > 0.03: # 30ms
                return -2

        t2 = time.time()

        # Measure Success
        distance = ((t2 - t1) * 34300) / 2
        return round(distance, 1)
#endregion

#region: Cameras
    def get_frame(self):
        return self.camera.capture_array("main").copy()

    def mjpeg_gen(self):
        while True:
            # RGB 프레임 -> BGR로 변환(OpenCV는 BGR 기준)
            arr = self.camera.capture_array("main").copy()

            ok, buf = cv2.imencode('.jpg', arr, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if not ok:
                continue
            jpg = buf.tobytes()

            yield (b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" +
                jpg + b"\r\n")

            # 과도한 CPU 점유 방지
            time.sleep(0.001)
#endregion

#region: Image Processing
    def mask_image(self, hsv_image, slider_values: list[int]):
        if slider_values is None or len(slider_values) != 6:
            print("배열의 값이 6개가 아닙니다.")
            return None
        if hsv_image is None or not isinstance(hsv_image, np.ndarray):
            print("이미지가 None 이거나 또는 np.ndarray가 아닙니다.")
            return None

        lower_bound = np.array([int(slider_values[0]), int(slider_values[2]), int(slider_values[4])])
        upper_bound = np.array([int(slider_values[1]), int(slider_values[3]), int(slider_values[5])])

        return cv2.inRange(hsv_image, lower_bound, upper_bound)

    def detect_traffic_light(self, hsv_image, green_bound=None, red_bound=None):
        """
        신호등 색상 인식 함수 (Contour 기반 필터링)

        Args:
            hsv_image: HSV 형식의 이미지 (numpy array)
            green_bound: 초록색 HSV 범위 [h_lower, h_upper, s_lower, s_upper, v_lower, v_upper]
                        기본값: [30, 80, 20, 255, 100, 255]
            red_bound: 빨간색 HSV 범위 [h_lower, h_upper, s_lower, s_upper, v_lower, v_upper]
                      기본값: [160, 180, 90, 255, 200, 255]

        Returns:
            0: 인식되지 않음
            1: 초록색 인식
            2: 빨간색 인식
        """
        if hsv_image is None or not isinstance(hsv_image, np.ndarray):
            return 0

        # 기본값 설정
        if green_bound is None:
            green_bound = [30, 80, 20, 255, 100, 255]
        if red_bound is None:
            red_bound = [160, 180, 90, 255, 200, 255]

        # 입력 검증
        if len(green_bound) != 6 or len(red_bound) != 6:
            print("HSV 범위 배열은 6개의 요소를 가져야 합니다.")
            return 0

        # 초록색 HSV 범위
        green_lower = np.array([green_bound[0], green_bound[2], green_bound[4]])
        green_upper = np.array([green_bound[1], green_bound[3], green_bound[5]])
        green_mask = cv2.inRange(hsv_image, green_lower, green_upper)

        # 빨간색 HSV 범위
        red_lower = np.array([red_bound[0], red_bound[2], red_bound[4]])
        red_upper = np.array([red_bound[1], red_bound[3], red_bound[5]])
        red_mask = cv2.inRange(hsv_image, red_lower, red_upper)

        # Contour 기반 필터링: 가장 큰 뭉친 영역의 면적 계산
        def get_largest_contour_area(mask):
            """마스크에서 가장 큰 contour의 면적 반환"""
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return 0
            largest_contour = max(contours, key=cv2.contourArea)
            return cv2.contourArea(largest_contour)

        # 각 색상의 가장 큰 contour 면적 계산
        green_area = get_largest_contour_area(green_mask)
        red_area = get_largest_contour_area(red_mask)

        # 최소 면적 기준 (노이즈 제거, 픽셀 단위)
        min_area = 100

        # 우선순위: 빨간색 > 초록색 (빨간색이 더 중요)
        if red_area >= min_area:
            return 2
        elif green_area >= min_area:
            return 1
        else:
            return 0

#endregion

#region: others
    @debug_decorator
    def cleanup(self):
        self._oled.clear(0)
        self._oled.show()
        self._oled_stop = True
        if self._oled_thread is not None and self._oled_thread.is_alive():
            self._oled_thread.join(timeout=1.0)
        if hasattr(self, '_imu') and self._imu is not None:
            self._imu.stop()
        if self._i2c is not None:
            try:
                self._i2c.close()
            except Exception:
                pass
            self._i2c = None
        # GPIO Cleanup (DRV8833). PWM 참조 해제 후 gc로 __del__을 먼저 실행해 lgpio 오류 방지.
        self.control_motors(0.0, 0.0)
        for p in ('_pwm_ain1', '_pwm_ain2', '_pwm_bin1', '_pwm_bin2'):
            if hasattr(self, p) and getattr(self, p) is not None:
                getattr(self, p).stop()
        self._pwm_ain1 = self._pwm_ain2 = self._pwm_bin1 = self._pwm_bin2 = None
        gc.collect()
        GPIO.output((self.AIN1, self.AIN2, self.BIN1, self.BIN2, self.nSLEEP, self.TRIG), GPIO.LOW)
        GPIO.cleanup()

        # Camera Cleanup
        if hasattr(self, 'camera'):
            if hasattr(self.camera, 'stop'):
                self.camera.stop()
            if hasattr(self.camera, 'close'):
                self.camera.close()
            del self.camera

        Findee._instance = None
        Findee._initialized = False
#endregion
