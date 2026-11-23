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


def transcript_text(segments: list[dict], include_hors_sujet: bool = False) -> str:
    return "\n".join(
        f"[{LOC.get(t['locuteur'], t['locuteur'])} {hms(t['debut'])}] {t['texte']}"
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


def attribuer_interlocuteurs(cfg: dict, segments: list[dict], progress=lambda p, m="": None) -> list[dict]:
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
        user = (
            "Voici un extrait de la transcription automatique d'un entretien de visite formative "
            "entre une FORMATRICE (F) et une enseignante STAGIAIRE (S), après l'observation d'une séance en classe.\n"
            "Indices : la formatrice pose les questions, reformule, apprécie, conseille, cite des ressources. "
            "La stagiaire décrit sa classe, ses choix, ses difficultés, répond aux questions.\n"
            "Pour CHAQUE ligne numérotée, indique qui parle (F ou S) et si la ligne est HORS SUJET "
            "(conversation parasite sans rapport avec l'entretien professionnel : téléphone, bavardage, "
            "interruption par un tiers, logistique sans intérêt).\n"
            + (f"\nLignes précédentes (pour le contexte) :\n{avant}\n" if avant else "")
            + f"\nLignes à traiter :\n{lignes}\n\nRéponds en JSON."
        )
        res = llm.chat_json(cfg, SYSTEME, user, SCHEMA_LOC)
        par_n = {int(x.get("n", 0)): x for x in res.get("lignes", []) if isinstance(x, dict)}
        for i, s in enumerate(lot):
            if s.get("verrouille"):
                continue
            x = par_n.get(i + 1)
            if x:
                s["locuteur"] = x.get("locuteur") if x.get("locuteur") in ("F", "S") else "?"
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
        res = llm.chat_json(cfg, SYSTEME, user, SCHEMA_CORR)
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


def analyser_document(cfg: dict, texte: str, nom: str, type_devine: str) -> dict:
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
    return llm.chat_json(cfg, SYSTEME, user, SCHEMA_DOC)


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
    "« extrait » = citation EXACTE, mot pour mot, de 5 à 25 mots, copiée de la transcription ou des notes.\n"
    "- Les notes de la formatrice sont une source valable pour B et C.\n"
    "- N'ajoute aucun élément qui ne figure pas dans les sources. Une rubrique sans élément reste une liste vide.\n"
    "- Pas de doublon d'une rubrique à l'autre.\n"
)


def analyse_reflexive(cfg: dict, visit: dict, grille: str, progress=lambda p, m="": None) -> dict:
    segments = visit.get("transcription", {}).get("segments", [])
    trans = transcript_text(segments)
    notes = (visit.get("notes_formatrice") or "").strip()
    docs = resume_documents(visit.get("documents", []))
    if not trans and not notes:
        raise llm.IAIndisponible("Il n'y a ni transcription ni notes à analyser.")

    legendes = legendes_photos(visit)
    if legendes:
        notes = (notes + "\n" + legendes).strip()
    contexte = (
        f"GRILLE ET ATTENTES DE LA FORMATRICE :\n{grille}\n\n"
        + (f"DOCUMENTS DE LA STAGIAIRE (pour comprendre la séance, pas comme source de propos) :\n{docs[:6000]}\n\n" if docs else "")
        + (f"NOTES DE LA FORMATRICE (observation de la séance) :\n{notes}\n\n" if notes else "")
    )
    budget = max(6000, _budget_chars(cfg) - len(contexte))
    morceaux = _chunks_by_chars(trans.split("\n"), budget) if trans else [""]

    if len(morceaux) == 1:
        progress(0.1, "Analyse de l'entretien…")
        user = (
            contexte + f"TRANSCRIPTION DE L'ENTRETIEN :\n{morceaux[0]}\n\n" + CONSIGNE_ANALYSE
            + "\nRédige enfin D : un bilan réflexif de 10 à 15 lignes, rédigé, structuré (séance observée, "
            "analyse de la stagiaire, points d'appui, axes de progrès, conseils), uniquement à partir des "
            "éléments ci-dessus.\n\nRéponds en JSON."
        )
        res = llm.chat_json(cfg, SYSTEME, user, _schema_analyse(True))
    else:
        partiels = []
        for i, m in enumerate(morceaux):
            progress(0.05 + 0.75 * i / len(morceaux), f"Analyse de l'entretien : partie {i + 1}/{len(morceaux)}")
            user = (
                contexte + f"TRANSCRIPTION (partie {i + 1} sur {len(morceaux)}) :\n{m}\n\n" + CONSIGNE_ANALYSE
                + "\nRéponds en JSON."
            )
            partiels.append(llm.chat_json(cfg, SYSTEME, user, _schema_analyse(False)))
        progress(0.85, "Fusion et bilan…")
        res = _fusionner(cfg, partiels, grille, notes)

    return _nettoyer_analyse(res, sources=trans + "\n" + notes)


SCHEMA_FUSION = {"type": "object", "properties": {"D": {"type": "string"}, "doublons": {"type": "array", "items": {"type": "string"}}}, "required": ["D", "doublons"]}


def _fusionner(cfg, partiels, grille, notes):
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
        "Rédige D : un bilan réflexif de 10 à 15 lignes, rédigé, structuré (séance observée, analyse de la "
        "stagiaire, points d'appui, axes de progrès, conseils), uniquement à partir de ces éléments. "
        "Laisse « doublons » vide.\n\nRéponds en JSON."
    )
    out = llm.chat_json(cfg, SYSTEME, user, SCHEMA_FUSION)
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

SCHEMA_BULLETIN = {
    "type": "object",
    "properties": {
        "enseignements": {"type": "string"},
        "description": {"type": "string"},
        "deroulement": SCHEMA_DOC["properties"]["deroulement"],
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"titre": {"type": "string"}, "analyse": {"type": "string"}, "ressources": {"type": "string"}},
                "required": ["titre", "analyse", "ressources"],
            },
        },
        "positifs": {"type": "array", "items": {"type": "string"}},
        "ameliorer": {"type": "array", "items": {"type": "string"}},
        "langue_observations": {"type": "string"},
    },
    "required": ["enseignements", "description", "deroulement", "points", "positifs", "ameliorer", "langue_observations"],
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
    """Les légendes des photos de la séance, écrites par la formatrice, sont des observations."""
    leg = [p.get("legende", "").strip() for p in visit.get("photos", []) if p.get("legende", "").strip()]
    return ("Photos prises pendant la séance : " + " ; ".join(leg) + ".") if leg else ""


def preremplir_bulletin(cfg: dict, visit: dict, grille: str) -> dict:
    adm = visit.get("admin", {})
    docs = resume_documents(visit.get("documents", []))
    notes = ((visit.get("notes_formatrice") or "") + "\n" + legendes_photos(visit)).strip()
    ana = analyse_en_texte(visit.get("analyse", {}))
    trans = transcript_text(visit.get("transcription", {}).get("segments", []))
    if not (docs or notes or ana or trans):
        raise llm.IAIndisponible("Il n'y a encore aucune information pour préremplir le bulletin.")
    reste = _budget_chars(cfg) - len(docs) - len(notes) - len(ana) - len(grille) - 3000
    extrait_trans = trans[: max(0, reste)] if reste > 2000 else ""
    user = (
        f"GRILLE ET ATTENTES :\n{grille}\n\n"
        f"CLASSE : {adm.get('classe', '')} – effectif {adm.get('effectif', '')}\n\n"
        + (f"DOCUMENTS DE LA STAGIAIRE :\n{docs}\n\n" if docs else "")
        + (f"NOTES DE LA FORMATRICE :\n{notes}\n\n" if notes else "")
        + (f"ANALYSE DE L'ENTRETIEN (validée par la formatrice) :\n{ana}\n\n" if ana else "")
        + (f"TRANSCRIPTION (extrait) :\n{extrait_trans}\n\n" if extrait_trans else "")
        + "Prépare les rubriques du bulletin officiel de visite :\n"
        "- enseignements : domaine ou discipline + objectif(s) de la séance observée (2 lignes maximum).\n"
        "- description : description factuelle de la séance présentée (3 à 6 lignes).\n"
        "- deroulement : les phases de la séance (temps/phase, déroulement, dispositif, organisation matérielle), "
        "d'après la fiche de séance et les notes. Liste vide si aucune source ne les décrit.\n"
        "- points : les 3 sujets LES PLUS DISCUTÉS pendant l'entretien. Pour chacun : titre court ; analyse = "
        "éléments d'analyse ET conseils donnés (3 à 5 lignes) ; ressources = uniquement les supports ou ressources "
        "réellement cités dans l'entretien ou les notes (sinon chaîne vide). Moins de 3 points si l'entretien "
        "n'en aborde pas 3.\n"
        "- positifs / ameliorer : avis sur la façon dont la stagiaire a conduit l'ENTRETIEN (réflexivité, écoute, "
        "argumentation, prise de recul), en phrases courtes. Listes vides si rien ne le permet.\n"
        "- langue_observations : observation sur la maîtrise de la langue UNIQUEMENT si les sources en parlent, "
        "sinon chaîne vide.\n"
        "N'écris jamais de note, de positionnement (TI, I, S, TS) ni d'appréciation chiffrée : c'est la formatrice "
        "qui décide. N'invente rien.\n\nRéponds en JSON."
    )
    res = llm.chat_json(cfg, SYSTEME, user, SCHEMA_BULLETIN)
    points = [
        {"titre": str(p.get("titre", "")).strip(), "analyse": str(p.get("analyse", "")).strip(),
         "ressources": str(p.get("ressources", "")).strip()}
        for p in (res.get("points") or [])[:3] if isinstance(p, dict)
    ]
    while len(points) < 3:
        points.append({"titre": "", "analyse": "", "ressources": ""})
    return {
        "enseignements": str(res.get("enseignements", "")).strip(),
        "description": str(res.get("description", "")).strip(),
        "deroulement": [
            {k: str(r.get(k, "")).strip() for k in ("temps", "deroulement", "dispositif", "organisation")}
            for r in (res.get("deroulement") or []) if isinstance(r, dict)
        ],
        "points": points,
        "positifs": [str(x).strip() for x in res.get("positifs") or [] if str(x).strip()],
        "ameliorer": [str(x).strip() for x in res.get("ameliorer") or [] if str(x).strip()],
        "langue_observations": str(res.get("langue_observations", "")).strip(),
    }
