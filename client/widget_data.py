"""위젯 데이터 저장소 및 접근 함수 (PID, Slider, 모바일 명령)."""
from __future__ import annotations

PID_Wdata: dict[str, dict] = {}
Slider_Wdata: dict[str, list] = {}
Last_Command: dict[str, tuple] = {}


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
