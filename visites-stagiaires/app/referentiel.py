"""Cadre d'analyse professionnel et bibliothèque intégrée de références.

Les références ci-dessous sont des textes réels et connus (institution, didacticiens).
L'IA ne peut conseiller que des références de cette liste, de la bibliothèque personnelle
de la formatrice, ou citées pendant l'entretien : toute autre est signalée « à vérifier ».
"""

CADRE_ANALYSE = """\
CADRE D'ANALYSE PROFESSIONNEL (à mobiliser pour analyser la séance et l'entretien)

1. Le multi-agenda de l'enseignant (D. Bucheton et Y. Soulé, 2009) : cinq préoccupations enchâssées.
- Objets de savoir (au cœur) : les savoirs et techniques visés, leur clarté, leur exactitude, leur institutionnalisation.
- Pilotage : gestion du temps, de l'espace, des phases et des contraintes de la séance ; avancée de la tâche.
- Atmosphère : climat cognitif et relationnel, espace de parole, sécurité et engagement des élèves.
- Tissage : donner du sens, relier avant / après la séance, dedans / dehors l'école, une tâche à une autre.
- Étayage : aider à faire, à comprendre, à dire. Postures d'étayage : accompagnement, contrôle,
  lâcher-prise, enseignement (conceptualisation), magistère, sur-étayage (« faire à la place »).
- Postures d'élèves : première, scolaire, ludique-créative, réflexive, dogmatique, de refus.

2. L'activité enseignante (R. Goigoux, 2007) : elle est orientée par des buts et réalise des compromis
entre les contraintes de l'institution (programmes, prescriptions), des élèves (hétérogénéité, besoins)
et de l'enseignant lui-même (expérience, ressources). Distinguer la tâche prescrite, la tâche attendue
et l'activité réellement mise en œuvre par les élèves.

3. Le référentiel des compétences professionnelles des métiers du professorat (2013) pour situer les
compétences observées (P1 à P5, CC1 à CC14).

Valoriser les points forts : toujours partir de ce qui fonctionne. Les réussites et compétences
de la stagiaire relevées par la formatrice sont des points d'appui sur lesquels construire les conseils.

Pour chaque point discuté : 1) le point d'appui : ce que la stagiaire réussit sur ce sujet (s'il a été relevé) ;
2) un constat précis et daté (ce qui a été observé, par qui, à quel moment) ;
3) une analyse qui nomme la ou les préoccupations concernées et utilise le vocabulaire ci-dessus ;
4) un conseil opérationnel, réalisable dès la prochaine séance, qui s'appuie sur ces réussites.
"""

REFERENCES_INTEGREES = [
    # Institution
    "Référentiel des compétences professionnelles des métiers du professorat et de l'éducation, "
    "arrêté du 1er juillet 2013 (BO n° 30 du 25 juillet 2013)",
    "Programmes en vigueur du cycle concerné (Bulletin officiel de l'Éducation nationale)",
    "Éduscol – Ressources d'accompagnement des programmes du cycle concerné",
    "Guide « Pour enseigner la lecture et l'écriture au CP », ministère de l'Éducation nationale, 2018 (Éduscol)",
    "Guide « Pour enseigner la lecture et l'écriture au CE1 », ministère de l'Éducation nationale, 2019 (Éduscol)",
    "Guide « Pour enseigner les nombres, le calcul et la résolution de problèmes au CP », "
    "ministère de l'Éducation nationale, 2021 (Éduscol)",
    "Guide « La résolution de problèmes mathématiques au cours moyen », ministère de l'Éducation nationale, 2021 (Éduscol)",
    "Note de service « La résolution de problèmes à l'école élémentaire », BO spécial n° 3 du 26 avril 2018",
    "Cnesco, conférence de consensus « Différenciation pédagogique », 2017",
    "Cnesco, conférence de consensus « Lire, comprendre, apprendre », 2016",
    "Fondation La main à la pâte – ressources pour enseigner les sciences à l'école",
    # Didacticiens et chercheurs
    "D. Bucheton et Y. Soulé, « Les gestes professionnels et le jeu des postures de l'enseignant dans la classe : "
    "un multi-agenda de préoccupations enchâssées », Éducation et didactique, vol. 3, n° 3, 2009",
    "D. Bucheton (dir.), Refonder l'enseignement de l'écriture, Retz, 2014",
    "R. Goigoux, « Un modèle d'analyse de l'activité des enseignants », Éducation et didactique, vol. 1, n° 3, 2007",
    "R. Goigoux et S. Cèbe, Apprendre à lire à l'école, Retz, 2006",
    "J.-P. Astolfi, L'erreur, un outil pour enseigner, ESF, 1997",
    "J. S. Bruner, Le développement de l'enfant : savoir faire, savoir dire, PUF, 1983 (notion d'étayage)",
    "L. Vygotski, Pensée et langage (notion de zone proximale de développement)",
    "B.-M. Barth, L'apprentissage de l'abstraction, Retz, 1987",
    "P. Meirieu, Apprendre… oui, mais comment, ESF, 1987",
    "R. Brissiaud, Comment les enfants apprennent à calculer, Retz",
    "S. Connac, La coopération entre élèves, Réseau Canopé, 2017",
    "S. Dehaene, Apprendre ! Les talents du cerveau, le défi des machines, Odile Jacob, 2018",
]


def bibliotheque_complete(perso: str) -> str:
    """Bibliothèque intégrée + bibliothèque personnelle de la formatrice (une référence par ligne)."""
    lignes = list(REFERENCES_INTEGREES)
    lignes += [ln.strip(" -•\t") for ln in (perso or "").splitlines() if ln.strip()]
    return "\n".join(lignes)
