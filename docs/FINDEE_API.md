# Findee 모듈 사용자 가이드 (V1)

Findee 모듈은 라즈베리파이 기반 자율주행 자동차(V1 Kit)의 하드웨어를 제어하는 Python 모듈입니다. OLED, IMU, INA219(배터리), 부저를 지원합니다.

## 모듈 임포트

```python
from findee import Findee
```

## Findee 객체 생성

Findee는 싱글톤 패턴을 사용하므로, 어디서든 `Findee()`를 호출하면 같은 인스턴스를 반환합니다.

```python
findee = Findee()
```

---

## 모터 제어 함수

### 기본 이동 함수

#### `move_forward(speed, duration)`
로봇을 전진시킵니다.

**파라미터:**
- `speed` (float, 기본값: 80.0): 속도 (20~100 범위)
- `duration` (float, 기본값: 0.0): 이동 시간 (초). 0이면 계속 이동, 0보다 크면 지정 시간 후 자동 정지

**사용 예:**
```python
findee.move_forward(80, 2.0)  # 80 속도로 2초 전진
findee.move_forward()          # 기본 속도로 계속 전진
```

#### `move_backward(speed, duration)`
로봇을 후진시킵니다.

#### `turn_left(speed, duration)` / `turn_right(speed, duration)`
제자리에서 왼쪽/오른쪽 회전.

#### `curve_left(speed, ratio, duration)` / `curve_right(speed, ratio, duration)`
곡선 이동. `ratio`는 좌측/우측 속도 비율 (0~1).

#### `stop()`
로봇을 즉시 정지시킵니다.

---

## 초음파 센서

### `get_distance()`
앞쪽 장애물까지의 거리(cm)를 측정합니다. 실패 시 -1(Trig 타임아웃), -2(Echo 타임아웃)을 반환할 수 있습니다.

---

## 카메라 함수

### `get_frame()`
현재 프레임을 numpy 배열(RGB)로 반환합니다.

### `set_fps(fps)` / `set_resolution(resolution)`
FPS 및 해상도 설정.

---

## OLED 및 상태 (V1)

- **`set_oled_status(status: str)`**: OLED에 상태 문구 표시 (예: "Connecting...", "Connected !").
- **`set_code_running(running: bool)`**: 코드 실행 중 표시 제어.
- **`get_oled()`**: 내부 OLED 객체 (고급 사용).

---

## 배터리 (V1)

V1은 INA219를 사용합니다. 내부적으로 `_battery`, `_battery_remaining_pct` 등이 있으며, 블록코딩/센서 요청 시 배터리 잔량이 전송됩니다.

---

## 주의사항

1. 모터 속도는 20~100 범위로 제한됩니다.
2. Findee는 싱글톤이므로 여러 번 `Findee()`를 호출해도 동일한 인스턴스입니다.
3. 프로그램 종료 시 GPIO·카메라 리소스가 자동 정리됩니다.
4. `get_frame()` 반환값은 numpy 배열이므로 OpenCV 등과 함께 사용할 수 있습니다.

---

## 함수 목록

**모터:** `move_forward`, `move_backward`, `turn_left`, `turn_right`, `curve_left`, `curve_right`, `stop`, `control_motors`

**센서:** `get_distance`

**카메라:** `get_frame`, `set_fps`, `set_resolution`

**OLED/상태:** `set_oled_status`, `set_code_running`, `get_oled`

**기타:** `mask_image`, `detect_traffic_light`, `cleanup`, `constrain`
