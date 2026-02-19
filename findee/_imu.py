"""MPU6050 + Madgwick 6DOF. findee._i2c_bus 락 사용."""
from __future__ import annotations

import math
import threading
import time

import RPi.GPIO as GPIO

from findee._i2c_bus import _I2C_LOCK

_MPU_ADDR = 0x68
_REG_PWR = 0x6B
_REG_SMPLRT = 0x19
_REG_CFG = 0x1A
_REG_GYRO_CFG = 0x1B
_REG_ACCEL_CFG = 0x1C
_REG_INT_PIN_CFG = 0x37
_REG_INT_ENABLE = 0x38
_REG_ACCEL_XOUT_H = 0x3B
_MPU_INT_GPIO_BCM = 4
_MPU_BOUNCETIME_MS = 1
_ACCEL_SCALE = 16384.0
_GYRO_SCALE = 131.0
_GRAVITY = 9.80665
_MADGWICK_BETA = 0.05


class _IMU:
    """MPU6050 + Madgwick 6DOF. Data Ready 인터럽트(GPIO 4)로 100Hz 갱신."""
    def __init__(self, bus, addr: int = _MPU_ADDR):
        self._bus = bus
        self._addr = addr
        self._q = [1.0, 0.0, 0.0, 0.0]
        self._roll = self._pitch = self._yaw = 0.0
        self._gyro_off = (0.0, 0.0, 0.0)
        self._accel_off = (0.0, 0.0, 0.0)
        self._last_ts = None
        self._last_gyro_rad = None
        self._offset_m = (0.03, 0.0, 0.0)
        self._running = False
        self._int_occurred = False
        self._read_thread = None

    def init(self) -> None:
        with _I2C_LOCK:
            self._bus.write_byte_data(self._addr, _REG_PWR, 0x00)
        time.sleep(0.1)
        with _I2C_LOCK:
            self._bus.write_byte_data(self._addr, _REG_SMPLRT, 0x09)
            self._bus.write_byte_data(self._addr, _REG_CFG, 0x03)
            self._bus.write_byte_data(self._addr, _REG_GYRO_CFG, 0x00)
            self._bus.write_byte_data(self._addr, _REG_ACCEL_CFG, 0x00)
            self._bus.write_byte_data(self._addr, _REG_INT_PIN_CFG, 0x80)
            self._bus.write_byte_data(self._addr, _REG_INT_ENABLE, 0x01)
        self._last_ts = time.monotonic()
        self._q = [1.0, 0.0, 0.0, 0.0]
        self._last_gyro_rad = None

    def _on_int(self, channel):
        self._int_occurred = True

    def _read_loop(self) -> None:
        while self._running:
            if self._int_occurred:
                self._int_occurred = False
                try:
                    self.update()
                except Exception:
                    pass
            else:
                time.sleep(0.0001)

    def start(self) -> None:
        if self._running:
            return
        try:
            GPIO.remove_event_detect(_MPU_INT_GPIO_BCM)
        except (RuntimeError, ValueError):
            pass
        try:
            GPIO.cleanup(_MPU_INT_GPIO_BCM)
        except (RuntimeError, ValueError):
            pass
        GPIO.setup(_MPU_INT_GPIO_BCM, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        time.sleep(0.01)
        GPIO.add_event_detect(_MPU_INT_GPIO_BCM, GPIO.FALLING, callback=self._on_int, bouncetime=_MPU_BOUNCETIME_MS)
        self._running = True
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()

    def stop(self) -> None:
        self._running = False
        if self._read_thread is not None:
            self._read_thread.join(timeout=1.0)
        try:
            GPIO.remove_event_detect(_MPU_INT_GPIO_BCM)
        except (RuntimeError, ValueError):
            pass

    @staticmethod
    def _s16(h, l):
        v = (h << 8) | l
        return v - 65536 if v >= 32768 else v

    def _read_block(self):
        with _I2C_LOCK:
            return self._bus.read_i2c_block_data(self._addr, _REG_ACCEL_XOUT_H, 14)

    def get_raw_data(self):
        b = self._read_block()
        ax = self._s16(b[0], b[1]) / _ACCEL_SCALE - self._accel_off[0]
        ay = self._s16(b[2], b[3]) / _ACCEL_SCALE - self._accel_off[1]
        az = self._s16(b[4], b[5]) / _ACCEL_SCALE - self._accel_off[2]
        gx = self._s16(b[8], b[9]) / _GYRO_SCALE - self._gyro_off[0]
        gy = self._s16(b[10], b[11]) / _GYRO_SCALE - self._gyro_off[1]
        gz = self._s16(b[12], b[13]) / _GYRO_SCALE - self._gyro_off[2]
        return ax, ay, az, gx, gy, gz

    def _lever_arm(self, ax, ay, az, gx, gy, gz, dt):
        rx, ry, rz = self._offset_m
        if rx == ry == rz == 0:
            return ax, ay, az
        deg2rad = math.pi / 180.0
        wx, wy, wz = gx * deg2rad, gy * deg2rad, gz * deg2rad
        if self._last_gyro_rad and dt > 0:
            ax_ = (wx - self._last_gyro_rad[0]) / dt
            ay_ = (wy - self._last_gyro_rad[1]) / dt
            az_ = (wz - self._last_gyro_rad[2]) / dt
        else:
            ax_, ay_, az_ = 0.0, 0.0, 0.0
        self._last_gyro_rad = (wx, wy, wz)
        def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
        om = (wx, wy, wz)
        r = (rx, ry, rz)
        tan_acc = cross((ax_, ay_, az_), r)
        cen_acc = cross(om, cross(om, r))
        c = 1.0 / _GRAVITY
        return ax - (tan_acc[0]+cen_acc[0])*c, ay - (tan_acc[1]+cen_acc[1])*c, az - (tan_acc[2]+cen_acc[2])*c

    def _madgwick(self, gx, gy, gz, ax, ay, az, dt):
        q0, q1, q2, q3 = self._q
        qd1 = 0.5 * (-q1*gx - q2*gy - q3*gz)
        qd2 = 0.5 * ( q0*gx + q2*gz - q3*gy)
        qd3 = 0.5 * ( q0*gy - q1*gz + q3*gx)
        qd4 = 0.5 * ( q0*gz + q1*gy - q2*gx)
        if not (ax == ay == az == 0.0):
            n = 1.0 / math.sqrt(ax*ax + ay*ay + az*az)
            ax, ay, az = ax*n, ay*n, az*n
            s0 = 4*q0*q2*q2 + 2*q2*ax + 4*q0*q1*q1 - 2*q1*ay
            s1 = 4*q1*q3*q3 - 2*q3*ax + 4*q0*q0*q1 - 2*q0*ay - 4*q1 + 8*q1*q1*q1 + 8*q1*q2*q2 + 4*q1*az
            s2 = 4*q0*q0*q2 + 2*q0*ax + 4*q2*q3*q3 - 2*q3*ay - 4*q2 + 8*q2*q1*q1 + 8*q2*q2*q2 + 4*q2*az
            s3 = 4*q1*q1*q3 - 2*q1*ax + 4*q2*q2*q3 - 2*q2*ay
            n = 1.0 / math.sqrt(s0*s0 + s1*s1 + s2*s2 + s3*s3)
            qd1 -= _MADGWICK_BETA * s0 * n
            qd2 -= _MADGWICK_BETA * s1 * n
            qd3 -= _MADGWICK_BETA * s2 * n
            qd4 -= _MADGWICK_BETA * s3 * n
        q0 += qd1*dt; q1 += qd2*dt; q2 += qd3*dt; q3 += qd4*dt
        n = 1.0 / math.sqrt(q0*q0 + q1*q1 + q2*q2 + q3*q3)
        self._q = [q0*n, q1*n, q2*n, q3*n]

    def _quat_to_euler(self):
        q0, q1, q2, q3 = self._q
        sinr = 2*(q0*q1 + q2*q3)
        cosr = 1 - 2*(q1*q1 + q2*q2)
        roll = math.atan2(sinr, cosr)
        sinp = 2*(q0*q2 - q3*q1)
        pitch = math.asin(max(-1, min(1, sinp))) if abs(sinp) < 1 else math.copysign(math.pi/2, sinp)
        siny = 2*(q0*q3 + q1*q2)
        cosy = 1 - 2*(q2*q2 + q3*q3)
        yaw = math.atan2(siny, cosy)
        return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)

    def update(self) -> None:
        ax, ay, az, gx, gy, gz = self.get_raw_data()
        now = time.monotonic()
        dt = now - self._last_ts if self._last_ts else 0.01
        self._last_ts = now
        ax, ay, az = self._lever_arm(ax, ay, az, gx, gy, gz, dt)
        deg2rad = math.pi / 180.0
        self._madgwick(gx*deg2rad, gy*deg2rad, gz*deg2rad, ax, ay, az, dt)
        self._roll, self._pitch, self._yaw = self._quat_to_euler()

    def calibrate(self, samples: int = 500) -> None:
        gx_s = gy_s = gz_s = ax_s = ay_s = az_s = 0.0
        for _ in range(samples):
            b = self._read_block()
            ax_s += self._s16(b[0], b[1]); ay_s += self._s16(b[2], b[3]); az_s += self._s16(b[4], b[5])
            gx_s += self._s16(b[8], b[9]); gy_s += self._s16(b[10], b[11]); gz_s += self._s16(b[12], b[13])
            time.sleep(0.002)
        n = samples
        self._gyro_off = (gx_s/n/_GYRO_SCALE, gy_s/n/_GYRO_SCALE, gz_s/n/_GYRO_SCALE)
        self._accel_off = (ax_s/n/_ACCEL_SCALE, ay_s/n/_ACCEL_SCALE, az_s/n/_ACCEL_SCALE - 1.0)

    def get_rpy(self):
        return self._roll, self._pitch, self._yaw
