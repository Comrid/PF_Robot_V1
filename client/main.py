"""Main: findee load, sio connect, event registration, main loop and signal handler."""
from __future__ import annotations

import signal
import sys
import threading
import time

import socketio

from config.robot_config import ROBOT_ID, ROBOT_NAME, SERVER_URL
from findee import Findee
from findee._oled_shared import init_early, get_shared_oled
from client.state import state
from client import webrtc
from client import socket_events


def main() -> None:
    oled = init_early() or get_shared_oled(init_if_missing=True)
    if oled is not None:
        try:
            oled.clear(0)
            oled.draw_text("Booting...", 0, 0)
            oled.show()
        except Exception:
            pass
    time.sleep(0.2)

    findee = Findee()
    findee.set_oled_status("WebRTC Starting...")
    time.sleep(0.5)

    state.findee = findee
    state.sio = sio = socketio.Client()
    socket_events.register(sio)

    def signal_handler(signum, frame):
        try:
            webrtc.webrtc_loop.call_soon_threadsafe(webrtc.webrtc_task_queue.put_nowait, ("shutdown", None))
        except Exception:
            pass
        time.sleep(0.5)
        sio.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    webrtc_thread = threading.Thread(target=webrtc.start_webrtc_loop, daemon=True)
    webrtc_thread.start()
    sio.connect(SERVER_URL)
    while True:
        time.sleep(5)
