"""Socket.IO event registration: connect, disconnect, execute_code, stop, request_sensor_data, pid/slider, webrtc, client_update/reset."""
from __future__ import annotations

import subprocess
import threading
import time

from config.robot_config import ROBOT_ID, ROBOT_NAME, SERVER_URL, ROBOT_VERSION
from client.state import state
from client import executor
from client import webrtc
from client import updater
from client import widget_data


def register(sio):
    """Register all sio event handlers with the given client."""

    @sio.event
    def connect():
        findee = state.findee
        if findee:
            findee.set_oled_status("Connecting...")
        sio.emit("robot_connected", {"robot_id": ROBOT_ID, "robot_name": ROBOT_NAME, "robot_version": ROBOT_VERSION})

    @sio.event
    def robot_registered(data):
        findee = state.findee
        if data.get("success"):
            if findee:
                findee.set_oled_status("Connected !")
            time.sleep(1)
            if findee:
                findee.set_oled_status("")
        else:
            if findee:
                findee.set_oled_status(f"Fail:{data.get('error')}")

    @sio.event
    def disconnect():
        findee = state.findee
        if findee:
            findee.set_oled_status("Disconnected...")

        def reconnect_loop():
            while not sio.connected:
                try:
                    time.sleep(5)
                    if not sio.connected:
                        sio.connect(SERVER_URL)
                except Exception:
                    pass

        threading.Thread(target=reconnect_loop, daemon=True).start()

    @sio.event
    def execute_code(data):
        try:
            code = data.get("code", "")
            session_id = data.get("session_id", "")
            if session_id in executor.session_threads:
                old_manager = executor.session_threads[session_id]
                if old_manager.thread.is_alive():
                    old_manager.stop_flag = True
                    executor._raise_exception_in_thread(old_manager.thread, SystemExit)
                    old_manager.thread.join(timeout=0.5)
            thread = threading.Thread(target=executor.exec_code, args=(code, session_id), daemon=True)
            executor.session_threads[session_id] = executor.ThreadManager(thread)
            thread.start()
        except Exception as e:
            session_id = data.get("session_id", "")
            sio.emit("robot_stderr", {"session_id": session_id, "output": f"코드 실행 중 오류: {str(e)}"})

    @sio.event
    def stop_execution(data):
        try:
            session_id = data.get("session_id", "")
            if session_id not in executor.session_threads:
                sio.emit("robot_stderr", {"session_id": session_id, "output": "실행 중인 코드가 없습니다."})
                return
            manager = executor.session_threads[session_id]
            manager.stop_flag = True
            if manager.thread.is_alive():
                executor._raise_exception_in_thread(manager.thread, SystemExit)
                manager.thread.join(timeout=1.0)
            if session_id in executor.session_threads:
                del executor.session_threads[session_id]
        except Exception as e:
            session_id = data.get("session_id", "")
            sio.emit("robot_stderr", {"session_id": session_id, "output": f"코드 중지 중 오류: {str(e)}"})

    @sio.event
    def request_sensor_data(data):
        try:
            session_id = data.get("session_id", "")
            if not session_id:
                return
            findee = state.findee
            dist = findee.get_distance() if findee else None
            if dist is None:
                dist = -1
            sio.emit("robot_emit_text", {"session_id": session_id, "text": str(round(float(dist), 1)), "widget_id": "ultrasonic"})
            pct = 0
            if findee and hasattr(findee, "_battery") and getattr(findee, "_battery", None) and hasattr(findee, "_battery_remaining_pct"):
                try:
                    v = findee._battery.voltage()
                    pct = findee._battery_remaining_pct(v)
                except Exception:
                    pass
            sio.emit("robot_emit_text", {"session_id": session_id, "text": str(round(pct)), "widget_id": "battery"})
        except Exception as e:
            print(f"request_sensor_data 오류: {e}")

    @sio.event
    def pid_update(data):
        try:
            widget_id = data.get("widget_id")
            if widget_id:
                widget_data.update_pid_data(widget_id, data.get("p", 0.0), data.get("i", 0.0), data.get("d", 0.0))
        except Exception as e:
            print(f"PID 업데이트 수신 오류: {e}")

    @sio.event
    def slider_update(data):
        try:
            widget_id = data.get("widget_id")
            if widget_id:
                widget_data.update_slider_data(widget_id, data.get("values", []))
        except Exception as e:
            print(f"Slider 업데이트 수신 오류: {e}")

    @sio.event
    def webrtc_offer(data):
        webrtc.enqueue_offer(data)

    @sio.event
    def webrtc_ice_candidate(data):
        webrtc.enqueue_ice_candidate(data)

    @sio.event
    def client_update(data):
        try:
            findee = state.findee
            if findee:
                findee.set_oled_status("Updating...")
            script_dir = updater._repo_root()
            robot_id, robot_name = ROBOT_ID, ROBOT_NAME
            updater.force_git_pull(script_dir)
            updater._restore_robot_config(script_dir / "config" / "robot_config.py", robot_id, robot_name)
            if findee:
                findee.set_oled_status("Update Complete!")
            time.sleep(1.5)
            subprocess.run(["sudo", "systemctl", "restart", "robot_client.service"], capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

    @sio.event
    def client_reset(data):
        findee = state.findee
        if findee:
            findee.set_oled_status("Resetting...")
        subprocess.run(["sudo", "tee", "/etc/pf_env"], input=b"MODE=AP\n", check=True, capture_output=True)
        script_dir = updater._repo_root()
        updater.force_git_pull(script_dir)
        if findee:
            findee.set_oled_status("Reset Complete!")
        time.sleep(1.5)
        subprocess.Popen(["sudo", "reboot"])
