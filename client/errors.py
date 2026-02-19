"""Error codes for client (executor/webrtc)."""
from __future__ import annotations
from enum import IntEnum


class ErrCode(IntEnum):
    WRTC_WORKER = 0x0001
    WRTC_WORKER_START = 0x0002
    WRTC_OFFER = 0x0003
    WRTC_OFFER_QUEUE = 0x0004
    WRTC_IMAGE_IO = 0x0005
    IMG_NOT_NUMPY = 0x0006
    WRTC_TEXT_IO = 0x0007
    WRTC_CANDIDATE_QUEUE = 0x0008
    WRTC_CANDIDATE_EXTRACT = 0x0009
    WRTC_CANDIDATE_HANDLE = 0x0010
