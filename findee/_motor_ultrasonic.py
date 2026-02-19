"""DRV8833 모터 + 초음파 거리센서. GPIO/PWM 제어."""
from __future__ import annotations

import gc
import time

import RPi.GPIO as GPIO

USE_DEBUG = False

def _debug_decorator(func):
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


class _MotorUltrasonic:
    PWM_FREQ: int = 1000
    default_speed: float = 50.0

    def __init__(self):
        self.AIN1: int = 24
        self.AIN2: int = 23
        self.BIN1: int = 27
        self.BIN2: int = 22
        self.nSLEEP: int = 25
        self.TRIG: int = 5
        self.ECHO: int = 6
        self._pwm_ain1 = None
        self._pwm_ain2 = None
        self._pwm_bin1 = None
        self._pwm_bin2 = None

    @staticmethod
    def constrain(value, min_value, max_value):
        return max(min(value, max_value), min_value)

    @_debug_decorator
    def gpio_init(self) -> None:
        try:
            GPIO.cleanup()
        except Exception:
            pass
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup((self.AIN1, self.AIN2, self.BIN1, self.BIN2, self.nSLEEP, self.TRIG),
                   GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.ECHO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.output(self.nSLEEP, GPIO.HIGH)
        self._pwm_ain1 = GPIO.PWM(self.AIN1, self.PWM_FREQ)
        self._pwm_ain2 = GPIO.PWM(self.AIN2, self.PWM_FREQ)
        self._pwm_bin1 = GPIO.PWM(self.BIN1, self.PWM_FREQ)
        self._pwm_bin2 = GPIO.PWM(self.BIN2, self.PWM_FREQ)
        self._pwm_ain1.start(0)
        self._pwm_ain2.start(0)
        self._pwm_bin1.start(0)
        self._pwm_bin2.start(0)

    def _duty(self, speed: float) -> float:
        return max(0.0, min(100.0, abs(speed)))

    def _set_channel(self, speed: float, pwm1: GPIO.PWM, pwm2: GPIO.PWM, decay: str = "slow") -> None:
        duty = self._duty(speed)
        fwd = speed >= 0
        if decay == "slow":
            if fwd:
                pwm1.ChangeDutyCycle(duty)
                pwm2.ChangeDutyCycle(0)
            else:
                pwm1.ChangeDutyCycle(0)
                pwm2.ChangeDutyCycle(duty)
        else:
            if fwd:
                pwm1.ChangeDutyCycle(duty)
                pwm2.ChangeDutyCycle(100 - duty)
            else:
                pwm1.ChangeDutyCycle(100 - duty)
                pwm2.ChangeDutyCycle(duty)

    def control_motors(self, left: float, right: float, decay: str = "slow") -> None:
        if self._pwm_ain1 is None or self._pwm_bin1 is None:
            return
        def normalize(s: float) -> float:
            return (1 if s >= 0 else -1) * self.constrain(abs(s), 20, 100) if s != 0.0 else 0.0
        self._set_channel(normalize(right), self._pwm_ain1, self._pwm_ain2, decay)
        self._set_channel(normalize(left), self._pwm_bin1, self._pwm_bin2, decay)

    @_debug_decorator
    def stop(self) -> None:
        if self._pwm_ain1 is None:
            return
        self.control_motors(0.0, 0.0)

    @_debug_decorator
    def force_stop(self) -> None:
        if self._pwm_ain1 is None:
            return
        self._pwm_ain1.ChangeDutyCycle(100)
        self._pwm_ain2.ChangeDutyCycle(100)
        self._pwm_bin1.ChangeDutyCycle(100)
        self._pwm_bin2.ChangeDutyCycle(100)
        time.sleep(0.5)
        self._pwm_ain1.ChangeDutyCycle(0)
        self._pwm_ain2.ChangeDutyCycle(0)
        self._pwm_bin1.ChangeDutyCycle(0)
        self._pwm_bin2.ChangeDutyCycle(0)

    @_debug_decorator
    def move_forward(self, speed: float = None, duration: float = 0.0) -> None:
        s = speed if speed is not None else self.default_speed
        self.control_motors(s, s)
        self._duration_check(duration)

    @_debug_decorator
    def move_backward(self, speed: float = None, duration: float = 0.0) -> None:
        s = speed if speed is not None else self.default_speed
        self.control_motors(-s, -s)
        self._duration_check(duration)

    @_debug_decorator
    def turn_left(self, speed: float = None, duration: float = 0.0) -> None:
        s = speed if speed is not None else self.default_speed
        self.control_motors(-s, s)
        self._duration_check(duration)

    @_debug_decorator
    def turn_right(self, speed: float = None, duration: float = 0.0) -> None:
        s = speed if speed is not None else self.default_speed
        self.control_motors(s, -s)
        self._duration_check(duration)

    @_debug_decorator
    def curve_left(self, speed: float = None, ratio: float = 0.5, duration: float = 0.0) -> None:
        s = speed if speed is not None else self.default_speed
        self.control_motors(s * ratio, s)
        self._duration_check(duration)

    @_debug_decorator
    def curve_right(self, speed: float = None, ratio: float = 0.5, duration: float = 0.0) -> None:
        s = speed if speed is not None else self.default_speed
        self.control_motors(s, s * ratio)
        self._duration_check(duration)

    def _duration_check(self, duration: float) -> None:
        if duration < 0.0:
            raise ValueError("Duration must be greater or equal to 0.0")
        elif duration > 0.0:
            time.sleep(duration)
            self.stop()

    @_debug_decorator
    def get_distance(self) -> float:
        GPIO.output(self.TRIG, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(self.TRIG, GPIO.LOW)
        t1 = time.time()
        while GPIO.input(self.ECHO) is not GPIO.HIGH:
            if time.time() - t1 > 0.1:
                return -1.0
        t1 = time.time()
        while GPIO.input(self.ECHO) is not GPIO.LOW:
            if time.time() - t1 > 0.03:
                return -2.0
        t2 = time.time()
        distance = ((t2 - t1) * 34300) / 2
        return round(distance, 1)

    def cleanup(self) -> None:
        self.control_motors(0.0, 0.0)
        for p in ('_pwm_ain1', '_pwm_ain2', '_pwm_bin1', '_pwm_bin2'):
            pwm = getattr(self, p, None)
            if pwm is not None:
                try:
                    pwm.stop()
                except Exception:
                    pass
                setattr(self, p, None)
        gc.collect()
        # GPIO.cleanup()을 호출하지 않음. 호출 시 lgpio 핸들이 무효화되어,
        # 나중에 PWM 객체가 GC될 때 __del__ → stop()에서 TypeError가 난다.
        # 핀만 LOW로 두고 프로세스 종료 시 OS가 정리하도록 함.
        try:
            GPIO.output((self.AIN1, self.AIN2, self.BIN1, self.BIN2, self.nSLEEP, self.TRIG), GPIO.LOW)
        except Exception:
            pass
