"""Socket.IO handlers for AP play (joystick, camera, ultrasonic)."""
from __future__ import annotations

from flask import request
from flask_socketio import SocketIO, emit

from wifi_setup import ap_hardware


def register(socketio: SocketIO) -> None:
    @socketio.on("ap_play_start")
    def on_ap_play_start():
        ok, err = ap_hardware.start_session(socketio.emit, request.sid)
        emit("ap_play_status", {"running": ok, "error": err})

    @socketio.on("ap_play_stop")
    def on_ap_play_stop():
        ap_hardware.stop_session()
        emit("ap_play_status", {"running": False, "error": ""})

    @socketio.on("ap_joystick")
    def on_ap_joystick(data):
        if not ap_hardware.is_running():
            return
        data = data or {}
        ap_hardware.set_joystick(data.get("x", 0), data.get("y", 0))

    @socketio.on("disconnect")
    def on_disconnect():
        ap_hardware.stop_session()
