"""위젯 데이터 저장소 및 접근 함수 (PID, Slider, 모바일 명령, 딥러닝 위젯 추론 결과)."""
from __future__ import annotations

PID_Wdata: dict[str, dict] = {}
Slider_Wdata: dict[str, list] = {}
Last_Command: dict[str, tuple] = {}
# 브라우저(WebRTC pfDlResult)가 갱신 — session_id = IDE 소켓 sid
DL_inference_result: dict[str, dict] = {}


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
    return dict(r) if isinstance(r, dict) else {}


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
