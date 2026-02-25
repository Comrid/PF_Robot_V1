"""OLED QR + 고정 텍스트 (와이파이 셋업) using findee 공용 OLED (V1 only)."""
from __future__ import annotations

import threading
import time

from findee._oled_shared import get_shared_oled, stop_buffering_animation

_oled = None
_oled_scroll_stop = False
CHAR_WIDTH = 6
# QR 오른쪽 붙임 시 왼쪽 텍스트 영역 (128 - 42 = 86, 여유 2)
TEXT_AREA_WIDTH = 84

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
    """공용 OLED 사용. 없으면 초기화 후 True/False 반환."""
    global _oled
    if _oled is not None:
        return True
    try:
        _oled = get_shared_oled(init_if_missing=True)
        return _oled is not None
    except Exception:
        return False


def _draw_qr_and_static_text(oled, line_y_positions, static_lines, wifi_name_line, wifi_name_x):
    W, H = 21, 21
    scale = 2  # 1/2 of previous (was 3 → 63px; now 42px). Check camera scan.
    out_w, out_h = W * scale, H * scale
    # QR: 오른쪽 아래로 붙임
    x_off = 128 - out_w
    y_off = 64 - out_h
    oled.clear(0)
    for i in range(H):
        for j in range(W):
            pixel = _QR_10_0_0_1[i][j]
            for di in range(scale):
                for dj in range(scale):
                    oled.draw_pixel(x_off + j * scale + dj, y_off + i * scale + di, pixel)
    for i in (0, 1, 3, 4):
        oled.draw_text(static_lines[i], 0, line_y_positions[i])
    oled.draw_text(wifi_name_line, wifi_name_x, line_y_positions[2])
    oled.show()


def _oled_scroll_loop(get_robot_name_fn):
    global _oled_scroll_stop
    if _oled is None:
        return
    try:
        robot_name = get_robot_name_fn()
    except Exception:
        robot_name = ""
    # 와이파이 아이디 고정 표시 (이동 없음). 길면 영역 안에 맞게 잘라서 표시
    raw_line = f"PF_Kit_Wifi({robot_name})"
    max_chars = TEXT_AREA_WIDTH // CHAR_WIDTH
    wifi_name_line = raw_line[:max_chars] if len(raw_line) > max_chars else raw_line
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
            if _oled_scroll_stop or _oled is None:
                return
            _draw_qr_and_static_text(_oled, line_y_positions, static_lines, wifi_name_line, 0)
            time.sleep(1.0)
        except Exception:
            pass


def show_qr_on_oled(get_robot_name_fn):
    """Show QR(오른쪽 아래) + 고정 와이파이 문구 on OLED. 버퍼링 중지 후 와이파이 셋업 표시."""
    global _oled_scroll_stop
    stop_buffering_animation()
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