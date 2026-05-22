"""AP play session: motor, camera, ultrasonic only (no OLED / Findee)."""
from __future__ import annotations

import base64
import math
import platform
import threading
import time
from typing import Callable, Optional

import cv2

_lock = threading.Lock()
_motor = None
_camera = None
_running = False
_thread: Optional[threading.Thread] = None
_sid: Optional[str] = None
_cmd: tuple[int, int] = (0, 0)
_emit: Optional[Callable[..., None]] = None
_mock = False


def joystick_to_motors(x_value: int, y_value: int) -> tuple[float, float]:
    x = x_value / 127.0
    y = y_value / 127.0
    distance = min(1.0, math.sqrt(x * x + y * y))
    abs_y, abs_x = abs(y), abs(x)
    if abs_y < 0.1 and abs_x > 0.1:
        rotation_speed = abs_x * 100.0
        if x > 0:
            return rotation_speed, -rotation_speed
        return -rotation_speed, rotation_speed
    angle = math.atan2(x, y)
    speed = distance * 100.0
    if y < 0:
        speed = -speed
    rotation_ratio = math.sin(angle)
    left = speed * (1.0 + rotation_ratio)
    right = speed * (1.0 - rotation_ratio)
    return max(-100.0, min(100.0, left)), max(-100.0, min(100.0, right))


def _loop() -> None:
    global _running
    frame_skip = 0
    while _running:
        t0 = time.time()
        with _lock:
            x, y = _cmd
            motor, camera, sid, emit, mock = _motor, _camera, _sid, _emit, _mock
        if motor and not mock:
            left, right = joystick_to_motors(x, y)
            motor.control_motors(left, right)
        if emit and sid:
            if mock:
                emit("ap_ultrasonic", {"value": 42.0}, room=sid)
            elif motor:
                try:
                    emit("ap_ultrasonic", {"value": motor.get_distance()}, room=sid)
                except Exception:
                    pass
            frame_skip += 1
            if frame_skip >= 1 and camera and not mock:
                frame_skip = 0
                try:
                    frame = camera.get_frame()
                    if frame is not None:
                        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 55])
                        if ok:
                            emit(
                                "ap_camera_frame",
                                {"jpeg": base64.b64encode(buf.tobytes()).decode("ascii")},
                                room=sid,
                            )
                except Exception:
                    pass
        time.sleep(max(0.0, 0.1 - (time.time() - t0)))


def is_running() -> bool:
    return _running


def set_joystick(x: int, y: int) -> None:
    with _lock:
        global _cmd
        _cmd = (max(-128, min(127, int(x))), max(-128, min(127, int(y))))


def start_session(emit_fn: Callable[..., None], sid: str) -> tuple[bool, str]:
    global _motor, _camera, _running, _thread, _sid, _emit, _mock, _cmd
    stop_session()
    _mock = platform.system() != "Linux"
    _emit = emit_fn
    _sid = sid
    _cmd = (0, 0)
    if not _mock:
        try:
            from findee._camera import _Camera
            from findee._motor_ultrasonic import _MotorUltrasonic

            _motor = _MotorUltrasonic()
            _motor.gpio_init()
            _camera = _Camera()
            _camera.init()
        except Exception as e:
            _cleanup_hw()
            return False, str(e)
    _running = True
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()
    return True, ""


def _cleanup_hw() -> None:
    global _motor, _camera
    if _motor is not None:
        try:
            _motor.cleanup()
        except Exception:
            pass
        _motor = None
    if _camera is not None:
        try:
            _camera.cleanup()
        except Exception:
            pass
        _camera = None


def stop_session() -> None:
    global _running, _thread, _sid, _emit, _cmd
    _running = False
    if _thread is not None and _thread.is_alive():
        _thread.join(timeout=1.5)
    _thread = None
    _sid = None
    _emit = None
    _cmd = (0, 0)
    _cleanup_hw()
