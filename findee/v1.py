from __future__ import annotations
import os
import random
import threading
import time
import atexit
import cv2
import psutil
import numpy as np

import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('picamera2').setLevel(logging.ERROR)
os.environ['LIBCAMERA_LOG_FILE'] = '/dev/null'

from findee._i2c_bus import get_i2c_bus
from findee._oled import _OLED, _Animation
from findee._imu import _IMU
from findee._battery import _Battery
from findee._camera import _Camera
from findee._motor_ultrasonic import _MotorUltrasonic

USE_DEBUG = False


def debug_decorator(func):
    def wrapper(*args, **kwargs):
        if USE_DEBUG:
            print(f"DEBUG: {func.__name__} Called")
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if USE_DEBUG:
                print(f"DEBUG: ERR:{e}")
            raise
    return wrapper


class Findee:
    default_speed: float = 50.0
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Findee, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, safe_mode: bool = False):
        if self._initialized:
            return
        self._initialized = True

        self._motor = _MotorUltrasonic()
        self._motor.gpio_init()
        self._camera = _Camera()
        self._camera.init()

        self._code_running = False
        self._oled_stop = False
        self._oled_thread = None
        self._oled_status = ""

        self._i2c = get_i2c_bus()
        self._oled = _OLED(self._i2c)
        self._imu = _IMU(self._i2c)
        self._battery = _Battery(self._i2c)

        self._oled.init()
        self._oled.clear(0)

        self._imu.init()
        self._imu.calibrate()
        self._imu.start()

        self._battery.init()

        time.sleep(5)
        self._oled_thread = threading.Thread(target=self._oled_loop, daemon=True)
        self._oled_thread.start()

        atexit.register(self.__cleanup)

    def set_code_running(self, running: bool) -> None:
        """로봇 코드 실행 중이면 True. OLED 표정은 중단하고 기울기 시 배터리만 표시."""
        self._code_running = running

    def get_oled(self):
        """블록코딩/사용자 코드에서 OLED·표정 제어용. clear, draw_text, show, launch_animation 등 사용."""
        return self._oled

    def set_oled_status(self, status: str) -> None:
        """OLED 상태 문구 설정. 비어 있으면 표정/배터리 표시, 아니면 해당 문구만 표시 (예: '서버 연결 중', '대기 중')."""
        self._oled_status = (status or "").strip()

    def _battery_remaining_pct(self, voltage: float) -> float:
        """6.5V=0%, 8.1V=100%, 0~100으로 제한."""
        pct = (voltage - 6.5) / (8.1 - 6.5) * 100.0
        return max(0.0, min(100.0, pct))

    def _oled_loop(self) -> None:
        """OLED: 기울기 유지 시 배터리 정보(코드 실행 중에도 갱신). 그 외엔 코드 미실행 시에만 표정/상태 문구."""
        if self._i2c is None or not hasattr(self, '_oled'):
            return
        high_roll_start = None
        showing_battery = False
        last_battery_draw = 0.0
        last_anim_time = 0.0
        last_status_draw = 0.0
        LINE_SPACING = 14
        ROLL_THRESH = 30
        HOLD_S = 0.5

        while not getattr(self, '_oled_stop', True):
            time.sleep(0.01)
            try:
                roll, _, _ = self._imu.get_rpy()
            except Exception:
                roll = 0.0
            if abs(roll) >= ROLL_THRESH:
                if high_roll_start is None:
                    high_roll_start = time.monotonic()
                elif time.monotonic() - high_roll_start >= HOLD_S:
                    showing_battery = True
            else:
                high_roll_start = None
                showing_battery = False

            if showing_battery:
                # 배터리 정보는 코드 실행 중에도 갱신 (모터 전류 등 확인 가능)
                now = time.monotonic()
                if now - last_battery_draw >= 0.1:
                    last_battery_draw = now
                    try:
                        v = self._battery.voltage()
                        i = self._battery.current()
                        pct = self._battery_remaining_pct(v)
                        r, p, y = self._imu.get_rpy()
                        cpu_pct = int(psutil.cpu_percent()) if psutil is not None else 0
                    except Exception:
                        v, i, pct = 0.0, 0.0, 0.0
                        r, p, y = 0.0, 0.0, 0.0
                        cpu_pct = 0
                    self._oled.clear(0)
                    self._oled.draw_text("[ Battery Info ]", 0, 0)
                    i_mA = int(i * 1000)
                    self._oled.draw_text(f"V: {v:.2f} V, I: {i_mA} mA", 0, LINE_SPACING)
                    self._oled.draw_text(f"Remaining : {pct:.0f}%", 0, LINE_SPACING * 2)
                    self._oled.draw_text(f"CPU: {cpu_pct} %", 0, LINE_SPACING * 3)
                    self._oled.draw_text(f"R:{r:.1f} P:{p:.1f} Y:{y:.1f}", 0, LINE_SPACING * 4)
                    self._oled.show()
            elif not self._code_running:
                # 표정/상태 문구는 코드 미실행 시에만
                status = getattr(self, '_oled_status', '')
                if status:
                    now = time.monotonic()
                    if now - last_status_draw >= 0.3:
                        last_status_draw = now
                        try:
                            self._oled.clear(0)
                            for i, line in enumerate(status.split('\n')):
                                self._oled.draw_text(line, 0, LINE_SPACING * i)
                            self._oled.show()
                        except Exception:
                            pass
                else:
                    now = time.monotonic()
                    if now - last_anim_time >= 2.5:
                        last_anim_time = now
                        try:
                            idx = random.choice([_Animation.HAPPY, _Animation.BLINK_SHORT, _Animation.MOVE_LEFT_BIG, _Animation.MOVE_RIGHT_BIG])
                            self._oled.launch_animation(idx)
                        except Exception:
                            pass

    # --- 위임: GPIO/카메라 초기화 (호환용) ---
    @debug_decorator
    def gpio_init(self):
        self._motor.gpio_init()

    @debug_decorator
    def camera_init(self):
        self._camera.init()

    # --- 위임: 모터/초음파 (공개 API) ---
    @staticmethod
    def constrain(value, min_value, max_value):
        return _MotorUltrasonic.constrain(value, min_value, max_value)

    @debug_decorator
    def control_motors(self, left: float, right: float, decay: str = "slow") -> None:
        if getattr(self, '_motor', None) is not None:
            self._motor.control_motors(left, right, decay)

    @debug_decorator
    def stop(self):
        if getattr(self, '_motor', None) is not None:
            self._motor.stop()

    @debug_decorator
    def force_stop(self):
        self._motor.force_stop()

    @debug_decorator
    def move_forward(self, speed: float = None, duration: float = 0.0):
        s = speed if speed is not None else self.default_speed
        self._motor.move_forward(s, duration)

    @debug_decorator
    def move_backward(self, speed: float = None, duration: float = 0.0):
        s = speed if speed is not None else self.default_speed
        self._motor.move_backward(s, duration)

    @debug_decorator
    def turn_left(self, speed: float = None, duration: float = 0.0):
        s = speed if speed is not None else self.default_speed
        self._motor.turn_left(s, duration)

    @debug_decorator
    def turn_right(self, speed: float = None, duration: float = 0.0):
        s = speed if speed is not None else self.default_speed
        self._motor.turn_right(s, duration)

    @debug_decorator
    def curve_left(self, speed: float = None, ratio: float = 0.5, duration: float = 0.0):
        s = speed if speed is not None else self.default_speed
        self._motor.curve_left(s, ratio, duration)

    @debug_decorator
    def curve_right(self, speed: float = None, ratio: float = 0.5, duration: float = 0.0):
        s = speed if speed is not None else self.default_speed
        self._motor.curve_right(s, ratio, duration)

    @debug_decorator
    def get_distance(self):
        if getattr(self, '_motor', None) is None:
            return -1.0
        return self._motor.get_distance()

    # --- 위임: 카메라 ---
    def get_frame(self):
        if getattr(self, '_camera', None) is None:
            return None
        return self._camera.get_frame()

    def mjpeg_gen(self):
        if getattr(self, '_camera', None) is None:
            return
        yield from self._camera.mjpeg_gen()

    # --- Image Processing ---
    def mask_image(self, hsv_image, slider_values: list[int]):
        if slider_values is None or len(slider_values) != 6:
            print("배열의 값이 6개가 아닙니다.")
            return None
        if hsv_image is None or not isinstance(hsv_image, np.ndarray):
            print("이미지가 None 이거나 또는 np.ndarray가 아닙니다.")
            return None

        lower_bound = np.array([int(slider_values[0]), int(slider_values[2]), int(slider_values[4])])
        upper_bound = np.array([int(slider_values[1]), int(slider_values[3]), int(slider_values[5])])

        return cv2.inRange(hsv_image, lower_bound, upper_bound)

    def detect_traffic_light(self, hsv_image, green_bound=None, red_bound=None):
        """
        신호등 색상 인식 함수 (Contour 기반 필터링)

        Args:
            hsv_image: HSV 형식의 이미지 (numpy array)
            green_bound: 초록색 HSV 범위 [h_lower, h_upper, s_lower, s_upper, v_lower, v_upper]
                        기본값: [30, 80, 20, 255, 100, 255]
            red_bound: 빨간색 HSV 범위 [h_lower, h_upper, s_lower, s_upper, v_lower, v_upper]
                      기본값: [160, 180, 90, 255, 200, 255]

        Returns:
            0: 인식되지 않음
            1: 초록색 인식
            2: 빨간색 인식
        """
        if hsv_image is None or not isinstance(hsv_image, np.ndarray):
            return 0

        if green_bound is None:
            green_bound = [30, 80, 20, 255, 100, 255]
        if red_bound is None:
            red_bound = [160, 180, 90, 255, 200, 255]

        if len(green_bound) != 6 or len(red_bound) != 6:
            print("HSV 범위 배열은 6개의 요소를 가져야 합니다.")
            return 0

        green_lower = np.array([green_bound[0], green_bound[2], green_bound[4]])
        green_upper = np.array([green_bound[1], green_bound[3], green_bound[5]])
        green_mask = cv2.inRange(hsv_image, green_lower, green_upper)

        red_lower = np.array([red_bound[0], red_bound[2], red_bound[4]])
        red_upper = np.array([red_bound[1], red_bound[3], red_bound[5]])
        red_mask = cv2.inRange(hsv_image, red_lower, red_upper)

        def get_largest_contour_area(mask):
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return 0
            largest_contour = max(contours, key=cv2.contourArea)
            return cv2.contourArea(largest_contour)

        green_area = get_largest_contour_area(green_mask)
        red_area = get_largest_contour_area(red_mask)
        min_area = 100

        if red_area >= min_area:
            return 2
        elif green_area >= min_area:
            return 1
        else:
            return 0

    def cleanup(self):
        """사용자/블록 코드에서 호출 금지. 프로세스 종료 시 atexit에서만 __cleanup이 호출된다."""
        print("This function must not be called by user anymore.")

    def __cleanup(self):
        """실제 정리. atexit에서만 호출되며 사용자는 호출할 수 없다."""
        if getattr(self, '_oled', None) is not None:
            try:
                self._oled.clear(0)
                self._oled.show()
            except Exception:
                pass
        self._oled_stop = True
        if self._oled_thread is not None and self._oled_thread.is_alive():
            self._oled_thread.join(timeout=1.0)
        if hasattr(self, '_imu') and self._imu is not None:
            self._imu.stop()
        if self._i2c is not None:
            try:
                self._i2c.close()
            except Exception:
                pass
            self._i2c = None
        if hasattr(self, '_motor') and self._motor is not None:
            self._motor.cleanup()
            self._motor = None
        if hasattr(self, '_camera') and self._camera is not None:
            self._camera.cleanup()
            self._camera = None
        self._oled = None
        self._imu = None
        self._battery = None
