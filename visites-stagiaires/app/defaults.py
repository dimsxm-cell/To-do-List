"""Valeurs par défaut : paramètres permanents, grille d'analyse, structure d'une visite."""

from __future__ import annotations

from datetime import datetime

GRILLE_PAR_DEFAUT = """\
GRILLE D'ANALYSE DE L'ENTRETIEN (permanente)

A. Points relevés par la stagiaire
- Ses propres constats sur la séance.
- Les réussites qu'elle identifie.
- Les difficultés qu'elle a rencontrées.
- Son analyse de sa pratique.
- Ses questionnements.
- Ses propositions d'amélioration.

B. Points relevés par la formatrice
- Les points forts observés.
- Les compétences maîtrisées.
- Les difficultés constatées.
- Les axes d'amélioration.
- Les éléments nécessitant un accompagnement.

C. Conseils prodigués par la formatrice
- Conseils pédagogiques.
- Préconisations méthodologiques.
- Pistes de remédiation.
- Supports et ressources conseillés.
- Perspectives de progression.

D. Bilan réflexif
- Synthèse professionnelle, structurée et rédigée.

ATTENTES DE RÉDACTION
- Style professionnel, précis, synthétique, sans répétition.
- Vouvoiement ou troisième personne (« la stagiaire », « l'enseignante »), jamais de tutoiement.
- S'appuyer sur le référentiel des compétences professionnels des métiers du professorat (2013) quand c'est pertinent.
- Ne jamais inventer une observation, une compétence, un conseil, une appréciation, une note ou un positionnement.
"""

VOCABULAIRE_PAR_DEFAUT = (
    "Entretien de visite formative. Fonctionnaire stagiaire, formatrice, PEMF, "
    "INSPE, séquence, séance, cahier journal, registre d'appel, programmation, "
    "progression, emploi du temps, différenciation, étayage, consigne, "
    "institutionnalisation, mise en commun, trace écrite, AESH, REP, REP+, "
    "cycle 1, cycle 2, cycle 3, CP, CE1, CE2, CM1, CM2, maternelle, Éduscol."
)

DEFAULT_SETTINGS = {
    "formatrice": {"nom": "", "qualite": "PEMF", "lieu": ""},
    "grille": GRILLE_PAR_DEFAUT,
    "vocabulaire": VOCABULAIRE_PAR_DEFAUT,
    # Bibliothèque de références de la formatrice (une par ligne) : la seule source, avec l'entretien,
    # où l'IA peut puiser les références à communiquer à la stagiaire.
    "references": "",
    "ia": {
        "url": "http://127.0.0.1:11434",
        "modele": "mistral-nemo",
        "contexte": 16384,
        "temperature": 0.2,
    },
    "transcription": {
        # "auto" : MLX sur Mac Apple Silicon, sinon faster-whisper.
        "moteur": "auto",
        "modele": "large-v3-turbo",
        "langue": "fr",
    },
}

ADMIN_VIDE = {
    "numero": "",
    "stagiaire_nom": "",
    "statut": "",  # temps_plein | mi_temps_diu | mi_temps_m2
    "date": "",
    "horaire": "",
    "classe": "",
    "effectif": "",
    "ecole": "",
    "circonscription": "",
    "commune": "",
    "conditions": "",
    "formateurs": [],  # [{"nom": "", "qualite": ""}]
    "lieu": "",
}

OUTILS = [
    ("cahier_journal", "Cahier journal"),
    ("registre_appel", "Registre d'appel"),
    ("fiches_sequences", "Fiches de séquences"),
    ("fiches_seances", "Fiches de séances"),
    ("progressions", "Progressions (programmation)"),
    ("emploi_du_temps", "Emploi du temps"),
    ("autres", "Autres (projet…)"),
    ("cahiers_eleves", "Cahiers/classeurs des élèves visés par l'enseignant"),
]

BULLETIN_VIDE = {
    "enseignements": "",
    "description": "",
    "deroulement": [],  # (avant la v1.8) remplacé par « seances »
    # Une ou plusieurs séances observées : [{"domaine", "objectifs", "description",
    #   "deroulement": [{"temps", "deroulement", "remarque", "dispositif", "organisation"}]}]
    "seances": [],
    "points": [
        {"titre": "", "analyse": "", "ressources": ""},
        {"titre": "", "analyse": "", "ressources": ""},
        {"titre": "", "analyse": "", "ressources": ""},
    ],
    "positifs": [],
    "ameliorer": [],
    "langue": {"orale": "", "ecrite": "", "observations": ""},
    "positionnement": "",  # TI | I | S | TS : choix de la formatrice uniquement
    "note": "",  # sur 20 : choix de la formatrice uniquement
    "date_signature": "",
    "references": [],  # [{"texte", "source": "entretien"|"bibliotheque"|"", "verifie"}] à communiquer à la stagiaire
    "valide": False,
}

ANALYSE_VIDE = {
    "A": {
        "constats": [], "reussites": [], "difficultes": [],
        "analyse_pratique": [], "questionnements": [], "propositions": [],
    },
    "B": {
        "points_forts": [], "competences_maitrisees": [], "difficultes": [],
        "axes_amelioration": [], "accompagnement": [],
    },
    "C": {
        "conseils_pedagogiques": [], "preconisations": [], "remediations": [],
        "ressources": [], "perspectives": [],
    },
    "D": "",
    "genere": "",
}


def empty_visit(vid: str) -> dict:
    import copy

    now = datetime.now().isoformat(timespec="seconds")
    return {
        "id": vid,
        "cree": now,
        "modifie": now,
        "etape": "infos",
        "admin": copy.deepcopy(ADMIN_VIDE),
        "outils": {k: False for k, _ in OUTILS},
        "notes_formatrice": "",
        "documents": [],
        "photos": [],  # [{"id", "fichier", "legende", "largeur", "hauteur", "cree"}]
        "audios": [],
        "transcription": {"segments": [], "progression": {}, "moteur": ""},
        "analyse": copy.deepcopy(ANALYSE_VIDE),
        "bulletin": copy.deepcopy(BULLETIN_VIDE),
    }
