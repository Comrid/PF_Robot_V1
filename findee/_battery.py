"""INA219 전압/전류. findee._i2c_bus 락 사용."""
from __future__ import annotations

import time

from findee._i2c_bus import _I2C_LOCK

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
    """INA219 전압/전류."""
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
        with _I2C_LOCK:
            self._bus.write_i2c_block_data(self._addr, reg, [(val>>8)&0xFF, val&0xFF])

    def _r16(self, reg: int) -> int:
        with _I2C_LOCK:
            d = self._bus.read_i2c_block_data(self._addr, reg, 2)
        return (d[0]<<8)|d[1]

    def voltage(self) -> float:
        raw = self._r16(_INA_REG_BUS_V) >> 3
        return raw * _INA_BUS_LSB

    def current(self) -> float:
        v = self._r16(_INA_REG_CURRENT)
        v = v - 0x10000 if v >= 0x8000 else v
        return v * self._current_lsb
