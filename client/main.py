"""Main: OLED first, buffering animation, then connect, then Findee."""
from __future__ import annotations

import signal
import sys
import threading
import time

# OLED first: init and start buffering before heavy imports
from findee._oled_shared import init_early, start_buffering_animation

init_early()
start_buffering_animation()

import socketio

from config.robot_config import ROBOT_ID, ROBOT_NAME, SERVER_URL
from findee import Findee
from client.state import state
from client import webrtc
from client import socket_events


def main() -> None:
    state.findee = None
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

    findee = Findee()
    state.findee = findee

    while True:
        time.sleep(5)
