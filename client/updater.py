"""force_git_pull, _restore_robot_config (config/robot_config.py)."""
from __future__ import annotations

import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def force_git_pull(script_dir: Path | None = None) -> None:
    root = script_dir or _repo_root()
    subprocess.run(["git", "stash", "push", "-m", '"Temp"'], capture_output=True, text=True, cwd=str(root))
    subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True, cwd=str(root))


def _restore_robot_config(config_path: Path, robot_id: str, robot_name: str) -> None:
    text = config_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = []
    for line in lines:
        s = line.strip()
        if s.startswith("ROBOT_ID ="):
            out.append(f"ROBOT_ID = {repr(robot_id)}")
        elif s.startswith("ROBOT_NAME ="):
            out.append(f"ROBOT_NAME = {repr(robot_name)}")
        else:
            out.append(line)
    config_path.write_text("\n".join(out) + "\n", encoding="utf-8")
