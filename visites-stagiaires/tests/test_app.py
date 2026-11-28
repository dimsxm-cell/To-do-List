"""Tests de bout en bout (sans Internet, sans IA réelle : l'IA est simulée)."""

import io
import json
import math
import wave
from pathlib import Path

import docx
import numpy as np
import pytest

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VISITES_DATA_DIR", str(tmp_path / "donnees"))
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _texte_docx(path) -> str:
    d = docx.Document(str(path))
    return "\n".join(t.text or "" for t in d.element.body.iter() if t.tag.endswith("}t"))


def _wav_bytes(seconds=3.0, sr=16000) -> bytes:
    t = np.arange(int(seconds * sr)) / sr
    a = (0.2 * np.sin(2 * math.pi * 440 * t) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(a.tobytes())
    return buf.getvalue()


# ------------------------------------------------------------------ bulletin

def test_bulletin_rempli(tmp_path):
    from app.bulletin import champs_manquants, fill_bulletin
    from tests.exemple import visite_exemple

    v = visite_exemple()
    out = fill_bulletin(v, tmp_path / "b.docx")
    txt = _texte_docx(out)
    for attendu in ("DUPONT Camille", "20/11/2026", "CE1", "Baie-Mahault", "MARTIN Sophie, PEMF",
                    "La consigne a été reformulée", "Éduscol", "Analyse lucide", "13 /20", "☒"):
        assert attendu in txt, attendu
    # La structure du modèle est conservée : mêmes rubriques, mêmes tableaux.
    d = docx.Document(str(out))
    assert len(d.tables) == 9
    assert champs_manquants(v) == ["Point discuté 3"]


def test_bulletin_vide_ne_plante_pas(tmp_path):
    from app.bulletin import fill_bulletin
    from app.defaults import empty_visit

    out = fill_bulletin(empty_visit("x"), tmp_path / "vide.docx")
    assert out.exists()
    assert "X" not in [c.text.strip() for t in docx.Document(str(out)).tables for r in t.rows for c in r.cells]


def test_positionnement_et_langue_marques(tmp_path):
    from app.bulletin import fill_bulletin
    from tests.exemple import visite_exemple

    v = visite_exemple()
    d = docx.Document(str(fill_bulletin(v, tmp_path / "b.docx")))
    langue = next(t for t in d.tables if "MAITRISE" in t.rows[0].cells[0].text)
    marques = [c.text.strip() for c in langue.rows[3].cells[:8]]
    assert marques == ["", "", "X", "", "", "", "", "X"]  # orale S, écrite TS
    pos = next(t for t in d.tables if "De 0 à 4" in t.rows[1].cells[0].text)
    assert "X" in pos.rows[1].cells[2].text and "X" not in pos.rows[1].cells[1].text


# ------------------------------------------------------------------ documents

def test_detection_type_documents():
    from app.documents import extract_text, guess_type

    txt = extract_text(FIX / "fiche_seance_ce1.docx")
    assert "Mise en commun" in txt and "Ardoises" in txt
    assert guess_type(txt, "fiche_seance_ce1.docx") == "seance"
    seq = "Fiche de séquence\nSéance 1 : découverte\nSéance 2 : entraînement\nSéance 3 : réinvestissement\nÉvaluation finale"
    assert guess_type(seq, "doc.docx") == "sequence"
    assert guess_type("Liste des élèves de la classe", "eleves.docx") == "autre"
    # Trames INSPE (titres réels), sans indice dans le nom du fichier
    trame_seq = ("Fiche de préparation de séquence\nTitre de la séquence : Le cycle de vie | Niveau : CE2 | "
                 "Nombre de séances envisagées : 5 séances (40-45 min)\nSéance 1 | Séance 2 | Séance 3 | Phase | 10 min")
    trame_sea = ("Fiche de préparation de séance\nTitre de la séquence : Le cycle de vie | Niveau : CE2 | Séance n° 2 sur 5\n"
                 "Phases possibles | Durée | Consignes | 3 min | mise en commun | Séance 1")
    assert guess_type(trame_seq, "doc1.docx") == "sequence"
    assert guess_type(trame_sea, "doc2.docx") == "seance"
    assert guess_type("Séquence d'apprentissage en arts visuels\nSéance 1\nSéance 2\nSéance 3\n20 min", "a.pdf") == "sequence"


# ------------------------------------------------------------------ IA : sécurité et anti-invention

def test_ia_refuse_adresse_exterieure():
    from app import llm

    with pytest.raises(llm.IAIndisponible):
        llm.chat_json({"url": "https://api.exemple.com", "modele": "x"}, "s", "u", {})


def test_extrait_verifie():
    from app.analysis import extrait_present

    src = "[Stagiaire 00:10] Par contre, la mise en commun a été trop rapide, je n'ai pas eu le temps."
    assert extrait_present("la mise en commun a été trop rapide", src)
    assert extrait_present("la mise en commun a ete trop rapide", src)  # accents perdus
    assert not extrait_present("les élèves étaient agités et bruyants", src)


def test_analyse_avec_ia_simulee(monkeypatch):
    from app import analysis, llm

    segments = [
        {"debut": 0, "fin": 4, "texte": "Comment as-tu vécu ta séance ?", "locuteur": "F"},
        {"debut": 4, "fin": 9, "texte": "La mise en commun a été trop rapide, je n'ai pas eu le temps.", "locuteur": "S"},
        {"debut": 9, "fin": 12, "texte": "Il a commencé à pleuvoir, tu as un parapluie ?", "locuteur": "S", "hors_sujet": True},
        {"debut": 12, "fin": 18, "texte": "Je te conseille d'afficher les procédures au tableau.", "locuteur": "F"},
    ]
    reponse = {
        "A": {"constats": [], "reussites": [], "analyse_pratique": [], "questionnements": [], "propositions": [],
              "difficultes": [{"texte": "Mise en commun trop rapide.", "extrait": "La mise en commun a été trop rapide"}]},
        "B": {k: [] for k in analysis.CLES["B"]},
        "C": {k: [] for k in analysis.CLES["C"]},
        "D": "Bilan.",
    }
    reponse["C"]["conseils_pedagogiques"] = [
        {"texte": "Afficher les procédures.", "extrait": "afficher les procédures au tableau"},
        {"texte": "Utiliser des jetons.", "extrait": "prends des jetons de couleur"},  # inventé
    ]
    vu = {}

    def fake(cfg, system, user, schema, timeout=0, **kw):
        vu["user"] = user
        return json.loads(json.dumps(reponse))

    monkeypatch.setattr(llm, "chat_json", fake)
    v = {"transcription": {"segments": segments}, "notes_formatrice": "", "documents": []}
    res = analysis.analyse_reflexive({"contexte": 16384}, v, "grille")
    assert res["A"]["difficultes"][0]["verifie"] is True
    conseils = res["C"]["conseils_pedagogiques"]
    assert conseils[0]["verifie"] is True and conseils[1]["verifie"] is False
    assert "parapluie" not in vu["user"]  # le hors-sujet n'est jamais envoyé à l'analyse
    assert "[Stagiaire" in vu["user"] and "[Formatrice" in vu["user"]


def test_correction_trop_eloignee_refusee(monkeypatch):
    from app import analysis, llm

    segs = [{"texte": "les élèves on bien travailler", "id": "a"}, {"texte": "la séance était bien", "id": "b"}]

    def fake(*a, **k):
        return {"corrections": [
            {"n": 1, "texte": "les élèves ont bien travaillé"},
            {"n": 2, "texte": "la séance était catastrophique du début à la fin"},  # change le sens
        ]}

    monkeypatch.setattr(llm, "chat_json", fake)
    nb = analysis.corriger_transcription({}, segs)
    assert nb == 1
    assert segs[0]["texte"] == "les élèves ont bien travaillé" and segs[0]["texte_original"]
    assert segs[1]["texte"] == "la séance était bien"


# ------------------------------------------------------------------ audio

def test_decoupage_audio_sur_silence():
    from app.audio import SR, split_points

    son = np.ones(SR * 700, dtype=np.float32) * 0.5
    son[SR * 302: SR * 303] = 0  # un silence près de la 5e minute
    bornes = split_points(son)
    assert bornes[0][0] == 0 and bornes[-1][1] == len(son)
    assert SR * 302 <= bornes[0][1] <= SR * 303
    assert all(a < b for a, b in bornes)


def test_hallucinations_filtrees():
    from app.audio import is_hallucination

    assert is_hallucination("Sous-titrage ST' 501")
    assert is_hallucination("Merci d'avoir regardé cette vidéo !")
    assert not is_hallucination("Merci pour cette séance, c'était très riche.")


# ------------------------------------------------------------------ parcours complet via l'API

def test_parcours_complet(client):
    r = client.get("/api/etat")
    assert r.status_code == 200 and r.json()["ia"]["ok"] is False  # pas d'Ollama ici : pas de plantage

    client.put("/api/parametres", json={**client.get("/api/parametres").json(),
                                         "formatrice": {"nom": "MARTIN Sophie", "qualite": "PEMF", "lieu": "Baie-Mahault"}})
    v = client.post("/api/visites", json={"admin": {"stagiaire_nom": "DUPONT Camille"}}).json()
    vid = v["id"]
    assert v["admin"]["formateurs"][0]["nom"] == "MARTIN Sophie"

    v["admin"].update({"date": "2026-11-20", "classe": "CE1", "statut": "temps_plein"})
    r = client.put(f"/api/visites/{vid}", json={"admin": v["admin"], "outils": {**v["outils"], "cahier_journal": True}})
    assert r.json()["admin"]["classe"] == "CE1"

    # Fiche stagiaire réutilisée à la visite suivante
    client.post(f"/api/visites/{vid}/stagiaire")
    st = client.get("/api/stagiaires").json()
    assert st[0]["classe"] == "CE1"
    v2 = client.post("/api/visites", json={"stagiaire_id": st[0]["id"]}).json()
    assert v2["admin"]["classe"] == "CE1" and v2["admin"]["numero"] == "2"

    # Documents
    with open(FIX / "fiche_seance_ce1.docx", "rb") as f:
        r = client.post(f"/api/visites/{vid}/documents", files=[("fichiers", ("fiche_seance_ce1.docx", f.read()))])
    doc = r.json()["visite"]["documents"][0]
    assert doc["type"] == "seance" and "Ardoises" in doc["texte"]
    r = client.post(f"/api/visites/{vid}/documents", files=[("fichiers", ("photo.jpg", b"xx"))])
    assert r.json()["erreurs"]

    # Enregistrement envoyé par morceaux (comme le navigateur), puis finalisé
    rec = client.post(f"/api/visites/{vid}/enregistrement", json={"mime": "audio/wav"}).json()
    data = _wav_bytes(3)
    for i in range(0, len(data), 20000):
        assert client.post(f"/api/visites/{vid}/enregistrement/{rec['id']}/morceau", content=data[i:i + 20000]).status_code == 200
    v = client.post(f"/api/visites/{vid}/enregistrement/{rec['id']}/fin").json()
    a = v["audios"][0]
    assert a["etat"] == "pret" and a["fichier"].endswith(".m4a") and 2.5 < a["duree"] < 3.6
    r = client.get(f"/api/visites/{vid}/audios/{a['id']}")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mp4"

    # Import d'un fichier audio
    v = client.post(f"/api/visites/{vid}/audios", files={"fichier": ("memo.wav", _wav_bytes(2))}).json()
    assert len([x for x in v["audios"] if x["etat"] == "pret"]) == 2

    # L'IA indisponible renvoie un message clair, sans planter
    r = client.post(f"/api/visites/{vid}/analyser")
    job = r.json()
    import time
    for _ in range(50):
        j = client.get(f"/api/taches/{job['id']}").json()
        if j["etat"] in ("termine", "erreur"):
            break
        time.sleep(0.1)
    assert j["etat"] == "erreur" and "Ollama" in j["erreur"]

    # Bulletin et exports
    b = client.get(f"/api/visites/{vid}").json()["bulletin"]
    b.update({"enseignements": "Mathématiques", "positionnement": "S", "positifs": ["Écoute"]})
    client.put(f"/api/visites/{vid}", json={"bulletin": b, "notes_formatrice": "Rituel dynamique."})
    manque = client.get(f"/api/visites/{vid}/manquants").json()
    assert "Enseignements observés" not in manque and "Description de la séance" in manque
    r = client.post(f"/api/visites/{vid}/exporter", json={"types": ["bulletin_docx", "transcription", "bilan", "synthese"]})
    out = r.json()
    assert len(out["fichiers"]) == 4 and not out["erreurs"]
    r = client.get(f"/api/visites/{vid}/fichiers/{out['fichiers'][0]}")
    assert r.status_code == 200 and len(r.content) > 10000

    # Liste et suppression (vers la corbeille, récupérable)
    assert any(x["id"] == vid for x in client.get("/api/visites").json())
    client.delete(f"/api/visites/{vid}")
    assert not any(x["id"] == vid for x in client.get("/api/visites").json())


def test_acces_refuse_depuis_un_autre_site(client):
    r = client.get("/api/visites", headers={"Origin": "https://site-malveillant.example"})
    assert r.status_code == 403
    r = client.get("/api/visites", headers={"Host": "192.168.1.20:8765"})
    assert r.status_code == 403


# ------------------------------------------------------------------ photos de la séance

def _image_bytes(fmt="JPEG", size=(400, 300), orientation=None):
    from PIL import Image

    im = Image.new("RGB", size, (200, 120, 160))
    buf = io.BytesIO()
    kw = {}
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation
        kw["exif"] = exif
    im.save(buf, fmt, **kw)
    return buf.getvalue()


def test_photos_import_legende_et_export(client):
    v = client.post("/api/visites", json={"admin": {"stagiaire_nom": "TEST Photo"}}).json()
    vid = v["id"]
    files = [
        ("fichiers", ("tableau.jpg", _image_bytes())),
        # Photo prise téléphone tourné : l'orientation EXIF 6 doit être appliquée (400x300 -> 300x400)
        ("fichiers", ("eleve.jpg", _image_bytes(orientation=6))),
        ("fichiers", ("note.txt", b"pas une image")),
    ]
    r = client.post(f"/api/visites/{vid}/photos", files=files).json()
    ph = r["visite"]["photos"]
    assert len(ph) == 2 and len(r["erreurs"]) == 1
    assert (ph[1]["largeur"], ph[1]["hauteur"]) == (300, 400)
    assert client.get(f"/api/visites/{vid}/photos/{ph[0]['id']}").headers["content-type"] == "image/jpeg"

    client.patch(f"/api/visites/{vid}/photos/{ph[0]['id']}", json={"legende": "Trace écrite au tableau"})
    v = client.patch(f"/api/visites/{vid}/photos/{ph[1]['id']}", json={"ordre": [ph[1]["id"], ph[0]["id"]]}).json()
    assert [p["id"] for p in v["photos"]] == [ph[1]["id"], ph[0]["id"]]

    out = client.post(f"/api/visites/{vid}/exporter", json={"types": ["synthese", "bilan", "bulletin_docx"]}).json()
    from app import storage
    edir = storage.visit_dir(vid) / "exports"
    synthese = docx.Document(str(edir / out["fichiers"][0]))
    assert len(synthese.inline_shapes) == 2
    assert "Trace écrite au tableau" in _texte_docx(edir / out["fichiers"][0])
    assert len(docx.Document(str(edir / out["fichiers"][1])).inline_shapes) == 2
    # Le bulletin officiel ne reçoit pas les photos (seulement les 3 images d'origine du modèle)
    assert len(docx.Document(str(edir / out["fichiers"][2])).inline_shapes) == 3

    v = client.delete(f"/api/visites/{vid}/photos/{ph[0]['id']}").json()
    assert len(v["photos"]) == 1


def test_photo_heic_iphone(client):
    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (10, 120, 60)).save(buf, "HEIF")
    v = client.post("/api/visites", json={"admin": {"stagiaire_nom": "TEST Heic"}}).json()
    r = client.post(f"/api/visites/{v['id']}/photos", files=[("fichiers", ("IMG_0001.HEIC", buf.getvalue()))]).json()
    assert not r["erreurs"] and r["visite"]["photos"][0]["fichier"].endswith(".jpg")


def test_legendes_transmises_a_l_ia():
    from app.analysis import legendes_photos

    v = {"photos": [{"legende": "Trace écrite : ovipare / vivipare"}, {"legende": ""}]}
    assert legendes_photos(v) == "Photos prises pendant la séance — Photo 1 : Trace écrite : ovipare / vivipare."
    assert legendes_photos({"photos": []}) == ""


def test_ia_reponse_au_fil_de_l_eau():
    """Simule Ollama qui écrit sa réponse morceau par morceau (format NDJSON)."""
    import http.server
    import threading

    from app import llm

    reponse = json.dumps({"D": "Bilan rédigé par morceaux.", "liste": ["a", "b"]})
    morceaux = [reponse[i:i + 7] for i in range(0, len(reponse), 7)]
    recu = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            recu["payload"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            for m in morceaux:
                self.wfile.write((json.dumps({"message": {"content": m}, "done": False}) + "\n").encode())
                self.wfile.flush()
            self.wfile.write((json.dumps({"message": {"content": ""}, "done": True}) + "\n").encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    etapes = []
    try:
        cfg = {"url": f"http://127.0.0.1:{srv.server_port}", "modele": "test"}
        res = llm.chat_json(cfg, "s", "u", {"type": "object"}, progress=lambda f, m: etapes.append((f, m)), attendu=10)
    finally:
        srv.shutdown()
    assert res == {"D": "Bilan rédigé par morceaux.", "liste": ["a", "b"]}
    assert recu["payload"]["stream"] is True and recu["payload"]["keep_alive"] == "30m"
    assert etapes and etapes[0][1].startswith("L'IA lit")


# ------------------------------------------------------------------ description, horaires, références

def test_horaires_du_deroulement():
    from app.analysis import horodater

    d = [{"temps": "10 min – Rituel"}, {"temps": "Recherche 20 min"}, {"temps": "Mise en commun 10min"}]
    t = [r["temps"] for r in horodater(d, "14h25 - 15h10")]
    assert t == ["14h25 – 14h35 (10 min)\nRituel", "14h35 – 14h55 (20 min)\nRecherche",
                 "14h55 – 15h05 (10 min)\nMise en commun"]
    # Heures déjà notées par la formatrice : on se recale dessus
    t = [r["temps"] for r in horodater([{"temps": "14h40 – 14h50 rituel"}, {"temps": "15 min"}], "14h25")]
    assert t[1].startswith("14h50 – 15h05 (15 min)")
    # Sans horaire, ou durée inconnue : on ne devine rien
    assert horodater([{"temps": "10 min"}], "") == [{"temps": "10 min"}]
    assert horodater([{"temps": "Rituel"}, {"temps": "10 min"}], "14h25")[0] == {"temps": "Rituel"}


def test_preremplissage_references_et_horaires(monkeypatch):
    from app import analysis, llm

    vu_prompt = []

    def fake(cfg, system, user, schema, timeout=0, **kw):
        vu_prompt.append(user)
        assert "BIBLIOTHÈQUE DE RÉFÉRENCES" in user and "Photo 1 : Trace écrite" in user
        return {
            "enseignements": "Questionner le monde", "description": "Tri des animaux (photo 1).",
            "deroulement": [{"temps": "10 min – Rappel", "deroulement": "a", "remarque": "Tissage réussi", "dispositif": "b", "organisation": "c"},
                            {"temps": "25 min – Tri", "deroulement": "a", "remarque": "", "dispositif": "b", "organisation": "c"}],
            "points": [{"titre": "Étayage – Difficultés lors du tri", "analyse": "Constat, analyse, conseil.",
                        "ressources": "J.-P. Astolfi, L'erreur, un outil pour enseigner, ESF, 1997 ; Manuel inventé, 2030"}],
            "positifs": [], "ameliorer": [], "langue_observations": "",
            "references": ["La main à la pâte – Le vivant", "Ouvrage imaginaire de M. Personne"],
        }

    monkeypatch.setattr(llm, "chat_json", fake)
    v = {"admin": {"horaire": "9h00 – 9h45"}, "documents": [], "notes_formatrice": "Bonne séance.",
         "photos": [{"legende": "Trace écrite au tableau"}], "analyse": {},
         "transcription": {"segments": [{"debut": 0, "fin": 1, "texte": "Regarde le site La main à la pâte sur le vivant", "locuteur": "F"}]}}
    res = analysis.preremplir_bulletin({"contexte": 16384}, v, "grille", bibliotheque="Éduscol – Le vivant au cycle 2")
    assert [r["temps"] for r in res["deroulement"]] == ["9h00 – 9h10 (10 min)\nRappel", "9h10 – 9h35 (25 min)\nTri"]
    refs = {r["texte"]: r for r in res["references"]}
    assert refs["La main à la pâte – Le vivant"]["verifie"] is True
    assert refs["Ouvrage imaginaire de M. Personne"]["verifie"] is False
    assert len(res["points"]) == 3
    assert res["deroulement"][0]["remarque"] == "Tissage réussi"
    # Une référence de la bibliothèque intégrée passe, une référence inventée est signalée
    assert res["points"][0]["ressources_a_verifier"] == ["Manuel inventé, 2030"]
    assert "CADRE D'ANALYSE PROFESSIONNEL" in vu_prompt[0] and "Bucheton" in vu_prompt[0]


def test_synthese_complete_et_photos_dans_bulletin(client):
    v = client.post("/api/visites", json={"admin": {"stagiaire_nom": "TEST Synthese", "horaire": "14h25"}}).json()
    vid = v["id"]
    client.post(f"/api/visites/{vid}/photos", files=[("fichiers", ("a.jpg", _image_bytes())), ("fichiers", ("b.jpg", _image_bytes()))])
    b = client.get(f"/api/visites/{vid}").json()["bulletin"]
    b.update({
        "enseignements": "Questionner le monde : le vivant",
        "description": "Les élèves trient des étiquettes d'animaux (photo 2).",
        "deroulement": [{"temps": "14h25 – 14h35 (10 min)\nRappel", "deroulement": "Rappel séance 1", "dispositif": "Collectif", "organisation": "Vidéo"}],
        "references": [{"texte": "Éduscol – Le vivant au cycle 2", "verifie": True}],
        "points": [{"titre": "Tri", "analyse": "…", "ressources": "La main à la pâte"}, {}, {}],
    })
    client.put(f"/api/visites/{vid}", json={"bulletin": b})
    out = client.post(f"/api/visites/{vid}/exporter",
                      json={"types": ["synthese", "bulletin_docx"], "photos_dans_bulletin": True}).json()
    from app import storage
    edir = storage.visit_dir(vid) / "exports"
    texte = _texte_docx(edir / out["fichiers"][0])
    for attendu in ("La séance observée", "14h25 – 14h35 (10 min)", "(photo 2)", "Photo 1", "Photo 2",
                    "Les activités des élèves en images", "Références à communiquer à la stagiaire",
                    "Éduscol – Le vivant au cycle 2", "La main à la pâte"):
        assert attendu in texte, attendu
    assert texte.index("La séance observée") < texte.index("Points forts") < texte.index("Références à communiquer")
    bul = docx.Document(str(edir / out["fichiers"][1]))
    assert len(bul.inline_shapes) == 3 + 2  # images du modèle + 2 photos sous la description
    assert "Photo 1" in _texte_docx(edir / out["fichiers"][1])



def test_deroulement_observe_puis_conseil_dans_le_bulletin(tmp_path):
    from app.bulletin import fill_bulletin
    from tests.exemple import visite_exemple

    v = visite_exemple()
    v["bulletin"]["deroulement"] = [
        {"temps": "14h25 – 14h35 (10 min)", "deroulement": "Calcul mental sur ardoise",
         "remarque": "Pilotage efficace ; prévoir une validation collective.", "dispositif": "Collectif", "organisation": "Ardoises"},
        {"temps": "14h35 – 14h55 (20 min)", "deroulement": "Recherche en binômes", "remarque": "",
         "dispositif": "Binômes", "organisation": "Fiche"},
    ]
    d = docx.Document(str(fill_bulletin(v, tmp_path / "b.docx")))
    t = next(t for t in d.tables if t.rows[0].cells[0].text.startswith("Temps"))
    cellule = t.rows[1].cells[1]
    assert [p.text for p in cellule.paragraphs] == [
        "Observé : Calcul mental sur ardoise",
        "Analyse et conseil : Pilotage efficace ; prévoir une validation collective.",
    ]
    assert cellule.paragraphs[0].runs[0].bold and cellule.paragraphs[1].runs[0].bold
    assert t.rows[2].cells[1].text == "Recherche en binômes"  # sans remarque : l'observé seul


def test_bibliotheque_integree_reconnue():
    from app.analysis import verifier_references
    from app.referentiel import REFERENCES_INTEGREES, bibliotheque_complete

    biblio = bibliotheque_complete("Ma référence perso")
    assert len(REFERENCES_INTEGREES) >= 20 and biblio.endswith("Ma référence perso")
    res = verifier_references(["R. Goigoux et S. Cèbe, Apprendre à lire à l'école, Retz, 2006", "Ma référence perso"], biblio, "")
    assert all(r["verifie"] and r["source"] == "bibliotheque" for r in res)
