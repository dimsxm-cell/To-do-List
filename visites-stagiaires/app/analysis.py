"""Analyse par l'IA locale : interlocuteurs, corrections, fiches, analyse réflexive, bulletin.

Principe anti-invention : chaque élément proposé doit citer un court extrait de la
source. On vérifie ensuite que l'extrait existe vraiment ; sinon l'élément est
signalé « à vérifier » à la formatrice.
"""

from __future__ import annotations

import difflib
import re
import unicodedata

from . import llm

SYSTEME = (
    "Tu es l'assistant d'une formatrice de l'Éducation nationale (PEMF) qui conduit des visites "
    "formatives de fonctionnaires stagiaires professeurs des écoles. Tu écris en français, dans un "
    "style professionnel, précis et synthétique. Règle absolue : tu n'inventes jamais rien. Tu "
    "n'utilises que les informations présentes dans les sources fournies. Si une information "
    "manque, tu laisses le champ vide. Tu n'attribues jamais à une personne des propos qu'elle "
    "n'a pas tenus."
)


# ------------------------------------------------------------------ outils texte

def hms(sec: float) -> str:
    sec = int(sec or 0)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


LOC = {"F": "Formatrice", "S": "Stagiaire", "?": "Interlocuteur non identifié"}
# Dans l'enregistrement d'une séance en classe, la stagiaire est l'enseignante (« E »).
LOC_SEANCE = {"S": "E", "EL": "Élève", "?": "?"}


def types_audios(visit: dict) -> dict:
    """{id audio: (type, numéro de séance)} — type « entretien » (par défaut) ou « seance »."""
    return {a["id"]: (a.get("type") or "entretien", int(a.get("seance") or 1)) for a in visit.get("audios", [])}


def segments_entretien(visit: dict) -> list[dict]:
    types = types_audios(visit)
    return [s for s in visit.get("transcription", {}).get("segments", [])
            if types.get(s.get("audio"), ("entretien", 1))[0] != "seance"]


def segments_seance(visit: dict, numero: int) -> list[dict]:
    types = types_audios(visit)
    return [s for s in visit.get("transcription", {}).get("segments", [])
            if types.get(s.get("audio"), ("entretien", 1)) == ("seance", numero)]


def numeros_seances_enregistrees(visit: dict) -> list[int]:
    return sorted({n for t, n in types_audios(visit).values() if t == "seance"})


def turns(segments: list[dict], include_hors_sujet: bool = False) -> list[dict]:
    """Regroupe les segments consécutifs d'un même interlocuteur en tours de parole."""
    out = []
    for s in segments:
        if s.get("hors_sujet") and not include_hors_sujet:
            continue
        loc = s.get("locuteur") or "?"
        if out and out[-1]["locuteur"] == loc:
            out[-1]["texte"] += " " + s["texte"]
            out[-1]["fin"] = s["fin"]
        else:
            out.append({"locuteur": loc, "debut": s["debut"], "fin": s["fin"], "texte": s["texte"]})
    return out


def transcript_text(segments: list[dict], include_hors_sujet: bool = False, seance: bool = False) -> str:
    noms = LOC_SEANCE if seance else LOC
    return "\n".join(
        f"[{noms.get(t['locuteur'], t['locuteur'])} {hms(t['debut'])}] {t['texte']}"
        for t in turns(segments, include_hors_sujet)
    )


def _budget_chars(cfg: dict, reserve_tokens: int = 5000) -> int:
    ctx = int(cfg.get("contexte", 16384))
    return max(6000, int((ctx - reserve_tokens) * 3.0))


def _chunks_by_chars(lines: list[str], max_chars: int) -> list[str]:
    out, cur, size = [], [], 0
    for ln in lines:
        if cur and size + len(ln) > max_chars:
            out.append("\n".join(cur))
            cur, size = [], 0
        cur.append(ln)
        size += len(ln) + 1
    if cur:
        out.append("\n".join(cur))
    return out


def extrait_present(extrait: str, source: str) -> bool:
    """L'extrait cité se retrouve-t-il (à peu près mot pour mot) dans la source ?"""
    e, s = _norm(extrait), _norm(source)
    if not e or len(e) < 6:
        return False
    if e in s:
        return True
    words = e.split()
    if len(words) < 3:
        return False
    # Tolérance : on cherche une fenêtre de la source très proche de l'extrait.
    sw = s.split()
    n = len(words)
    best = 0.0
    first = {w for w in words[:3]}
    for i, w in enumerate(sw):
        if w not in first:
            continue
        window = " ".join(sw[i: i + n + 3])
        r = difflib.SequenceMatcher(None, e, window).ratio()
        best = max(best, r)
        if best > 0.8:
            return True
    return False


# ------------------------------------------------------------------ 1. interlocuteurs

SCHEMA_LOC = {
    "type": "object",
    "properties": {
        "lignes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "locuteur": {"type": "string", "enum": ["F", "S"]},
                    "hors_sujet": {"type": "boolean"},
                },
                "required": ["n", "locuteur", "hors_sujet"],
            },
        }
    },
    "required": ["lignes"],
}


SCHEMA_LOC_SEANCE = {
    "type": "object",
    "properties": {
        "lignes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "locuteur": {"type": "string", "enum": ["S", "EL"]},
                    "hors_sujet": {"type": "boolean"},
                },
                "required": ["n", "locuteur", "hors_sujet"],
            },
        }
    },
    "required": ["lignes"],
}


def attribuer_interlocuteurs(cfg: dict, segments: list[dict], progress=lambda p, m="": None,
                             mode: str = "entretien") -> list[dict]:
    """Propose F (formatrice) / S (stagiaire) et repère les conversations parasites.

    Les choix faits à la main par la formatrice (verrouille=True) ne sont jamais écrasés.
    """
    size = 50
    total = max(1, (len(segments) + size - 1) // size)
    for k in range(total):
        lot = segments[k * size: (k + 1) * size]
        contexte = segments[max(0, k * size - 4): k * size]
        lignes = "\n".join(f"{i + 1}. {s['texte']}" for i, s in enumerate(lot))
        avant = "\n".join(f"- ({s.get('locuteur', '?')}) {s['texte']}" for s in contexte)
        if mode == "seance":
            consigne = (
                "Voici un extrait de la transcription automatique d'une SÉANCE EN CLASSE (école primaire). "
                "Codes : S = l'ENSEIGNANTE (elle donne les consignes, questionne, valide, relance, gère la classe), "
                "EL = un ou des ÉLÈVES (réponses, questions, propositions).\n"
                "Pour CHAQUE ligne numérotée, indique qui parle (S ou EL) et si la ligne est HORS SUJET "
                "(bruit, échange sans rapport avec la séance).\n"
            )
        else:
            consigne = (
                "Voici un extrait de la transcription automatique d'un entretien de visite formative "
                "entre une FORMATRICE (F) et une enseignante STAGIAIRE (S), après l'observation d'une séance en classe.\n"
                "Indices : la formatrice pose les questions, reformule, apprécie, conseille, cite des ressources. "
                "La stagiaire décrit sa classe, ses choix, ses difficultés, répond aux questions.\n"
                "Pour CHAQUE ligne numérotée, indique qui parle (F ou S) et si la ligne est HORS SUJET "
                "(conversation parasite sans rapport avec l'entretien professionnel : téléphone, bavardage, "
                "interruption par un tiers, logistique sans intérêt).\n"
            )
        user = (
            consigne
            + (f"\nLignes précédentes (pour le contexte) :\n{avant}\n" if avant else "")
            + f"\nLignes à traiter :\n{lignes}\n\nRéponds en JSON."
        )
        schema = SCHEMA_LOC_SEANCE if mode == "seance" else SCHEMA_LOC
        codes = ("S", "EL") if mode == "seance" else ("F", "S")
        res = llm.chat_json(cfg, SYSTEME, user, schema, attendu=45 * len(lot),
                            progress=lambda f, m, k=k: progress((k + f) / total, f"Interlocuteurs : lot {k + 1}/{total}"))
        par_n = {int(x.get("n", 0)): x for x in res.get("lignes", []) if isinstance(x, dict)}
        for i, s in enumerate(lot):
            if s.get("verrouille"):
                continue
            x = par_n.get(i + 1)
            if x:
                s["locuteur"] = x.get("locuteur") if x.get("locuteur") in codes else "?"
                s["hors_sujet"] = bool(x.get("hors_sujet"))
        progress((k + 1) / total, f"Interlocuteurs : lot {k + 1}/{total}")
    return segments


# ------------------------------------------------------------------ 2. corrections

SCHEMA_CORR = {
    "type": "object",
    "properties": {
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"n": {"type": "integer"}, "texte": {"type": "string"}},
                "required": ["n", "texte"],
            },
        }
    },
    "required": ["corrections"],
}


def corriger_transcription(cfg: dict, segments: list[dict], vocabulaire: str = "", progress=lambda p, m="": None):
    """Corrige les erreurs évidentes de reconnaissance vocale, sans changer le sens.

    Le texte d'origine est conservé (texte_original) pour pouvoir revenir en arrière.
    Une correction trop éloignée du texte d'origine est refusée.
    """
    size = 40
    total = max(1, (len(segments) + size - 1) // size)
    nb = 0
    for k in range(total):
        lot = segments[k * size: (k + 1) * size]
        lignes = "\n".join(f"{i + 1}. {s['texte']}" for i, s in enumerate(lot))
        user = (
            "Voici des lignes issues d'une reconnaissance vocale automatique (entretien pédagogique). "
            "Corrige UNIQUEMENT les erreurs évidentes de reconnaissance (mot mal entendu, orthographe, "
            "accord, ponctuation, sigle mal écrit). Ne reformule pas, ne résume pas, ne change jamais le sens, "
            "garde le style oral. Ne renvoie QUE les lignes qui ont besoin d'une correction, avec leur numéro.\n"
            + (f"Vocabulaire du métier : {vocabulaire}\n" if vocabulaire else "")
            + f"\nLignes :\n{lignes}\n\nRéponds en JSON."
        )
        res = llm.chat_json(cfg, SYSTEME, user, SCHEMA_CORR, attendu=25 * len(lot),
                            progress=lambda f, m, k=k: progress((k + f) / total, f"Corrections : lot {k + 1}/{total}"))
        for c in res.get("corrections", []):
            try:
                i = int(c.get("n", 0)) - 1
            except (TypeError, ValueError):
                continue
            if not (0 <= i < len(lot)):
                continue
            s, new = lot[i], str(c.get("texte", "")).strip()
            if not new or new == s["texte"] or s.get("verrouille"):
                continue
            ratio = difflib.SequenceMatcher(None, _norm(s["texte"]), _norm(new)).ratio()
            if ratio < 0.7:
                continue  # trop différent : risque de changement de sens, on refuse
            s.setdefault("texte_original", s["texte"])
            s["texte"] = new
            nb += 1
        progress((k + 1) / total, f"Corrections : lot {k + 1}/{total}")
    return nb


# ------------------------------------------------------------------ 3. documents

SCHEMA_DOC = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["seance", "sequence", "autre"]},
        "discipline": {"type": "string"},
        "niveau": {"type": "string"},
        "titre": {"type": "string"},
        "objectifs": {"type": "array", "items": {"type": "string"}},
        "competences": {"type": "array", "items": {"type": "string"}},
        "deroulement": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "temps": {"type": "string"}, "deroulement": {"type": "string"},
                    "dispositif": {"type": "string"}, "organisation": {"type": "string"},
                },
                "required": ["temps", "deroulement", "dispositif", "organisation"],
            },
        },
        "modalites": {"type": "string"},
        "resume": {"type": "string"},
    },
    "required": ["type", "discipline", "niveau", "titre", "objectifs", "competences", "deroulement", "modalites", "resume"],
}


def analyser_document(cfg: dict, texte: str, nom: str, type_devine: str, progress=None) -> dict:
    extrait = texte[: _budget_chars(cfg, 4000)]
    user = (
        f"Document importé : « {nom} » (type pressenti : {type_devine}).\n"
        "Détermine s'il s'agit d'une FICHE DE SÉANCE (une seule séance détaillée : phases, durées, consignes), "
        "d'une FICHE DE SÉQUENCE (plan de plusieurs séances autour d'un objectif) ou d'un AUTRE document.\n"
        "Puis extrais, uniquement à partir du texte : discipline ou domaine, niveau de classe, titre, objectifs, "
        "compétences visées, déroulement (pour une fiche de séance : chaque phase avec temps, déroulement, "
        "dispositif, organisation matérielle ; pour une séquence : laisse le déroulement vide), modalités de mise "
        "en œuvre (différenciation, évaluation…) et un résumé de 2 à 3 phrases. Laisse vide ce qui n'y figure pas.\n\n"
        f"TEXTE DU DOCUMENT :\n{extrait}\n\nRéponds en JSON."
    )
    return llm.chat_json(cfg, SYSTEME, user, SCHEMA_DOC, attendu=2000, progress=progress)


def resume_documents(documents: list[dict]) -> str:
    parts = []
    for d in documents:
        info = d.get("analyse") or {}
        lab = {"seance": "FICHE DE SÉANCE", "sequence": "FICHE DE SÉQUENCE"}.get(d.get("type"), "DOCUMENT")
        if info:
            lines = [f"{lab} « {d.get('nom', '')} »"]
            for key, title in (("discipline", "Discipline"), ("niveau", "Niveau"), ("titre", "Titre")):
                if info.get(key):
                    lines.append(f"{title} : {info[key]}")
            if info.get("objectifs"):
                lines.append("Objectifs : " + " ; ".join(info["objectifs"]))
            if info.get("competences"):
                lines.append("Compétences : " + " ; ".join(info["competences"]))
            for ph in info.get("deroulement", []):
                lines.append(
                    f"Phase : {ph.get('temps', '')} | {ph.get('deroulement', '')} | "
                    f"{ph.get('dispositif', '')} | {ph.get('organisation', '')}"
                )
            if info.get("modalites"):
                lines.append(f"Modalités : {info['modalites']}")
            if info.get("resume"):
                lines.append(f"Résumé : {info['resume']}")
            parts.append("\n".join(lines))
        elif d.get("texte"):
            parts.append(f"{lab} « {d.get('nom', '')} » :\n{d['texte'][:4000]}")
    return "\n\n".join(parts)


# ------------------------------------------------------------------ 4. analyse réflexive

_ITEM = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"texte": {"type": "string"}, "extrait": {"type": "string"}},
        "required": ["texte", "extrait"],
    },
}

CLES = {
    "A": ["constats", "reussites", "difficultes", "analyse_pratique", "questionnements", "propositions"],
    "B": ["points_forts", "competences_maitrisees", "difficultes", "axes_amelioration", "accompagnement"],
    "C": ["conseils_pedagogiques", "preconisations", "remediations", "ressources", "perspectives"],
}

TITRES = {
    "A": "Points relevés par la stagiaire",
    "B": "Points relevés par la formatrice",
    "C": "Conseils prodigués par la formatrice",
    "D": "Bilan réflexif",
    "constats": "Ses constats", "reussites": "Réussites identifiées", "difficultes": "Difficultés",
    "analyse_pratique": "Analyse de sa pratique", "questionnements": "Questionnements",
    "propositions": "Propositions d'amélioration", "points_forts": "Points forts observés",
    "competences_maitrisees": "Compétences maîtrisées", "axes_amelioration": "Axes d'amélioration",
    "accompagnement": "Éléments nécessitant un accompagnement",
    "conseils_pedagogiques": "Conseils pédagogiques", "preconisations": "Préconisations méthodologiques",
    "remediations": "Pistes de remédiation", "ressources": "Supports et ressources conseillés",
    "perspectives": "Perspectives de progression",
}


def _schema_analyse(with_bilan: bool) -> dict:
    props = {
        g: {"type": "object", "properties": {k: _ITEM for k in keys}, "required": keys}
        for g, keys in CLES.items()
    }
    req = list(CLES)
    if with_bilan:
        props["D"] = {"type": "string"}
        req.append("D")
    return {"type": "object", "properties": props, "required": req}


CONSIGNE_ANALYSE = (
    "Classe les éléments de l'entretien selon la grille :\n"
    "A = ce que dit LA STAGIAIRE elle-même (constats, réussites, difficultés, analyse de sa pratique, "
    "questionnements, propositions d'amélioration).\n"
    "B = ce que relève LA FORMATRICE (points forts observés, compétences maîtrisées, difficultés constatées, "
    "axes d'amélioration, éléments nécessitant un accompagnement).\n"
    "C = les CONSEILS donnés par LA FORMATRICE (conseils pédagogiques, préconisations méthodologiques, pistes "
    "de remédiation, supports et ressources conseillés, perspectives de progression).\n"
    "Règles :\n"
    "- Respecte strictement qui a parlé : les lignes [Stagiaire] vont en A, les lignes [Formatrice] en B ou C.\n"
    "- Chaque élément : « texte » = reformulation professionnelle courte (une phrase), "
    "« extrait » = citation EXACTE, mot pour mot, de 5 à 15 mots, copiée de la transcription ou des notes.\n"
    "- Les notes de la formatrice sont une source valable pour B et C.\n"
    "- N'ajoute aucun élément qui ne figure pas dans les sources. Une rubrique sans élément reste une liste vide.\n"
    "- Au maximum 4 éléments par rubrique : garde les plus importants. Extraits de 5 à 15 mots.\n"
    "- Pas de doublon d'une rubrique à l'autre.\n"
)


def analyse_reflexive(cfg: dict, visit: dict, grille: str, progress=lambda p, m="": None) -> dict:
    segments = segments_entretien(visit)
    trans = transcript_text(segments)
    notes = (visit.get("notes_formatrice") or "").strip()
    docs = resume_documents(visit.get("documents", []))
    if not trans and not notes:
        raise llm.IAIndisponible("Il n'y a ni transcription ni notes à analyser.")

    legendes = legendes_photos(visit)
    if legendes:
        notes = (notes + "\n" + legendes).strip()
    from .referentiel import CADRE_ANALYSE

    contexte = (
        f"GRILLE ET ATTENTES DE LA FORMATRICE :\n{grille}\n\n{CADRE_ANALYSE}\n"
        + (f"DOCUMENTS DE LA STAGIAIRE (pour comprendre la séance, pas comme source de propos) :\n{docs[:6000]}\n\n" if docs else "")
        + (f"NOTES DE LA FORMATRICE (observation de la séance) :\n{notes}\n\n" if notes else "")
    )
    budget = max(6000, _budget_chars(cfg) - len(contexte))
    morceaux = _chunks_by_chars(trans.split("\n"), budget) if trans else [""]

    if len(morceaux) == 1:
        progress(0.1, "Analyse de l'entretien…")
        user = (
            contexte + f"TRANSCRIPTION DE L'ENTRETIEN :\n{morceaux[0]}\n\n" + CONSIGNE_ANALYSE
            + "\nRédige enfin D : un bilan réflexif de 8 à 12 lignes, rédigé, structuré (séance observée, "
            "points forts et réussites de la stagiaire, son analyse réflexive, axes de progrès, conseils qui "
            "s'appuient sur ces points forts), uniquement à partir des "
            "éléments ci-dessus.\n\nRéponds en JSON."
        )
        res = llm.chat_json(cfg, SYSTEME, user, _schema_analyse(True), attendu=6500,
                            progress=lambda f, m: progress(0.1 + 0.85 * f, m))
    else:
        partiels = []
        for i, m in enumerate(morceaux):
            progress(0.05 + 0.75 * i / len(morceaux), f"Analyse de l'entretien : partie {i + 1}/{len(morceaux)}")
            user = (
                contexte + f"TRANSCRIPTION (partie {i + 1} sur {len(morceaux)}) :\n{m}\n\n" + CONSIGNE_ANALYSE
                + "\nRéponds en JSON."
            )
            partiels.append(llm.chat_json(
                cfg, SYSTEME, user, _schema_analyse(False), attendu=4500,
                progress=lambda f, m, i=i: progress(0.05 + 0.75 * (i + f) / len(morceaux),
                                                    f"Partie {i + 1}/{len(morceaux)} — {m}")))
        progress(0.85, "Fusion et bilan…")
        res = _fusionner(cfg, partiels, grille, notes, progress)

    return _nettoyer_analyse(res, sources=trans + "\n" + notes)


SCHEMA_FUSION = {"type": "object", "properties": {"D": {"type": "string"}, "doublons": {"type": "array", "items": {"type": "string"}}}, "required": ["D", "doublons"]}


def _fusionner(cfg, partiels, grille, notes, progress=lambda p, m="": None):
    res = {g: {k: [] for k in keys} for g, keys in CLES.items()}
    for p in partiels:
        for g, keys in CLES.items():
            for k in keys:
                res[g][k].extend((p.get(g) or {}).get(k) or [])
    # Dédoublonnage simple (textes très proches)
    for g, keys in CLES.items():
        for k in keys:
            uniques = []
            for it in res[g][k]:
                if not any(difflib.SequenceMatcher(None, _norm(it.get("texte", "")), _norm(u.get("texte", ""))).ratio() > 0.85 for u in uniques):
                    uniques.append(it)
            res[g][k] = uniques
    resume = "\n".join(
        f"{TITRES[g]} / {TITRES[k]} : " + " ; ".join(i.get("texte", "") for i in res[g][k])
        for g, keys in CLES.items() for k in keys if res[g][k]
    )
    user = (
        f"GRILLE :\n{grille}\n\n" + (f"NOTES DE LA FORMATRICE :\n{notes}\n\n" if notes else "")
        + f"ÉLÉMENTS RELEVÉS DANS L'ENTRETIEN :\n{resume}\n\n"
        "Rédige D : un bilan réflexif de 8 à 12 lignes, rédigé, structuré (séance observée, analyse de la "
        "points forts et réussites de la stagiaire, son analyse réflexive, axes de progrès, conseils qui s'appuient "
        "sur ces points forts), uniquement à partir de ces éléments. "
        "Laisse « doublons » vide.\n\nRéponds en JSON."
    )
    out = llm.chat_json(cfg, SYSTEME, user, SCHEMA_FUSION, attendu=1500,
                        progress=lambda f, m: progress(0.85 + 0.13 * f, "Bilan réflexif — " + m))
    res["D"] = out.get("D", "")
    return res


def _nettoyer_analyse(res: dict, sources: str) -> dict:
    propre = {}
    for g, keys in CLES.items():
        propre[g] = {}
        for k in keys:
            items = []
            for it in (res.get(g) or {}).get(k) or []:
                if isinstance(it, str):
                    it = {"texte": it, "extrait": ""}
                texte = str(it.get("texte", "")).strip()
                if not texte:
                    continue
                extrait = str(it.get("extrait", "")).strip()
                items.append({"texte": texte, "extrait": extrait, "verifie": extrait_present(extrait, sources)})
            propre[g][k] = items
    propre["D"] = str(res.get("D", "")).strip()
    return propre


# ------------------------------------------------------------------ 5. bulletin

_PHASE = {
    "type": "object",
    "properties": {
        "temps": {"type": "string"}, "deroulement": {"type": "string"}, "remarque": {"type": "string"},
        "dispositif": {"type": "string"}, "organisation": {"type": "string"},
    },
    "required": ["temps", "deroulement", "remarque", "dispositif", "organisation"],
}

SCHEMA_SEANCES = {
    "type": "object",
    "properties": {
        "seances": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"domaine": {"type": "string"}, "objectifs": {"type": "string"},
                               "description": {"type": "string"}},
                "required": ["domaine", "objectifs", "description"],
            },
        }
    },
    "required": ["seances"],
}

SCHEMA_DEROULEMENT = {
    "type": "object",
    "properties": {"deroulement": {"type": "array", "items": _PHASE}},
    "required": ["deroulement"],
}

SCHEMA_BULLETIN = {
    "type": "object",
    "properties": {
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "focale": {"type": "string", "enum": ["pilotage", "etayage", "tissage", "atmosphere", "objets_savoir"]},
                    "analyse": {"type": "string"}, "ressources": {"type": "string"},
                },
                "required": ["focale", "analyse", "ressources"],
            },
        },
        "positifs": {"type": "array", "items": {"type": "string"}},
        "ameliorer": {"type": "array", "items": {"type": "string"}},
        "langue_observations": {"type": "string"},
        "references": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["points", "positifs", "ameliorer", "langue_observations", "references"],
}


def analyse_en_texte(analyse: dict) -> str:
    lines = []
    for g, keys in CLES.items():
        for k in keys:
            for it in analyse.get(g, {}).get(k, []):
                lines.append(f"[{g} – {TITRES[k]}] {it.get('texte', '')}")
    if analyse.get("D"):
        lines.append(f"[Bilan] {analyse['D']}")
    return "\n".join(lines)


def legendes_photos(visit: dict) -> str:
    """Les légendes des photos de la séance, écrites par la formatrice, sont des observations.

    Les photos sont numérotées dans l'ordre choisi par la formatrice : l'IA peut y renvoyer
    (« voir photo 2 ») et les documents exportés utilisent la même numérotation.
    """
    leg = [
        f"Photo {n} : {p.get('legende', '').strip()}"
        for n, p in enumerate(visit.get("photos", []), 1) if p.get("legende", "").strip()
    ]
    return ("Photos prises pendant la séance — " + " ; ".join(leg) + ".") if leg else ""


# ------------------------------------------------------------------ horaires du déroulement

_HEURE = re.compile(r"(\d{1,2})\s*[hH:]\s*(\d{2})?")
_DUREE = re.compile(r"(\d{1,3})\s*(?:min|mn|minutes?|')", re.IGNORECASE)


def _fmt(minutes: int) -> str:
    h, m = divmod(minutes % (24 * 60), 60)
    return f"{h}h{m:02d}"


def horodater(deroulement: list[dict], horaire: str) -> list[dict]:
    """Ajoute l'heure de début à chaque phase, au format de la formatrice : « 14h06 : Rappel (5 min) ».

    Calcul uniquement si l'heure de début de séance est connue (champ Horaire) et que
    chaque phase sans heure indique sa durée. Une phase qui a déjà une heure est gardée
    telle quelle et sert de point de repère pour la suite.
    """
    m = _HEURE.search(horaire or "")
    if not m or not deroulement:
        return deroulement
    courant = int(m.group(1)) * 60 + int(m.group(2) or 0)
    out = []
    for r in deroulement:
        r = dict(r)
        temps = r.get("temps", "")
        heures = _HEURE.findall(temps)
        duree = _DUREE.search(temps)
        if heures:
            # Heure déjà notée (par exemple dans les notes de la formatrice) : on se recale dessus.
            dernier = heures[-1]
            courant = int(dernier[0]) * 60 + int(dernier[1] or 0)
            if len(heures) == 1:
                # Une seule heure : c'est le début de la phase ; sans durée, la fin reste inconnue.
                courant = courant + int(duree.group(1)) if duree else None
        elif courant is None:
            pass  # heure de début inconnue : on ne devine pas
        elif duree:
            d = int(duree.group(1))
            reste = _DUREE.sub("", temps).strip(" -–—,:()")
            r["temps"] = f"{_fmt(courant)} : {reste} ({d} min)" if reste else f"{_fmt(courant)} ({d} min)"
            courant += d
        else:
            return deroulement  # une durée inconnue : on ne devine pas la suite
        out.append(r)
    return out


def verifier_references(refs: list[str], bibliotheque: str, sources: str) -> list[dict]:
    """Une référence doit venir de l'entretien / des notes, ou de la bibliothèque de la formatrice."""
    biblio = [ln.strip(" -•\t") for ln in (bibliotheque or "").splitlines() if ln.strip()]
    out = []
    for r in refs:
        r = str(r).strip(" -•")
        if not r:
            continue
        dans_biblio = any(
            difflib.SequenceMatcher(None, _norm(r), _norm(b)).ratio() > 0.6 or _norm(b) in _norm(r) or _norm(r) in _norm(b)
            for b in biblio
        )
        mots = [w for w in _norm(r).split() if len(w) > 3][:6]
        dans_sources = bool(mots) and sum(w in _norm(sources) for w in mots) >= max(1, len(mots) * 2 // 3)
        out.append({
            "texte": r,
            "source": "bibliotheque" if dans_biblio else "entretien" if dans_sources else "",
            "verifie": dans_biblio or dans_sources,
        })
    return out


def _seances_resume(seances: list[dict]) -> str:
    return "\n".join(
        f"Séance {n} – {x.get('domaine', '')} : {x.get('objectifs', '')} — {x.get('description', '')[:600]}"
        for n, x in enumerate(seances, 1)
    )


CONSIGNE_DEROULEMENT = (
    "Construis le DÉROULEMENT OBSERVÉ de cette séance, phase par phase, dans l'ordre chronologique.\n"
    "C'est un relevé d'observation FIDÈLE, comme celui que la formatrice tape en direct : ne résume pas.\n"
    "- temps : l'heure de début de la phase si elle est connue, son nom et sa durée, au format "
    "« 14h06 : Rappel (5 min) » ; sans heure connue : « Rappel (5 min) ».\n"
    "- deroulement : ce qui se passe réellement, en reprenant MOT POUR MOT les paroles importantes, entre "
    "guillemets : « E : » pour l'enseignante, « Un élève : » ou « Les élèves : » pour les élèves. Consignes "
    "données, questions posées, réponses et erreurs des élèves, aides apportées, ce qui est écrit au tableau. "
    "Plusieurs lignes par phase si nécessaire. Aucun jugement ici.\n"
    "- remarque : l'analyse et le conseil de la formatrice sur cette phase s'ils figurent dans ses notes ou dans "
    "l'entretien (en commençant par ce qui a bien fonctionné), sinon chaîne vide.\n"
    "- dispositif (collectif, binômes, individuel…) ; organisation matérielle (supports, matériel).\n"
    "N'invente aucune parole ni aucun événement : n'utilise que les notes et la transcription fournies.\n"
)


def preremplir_bulletin(cfg: dict, visit: dict, grille: str, progress=lambda p, m="": None,
                        bibliotheque: str = "") -> dict:
    """Préremplit le bulletin en trois temps : séances, déroulement fidèle de chaque séance, points discutés."""
    from .referentiel import CADRE_ANALYSE, FOCALES, bibliotheque_complete

    adm = visit.get("admin", {})
    docs = resume_documents(visit.get("documents", []))
    photos = legendes_photos(visit)
    notes = ((visit.get("notes_formatrice") or "") + "\n" + photos).strip()
    ana = analyse_en_texte(visit.get("analyse", {}))
    trans = transcript_text(segments_entretien(visit))
    num_enreg = numeros_seances_enregistrees(visit)
    trans_seances = {n: transcript_text(segments_seance(visit, n), seance=True) for n in num_enreg}
    if not (docs or notes or ana or trans or any(trans_seances.values())):
        raise llm.IAIndisponible("Il n'y a encore aucune information pour préremplir le bulletin.")
    biblio = bibliotheque_complete(bibliotheque)
    entete = (
        f"CLASSE : {adm.get('classe', '')} – effectif {adm.get('effectif', '')} – horaire de la visite : "
        f"{adm.get('horaire', '') or 'non renseigné'}\n\n"
        + (f"DOCUMENTS DE LA STAGIAIRE :\n{docs}\n\n" if docs else "")
        + (f"NOTES D'OBSERVATION DE LA FORMATRICE (dont les légendes des photos) :\n{notes}\n\n" if notes else "")
    )

    # --- 1. Les séances observées : domaine, objectif(s), description
    progress(0.02, "Repérage des séances observées…")
    apercus = "".join(
        f"DÉBUT DE L'ENREGISTREMENT DE LA SÉANCE {n} :\n{t[:2500]}\n\n" for n, t in trans_seances.items() if t
    )
    user = (
        entete + apercus
        + "Combien de séances ont été observées pendant cette visite (souvent une seule, parfois deux dans des "
        "disciplines différentes, par exemple une fiche de séance par discipline ou « 2ème séance » dans les notes) ? "
        + (f"Des enregistrements existent pour les séances n° {', '.join(map(str, num_enreg))}. " if num_enreg else "")
        + "Pour CHAQUE séance, dans l'ordre :\n"
        "- domaine : le domaine ou la discipline avec l'intitulé OFFICIEL des programmes du cycle de la classe "
        "(par exemple au cycle 2 : « Questionner le monde – le vivant », « Français – lecture », "
        "« Mathématiques – résolution de problèmes », « Enseignements artistiques – arts plastiques » ; jamais "
        "« SVT » ni un intitulé du collège à l'école primaire) ;\n"
        "- objectifs : le ou les objectifs de la séance, repris de la fiche de séance (1 à 2 lignes) ;\n"
        "- description : description DÉTAILLÉE mais synthétique de CETTE séance (8 à 12 lignes) : place dans la "
        "séquence, enchaînement des phases, ce que font concrètement les élèves, organisation, différenciation, rôle "
        "de l'enseignante ; renvoie aux photos pertinentes « (photo 2) ». Ne recopie jamais la description d'une "
        "autre séance.\n\nRéponds en JSON."
    )
    res = llm.chat_json(cfg, SYSTEME, user, SCHEMA_SEANCES, attendu=2500,
                        progress=lambda f, m: progress(0.02 + 0.18 * f, "Séances observées — " + m))
    seances = [
        {"domaine": str(x.get("domaine", "")).strip(), "objectifs": str(x.get("objectifs", "")).strip(),
         "description": str(x.get("description", "")).strip(), "deroulement": []}
        for x in (res.get("seances") or []) if isinstance(x, dict)
    ]
    while len(seances) < max(num_enreg or [1]):
        seances.append({"domaine": "", "objectifs": "", "description": "", "deroulement": []})
    seances = seances[:4]

    # --- 2. Déroulement fidèle de chaque séance (notes + enregistrement de la séance, par morceaux)
    budget = max(6000, _budget_chars(cfg, 6500) - len(entete))
    n_s = len(seances)
    for idx, se in enumerate(seances, 1):
        t = trans_seances.get(idx, "")
        morceaux = _chunks_by_chars(t.split("\n"), budget) if t else [""]
        lignes = []
        for k, m in enumerate(morceaux):
            base = 0.2 + 0.45 * ((idx - 1) + k / len(morceaux)) / n_s
            user = (
                entete
                + f"SÉANCE CONCERNÉE : séance {idx} sur {n_s} – {se['domaine']} – {se['objectifs']}\n"
                "(Si les notes ou documents concernent plusieurs séances, n'utilise que ce qui concerne celle-ci.)\n\n"
                + (f"ENREGISTREMENT DE LA SÉANCE (partie {k + 1} sur {len(morceaux)}) — « E » = l'enseignante :\n{m}\n\n" if m else "")
                + (f"Phases déjà relevées dans les parties précédentes : {', '.join(r['temps'] for r in lignes)}\n"
                   "Continue à partir de là, sans les répéter.\n\n" if lignes else "")
                + CONSIGNE_DEROULEMENT + "\nRéponds en JSON."
            )
            r = llm.chat_json(cfg, SYSTEME, user, SCHEMA_DEROULEMENT, attendu=3500,
                              progress=lambda f, mm, base=base: progress(
                                  base + 0.45 / n_s / len(morceaux) * f, f"Déroulement de la séance {idx} — {mm}"))
            lignes += [
                {key: str(x.get(key, "")).strip() for key in ("temps", "deroulement", "remarque", "dispositif", "organisation")}
                for x in (r.get("deroulement") or []) if isinstance(x, dict)
            ]
        se["deroulement"] = horodater(lignes, adm.get("horaire", "") if idx == 1 else "")

    # --- 3. Points discutés, avis sur l'entretien, langue, références
    reste = (_budget_chars(cfg) - len(entete) - len(ana) - len(grille) - len(biblio) - len(CADRE_ANALYSE) - 5000)
    extrait_trans = trans[: max(0, reste)] if reste > 2000 else ""
    user = (
        f"GRILLE ET ATTENTES :\n{grille}\n\n{CADRE_ANALYSE}\n" + entete
        + f"SÉANCES OBSERVÉES :\n{_seances_resume(seances)}\n\n"
        + (f"ANALYSE DE L'ENTRETIEN (validée par la formatrice) :\n{ana}\n\n" if ana else "")
        + (f"TRANSCRIPTION DE L'ENTRETIEN (extrait) :\n{extrait_trans}\n\n" if extrait_trans else "")
        + f"BIBLIOTHÈQUE DE RÉFÉRENCES AUTORISÉES :\n{biblio}\n\n"
        + "Prépare les rubriques suivantes du bulletin officiel :\n"
        "- points : les 3 préoccupations (focales de Bucheton) LES PLUS DISCUTÉES pendant l'entretien, toutes "
        "différentes, dans l'ordre d'importance. Pour chacune :\n"
        "  · focale : pilotage, etayage, tissage, atmosphere ou objets_savoir ;\n"
        "  · analyse : plusieurs sous-parties, UNE PAR LIGNE, chacune au format « Intitulé : texte ». Commence par "
        "ce qui fonctionne (par exemple « La progression est cohérente… » ou « Points d'appui : … »), puis les "
        "sous-parties utiles parmi : Objectif, Transitions, Gestion du temps et du matériel, Consignes, Variantes de "
        "la tâche, Différenciation, Évaluation, Rappel des termes, Support, Vidéo, Posture… Chaque sous-partie : "
        "constat précis (quand, quels élèves), analyse avec le vocabulaire professionnel (gestes professionnels, "
        "postures d'étayage et des élèves, tâche prescrite / activité réelle), puis conseil concret de la formatrice "
        "qui s'appuie sur les réussites. N'écris une sous-partie que si tu as quelque chose à y mettre ;\n"
        "  · ressources : 1 à 3 supports et ressources que la formatrice conseille sur ce point : ceux cités pendant "
        "l'entretien et, s'ils correspondent au sujet, des références de la BIBLIOTHÈQUE AUTORISÉE recopiées "
        "exactement, séparées par « ; ». Jamais « transcription de l'entretien ». Aucune autre référence.\n"
        "- positifs / ameliorer : avis sur la façon dont la stagiaire a conduit l'ENTRETIEN (réflexivité, écoute, "
        "argumentation, prise de recul), en phrases courtes. Listes vides si rien ne le permet.\n"
        "- langue_observations : observation sur la maîtrise de la langue UNIQUEMENT si les sources en parlent, "
        "sinon chaîne vide. Relis l'orthographe.\n"
        "- references : la liste récapitulative des références à communiquer à la stagiaire (celles citées pendant "
        "l'entretien et celles retenues dans les points), recopiées exactement.\n"
        "Valorise les points forts de la stagiaire relevés dans les sources, sans en inventer. N'écris jamais de "
        "note, de positionnement (TI, I, S, TS) ni d'appréciation chiffrée. N'invente aucune observation.\n\n"
        "Réponds en JSON."
    )
    res = llm.chat_json(cfg, SYSTEME, user, SCHEMA_BULLETIN, attendu=5000,
                        progress=lambda f, m: progress(0.66 + 0.33 * f, "Points discutés — " + m))
    sources = trans + "\n" + notes + "\n" + docs + "\n" + "\n".join(trans_seances.values())
    points, vues = [], set()
    for p in (res.get("points") or []):
        if not isinstance(p, dict) or len(points) == 3:
            continue
        focale = p.get("focale") if p.get("focale") in FOCALES else ""
        if focale in vues:
            continue
        vues.add(focale)
        ressources = str(p.get("ressources", "")).strip()
        verif = verifier_references([r for r in re.split(r"\s*;\s*|\n", ressources) if r.strip()], biblio, sources)
        points.append({
            "titre": f"{len(points) + 1}. {FOCALES[focale]}" if focale else "",
            "focale": focale,
            "analyse": str(p.get("analyse", "")).strip(),
            "ressources": ressources,
            "ressources_a_verifier": [r["texte"] for r in verif if not r["verifie"]],
        })
    while len(points) < 3:
        points.append({"titre": "", "focale": "", "analyse": "", "ressources": "", "ressources_a_verifier": []})
    return {
        "seances": seances,
        "points": points,
        "positifs": [str(x).strip() for x in res.get("positifs") or [] if str(x).strip()],
        "ameliorer": [str(x).strip() for x in res.get("ameliorer") or [] if str(x).strip()],
        "langue_observations": str(res.get("langue_observations", "")).strip(),
        "references": verifier_references(res.get("references") or [], biblio, sources),
    }
