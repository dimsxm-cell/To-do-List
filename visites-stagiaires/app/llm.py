"""Dialogue avec l'IA locale (Ollama, sur le Mac). Aucun appel vers Internet.

On refuse toute adresse qui ne serait pas sur la machine elle-même : c'est une
garantie de confidentialité, pas seulement un réglage.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class IAIndisponible(Exception):
    pass


def _check_local(url: str) -> str:
    host = urlparse(url).hostname or ""
    if host not in LOCAL_HOSTS:
        raise IAIndisponible(
            "Par sécurité, l'IA doit tourner sur ce Mac (adresse 127.0.0.1). "
            f"L'adresse « {url} » a été refusée."
        )
    return url.rstrip("/")


def _post(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    # Pas de proxy : on parle uniquement au Mac lui-même.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        if e.code == 404 and "not found" in body.lower():
            raise IAIndisponible(
                f"Le modèle d'IA « {payload.get('model')} » n'est pas installé. "
                "Relancez l'installation ou choisissez un autre modèle dans les Paramètres."
            ) from e
        raise IAIndisponible(f"L'IA locale a renvoyé une erreur ({e.code}) : {body[:300]}") from e
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise IAIndisponible(
            "L'IA locale (Ollama) ne répond pas. Ouvrez l'application Ollama sur le Mac, "
            "puis réessayez."
        ) from e


def status(cfg: dict) -> dict:
    base = _check_local(cfg["url"])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(base + "/api/tags", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return {"ok": False, "message": "Ollama n'est pas démarré.", "modeles": []}
    names = [m.get("name", "") for m in data.get("models", [])]
    want = cfg["modele"]
    present = any(n == want or n.split(":")[0] == want or n == want + ":latest" for n in names)
    return {
        "ok": present,
        "message": "IA prête." if present else f"Le modèle « {want} » n'est pas installé.",
        "modeles": names,
    }


def chat_json(cfg: dict, system: str, user: str, schema: dict, timeout: float = 1800) -> dict:
    """Envoie une demande et exige une réponse JSON conforme au schéma."""
    base = _check_local(cfg["url"])
    payload = {
        "model": cfg["modele"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "format": schema,
        "options": {
            "temperature": float(cfg.get("temperature", 0.2)),
            "num_ctx": int(cfg.get("contexte", 16384)),
        },
    }
    data = _post(base + "/api/chat", payload, timeout)
    content = (data.get("message") or {}).get("content", "")
    return parse_json(content)


def parse_json(content: str) -> dict:
    content = re.sub(r"<think>.*?</think>", "", content or "", flags=re.S).strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.S)
    if m:
        content = m.group(1)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(content[start: end + 1])
            except json.JSONDecodeError:
                pass
    raise IAIndisponible("L'IA a produit une réponse illisible. Relancez l'opération.")
