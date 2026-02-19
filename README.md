# PF_Robot_V1

Pathfinder 로봇 **V1 Kit** 전용 클라이언트 저장소입니다. OLED, IMU, INA219(배터리), 부저가 있는 보드에서 동작합니다.

## 폴더 구조

```
PF_Robot_V1/
├── config/
│   └── robot_config.py   # ROBOT_ID, ROBOT_NAME, SERVER_URL, ROBOT_VERSION
├── findee/
│   ├── __init__.py       # Findee (from findee.v1)
│   └── v1.py             # V1 하드웨어 제어
├── client/
│   ├── main.py           # 로봇 클라이언트 메인 (Socket.IO, WebRTC, 실행기)
│   ├── socket_events.py  # Socket.IO 이벤트 등록
│   ├── webrtc.py         # WebRTC 큐/매니저/시그널링/데이터 전송
│   ├── executor.py       # 코드 실행, 스레드 관리
│   ├── updater.py        # Git pull, config 복원
│   └── ...
├── wifi_setup/
│   ├── app.py            # Wi-Fi 설정 Flask 앱 (AP 모드)
│   ├── oled.py           # OLED QR/스크롤
│   └── templates/
│       └── index.html
├── Setup/
│   ├── setup4V2.sh       # V1 Kit 설치 스크립트
│   └── setup.md
├── docs/
│   └── FINDEE_API.md     # Findee V1 API 문서
├── run_robot_client.py   # 로봇 클라이언트 진입점
└── run_wifi_setup.py     # Wi-Fi 설정 앱 진입점
```

## 실행 방법

- **로봇 클라이언트 (서버 연결·코드 실행·WebRTC)**  
  `python3 run_robot_client.py`

- **Wi-Fi 설정 (AP 모드, 10.0.0.1:5000)**  
  `python3 run_wifi_setup.py`

## 설치 (라즈베리파이 V1 Kit)

`Setup/setup4V2.sh` 를 실행하면 이 저장소를 `/home/<user>/PF_Robot_V1` 에 클론하고, systemd 서비스(robot_client, wifi_setup, pf-netmode)를 등록합니다. 자세한 내용은 `Setup/setup.md` 를 참고하세요.

## 설정

`config/robot_config.py` 에서 `ROBOT_ID`, `ROBOT_NAME`, `SERVER_URL`, `ROBOT_VERSION` 을 수정할 수 있습니다. Wi-Fi 설정 완료 시 로봇 이름이 여기와 연동됩니다.

## Findee API

V1 전용 Findee API는 `docs/FINDEE_API.md` 에 정리되어 있습니다.
