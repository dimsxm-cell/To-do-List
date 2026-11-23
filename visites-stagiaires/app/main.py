"""Serveur local de l'application (écoute uniquement sur 127.0.0.1 : rien n'est accessible depuis le réseau)."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, analysis, audio, bulletin, documents, exports, jobs, llm, photos, storage
from .defaults import OUTILS

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Visites stagiaires", version=__version__, docs_url=None, redoc_url=None)


@app.exception_handler(FileNotFoundError)
async def _not_found(_req, exc):
    return JSONResponse({"detail": "Élément introuvable."}, status_code=404)


@app.exception_handler(ValueError)
async def _bad(_req, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(llm.IAIndisponible)
async def _ia(_req, exc):
    return JSONResponse({"detail": str(exc)}, status_code=503)


@app.middleware("http")
async def _local_only(request: Request, call_next):
    # Protection : on refuse les pages web extérieures qui tenteraient de parler au serveur.
    host = (request.headers.get("host") or "").split(":")[0]
    if host not in ("127.0.0.1", "localhost", "testserver"):
        return JSONResponse({"detail": "Accès refusé."}, status_code=403)
    origin = request.headers.get("origin")
    if origin and not re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$", origin):
        return JSONResponse({"detail": "Accès refusé."}, status_code=403)
    return await call_next(request)


# ------------------------------------------------------------------ état / paramètres

@app.get("/api/etat")
def etat():
    s = storage.get_settings()
    try:
        ia = llm.status(s["ia"])
    except llm.IAIndisponible as e:
        ia = {"ok": False, "message": str(e), "modeles": []}
    return {
        "version": __version__,
        "dossier": str(storage.data_dir()),
        "ia": ia,
        "transcription": {"moteur": audio.engine_name(s["transcription"]["moteur"]), "modele": s["transcription"]["modele"]},
        "pdf": bool(exports._soffice()) or Path("/Applications/Microsoft Word.app").exists(),
        "outils": [{"cle": k, "libelle": v} for k, v in OUTILS],
    }


@app.get("/api/parametres")
def get_parametres():
    return storage.get_settings()


@app.put("/api/parametres")
def put_parametres(data: dict = Body(...)):
    llm._check_local(data.get("ia", {}).get("url", "http://127.0.0.1:11434"))
    return storage.save_settings(data)


# ------------------------------------------------------------------ stagiaires

@app.get("/api/stagiaires")
def get_stagiaires():
    return storage.list_stagiaires()


@app.post("/api/stagiaires")
def post_stagiaire(data: dict = Body(...)):
    if not (data.get("nom") or "").strip():
        raise HTTPException(400, "Le nom du stagiaire est obligatoire.")
    return storage.save_stagiaire(data)


@app.delete("/api/stagiaires/{sid}")
def del_stagiaire(sid: str):
    storage.delete_stagiaire(sid)
    return {"ok": True}


# ------------------------------------------------------------------ visites

@app.get("/api/visites")
def get_visites():
    return storage.list_visits()


@app.post("/api/visites")
def post_visite(data: dict = Body(default={})):
    admin = dict(data.get("admin") or {})
    sid = data.get("stagiaire_id")
    if sid:
        st = next((s for s in storage.list_stagiaires() if s.get("id") == sid), None)
        if st:
            admin.setdefault("stagiaire_nom", st.get("nom", ""))
            for k in ("statut", "classe", "effectif", "ecole", "circonscription", "commune", "conditions"):
                if st.get(k):
                    admin.setdefault(k, st[k])
            # Numéro de visite suivant pour ce stagiaire
            nb = sum(1 for v in storage.list_visits() if v["stagiaire"] == st.get("nom"))
            admin.setdefault("numero", str(nb + 1))
    v = storage.create_visit(admin)
    if sid:
        v["stagiaire_id"] = sid
        storage.save_visit(v)
    return v


@app.get("/api/visites/{vid}")
def get_visite(vid: str):
    v = storage.get_visit(vid)
    v["taches"] = jobs.for_visit(vid)
    return v


EDITABLE = {"admin", "outils", "notes_formatrice", "etape", "bulletin", "analyse"}


@app.put("/api/visites/{vid}")
def put_visite(vid: str, data: dict = Body(...)):
    def apply(v):
        for k in EDITABLE & data.keys():
            v[k] = data[k]
        if "segments" in data:
            if any(j["type"] in ("transcription", "interlocuteurs", "corrections") for j in jobs.for_visit(vid)):
                raise HTTPException(409, "Une transcription ou une analyse est en cours : attendez la fin avant de modifier.")
            v["transcription"]["segments"] = data["segments"]
    v = storage.update_visit(vid, apply)
    v["taches"] = jobs.for_visit(vid)
    return v


@app.delete("/api/visites/{vid}")
def del_visite(vid: str):
    storage.delete_visit(vid)
    return {"ok": True}


@app.post("/api/visites/{vid}/stagiaire")
def save_as_stagiaire(vid: str):
    """Enregistre (ou met à jour) la fiche stagiaire à partir des infos de la visite."""
    v = storage.get_visit(vid)
    a = v["admin"]
    if not a.get("stagiaire_nom"):
        raise HTTPException(400, "Indiquez d'abord le nom du stagiaire.")
    existing = next((s for s in storage.list_stagiaires()
                     if s.get("id") == v.get("stagiaire_id") or s.get("nom") == a["stagiaire_nom"]), {})
    item = {**existing, "nom": a["stagiaire_nom"]}
    for k in ("statut", "classe", "effectif", "ecole", "circonscription", "commune", "conditions"):
        item[k] = a.get(k, "")
    item = storage.save_stagiaire(item)
    storage.update_visit(vid, lambda x: x.__setitem__("stagiaire_id", item["id"]))
    return item


# ------------------------------------------------------------------ documents

@app.post("/api/visites/{vid}/documents")
async def post_documents(vid: str, fichiers: list[UploadFile] = File(...)):
    vdir = storage.visit_dir(vid) / "documents"
    vdir.mkdir(parents=True, exist_ok=True)
    ajoutes, erreurs = [], []
    for f in fichiers:
        name = Path(f.filename or "document").name
        ext = Path(name).suffix.lower()
        if ext not in documents.EXTENSIONS:
            erreurs.append(f"{name} : format non pris en charge (Word .docx, PDF ou texte).")
            continue
        did = uuid.uuid4().hex[:8]
        path = vdir / f"{did}{ext}"
        path.write_bytes(await f.read())
        try:
            texte = documents.extract_text(path)
        except Exception as e:
            erreurs.append(f"{name} : {e}")
            texte = ""
        ajoutes.append({
            "id": did, "nom": name, "fichier": path.name, "texte": texte,
            "type": documents.guess_type(texte, name), "type_manuel": False, "analyse": None,
        })
    v = storage.update_visit(vid, lambda v: v["documents"].extend(ajoutes))
    return {"visite": v, "erreurs": erreurs}


@app.patch("/api/visites/{vid}/documents/{did}")
def patch_document(vid: str, did: str, data: dict = Body(...)):
    def apply(v):
        for d in v["documents"]:
            if d["id"] == did and data.get("type") in ("seance", "sequence", "autre"):
                d["type"] = data["type"]
                d["type_manuel"] = True
    return storage.update_visit(vid, apply)


@app.delete("/api/visites/{vid}/documents/{did}")
def delete_document(vid: str, did: str):
    def apply(v):
        for d in v["documents"]:
            if d["id"] == did:
                p = storage.visit_dir(vid) / "documents" / d["fichier"]
                p.unlink(missing_ok=True)
        v["documents"] = [d for d in v["documents"] if d["id"] != did]
    return storage.update_visit(vid, apply)


@app.post("/api/visites/{vid}/documents/analyser")
def analyser_documents(vid: str):
    storage.get_visit(vid)

    def run(progress):
        cfg = storage.get_settings()["ia"]
        docs = [d for d in storage.get_visit(vid)["documents"] if d.get("texte")]
        if not docs:
            raise ValueError("Aucun document lisible à analyser.")
        for i, d in enumerate(docs):
            progress(i / len(docs), f"Lecture de « {d['nom']} »…")
            res = analysis.analyser_document(
                cfg, d["texte"], d["nom"], d["type"],
                progress=lambda f, m, i=i, d=d: progress((i + f) / len(docs), f"« {d['nom']} » — {m}"),
            )

            def apply(v, d=d, res=res):
                for x in v["documents"]:
                    if x["id"] == d["id"]:
                        x["analyse"] = res
                        if not x.get("type_manuel") and res.get("type") in ("seance", "sequence", "autre"):
                            x["type"] = res["type"]
            storage.update_visit(vid, apply)

    return jobs.start("documents", vid, run)


# ------------------------------------------------------------------ photos de la séance

@app.post("/api/visites/{vid}/photos")
async def post_photos(vid: str, fichiers: list[UploadFile] = File(...)):
    pdir = storage.visit_dir(vid) / "photos"
    pdir.mkdir(parents=True, exist_ok=True)
    ajoutees, erreurs = [], []
    for f in fichiers:
        name = Path(f.filename or "photo").name
        ext = Path(name).suffix.lower()
        if ext not in photos.EXTENSIONS:
            erreurs.append(f"{name} : ce n'est pas une photo reconnue (JPEG, PNG, HEIC…).")
            continue
        pid = uuid.uuid4().hex[:8]
        brut = pdir / f"brut-{pid}{ext}"
        brut.write_bytes(await f.read())
        try:
            largeur, hauteur = photos.preparer(brut, pdir / f"{pid}.jpg")
            brut.unlink(missing_ok=True)
        except Exception:
            brut.unlink(missing_ok=True)
            erreurs.append(f"{name} : photo illisible.")
            continue
        ajoutees.append({
            "id": pid, "fichier": f"{pid}.jpg", "nom": name, "legende": "",
            "largeur": largeur, "hauteur": hauteur, "cree": datetime.now().isoformat(timespec="seconds"),
        })
    v = storage.update_visit(vid, lambda v: v["photos"].extend(ajoutees))
    return {"visite": v, "erreurs": erreurs}


@app.patch("/api/visites/{vid}/photos/{pid}")
def patch_photo(vid: str, pid: str, data: dict = Body(...)):
    def apply(v):
        for p in v["photos"]:
            if p["id"] == pid and "legende" in data:
                p["legende"] = str(data["legende"])[:300]
        if "ordre" in data:  # liste d'identifiants dans le nouvel ordre
            rang = {i: n for n, i in enumerate(data["ordre"])}
            v["photos"].sort(key=lambda p: rang.get(p["id"], 999))
    return storage.update_visit(vid, apply)


@app.delete("/api/visites/{vid}/photos/{pid}")
def delete_photo(vid: str, pid: str):
    def apply(v):
        for p in v["photos"]:
            if p["id"] == pid:
                (storage.visit_dir(vid) / "photos" / p["fichier"]).unlink(missing_ok=True)
        v["photos"] = [p for p in v["photos"] if p["id"] != pid]
    return storage.update_visit(vid, apply)


@app.get("/api/visites/{vid}/photos/{pid}")
def get_photo(vid: str, pid: str):
    v = storage.get_visit(vid)
    p = next((x for x in v["photos"] if x["id"] == pid), None)
    if not p:
        raise HTTPException(404, "Photo introuvable.")
    return FileResponse(storage.visit_dir(vid) / "photos" / p["fichier"], media_type="image/jpeg")


# ------------------------------------------------------------------ audio

AUDIO_EXT = {".m4a", ".mp3", ".wav", ".webm", ".ogg", ".mp4", ".aac", ".flac", ".mov", ".caf", ".opus"}


@app.post("/api/visites/{vid}/enregistrement")
def rec_start(vid: str, data: dict = Body(default={})):
    mime = (data.get("mime") or "").lower()
    ext = ".mp4" if "mp4" in mime else ".ogg" if "ogg" in mime else ".webm"
    rid = uuid.uuid4().hex[:8]
    entry = {
        "id": rid, "nom": f"Enregistrement du {datetime.now():%d/%m/%Y à %H:%M}",
        "brut": f"rec-{rid}{ext}", "fichier": "", "duree": 0, "etat": "en_cours",
        "cree": datetime.now().isoformat(timespec="seconds"),
    }
    (storage.visit_dir(vid) / "audio").mkdir(parents=True, exist_ok=True)
    storage.update_visit(vid, lambda v: v["audios"].append(entry))
    return entry


@app.post("/api/visites/{vid}/enregistrement/{rid}/morceau")
async def rec_chunk(vid: str, rid: str, request: Request):
    if not re.fullmatch(r"[a-f0-9]{8}", rid):
        raise HTTPException(400, "Identifiant invalide.")
    v = storage.get_visit(vid)
    entry = next((a for a in v["audios"] if a["id"] == rid), None)
    if not entry or entry["etat"] != "en_cours":
        raise HTTPException(404, "Enregistrement introuvable ou déjà terminé.")
    data = await request.body()
    with open(storage.visit_dir(vid) / "audio" / entry["brut"], "ab") as f:
        f.write(data)
    return {"ok": True, "taille": len(data)}


def _finalise_audio(vid: str, aid: str):
    v = storage.get_visit(vid)
    entry = next(a for a in v["audios"] if a["id"] == aid)
    adir = storage.visit_dir(vid) / "audio"
    raw = adir / entry["brut"]
    if not raw.exists() or raw.stat().st_size == 0:
        raise HTTPException(400, "L'enregistrement est vide. Vérifiez que le micro est autorisé.")
    final = adir / f"{aid}.m4a"
    try:
        audio.to_m4a(raw, final)
        fichier = final.name
    except Exception:
        fichier = raw.name  # on garde l'original : il reste transcriptible
    dur = audio.duration(adir / fichier)

    def apply(v):
        for a in v["audios"]:
            if a["id"] == aid:
                a.update({"fichier": fichier, "duree": round(dur, 1), "etat": "pret"})
    return storage.update_visit(vid, apply)


@app.post("/api/visites/{vid}/enregistrement/{rid}/fin")
def rec_stop(vid: str, rid: str):
    return _finalise_audio(vid, rid)


@app.post("/api/visites/{vid}/audios")
async def import_audio(vid: str, fichier: UploadFile = File(...)):
    name = Path(fichier.filename or "audio").name
    ext = Path(name).suffix.lower()
    if ext not in AUDIO_EXT:
        raise HTTPException(400, f"Format audio non reconnu ({ext}). Formats acceptés : m4a, mp3, wav, webm…")
    aid = uuid.uuid4().hex[:8]
    adir = storage.visit_dir(vid) / "audio"
    adir.mkdir(parents=True, exist_ok=True)
    with open(adir / f"import-{aid}{ext}", "wb") as f:
        while chunk := await fichier.read(1 << 20):
            f.write(chunk)
    entry = {"id": aid, "nom": name, "brut": f"import-{aid}{ext}", "fichier": "", "duree": 0,
             "etat": "en_cours", "cree": datetime.now().isoformat(timespec="seconds")}
    storage.update_visit(vid, lambda v: v["audios"].append(entry))
    return _finalise_audio(vid, aid)


@app.get("/api/visites/{vid}/audios/{aid}")
def get_audio(vid: str, aid: str):
    v = storage.get_visit(vid)
    a = next((x for x in v["audios"] if x["id"] == aid), None)
    if not a or not a.get("fichier"):
        raise HTTPException(404, "Audio introuvable.")
    path = storage.visit_dir(vid) / "audio" / a["fichier"]
    media = "audio/mp4" if path.suffix in (".m4a", ".mp4") else None
    return FileResponse(path, media_type=media)


@app.delete("/api/visites/{vid}/audios/{aid}")
def delete_audio(vid: str, aid: str):
    def apply(v):
        for a in v["audios"]:
            if a["id"] == aid:
                for name in {a.get("brut"), a.get("fichier")} - {None, ""}:
                    (storage.visit_dir(vid) / "audio" / name).unlink(missing_ok=True)
        v["audios"] = [a for a in v["audios"] if a["id"] != aid]
        v["transcription"]["segments"] = [s for s in v["transcription"]["segments"] if s.get("audio") != aid]
        v["transcription"]["progression"].pop(aid, None)
    return storage.update_visit(vid, apply)


# ------------------------------------------------------------------ transcription

@app.post("/api/visites/{vid}/transcrire")
def transcrire(vid: str, data: dict = Body(default={})):
    v = storage.get_visit(vid)
    if not [a for a in v["audios"] if a["etat"] == "pret"]:
        raise HTTPException(400, "Aucun enregistrement à transcrire.")
    if data.get("recommencer"):
        def reset(v):
            v["transcription"] = {"segments": [], "progression": {}, "moteur": ""}
        storage.update_visit(vid, reset)

    def run(progress):
        s = storage.get_settings()
        tcfg = s["transcription"]
        engine = audio.engine_name(tcfg["moteur"])
        tr = audio.Transcriber(engine, tcfg["modele"], tcfg.get("langue", "fr"), s.get("vocabulaire", ""))
        v = storage.get_visit(vid)
        audios = [a for a in v["audios"] if a["etat"] == "pret"]
        total_dur = sum(a.get("duree") or 0 for a in audios) or 1
        offset = 0.0
        fait = 0.0
        for a in audios:
            path = storage.visit_dir(vid) / "audio" / a["fichier"]
            done_idx = int(v["transcription"]["progression"].get(a["id"], 0))
            progress(fait / total_dur, f"Préparation de « {a['nom']} »…")
            samples = audio.decode(path)
            bounds = audio.split_points(samples)
            for i, (b0, b1) in enumerate(bounds):
                if i < done_idx:
                    continue
                progress(
                    (fait + b0 / audio.SR) / total_dur,
                    f"Transcription de « {a['nom']} » : {analysis.hms(b0 / audio.SR)} / {analysis.hms(len(samples) / audio.SR)}",
                )
                segs = tr.transcribe_chunk(samples[b0:b1], b0 / audio.SR)
                for sg in segs:
                    sg.update({
                        "id": uuid.uuid4().hex[:8], "audio": a["id"],
                        "debut_audio": sg["debut"], "fin_audio": sg["fin"],
                        "debut": round(offset + sg["debut"], 2), "fin": round(offset + sg["fin"], 2),
                        "locuteur": "?", "hors_sujet": False,
                    })

                def apply(v, segs=segs, i=i, aid=a["id"]):
                    v["transcription"]["segments"].extend(segs)
                    v["transcription"]["segments"].sort(key=lambda x: x["debut"])
                    v["transcription"]["progression"][aid] = i + 1
                    v["transcription"]["moteur"] = f"{engine} ({tcfg['modele']})"
                storage.update_visit(vid, apply)
            offset += len(samples) / audio.SR
            fait += a.get("duree") or len(samples) / audio.SR
        # On libère la mémoire de Whisper : l'IA de rédaction en aura besoin juste après.
        tr.release()
        if not storage.get_visit(vid)["transcription"]["segments"]:
            raise ValueError(
                "Aucune parole n'a été détectée dans l'enregistrement. Réécoutez-le (étape Entretien) "
                "pour vérifier que le micro captait bien le son."
            )

    return jobs.start("transcription", vid, run)


def _ia_job(kind: str, vid: str, work):
    storage.get_visit(vid)

    def run(progress):
        s = storage.get_settings()
        st = llm.status(s["ia"])
        if not st["ok"]:
            raise llm.IAIndisponible(st["message"] + " Ouvrez Ollama, puis réessayez.")
        work(s, progress)

    return jobs.start(kind, vid, run)


def _need_segments(vid):
    if not storage.get_visit(vid)["transcription"]["segments"]:
        raise HTTPException(400, "Il n'y a pas encore de transcription.")


@app.post("/api/visites/{vid}/interlocuteurs")
def interlocuteurs(vid: str):
    _need_segments(vid)

    def work(s, progress):
        segs = storage.get_visit(vid)["transcription"]["segments"]
        analysis.attribuer_interlocuteurs(s["ia"], segs, progress)
        par_id = {x["id"]: x for x in segs}

        def apply(v):
            for x in v["transcription"]["segments"]:
                if x["id"] in par_id and not x.get("verrouille"):
                    x["locuteur"] = par_id[x["id"]].get("locuteur", "?")
                    x["hors_sujet"] = par_id[x["id"]].get("hors_sujet", False)
        storage.update_visit(vid, apply)

    return _ia_job("interlocuteurs", vid, work)


@app.post("/api/visites/{vid}/corriger")
def corriger(vid: str):
    _need_segments(vid)

    def work(s, progress):
        segs = storage.get_visit(vid)["transcription"]["segments"]
        analysis.corriger_transcription(s["ia"], segs, s.get("vocabulaire", ""), progress)
        par_id = {x["id"]: x for x in segs}

        def apply(v):
            for x in v["transcription"]["segments"]:
                y = par_id.get(x["id"])
                if y and y.get("texte_original") and not x.get("verrouille"):
                    x["texte_original"] = y["texte_original"]
                    x["texte"] = y["texte"]
        storage.update_visit(vid, apply)

    return _ia_job("corrections", vid, work)


@app.post("/api/visites/{vid}/analyser")
def analyser(vid: str):
    def work(s, progress):
        res = analysis.analyse_reflexive(s["ia"], storage.get_visit(vid), s["grille"], progress)
        res["genere"] = datetime.now().isoformat(timespec="seconds")
        storage.update_visit(vid, lambda v: v.__setitem__("analyse", res))

    return _ia_job("analyse", vid, work)


@app.post("/api/visites/{vid}/preremplir")
def preremplir(vid: str):
    def work(s, progress):
        res = analysis.preremplir_bulletin(s["ia"], storage.get_visit(vid), s["grille"], progress)

        def apply(v):
            b = v["bulletin"]
            for k in ("enseignements", "description", "deroulement", "points", "positifs", "ameliorer"):
                b[k] = res[k]
            b["langue"]["observations"] = res["langue_observations"]
            b["prerempli"] = datetime.now().isoformat(timespec="seconds")
            b["valide"] = False
        storage.update_visit(vid, apply)

    return _ia_job("bulletin", vid, work)


@app.get("/api/taches/{jid}")
def tache(jid: str):
    j = jobs.get(jid)
    if not j:
        raise HTTPException(404, "Tâche inconnue (l'application a peut-être été relancée).")
    return j


# ------------------------------------------------------------------ exports

@app.get("/api/visites/{vid}/manquants")
def manquants(vid: str):
    return bulletin.champs_manquants(storage.get_visit(vid))


EXPORTS = {
    "bulletin_docx": exports.export_bulletin_docx,
    "transcription": exports.export_transcription,
    "bilan": exports.export_bilan,
    "synthese": exports.export_synthese,
}


@app.post("/api/visites/{vid}/exporter")
def exporter(vid: str, data: dict = Body(...)):
    v = storage.get_visit(vid)
    out = storage.visit_dir(vid) / "exports"
    out.mkdir(parents=True, exist_ok=True)
    types = data.get("types") or []
    fichiers, erreurs = [], []
    bulletin_docx = None
    for t in types:
        try:
            if t == "bulletin_pdf":
                bulletin_docx = bulletin_docx or exports.export_bulletin_docx(v, out)
                fichiers.append(exports.docx_to_pdf(bulletin_docx).name)
            elif t in EXPORTS:
                p = EXPORTS[t](v, out)
                if t == "bulletin_docx":
                    bulletin_docx = p
                fichiers.append(p.name)
        except exports.PDFImpossible as e:
            erreurs.append(str(e))
        except bulletin.ModeleIntrouvable as e:
            erreurs.append(str(e))
    return {"fichiers": fichiers, "erreurs": erreurs, "dossier": str(out)}


@app.get("/api/visites/{vid}/fichiers/{name}")
def fichier(vid: str, name: str):
    path = storage.visit_dir(vid) / "exports" / Path(name).name
    if not path.exists():
        raise HTTPException(404, "Fichier introuvable.")
    return FileResponse(path, filename=path.name)


@app.post("/api/visites/{vid}/ouvrir-dossier")
def ouvrir_dossier(vid: str):
    exports.open_in_finder(storage.visit_dir(vid) / "exports")
    return {"ok": True}


# ------------------------------------------------------------------ interface

app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")


def run():
    import threading
    import webbrowser

    import uvicorn

    port = int(os.environ.get("VISITES_PORT", "8765"))
    url = f"http://127.0.0.1:{port}/"
    if not os.environ.get("VISITES_NO_BROWSER"):
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"\n  Application ouverte sur {url}\n  Laissez cette fenêtre ouverte pendant l'utilisation.\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    run()
