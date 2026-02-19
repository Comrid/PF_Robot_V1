"""I2C bus 1 공유: 락 + 싱글톤 SMBus(1). OLED/IMU/INA219 동시 접근 방지."""
from __future__ import annotations

import threading

import smbus2

# RLock: 같은 스레드가 init() -> _cmd() 처럼 중첩 호출해도 deadlock 없음.
_I2C_LOCK = threading.RLock()

_bus_singleton = None


def get_i2c_bus():
    """SMBus(1) 싱글톤 반환."""
    global _bus_singleton
    if _bus_singleton is None:
        _bus_singleton = smbus2.SMBus(1)
    return _bus_singleton
