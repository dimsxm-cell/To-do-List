"""Visite fictive (anonymisée) utilisée par les tests."""
from app.defaults import empty_visit


def visite_exemple():
    v = empty_visit("test-visite")
    v["admin"].update({
        "numero": "2", "stagiaire_nom": "DUPONT Camille", "statut": "mi_temps_m2",
        "date": "2026-11-20", "horaire": "8h30 - 10h00", "classe": "CE1", "effectif": "24",
        "ecole": "École primaire Les Alizés", "circonscription": "Baie-Mahault", "commune": "Baie-Mahault",
        "conditions": "1 AESH, REP", "lieu": "Baie-Mahault",
        "formateurs": [{"nom": "MARTIN Sophie", "qualite": "PEMF"}],
    })
    v["outils"].update({"cahier_journal": True, "fiches_seances": True, "emploi_du_temps": True})
    b = v["bulletin"]
    b["seances"] = [
        {"domaine": "Mathématiques – résolution de problèmes",
         "objectifs": "Représenter un problème par un schéma.",
         "description": "Séance 3 d'une séquence sur les problèmes de transformation.",
         "deroulement": [
             {"temps": "10 min\nRituel", "deroulement": "Calcul mental", "dispositif": "Collectif", "organisation": "Ardoises"},
             {"temps": "20 min\nRecherche", "deroulement": "Résolution en binômes", "dispositif": "Binômes", "organisation": "Fiche problème"},
         ]},
        {"domaine": "Enseignements artistiques – arts plastiques",
         "objectifs": "Composer avec des papiers déchirés.",
         "description": "Observation d'une œuvre de Hans Arp, puis déchirure de papiers.",
         "deroulement": [
             {"temps": "14h44 : Observation (8 min)", "deroulement": "E : « Qu'est-ce que vous voyez ? »", "dispositif": "Collectif", "organisation": "Tablette"},
         ]},
    ]
    b["points"] = [
        {"titre": "La consigne", "analyse": "La consigne a été reformulée par deux élèves.", "ressources": "Éduscol : résoudre des problèmes"},
        {"titre": "La mise en commun", "analyse": "Mise en commun écourtée.", "ressources": ""},
        {"titre": "", "analyse": "", "ressources": ""},
    ]
    b["positifs"] = ["Analyse lucide de la séance", "Écoute des conseils", "Propositions concrètes"]
    b["ameliorer"] = ["Justifier ses choix didactiques"]
    b["langue"] = {"orale": "S", "ecrite": "TS", "observations": "Expression claire et précise."}
    b["positionnement"] = "S"
    b["note"] = "13"
    return v
