"""위젯 데이터 저장소 및 접근 함수 (PID, Slider, 모바일 명령, 딥러닝 위젯 추론 결과)."""
from __future__ import annotations

import threading

PID_Wdata: dict[str, dict] = {}
Slider_Wdata: dict[str, list] = {}
Last_Command: dict[str, tuple] = {}
# 브라우저(WebRTC pfDlResult)가 갱신 — session_id = IDE 소켓 sid
DL_inference_result: dict[str, dict] = {}

# get_dl_inference_result()에서 제외 (극값은 get_dl_class_extremes() 사용)
_DL_INFERENCE_RESULT_EXCLUDE = frozenset({
    "best",
    "worst",
    "bestIndex",
    "bestName",
    "bestConfidence",
    "worstIndex",
    "worstName",
    "worstConfidence",
})

# load_model() 블로킹: 웹(TF.js) 로드 완료 ACK까지 대기 — session_id = IDE 소켓 sid
_dl_load_lock = threading.Lock()
_dl_load_events: dict[str, threading.Event] = {}
_dl_load_results: dict[str, dict] = {}


def prepare_dl_load_wait(session_id: str) -> threading.Event | None:
    if not session_id:
        return None
    with _dl_load_lock:
        _dl_load_events.pop(session_id, None)
        _dl_load_results.pop(session_id, None)
        ev = threading.Event()
        _dl_load_events[session_id] = ev
        _dl_load_results[session_id] = {"success": False, "error": ""}
        return ev


def complete_dl_load(session_id: str, success: bool, error: str = "") -> None:
    if not session_id:
        return
    with _dl_load_lock:
        if session_id not in _dl_load_events:
            return
        _dl_load_results[session_id] = {"success": bool(success), "error": (error or "")[:2000]}
        ev = _dl_load_events.get(session_id)
    if ev is not None:
        ev.set()


def consume_dl_load_result(session_id: str) -> dict:
    with _dl_load_lock:
        r = _dl_load_results.get(session_id)
        return dict(r) if isinstance(r, dict) else {"success": False, "error": ""}


def clear_dl_load_wait(session_id: str) -> None:
    if not session_id:
        return
    with _dl_load_lock:
        _dl_load_events.pop(session_id, None)
        _dl_load_results.pop(session_id, None)


def update_pid_data(widget_id: str, p: float, i: float, d: float) -> None:
    PID_Wdata[widget_id] = {"p": float(p), "i": float(i), "d": float(d)}


def update_slider_data(widget_id: str, values: list) -> None:
    if isinstance(values, list):
        Slider_Wdata[widget_id] = values


def get_pid(widget_id: str) -> tuple[float | None, float | None, float | None]:
    data = PID_Wdata.get(widget_id)
    if data:
        return data["p"], data["i"], data["d"]
    return None, None, None


def get_slider(widget_id: str) -> list:
    return Slider_Wdata.get(widget_id, [])


def get_command(session_id: str | None = None) -> tuple:
    if session_id is None:
        if Last_Command:
            session_id = list(Last_Command.keys())[0]
        else:
            return (0, 0)
    return Last_Command.get(session_id, (0, 0))


def set_dl_inference_result(session_id: str, payload: dict) -> None:
    if session_id and isinstance(payload, dict):
        DL_inference_result[session_id] = payload


def get_dl_inference_result(session_id: str) -> dict:
    r = DL_inference_result.get(session_id)
    if not isinstance(r, dict):
        return {}
    return {k: v for k, v in r.items() if k not in _DL_INFERENCE_RESULT_EXCLUDE}


def get_dl_class_extremes(session_id: str) -> dict | None:
    r = DL_inference_result.get(session_id)
    if not isinstance(r, dict):
        return None
    probs = r.get("probs")
    names = r.get("classNames")
    if not isinstance(probs, list) or len(probs) == 0:
        return None
    if not isinstance(names, list) or len(names) != len(probs):
        names = [str(i) for i in range(len(probs))]
    best_i = max(range(len(probs)), key=lambda i: probs[i])
    worst_i = min(range(len(probs)), key=lambda i: probs[i])
    return {
        "best": {
            "index": best_i,
            "name": names[best_i] if best_i < len(names) else str(best_i),
            "confidence": probs[best_i],
        },
        "worst": {
            "index": worst_i,
            "name": names[worst_i] if worst_i < len(names) else str(worst_i),
            "confidence": probs[worst_i],
        },
    }
