"""WebRTC queue, manager, worker, signaling, ICE, DataChannel, image/text/system_info send."""
from __future__ import annotations

import asyncio
import json
import struct
from asyncio import Queue

try:
    from aiortc import (
        RTCPeerConnection,
        RTCSessionDescription,
        RTCIceCandidate,
        RTCDataChannel,
        RTCConfiguration,
    )
except ImportError:
    import subprocess
    subprocess.run(["sudo", "pip", "install", "aiortc", "--break-system-packages"], capture_output=True, text=True)
    from aiortc import (
        RTCPeerConnection,
        RTCSessionDescription,
        RTCIceCandidate,
        RTCDataChannel,
        RTCConfiguration,
    )

try:
    import psutil
except ImportError:
    import subprocess
    subprocess.run(["sudo", "pip", "install", "psutil", "--break-system-packages"], capture_output=True, text=True)
    import psutil

from client.errors import ErrCode
from client.state import state
from client import widget_data

webrtc_task_queue = Queue()


class WebRTC_Manager:
    def __init__(self, connection: RTCPeerConnection):
        self.connection: RTCPeerConnection = connection
        self.data_channel: RTCDataChannel | None = None
        self.candidate_queue: list = []
        self.remote_description_set: bool = False


webrtc_loop = asyncio.new_event_loop()
webrtc_sessions: dict[str, WebRTC_Manager] = {}


def _webrtc_parse_offer(d):
    return (d.get("session_id"), d.get("offer")) if (d.get("session_id") and d.get("offer")) else None


def _webrtc_parse_candidate(d):
    return (d.get("session_id"), d.get("candidate")) if (d.get("session_id") and d.get("candidate")) else None


def _webrtc_parse_send_image(d):
    return (d.get("session_id"), d.get("image_bytes"), d.get("widget_id")) if (d.get("session_id") and d.get("image_bytes") and d.get("widget_id")) else None


def _webrtc_parse_send_text(d):
    return (d.get("session_id"), d.get("text"), d.get("widget_id")) if (d.get("session_id") and d.get("text") and d.get("widget_id")) else None


def _webrtc_parse_system_info(d):
    return (d.get("session_id"),) if d.get("session_id") else None


def get_open_data_channel(session_id: str):
    """세션의 열린 DataChannel 반환, 없거나 닫혀 있으면 None."""
    session = webrtc_sessions.get(session_id)
    if not session or not session.data_channel or session.data_channel.readyState != "open":
        return None
    return session.data_channel


def _webrtc_header(type_byte: int, widget_id: str) -> bytes:
    widget_id_bytes = widget_id.encode("utf-8")
    return bytes([type_byte, len(widget_id_bytes)]) + widget_id_bytes


async def send_image_via_webrtc(session_id, image_bytes, widget_id):
    try:
        channel = get_open_data_channel(session_id)
        if not channel:
            return
        channel.send(_webrtc_header(0x01, widget_id) + image_bytes)
    except Exception:
        pass


async def send_text_via_webrtc(session_id, text, widget_id):
    try:
        channel = get_open_data_channel(session_id)
        if not channel:
            return
        channel.send(_webrtc_header(0x02, widget_id) + text.encode("utf-8"))
    except Exception:
        pass


async def send_system_info_via_webrtc(session_id):
    try:
        channel = get_open_data_channel(session_id)
        if not channel:
            return
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        ram_percent = memory.percent
        ram_used = memory.used / (1024**3)
        ram_total = memory.total / (1024**3)
        temp = None
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp_raw = int(f.read().strip())
                temp = temp_raw / 1000.0
        except Exception:
            pass
        system_info = {
            "type": "system_info",
            "cpu_percent": round(cpu_percent, 1),
            "ram_percent": round(ram_percent, 1),
            "ram_used": round(ram_used, 2),
            "ram_total": round(ram_total, 2),
            "temp": round(temp, 1) if temp else None,
        }
        channel.send(json.dumps(system_info))
    except Exception:
        pass


def create_ice_candidate(candidate_str, sdp_mid=None, sdp_m_line_index=None):
    try:
        if not candidate_str or not isinstance(candidate_str, str):
            return None
        if candidate_str.startswith("candidate:"):
            candidate_str = candidate_str[10:]
        parts = candidate_str.strip().split()
        if len(parts) < 8:
            return None
        foundation = parts[0]
        component = int(parts[1])
        protocol = parts[2].upper()
        priority = int(parts[3])
        ip = parts[4]
        port = int(parts[5])
        typ = "host"
        related_address = None
        related_port = None
        for i, part in enumerate(parts):
            if part == "typ" and i + 1 < len(parts):
                typ = parts[i + 1]
            elif part == "raddr" and i + 1 < len(parts):
                related_address = parts[i + 1]
            elif part == "rport" and i + 1 < len(parts):
                related_port = int(parts[i + 1])
        return RTCIceCandidate(
            foundation=foundation,
            component=component,
            protocol=protocol,
            priority=priority,
            ip=ip,
            port=port,
            type=typ,
            relatedAddress=related_address,
            relatedPort=related_port,
            sdpMid=sdp_mid,
            sdpMLineIndex=sdp_m_line_index,
        )
    except Exception:
        return None


def extract_and_send_candidates_from_sdp(sdp: str, session_id: str):
    try:
        candidate_lines = [line[2:] for line in sdp.split("\n") if line.startswith("a=candidate:")]
        if not candidate_lines:
            return
        sio = state.sio
        if not sio:
            return
        for candidate_str in candidate_lines:
            try:
                if len(candidate_str) < 20:
                    continue
                sio.emit(
                    "webrtc_ice_candidate",
                    {"candidate": {"candidate": candidate_str, "sdpMLineIndex": 0, "sdpMid": "0"}, "session_id": session_id},
                )
            except Exception:
                pass
        sio.emit("webrtc_ice_candidate", {"candidate": None, "session_id": session_id})
    except Exception:
        print(ErrCode.WRTC_CANDIDATE_EXTRACT)


async def _apply_queued_ice_candidates(session: WebRTC_Manager, pc: RTCPeerConnection) -> None:
    if not session.candidate_queue:
        return
    for candidate_dict in session.candidate_queue:
        try:
            candidate_str = candidate_dict.get("candidate", "")
            if candidate_str:
                candidate = create_ice_candidate(
                    candidate_str,
                    sdp_mid=candidate_dict.get("sdpMid"),
                    sdp_m_line_index=candidate_dict.get("sdpMLineIndex"),
                )
                if candidate:
                    await pc.addIceCandidate(candidate)
        except Exception:
            pass
    session.candidate_queue = []


async def _create_and_emit_answer(pc: RTCPeerConnection, session_id: str) -> None:
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    sio = state.sio
    if sio:
        sio.emit(
            "webrtc_answer",
            {"answer": {"type": pc.localDescription.type, "sdp": pc.localDescription.sdp}, "session_id": session_id},
        )


async def handle_webrtc_offer(session_id, offer_dict):
    try:
        old_session = webrtc_sessions.get(session_id)
        if old_session:
            await old_session.connection.close()
            del webrtc_sessions[session_id]
        configuration = RTCConfiguration(iceServers=[])
        pc = RTCPeerConnection(configuration=configuration)
        webrtc_sessions[session_id] = WebRTC_Manager(pc)
        sio = state.sio

        @pc.on("datachannel")
        def on_datachannel(channel: RTCDataChannel):
            webrtc_sessions[session_id].data_channel = channel

            async def system_info_loop():
                while session_id in webrtc_sessions:
                    session = webrtc_sessions.get(session_id)
                    if session and session.data_channel and session.data_channel.readyState == "open":
                        try:
                            webrtc_loop.call_soon_threadsafe(
                                webrtc_task_queue.put_nowait, ("send_system_info", {"session_id": session_id})
                            )
                        except Exception:
                            pass
                    await asyncio.sleep(1.0)

            asyncio.create_task(system_info_loop())

            @channel.on("message")
            def on_message(message):
                try:
                    if isinstance(message, bytes) and len(message) >= 2:
                        x_value, y_value = struct.unpack("bb", message[:2])
                        widget_data.Last_Command[session_id] = (x_value, y_value)
                        return
                    data = json.loads(message)
                    widget_type = data.get("type")
                    widget_id = data.get("widget_id")
                    if not widget_id:
                        return
                    if widget_type == "pid_update":
                        widget_data.update_pid_data(widget_id, data.get("p", 0.0), data.get("i", 0.0), data.get("d", 0.0))
                    elif widget_type == "slider_update":
                        widget_data.update_slider_data(widget_id, data.get("values", []))
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    print(f"위젯 데이터 수신 오류: {e}")

        @pc.on("icecandidate")
        def on_ice_candidate(candidate):
            if sio:
                if candidate:
                    sio.emit(
                        "webrtc_ice_candidate",
                        {
                            "candidate": {
                                "candidate": candidate.candidate,
                                "sdpMLineIndex": candidate.sdpMLineIndex,
                                "sdpMid": candidate.sdpMid,
                            },
                            "session_id": session_id,
                        },
                    )
                else:
                    sio.emit("webrtc_ice_candidate", {"candidate": None, "session_id": session_id})

        @pc.on("connectionstatechange")
        def on_connection_state_change():
            if pc.connectionState == "failed" or pc.connectionState == "closed":
                if session_id in webrtc_sessions:
                    del webrtc_sessions[session_id]

        @pc.on("icegatheringstatechange")
        def on_ice_gathering_state_change():
            if pc.iceGatheringState == "complete" and pc.localDescription:
                extract_and_send_candidates_from_sdp(pc.localDescription.sdp, session_id)

        offer = RTCSessionDescription(sdp=offer_dict["sdp"], type=offer_dict["type"])
        await pc.setRemoteDescription(offer)
        session = webrtc_sessions[session_id]
        session.remote_description_set = True
        await _apply_queued_ice_candidates(session, pc)
        await _create_and_emit_answer(pc, session_id)
    except Exception:
        print(ErrCode.WRTC_OFFER)


async def handle_webrtc_ice_candidate(session_id, candidate_dict):
    try:
        session = webrtc_sessions.get(session_id)
        if not session:
            return
        candidate_str = candidate_dict.get("candidate", "") if isinstance(candidate_dict, dict) else ""
        if not candidate_str:
            return
        if not session.remote_description_set:
            session.candidate_queue.append(candidate_dict)
            return
        try:
            candidate = create_ice_candidate(
                candidate_str,
                sdp_mid=candidate_dict.get("sdpMid"),
                sdp_m_line_index=candidate_dict.get("sdpMLineIndex"),
            )
            if candidate:
                await session.connection.addIceCandidate(candidate)
        except Exception:
            pass
    except Exception:
        print(ErrCode.WRTC_CANDIDATE_HANDLE)


async def webrtc_worker():
    asyncio.set_event_loop(webrtc_loop)
    task_handlers = {
        "offer": (_webrtc_parse_offer, handle_webrtc_offer),
        "candidate": (_webrtc_parse_candidate, handle_webrtc_ice_candidate),
        "send_image": (_webrtc_parse_send_image, send_image_via_webrtc),
        "send_text": (_webrtc_parse_send_text, send_text_via_webrtc),
        "send_system_info": (_webrtc_parse_system_info, send_system_info_via_webrtc),
    }
    while True:
        try:
            task_type, data = await webrtc_task_queue.get()
            if task_type == "shutdown":
                if webrtc_sessions:
                    tasks = [s.connection.close() for s in webrtc_sessions.values()]
                    await asyncio.gather(*tasks, return_exceptions=True)
                    webrtc_sessions.clear()
                break
            handler = task_handlers.get(task_type)
            if not handler:
                continue
            parse_fn, coro_fn = handler
            args = parse_fn(data)
            if args is not None:
                asyncio.create_task(coro_fn(*args))
        except Exception:
            print(ErrCode.WRTC_WORKER)


def start_webrtc_loop():
    webrtc_loop.run_until_complete(webrtc_worker())


def enqueue_offer(data):
    try:
        webrtc_loop.call_soon_threadsafe(webrtc_task_queue.put_nowait, ("offer", data))
    except Exception:
        print(ErrCode.WRTC_OFFER_QUEUE)


def enqueue_ice_candidate(data):
    try:
        webrtc_loop.call_soon_threadsafe(webrtc_task_queue.put_nowait, ("candidate", data))
    except Exception:
        print(ErrCode.WRTC_CANDIDATE_QUEUE)
