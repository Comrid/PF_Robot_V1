"""OLED 와이파이 셋업: 화면1(와이파이 정보) / 화면2(QR). 연결된 기기 유무로 전환."""
from __future__ import annotations

import threading
import time

from findee._oled_shared import get_shared_oled, stop_buffering_animation

from wifi_setup.client_check import has_connected_client

_oled = None
_oled_stop = False
CHAR_WIDTH = 6
LINE_SPACING = 10
FONT_H = 8
POLL_INTERVAL = 3  # 연결 감지 주기 (초)

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


def _draw_wifi_info_screen(oled, robot_name: str) -> None:
    """화면1: QR 없이 Wi-Fi / Name / PW 만 표시."""
    oled.clear(0)
    y_start = 4
    lines = [
        "Wi-Fi",
        "Name:",
        f"PF_Kit_Wifi({robot_name})"[:21],  # 화면 너비 내
        "PW:",
        "12345678",
    ]
    for i, s in enumerate(lines):
        oled.draw_text(s, 0, y_start + i * LINE_SPACING)
    oled.show()


def _draw_qr_screen(oled) -> None:
    """화면2: QR(scale=3, 오른쪽 아래) + 왼쪽에 Connect / Setup Browser ! / 화살표."""
    W, H = 21, 21
    scale = 3
    out_w, out_h = W * scale, H * scale
    x_off = 128 - out_w
    y_off = 64 - out_h
    oled.clear(0)
    for i in range(H):
        for j in range(W):
            pixel = _QR_10_0_0_1[i][j]
            for di in range(scale):
                for dj in range(scale):
                    oled.draw_pixel(x_off + j * scale + dj, y_off + i * scale + di, pixel)
    # 왼쪽 텍스트 (3줄)
    left_lines = ["Connect", "Setup !", "->"]
    y_start = (64 - (len(left_lines) - 1) * LINE_SPACING - FONT_H) // 2
    for i, s in enumerate(left_lines):
        oled.draw_text(s, 0, y_start + i * LINE_SPACING)
    oled.show()


def _oled_loop(get_robot_name_fn):
    """연결 유무 폴링 → 화면1(정보) / 화면2(QR) 전환."""
    global _oled_stop
    if _oled is None:
        return
    while not _oled_stop:
        try:
            if _oled_stop or _oled is None:
                return
            try:
                robot_name = get_robot_name_fn() or ""
            except Exception:
                robot_name = ""
            if has_connected_client():
                _draw_qr_screen(_oled)
            else:
                _draw_wifi_info_screen(_oled, robot_name)
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)


def show_qr_on_oled(get_robot_name_fn):
    """와이파이 셋업 OLED 시작: 기본은 화면1(와이파이 정보), 연결 시 화면2(QR)로 전환."""
    global _oled_stop
    stop_buffering_animation()
    if _oled is None and not _init_oled():
        return
    if _oled is None:
        return
    try:
        _oled_stop = False
        t = threading.Thread(target=_oled_loop, args=(get_robot_name_fn,), daemon=True)
        t.start()
    except Exception:
        pass
