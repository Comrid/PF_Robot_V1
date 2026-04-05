"""딥러닝 랩: 로봇 models/pf_models_index.json 유지 (목록·메타·이름/메모/삭제 동기화)."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

INDEX_FILENAME = "pf_models_index.json"
_MAX_NAME = 200
_MAX_MEMO = 4000
_MAX_CLASSES = 64
_MAX_CM = 64


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def models_root() -> Path:
    return _repo_root() / "models"


def sanitize_folder(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]", "_", (name or "").strip())[:80]
    return s or "model"


def index_path() -> Path:
    return models_root() / INDEX_FILENAME


def load_index() -> dict:
    p = index_path()
    if not p.exists():
        return {"version": 1, "models": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "models": []}
        data.setdefault("version", 1)
        data.setdefault("models", [])
        if not isinstance(data["models"], list):
            data["models"] = []
        return data
    except Exception:
        return {"version": 1, "models": []}


def save_index(data: dict) -> None:
    models_root().mkdir(parents=True, exist_ok=True)
    index_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _clamp_advanced(adv: object) -> dict:
    if not isinstance(adv, dict):
        return {}
    out: dict = {}
    pca = adv.get("perClassAccuracy")
    if isinstance(pca, list) and len(pca) <= _MAX_CLASSES:
        clean_pc = []
        for item in pca:
            if not isinstance(item, dict):
                continue
            clean_pc.append(
                {
                    "name": str(item.get("name", ""))[:120],
                    "correct": int(item.get("correct", 0) or 0),
                    "total": int(item.get("total", 0) or 0),
                    "accuracy": item.get("accuracy"),
                }
            )
        out["perClassAccuracy"] = clean_pc
    cm = adv.get("confusionMatrix")
    if isinstance(cm, list) and len(cm) <= _MAX_CM:
        clean_m = []
        for row in cm:
            if not isinstance(row, list) or len(row) > _MAX_CM:
                continue
            clean_m.append([int(x or 0) for x in row])
        out["confusionMatrix"] = clean_m
    return out


def _clamp_classes(classes: object) -> list:
    if not isinstance(classes, list):
        return []
    out = []
    for c in classes[:_MAX_CLASSES]:
        if not isinstance(c, dict):
            continue
        out.append(
            {
                "name": str(c.get("name", ""))[:120],
                "sampleCount": int(c.get("sampleCount", 0) or 0),
            }
        )
    return out


def _clamp_training(t: object) -> dict:
    if not isinstance(t, dict):
        return {}
    try:
        epochs = int(t.get("epochs", 0) or 0)
        batch = int(t.get("batchSize", 0) or t.get("batch", 0) or 0)
        lr = float(t.get("learningRate", 0) or t.get("lr", 0) or 0)
    except (TypeError, ValueError):
        return {}
    return {
        "epochs": max(1, min(500, epochs)),
        "batchSize": max(1, min(512, batch)),
        "learningRate": max(1e-8, min(1.0, lr)),
    }


def upsert_entry(folder_sanitized: str, entry: dict) -> None:
    """저장 직후: 클라이언트가 보낸 registry_entry로 인덱스 갱신."""
    folder = sanitize_folder(folder_sanitized)
    idx = load_index()
    models = idx.setdefault("models", [])
    now = datetime.now(timezone.utc).isoformat()
    display = str(entry.get("displayName") or folder).strip()[:_MAX_NAME] or folder
    memo = str(entry.get("memo") or "")[:_MAX_MEMO]
    training = _clamp_training(entry.get("training"))
    classes = _clamp_classes(entry.get("classes"))
    advanced = _clamp_advanced(entry.get("advanced"))
    embed_dim = entry.get("embedDim")
    base = entry.get("base")
    try:
        embed_dim = int(embed_dim) if embed_dim is not None else None
    except (TypeError, ValueError):
        embed_dim = None
    base_s = str(base)[:80] if base is not None else None

    blob = {
        "folder": folder,
        "displayName": display,
        "memo": memo,
        "training": training,
        "classes": classes,
        "advanced": advanced,
        "updatedAt": now,
    }
    if embed_dim is not None:
        blob["embedDim"] = embed_dim
    if base_s:
        blob["base"] = base_s

    found = False
    for m in models:
        if m.get("folder") == folder:
            created = m.get("createdAt") or now
            m.clear()
            m.update(blob)
            m["createdAt"] = created
            found = True
            break
    if not found:
        blob["createdAt"] = now
        models.append(blob)
    save_index(idx)


def upsert_minimal_from_manifest(folder_sanitized: str) -> None:
    """registry_entry 없을 때 manifest.json만으로 최소 항목."""
    folder = sanitize_folder(folder_sanitized)
    target = models_root() / folder / "manifest.json"
    if not target.exists():
        return
    try:
        man = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return
    class_names = man.get("classNames") if isinstance(man.get("classNames"), list) else []
    classes = [{"name": str(n)[:120], "sampleCount": 0} for n in class_names[:_MAX_CLASSES]]
    entry = {
        "displayName": folder,
        "memo": "",
        "classes": classes,
        "training": {},
        "advanced": {},
        "embedDim": man.get("embedDim"),
        "base": man.get("base"),
    }
    upsert_entry(folder, entry)


def sync_orphan_folders(idx: dict) -> dict:
    """디스크에만 있는 models/<folder>/ 를 인덱스에 반영."""
    root = models_root()
    if not root.is_dir():
        return idx
    known = {m.get("folder") for m in idx.get("models", []) if m.get("folder")}
    changed = False
    for p in root.iterdir():
        if not p.is_dir():
            continue
        name = p.name
        if name == INDEX_FILENAME.replace(".json", ""):  # paranoia
            continue
        if name in known:
            continue
        if not (p / "model.json").exists():
            continue
        try:
            st = p.stat()
            ts = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            ts = datetime.now(timezone.utc).isoformat()
        idx.setdefault("models", []).append(
            {
                "folder": name,
                "displayName": name,
                "memo": "",
                "createdAt": ts,
                "updatedAt": ts,
                "classes": [],
                "training": {},
                "advanced": {},
            }
        )
        known.add(name)
        changed = True
    if changed:
        save_index(idx)
    return idx


def update_entry(folder_sanitized: str, display_name: str | None, memo: str | None) -> bool:
    folder = sanitize_folder(folder_sanitized)
    idx = load_index()
    now = datetime.now(timezone.utc).isoformat()
    updated = False
    for m in idx.get("models", []):
        if m.get("folder") != folder:
            continue
        if display_name is not None:
            m["displayName"] = str(display_name).strip()[:_MAX_NAME] or folder
        if memo is not None:
            m["memo"] = str(memo)[:_MAX_MEMO]
        m["updatedAt"] = now
        updated = True
        break
    if updated:
        save_index(idx)
    return updated


def delete_folder_and_entry(folder_sanitized: str) -> bool:
    folder = sanitize_folder(folder_sanitized)
    target = models_root() / folder
    if target.exists() and target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
    idx = load_index()
    before = len(idx.get("models", []))
    idx["models"] = [m for m in idx.get("models", []) if m.get("folder") != folder]
    save_index(idx)
    return len(idx["models"]) < before or not (models_root() / folder).exists()
