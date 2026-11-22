"""Tâches longues (transcription, IA) exécutées en arrière-plan, une à la fois.

L'interface interroge régulièrement l'état d'avancement.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime

_jobs: dict[str, dict] = {}
_lock = threading.Lock()
# Une seule tâche lourde à la fois : le Mac n'a qu'une puce à partager entre Whisper et l'IA.
_heavy = threading.Lock()


def start(kind: str, visit_id: str, fn) -> dict:
    with _lock:
        for j in _jobs.values():
            if j["visite"] == visit_id and j["type"] == kind and j["etat"] in ("attente", "en_cours"):
                return j
        jid = uuid.uuid4().hex[:12]
        job = {
            "id": jid, "type": kind, "visite": visit_id, "etat": "attente",
            "progression": 0.0, "message": "En attente…", "erreur": "",
            "debut": datetime.now().isoformat(timespec="seconds"),
        }
        _jobs[jid] = job

    def progress(p: float, msg: str = ""):
        job["progression"] = max(0.0, min(1.0, float(p)))
        if msg:
            job["message"] = msg

    def run():
        with _heavy:
            job["etat"] = "en_cours"
            job["message"] = "Démarrage…"
            try:
                fn(progress)
                job["etat"] = "termine"
                job["progression"] = 1.0
                job["message"] = "Terminé."
            except Exception as e:  # on remonte un message lisible à l'interface
                job["etat"] = "erreur"
                job["erreur"] = str(e) or e.__class__.__name__
                job["message"] = "Erreur."
                traceback.print_exc()

    threading.Thread(target=run, daemon=True).start()
    return job


def get(jid: str) -> dict | None:
    return _jobs.get(jid)


def for_visit(visit_id: str) -> list[dict]:
    return [j for j in _jobs.values() if j["visite"] == visit_id and j["etat"] in ("attente", "en_cours")]
