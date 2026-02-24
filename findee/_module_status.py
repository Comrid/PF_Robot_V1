"""로봇 부착 모듈 상태. True=사용 가능, False=미연결/오류. 서버 모니터링용."""
from __future__ import annotations
from dataclasses import dataclass, asdict


@dataclass
class ModuleStatus:
    camera: bool = False
    oled: bool = False
    imu: bool = False
    battery: bool = False  # INA219
    ultrasonic: bool = False  # SR-04

    def to_dict(self):
        return asdict(self)
