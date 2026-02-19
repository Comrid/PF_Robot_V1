"""Code execution: exec_code, exec namespace, ThreadManager, check_stop_flag, ctypes thread stop."""
from __future__ import annotations

import ctypes
import threading
from traceback import format_exc

import cv2

from findee import Findee
from client.errors import ErrCode
from client.state import state
from client import widget_data
from client import webrtc


class ThreadManager:
    def __init__(self, thread: threading.Thread):
        self.thread: threading.Thread = thread
        self.stop_flag: bool = False


session_threads: dict[str, ThreadManager] = {}

_async_exc_func = ctypes.pythonapi.PyThreadState_SetAsyncExc
_async_exc_func.argtypes = [ctypes.c_ulong, ctypes.py_object]
_async_exc_func.restype = ctypes.c_int


def _raise_exception_in_thread(thread: threading.Thread, exc_type=SystemExit) -> bool:
    if thread is None or not thread.is_alive():
        return False
    tid = ctypes.c_ulong(thread.ident)
    res = _async_exc_func(tid, ctypes.py_object(exc_type))
    if res > 1:
        _async_exc_func(tid, ctypes.py_object(0))
        return False
    return res == 1


def check_stop_flag(session_id: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if session_id in session_threads and session_threads[session_id].stop_flag:
                return
            return func(*args, **kwargs)
        return wrapper
    return decorator


def _queue_webrtc_or_emit_socket(session_id: str, widget_id: str, task_type: str, task_payload: dict, sio_event: str, sio_payload: dict, err_code: ErrCode) -> None:
    channel = webrtc.get_open_data_channel(session_id)
    if channel:
        try:
            webrtc.webrtc_loop.call_soon_threadsafe(webrtc.webrtc_task_queue.put_nowait, (task_type, task_payload))
            return
        except Exception:
            print(err_code)
    sio = state.sio
    if sio:
        sio.emit(sio_event, sio_payload)


def exec_code(code, session_id):
    if session_id in session_threads:
        session_threads[session_id].stop_flag = False
    findee = state.findee
    if findee:
        findee.set_code_running(True)
    _check = check_stop_flag(session_id)

    @_check
    def realtime_print(*args, **kwargs):
        output = " ".join(str(arg) for arg in args)
        if output and state.sio:
            state.sio.emit("robot_stdout", {"session_id": session_id, "output": output})

    try:
        @_check
        def emit_image(image, widget_id):
            if not hasattr(image, "shape"):
                print(ErrCode.IMG_NOT_NUMPY)
                raise Exception(str(ErrCode.IMG_NOT_NUMPY))
            ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            if not ok:
                return
            image_bytes = buffer.tobytes()
            _queue_webrtc_or_emit_socket(
                session_id,
                widget_id,
                "send_image",
                {"session_id": session_id, "image_bytes": image_bytes, "widget_id": widget_id},
                "robot_emit_image",
                {"session_id": session_id, "image_data": image_bytes, "widget_id": widget_id},
                ErrCode.WRTC_IMAGE_IO,
            )

        @_check
        def emit_text(text, widget_id):
            _queue_webrtc_or_emit_socket(
                session_id,
                widget_id,
                "send_text",
                {"session_id": session_id, "text": text, "widget_id": widget_id},
                "robot_emit_text",
                {"session_id": session_id, "text": text, "widget_id": widget_id},
                ErrCode.WRTC_TEXT_IO,
            )

        exec_namespace = {
            "Findee": Findee,
            "emit_image": emit_image,
            "emit_text": emit_text,
            "print": realtime_print,
            "get_pid": widget_data.get_pid,
            "get_slider": widget_data.get_slider,
            "get_command": lambda: widget_data.get_command(session_id),
        }
        compiled_code = compile(code, "<string>", "exec")
        exec(compiled_code, exec_namespace)
    except Exception:
        if state.sio:
            for line in format_exc().splitlines():
                state.sio.emit("robot_stderr", {"session_id": session_id, "output": line})
    finally:
        if findee:
            findee.set_code_running(False)
        if session_id in session_threads:
            del session_threads[session_id]
        if state.sio:
            state.sio.emit("robot_finished", {"session_id": session_id})
        Findee().stop()
