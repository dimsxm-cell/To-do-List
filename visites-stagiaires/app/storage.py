"""Stockage local : tout est rangé dans un dossier du Mac, en fichiers JSON lisibles.

Arborescence (par défaut ~/Documents/Visites stagiaires) :
    parametres.json
    stagiaires.json
    visites/<id>/visite.json
    visites/<id>/audio/...
    visites/<id>/documents/...
    visites/<id>/exports/...
"""

from __future__ import annotations

import copy
import json
import os
import re
import threading
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

from .defaults import DEFAULT_SETTINGS, empty_visit

_lock = threading.RLock()


def data_dir() -> Path:
    env = os.environ.get("VISITES_DATA_DIR")
    base = Path(env) if env else Path.home() / "Documents" / "Visites stagiaires"
    base.mkdir(parents=True, exist_ok=True)
    (base / "visites").mkdir(exist_ok=True)
    return base


def _read_json(path: Path, default):
    if not path.exists():
        return copy.deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Fichier abîmé : on garde une copie et on repart du défaut plutôt que de planter.
        backup = path.with_suffix(path.suffix + f".abime-{datetime.now():%Y%m%d%H%M%S}")
        try:
            path.rename(backup)
        except OSError:
            pass
        return copy.deepcopy(default)


def _write_json(path: Path, data) -> None:
    """Écriture atomique : on écrit dans un fichier temporaire puis on remplace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _merge_defaults(data: dict, defaults: dict) -> dict:
    out = copy.deepcopy(defaults)
    for k, v in (data or {}).items():
        if v is None and k in out:
            continue  # None = « revenir à la valeur par défaut »
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_defaults(v, out[k])
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------- paramètres

def get_settings() -> dict:
    with _lock:
        raw = _read_json(data_dir() / "parametres.json", {})
        return _merge_defaults(raw, DEFAULT_SETTINGS)


def save_settings(new: dict) -> dict:
    with _lock:
        merged = _merge_defaults(new, DEFAULT_SETTINGS)
        _write_json(data_dir() / "parametres.json", merged)
        return merged


# ---------------------------------------------------------------- stagiaires

def list_stagiaires() -> list[dict]:
    with _lock:
        items = _read_json(data_dir() / "stagiaires.json", [])
        return sorted(items, key=lambda s: (s.get("nom") or "").lower())


def save_stagiaire(item: dict) -> dict:
    with _lock:
        items = _read_json(data_dir() / "stagiaires.json", [])
        if not item.get("id"):
            item["id"] = uuid.uuid4().hex[:10]
            items.append(item)
        else:
            items = [item if s.get("id") == item["id"] else s for s in items]
            if not any(s.get("id") == item["id"] for s in items):
                items.append(item)
        _write_json(data_dir() / "stagiaires.json", items)
        return item


def delete_stagiaire(sid: str) -> None:
    with _lock:
        items = [s for s in _read_json(data_dir() / "stagiaires.json", []) if s.get("id") != sid]
        _write_json(data_dir() / "stagiaires.json", items)


# ---------------------------------------------------------------- visites

def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:40] or "visite"


def visit_dir(vid: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]+", vid or ""):
        raise ValueError("Identifiant de visite invalide")
    return data_dir() / "visites" / vid


def list_visits() -> list[dict]:
    out = []
    for p in (data_dir() / "visites").glob("*/visite.json"):
        v = _read_json(p, None)
        if not v:
            continue
        adm = v.get("admin", {})
        out.append({
            "id": v["id"],
            "stagiaire": adm.get("stagiaire_nom", ""),
            "date": adm.get("date", ""),
            "numero": adm.get("numero", ""),
            "ecole": adm.get("ecole", ""),
            "classe": adm.get("classe", ""),
            "etape": v.get("etape", ""),
            "valide": bool(v.get("bulletin", {}).get("valide")),
            "modifie": v.get("modifie", ""),
        })
    return sorted(out, key=lambda x: x.get("modifie", ""), reverse=True)


def create_visit(admin: dict | None = None) -> dict:
    with _lock:
        admin = admin or {}
        base = f"{datetime.now():%Y%m%d-%H%M}-{_slug(admin.get('stagiaire_nom', ''))}"
        vid, n = base, 2
        while (data_dir() / "visites" / vid).exists():
            vid, n = f"{base}-{n}", n + 1
        v = empty_visit(vid)
        v["admin"].update({k: val for k, val in admin.items() if k in v["admin"]})
        settings = get_settings()
        if not v["admin"]["formateurs"] and settings["formatrice"].get("nom"):
            v["admin"]["formateurs"] = [dict(settings["formatrice"])]
        if not v["admin"]["lieu"] and settings["formatrice"].get("lieu"):
            v["admin"]["lieu"] = settings["formatrice"]["lieu"]
        for sub in ("audio", "documents", "photos", "exports"):
            (visit_dir(vid) / sub).mkdir(parents=True, exist_ok=True)
        _write_json(visit_dir(vid) / "visite.json", v)
        return v


def get_visit(vid: str) -> dict:
    path = visit_dir(vid) / "visite.json"
    if not path.exists():
        raise FileNotFoundError(vid)
    with _lock:
        return _merge_defaults(_read_json(path, {}), empty_visit(vid))


def save_visit(v: dict) -> dict:
    with _lock:
        v["modifie"] = datetime.now().isoformat(timespec="seconds")
        _write_json(visit_dir(v["id"]) / "visite.json", v)
        return v


def update_visit(vid: str, fn) -> dict:
    """Lecture, modification par fn(visite), écriture : le tout sous verrou."""
    with _lock:
        v = get_visit(vid)
        fn(v)
        return save_visit(v)


def delete_visit(vid: str) -> None:
    import shutil

    with _lock:
        d = visit_dir(vid)
        if d.exists():
            trash = data_dir() / "corbeille"
            trash.mkdir(exist_ok=True)
            # On ne détruit rien : la visite part dans une corbeille récupérable.
            shutil.move(str(d), str(trash / f"{vid}-{datetime.now():%Y%m%d%H%M%S}"))
