"""Picamera2 캡처 및 MJPEG 스트림. Findee에서 위임용."""
from __future__ import annotations

import time

import cv2
from picamera2 import Picamera2


class _Camera:
    """Picamera2 래퍼: init, get_frame, mjpeg_gen, cleanup."""
    def __init__(self):
        self.camera = None
        self.config = None

    def init(self) -> None:
        """이미 열린 카메라가 있으면 재초기화하지 않는다. 중복 Picamera2()는 장치 점유 실패로 camera=None이 되어 get_frame이 망가질 수 있음."""
        if self.camera is not None:
            return
        try:
            self.camera = Picamera2()
            self.config = self.camera.create_video_configuration(
                main={"size": (640, 480), "format": "RGB888"},
                controls={"FrameDurationLimits": (33333, 33333)},
                queue=False, buffer_count=2
            )
            self.camera.configure(self.config)
            self.camera.start()
        except Exception:
            self.camera = None
            self.config = None

    def get_frame(self):
        if self.camera is None:
            return None
        return self.camera.capture_array("main").copy()

    def mjpeg_gen(self):
        if self.camera is None:
            return
        while True:
            arr = self.camera.capture_array("main").copy()
            ok, buf = cv2.imencode('.jpg', arr, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if not ok:
                continue
            jpg = buf.tobytes()
            yield (b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" +
                jpg + b"\r\n")
            time.sleep(0.001)

    def cleanup(self) -> None:
        if self.camera is None:
            return
        try:
            if hasattr(self.camera, 'stop'):
                self.camera.stop()
            if hasattr(self.camera, 'close'):
                self.camera.close()
        except Exception:
            pass
        self.camera = None
        self.config = None
