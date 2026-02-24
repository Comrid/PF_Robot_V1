"""공용 OLED: 앱에서 가장 먼저 초기화해 부팅/연결/오류 표시, Findee에서도 동일 인스턴스 사용."""
from __future__ import annotations

from typing import Optional

from findee._i2c_bus import get_i2c_bus
from findee._oled import _OLED

_shared_oled: Optional[_OLED] = None


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
