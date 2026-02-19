"""OLED QR/scroll using findee.v1._OLED (V1 only)."""
from __future__ import annotations

import threading
import time

_oled = None
_oled_scroll_stop = False
CHAR_WIDTH = 6
TEXT_AREA_WIDTH = 65

# http://10.0.0.1 QR 21x21 (1=검정, 0=흰색)
_QR_10_0_0_1 = (
    (1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1),
    (1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1),
    (1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1, 1, 1, 0, 1),
    (1, 0, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1, 0, 1),
    (1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 1),
    (1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1),
    (1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1),
    (0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0),
    (1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 0, 0, 0, 1, 0, 0),
    (1, 1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 1, 1, 1, 0, 0, 1, 0, 0, 0, 1),
    (1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1),
    (1, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0),
    (1, 1, 1, 1, 1, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 0, 0, 0),
    (0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 0, 1, 1),
    (1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1),
    (1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 0, 0, 0, 1),
    (1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 0, 1, 0),
    (1, 0, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1, 0),
    (1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0, 1),
    (1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0),
    (1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1),
)


def _init_oled() -> bool:
    """Initialize OLED with findee.v1._OLED. Returns True on success."""
    global _oled
    if _oled is not None:
        return True
    try:
        import smbus2
        from findee.v1 import _OLED
        bus = smbus2.SMBus(1)
        _oled = _OLED(bus)
        _oled.init()
        return True
    except Exception:
        return False


def _draw_qr_and_static_text(oled, line_y_positions, static_lines, scroll_line, scroll_x):
    W, H = 21, 21
    scale = 3
    out_w, out_h = W * scale, H * scale
    x_off = 128 - out_w
    y_off = (64 - out_h) // 2
    oled.clear(0)
    for i in range(H):
        for j in range(W):
            pixel = _QR_10_0_0_1[i][j]
            for di in range(scale):
                for dj in range(scale):
                    oled.draw_pixel(x_off + j * scale + dj, y_off + i * scale + di, pixel)
    for i in (0, 1, 3, 4):
        oled.draw_text(static_lines[i], 0, line_y_positions[i])
    oled.draw_text(scroll_line, scroll_x, line_y_positions[2])
    oled.show()


def _oled_scroll_loop(get_robot_name_fn):
    global _oled_scroll_stop
    if _oled is None:
        return
    try:
        robot_name = get_robot_name_fn()
    except Exception:
        robot_name = ""
    scroll_line = f"PF_Kit_Wifi({robot_name})"
    total_width = len(scroll_line) * CHAR_WIDTH
    LINE_SPACING = 10
    FONT_H = 8
    num_lines = 6
    text_block_h = (num_lines - 1) * LINE_SPACING + FONT_H
    text_y_start = (64 - text_block_h) // 2
    line_y_positions = [text_y_start + i * LINE_SPACING for i in range(num_lines)]
    static_lines = [
        "Wifi Setup!",
        "Connect:",
        "",
        "PW:",
        "12345678",
    ]
    while not _oled_scroll_stop:
        try:
            for offset in range(0, total_width + TEXT_AREA_WIDTH + 1, 2):
                if _oled_scroll_stop or _oled is None:
                    return
                scroll_x = TEXT_AREA_WIDTH - total_width - offset
                _draw_qr_and_static_text(_oled, line_y_positions, static_lines, scroll_line, scroll_x)
                time.sleep(0.05)
            time.sleep(1.0)
        except Exception:
            pass


def show_qr_on_oled(get_robot_name_fn):
    """Show QR and scroll text on OLED. V1 only; always use OLED when available."""
    global _oled_scroll_stop
    if _oled is None and not _init_oled():
        return
    if _oled is None:
        return
    try:
        _oled_scroll_stop = False
        t = threading.Thread(target=_oled_scroll_loop, args=(get_robot_name_fn,), daemon=True)
        t.start()
    except Exception:
        pass
