"""Shared state set by main: sio and findee instance."""
from __future__ import annotations


class _State:
    sio = None
    findee = None


state = _State()
