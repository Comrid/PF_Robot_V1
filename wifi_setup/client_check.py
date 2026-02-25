"""AP에 연결된 기기 유무 감지 (OLED 화면 전환용). Linux only."""
from __future__ import annotations

import platform
import subprocess


def has_connected_client(interface: str = "wlan0") -> bool:
    """자기(라즈베리파이) AP에 연결된 클라이언트가 1명 이상이면 True."""
    if platform.system() != "Linux":
        return False
    try:
        r = subprocess.run(
            ["iw", "dev", interface, "station", "dump"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            return False
        # 출력에 "Station xx:xx:xx:xx:xx:xx" 한 줄당 연결 1개
        count = sum(
            1 for line in r.stdout.splitlines()
            if line.strip().startswith("Station ")
        )
        return count > 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False
