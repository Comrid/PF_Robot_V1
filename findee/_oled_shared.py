"""공용 OLED: 앱에서 가장 먼저 초기화해 부팅/연결/오류 표시, Findee에서도 동일 인스턴스 사용."""
from __future__ import annotations

import math
import threading
import time
from typing import Optional

from findee._i2c_bus import get_i2c_bus
from findee._oled import _OLED

_shared_oled: Optional[_OLED] = None
_buffering_stop = False
_buffering_thread: Optional[threading.Thread] = None

NUM_DOTS = 12
TRAIL_LEN = 5
CENTER_X, CENTER_Y = 64, 32
RADIUS = 22
# 크기: 0=3x3, 1=2x2, 2=1픽셀. 앞(방금 켜짐)이 크고 뒤로 갈수록 작게.
TRAIL_SIZES = (0, 1, 1, 2, 2)


def _draw_dot_size(oled: _OLED, cx: int, cy: int, size: int) -> None:
    """원 위 점 중심 (cx,cy)에 크기 size로 그리기. 0=3x3, 1=2x2, 2=1픽셀. 모두 중심 기준."""
    if size == 0:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                oled.draw_pixel(cx + dx, cy + dy, 1)
    elif size == 1:
        for dx in (0, -1):
            for dy in (0, -1):
                oled.draw_pixel(cx + dx, cy + dy, 1)
    else:
        oled.draw_pixel(cx, cy, 1)


def _buffering_loop() -> None:
    global _buffering_stop
    oled = _shared_oled
    if oled is None:
        return
    step = 0
    while not _buffering_stop:
        try:
            oled.clear(0)
            # 시계 방향: head가 한 칸씩 이동. head = (-step) % 12 이면 0→11→10→… 로 시계방향
            head = (-step) % NUM_DOTS
            for k in range(TRAIL_LEN):
                pos = (head + k) % NUM_DOTS
                angle = (pos / NUM_DOTS) * 2 * math.pi
                cx = int(CENTER_X + RADIUS * math.cos(angle))
                cy = int(CENTER_Y + RADIUS * math.sin(angle))
                _draw_dot_size(oled, cx, cy, TRAIL_SIZES[k])
            oled.show()
            step += 1
            time.sleep(0.08)
        except Exception:
            pass
    _buffering_stop = False


def start_buffering_animation() -> None:
    """Start spinning-dots buffering animation in a daemon thread. Uses shared OLED."""
    global _shared_oled, _buffering_stop, _buffering_thread
    if _shared_oled is None:
        init_early()
    if _shared_oled is None:
        return
    _buffering_stop = False
    if _buffering_thread is not None and _buffering_thread.is_alive():
        return
    _buffering_thread = threading.Thread(target=_buffering_loop, daemon=True)
    _buffering_thread.start()


def stop_buffering_animation() -> None:
    """Stop the buffering animation; returns after thread exits (short timeout)."""
    global _buffering_stop, _buffering_thread
    _buffering_stop = True
    if _buffering_thread is not None and _buffering_thread.is_alive():
        _buffering_thread.join(timeout=1.0)
    _buffering_thread = None


def init_early() -> Optional[_OLED]:
    """I2C + OLED만 초기화해 공용 인스턴스로 저장. 성공 시 인스턴스, 실패 시 None."""
    global _shared_oled
    if _shared_oled is not None:
        return _shared_oled
    try:
        bus = get_i2c_bus()
        oled = _OLED(bus)
        oled.init()
        oled.clear(0)
        _shared_oled = oled
        return _shared_oled
    except Exception:
        return None


def get_shared_oled(init_if_missing: bool = False) -> Optional[_OLED]:
    """이미 초기화된 공용 OLED 반환. init_if_missing=True면 없을 때 init_early() 시도."""
    global _shared_oled
    if _shared_oled is not None:
        return _shared_oled
    if init_if_missing:
        return init_early()
    return None
