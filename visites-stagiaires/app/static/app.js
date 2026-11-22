/* Visites stagiaires – interface. Tout reste sur ce Mac : le serveur écoute sur 127.0.0.1. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const app = $("#app");

const S = {
  etat: null,
  visit: null,
  settings: null,
  saving: null,
  segTimer: null,
  saveTimer: null,
  polling: {},
  rec: null,
};

const ETAPES = [
  ["infos", "Infos"],
  ["documents", "Documents"],
  ["entretien", "Entretien"],
  ["transcription", "Transcription"],
  ["analyse", "Analyse"],
  ["bulletin", "Bulletin"],
  ["export", "Export"],
];
const STATUTS = [
  ["temps_plein", "Temps plein"],
  ["mi_temps_diu", "Mi-temps DIU"],
  ["mi_temps_m2", "Mi-temps M2 M2E"],
];
const NIV = ["TI", "I", "S", "TS"];
const NIV_LIB = { TI: "Très insuffisant", I: "Insuffisant", S: "Satisfaisant", TS: "Très satisfaisant" };
const AFAIRE = "À compléter";

/* ------------------------------------------------------------------ API */

async function api(method, url, body, opts = {}) {
  const init = { method, headers: {} };
  if (body instanceof FormData || body instanceof Blob) init.body = body;
  else if (body !== undefined) { init.body = JSON.stringify(body); init.headers["Content-Type"] = "application/json"; }
  const r = await fetch(url, init);
  if (!r.ok) {
    let msg = `Erreur ${r.status}`;
    try { const j = await r.json(); msg = j.detail || msg; } catch (_) {}
    if (!opts.silent) toast(msg, true);
    throw new Error(msg);
  }
  return r.headers.get("content-type")?.includes("json") ? r.json() : r;
}

function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (err ? " erreur" : "");
  t.hidden = false;
  clearTimeout(t._h);
  t._h = setTimeout(() => (t.hidden = true), err ? 7000 : 3000);
}

/* ------------------------------------------------------------------ état (barre du haut) */

async function refreshEtat() {
  try {
    S.etat = await api("GET", "/api/etat", undefined, { silent: true });
  } catch (_) { return; }
  const e = S.etat;
  $("#etat").innerHTML = `
    <span class="pastille ${e.ia.ok ? "ok" : "ko"}" title="${esc(e.ia.message)}">IA ${e.ia.ok ? "prête" : "non prête"}</span>
    <span class="pastille" title="Moteur de transcription local">Transcription : ${esc(e.transcription.modele)}</span>`;
}

/* ------------------------------------------------------------------ routeur */

window.addEventListener("hashchange", route);
window.addEventListener("beforeunload", (e) => {
  if (S.rec && S.rec.mr && S.rec.mr.state !== "inactive") { e.preventDefault(); e.returnValue = ""; }
});

async function route() {
  const h = location.hash.replace(/^#\/?/, "");
  const [page, id, step] = h.split("/");
  $$(".topbar nav a").forEach((a) => a.classList.toggle("actif", a.dataset.nav === (page || "accueil")));
  if (S.rec && S.rec.mr && S.rec.mr.state !== "inactive" && !(page === "visite" && id === S.rec.vid && step === "entretien")) {
    // On ne quitte pas l'écran pendant un enregistrement
    toast("Arrêtez d'abord l'enregistrement en cours.", true);
    location.hash = `#/visite/${S.rec.vid}/entretien`;
    return;
  }
  try {
    if (page === "visite" && id) return await pageVisite(id, step || null);
    if (page === "stagiaires") return await pageStagiaires();
    if (page === "parametres") return await pageParametres();
    return await pageAccueil();
  } catch (err) {
    app.innerHTML = `<div class="erreur">${esc(err.message)}</div><a href="#/" class="btn">Retour à l'accueil</a>`;
  }
}

/* ------------------------------------------------------------------ accueil */

async function pageAccueil() {
  const [visites, stagiaires] = await Promise.all([api("GET", "/api/visites"), api("GET", "/api/stagiaires")]);
  const etapeLib = Object.fromEntries(ETAPES);
  app.innerHTML = `
    <div class="accueil-tete">
      <div><h1>Bonjour</h1><div class="muted">Préparez, enregistrez et rédigez vos visites. Tout reste sur ce Mac.</div></div>
      <span class="espace"></span>
      <button class="btn primaire gros" id="nouvelle">+ Nouvelle visite</button>
    </div>
    ${!S.etat?.ia?.ok ? `<div class="alerte"><b>L'IA locale n'est pas prête :</b> ${esc(S.etat?.ia?.message || "")} Vous pouvez quand même saisir, enregistrer et transcrire.</div>` : ""}
    <div class="carte">
      <div class="ligne" style="margin-bottom:12px"><h2 style="margin:0">Visites</h2><span class="espace"></span>
        <input type="search" id="filtre" placeholder="Rechercher un stagiaire, une école…" style="max-width:280px"></div>
      <div class="liste-visites" id="liste">
        ${visites.length ? visites.map((v) => `
          <a class="visite-ligne" href="#/visite/${v.id}" data-q="${esc((v.stagiaire + " " + v.ecole + " " + v.classe).toLowerCase())}">
            <div style="flex:1"><div class="nom">${esc(v.stagiaire || "Stagiaire sans nom")}${v.numero ? ` <span class="muted">– visite n° ${esc(v.numero)}</span>` : ""}</div>
              <div class="muted small">${esc([dateFr(v.date), v.classe, v.ecole].filter(Boolean).join(" · ") || "Informations à compléter")}</div></div>
            ${v.valide ? `<span class="badge vert">Bulletin validé</span>` : `<span class="badge">${esc(etapeLib[v.etape] || "En cours")}</span>`}
          </a>`).join("") : `<div class="vide">Aucune visite pour l'instant.<br>Cliquez sur « Nouvelle visite » pour commencer.</div>`}
      </div>
    </div>
    <dialog id="dlg">
      <h2>Nouvelle visite</h2>
      <label for="choixStag">Stagiaire</label>
      <select id="choixStag">
        <option value="">— Nouveau stagiaire —</option>
        ${stagiaires.map((s) => `<option value="${esc(s.id)}">${esc(s.nom)}${s.ecole ? " – " + esc(s.ecole) : ""}</option>`).join("")}
      </select>
      <div id="nouveauNom" style="margin-top:12px"><label for="nomStag">Nom et prénom</label><input type="text" id="nomStag" placeholder="NOM Prénom"></div>
      <p class="muted small">Les infos d'un stagiaire déjà enregistré (école, classe…) sont reprises automatiquement.</p>
      <div class="ligne fin"><button class="btn" id="annuler">Annuler</button><button class="btn primaire" id="creer">Créer la visite</button></div>
    </dialog>`;
  const dlg = $("#dlg");
  $("#nouvelle").onclick = () => { dlg.showModal(); $("#nomStag").focus(); };
  $("#annuler").onclick = () => dlg.close();
  $("#choixStag").onchange = (e) => ($("#nouveauNom").hidden = !!e.target.value);
  $("#creer").onclick = async () => {
    const sid = $("#choixStag").value;
    const body = sid ? { stagiaire_id: sid } : { admin: { stagiaire_nom: $("#nomStag").value.trim() } };
    const v = await api("POST", "/api/visites", body);
    dlg.close();
    location.hash = `#/visite/${v.id}/infos`;
  };
  $("#filtre").oninput = (e) => {
    const q = e.target.value.toLowerCase().trim();
    $$("#liste .visite-ligne").forEach((a) => (a.hidden = q && !a.dataset.q.includes(q)));
  };
}

/* ------------------------------------------------------------------ stagiaires */

async function pageStagiaires() {
  const list = await api("GET", "/api/stagiaires");
  app.innerHTML = `
    <h1>Stagiaires</h1><p class="muted">Fiches réutilisées à chaque nouvelle visite (école, classe, statut…).</p>
    <div class="carte">
      ${list.length ? list.map((s) => `
        <div class="audio-ligne">
          <div style="flex:1"><b>${esc(s.nom)}</b><div class="muted small">${esc([libStatut(s.statut), s.classe, s.ecole, s.commune].filter(Boolean).join(" · "))}</div></div>
          <button class="btn mini" data-nv="${esc(s.id)}">Nouvelle visite</button>
          <button class="btn mini" data-edit="${esc(s.id)}">Modifier</button>
          <button class="btn mini danger" data-del="${esc(s.id)}">Supprimer</button>
        </div>`).join("") : `<div class="vide">Aucun stagiaire enregistré.<br>Ajoutez-en un ci-dessous, ou depuis l'étape « Infos » d'une visite.</div>`}
    </div>
    <div class="carte" id="form"></div>`;
  const form = (s = {}) => {
    $("#form").innerHTML = `
      <h2>${s.id ? "Modifier" : "Ajouter"} un stagiaire</h2>
      <div class="grille g3">
        <div class="span3"><label>Nom et prénom</label><input type="text" name="nom" value="${esc(s.nom)}" placeholder="NOM Prénom"></div>
        <div class="span3"><label>Statut</label><div class="choix">${STATUTS.map(([k, l]) => `<label><input type="radio" name="statut" value="${k}" ${s.statut === k ? "checked" : ""}> ${l}</label>`).join("")}</div></div>
        <div><label>Classe</label><input type="text" name="classe" value="${esc(s.classe)}"></div>
        <div><label>Effectif</label><input type="text" name="effectif" value="${esc(s.effectif)}"></div>
        <div><label>Conditions particulières</label><input type="text" name="conditions" value="${esc(s.conditions)}" placeholder="AESH, REP, REP+…"></div>
        <div><label>École</label><input type="text" name="ecole" value="${esc(s.ecole)}"></div>
        <div><label>Circonscription</label><input type="text" name="circonscription" value="${esc(s.circonscription)}"></div>
        <div><label>Commune</label><input type="text" name="commune" value="${esc(s.commune)}"></div>
      </div>
      <div class="ligne fin" style="margin-top:14px">${s.id ? `<button class="btn" id="annulerForm">Annuler</button>` : ""}<button class="btn primaire" id="enreg">Enregistrer</button></div>`;
    $("#enreg").onclick = async () => {
      const item = { ...s };
      $$("#form input[type=text]").forEach((i) => (item[i.name] = i.value.trim()));
      item.statut = $("#form input[name=statut]:checked")?.value || "";
      await api("POST", "/api/stagiaires", item);
      toast("Stagiaire enregistré.");
      pageStagiaires();
    };
    if (s.id) $("#annulerForm").onclick = () => form();
  };
  form();
  app.onclick = async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.edit) form(list.find((s) => s.id === b.dataset.edit));
    if (b.dataset.del && confirm("Supprimer cette fiche stagiaire ? Les visites déjà faites sont conservées.")) {
      await api("DELETE", `/api/stagiaires/${b.dataset.del}`);
      pageStagiaires();
    }
    if (b.dataset.nv) {
      const v = await api("POST", "/api/visites", { stagiaire_id: b.dataset.nv });
      location.hash = `#/visite/${v.id}/infos`;
    }
  };
}

/* ------------------------------------------------------------------ paramètres */

async function pageParametres() {
  const s = await api("GET", "/api/parametres");
  app.onclick = null;
  const modeles = S.etat?.ia?.modeles || [];
  app.innerHTML = `
    <h1>Paramètres</h1><p class="muted">Réglés une fois pour toutes. Ils servent à chaque visite.</p>
    <div class="carte"><h2>Vous</h2>
      <div class="grille g3">
        <div><label>Nom et prénom</label><input type="text" data-k="formatrice.nom" value="${esc(s.formatrice.nom)}"></div>
        <div><label>Qualité</label><input type="text" data-k="formatrice.qualite" value="${esc(s.formatrice.qualite)}" placeholder="PEMF, CPC…"></div>
        <div><label>Lieu (pour les signatures)</label><input type="text" data-k="formatrice.lieu" value="${esc(s.formatrice.lieu)}"></div>
      </div></div>
    <div class="carte"><h2>Grille d'analyse et attentes</h2>
      <div class="aide">C'est ici que vous décrivez une fois pour toutes ce que vous attendez de l'analyse et de la rédaction. L'IA s'en sert à chaque visite.</div>
      <textarea data-k="grille" rows="18">${esc(s.grille)}</textarea>
      <div class="ligne fin" style="margin-top:8px"><button class="btn mini" id="grilleDefaut">Revenir à la grille d'origine</button></div>
    </div>
    <div class="carte"><h2>Vocabulaire du métier</h2>
      <p class="muted small">Aide la transcription à bien écrire les sigles et termes (REP+, AESH, Éduscol…).</p>
      <textarea data-k="vocabulaire" rows="3">${esc(s.vocabulaire)}</textarea></div>
    <div class="carte"><h2>Moteurs locaux</h2>
      <div class="grille g2">
        <div><label>Modèle d'IA (Ollama)</label>
          <input type="text" data-k="ia.modele" value="${esc(s.ia.modele)}" list="listeModeles">
          <datalist id="listeModeles">${modeles.map((m) => `<option value="${esc(m)}">`).join("")}</datalist>
          <div class="muted small">Installés : ${modeles.length ? esc(modeles.join(", ")) : "aucun détecté"}</div></div>
        <div><label>Mémoire de travail de l'IA (contexte)</label>
          <select data-k="ia.contexte">${[8192, 16384, 32768].map((n) => `<option value="${n}" ${+s.ia.contexte === n ? "selected" : ""}>${n} ${n === 16384 ? "(recommandé)" : n === 8192 ? "(Mac 8 Go)" : "(Mac 32 Go et plus)"}</option>`).join("")}</select></div>
        <div><label>Modèle de transcription (Whisper)</label>
          <select data-k="transcription.modele">${["large-v3-turbo", "medium", "small"].map((m) => `<option ${s.transcription.modele === m ? "selected" : ""}>${m}</option>`).join("")}</select>
          <div class="muted small">« large-v3-turbo » : le plus fidèle. « small » : plus rapide, moins précis.</div></div>
        <div><label>Adresse de l'IA</label><input type="text" data-k="ia.url" value="${esc(s.ia.url)}">
          <div class="muted small">Doit rester sur ce Mac (127.0.0.1).</div></div>
      </div></div>
    <div class="carte small muted">Dossier des données : <b>${esc(S.etat?.dossier || "")}</b> — sauvegardez-le régulièrement (Time Machine, clé USB).</div>
    <div class="ligne fin"><button class="btn primaire gros" id="enregParams">Enregistrer les paramètres</button></div>`;
  $("#grilleDefaut").onclick = async () => {
    if (!confirm("Remplacer votre grille par la grille d'origine ?")) return;
    const r = await fetch("/api/parametres", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...s, grille: null }) });
    if (r.ok) { toast("Grille d'origine rétablie."); pageParametres(); }
  };
  $("#enregParams").onclick = async () => {
    const out = JSON.parse(JSON.stringify(s));
    $$("[data-k]").forEach((el) => {
      const path = el.dataset.k.split(".");
      let o = out;
      while (path.length > 1) o = o[path.shift()];
      o[path[0]] = el.dataset.k === "ia.contexte" ? parseInt(el.value, 10) : el.value;
    });
    await api("PUT", "/api/parametres", out);
    toast("Paramètres enregistrés.");
    refreshEtat();
  };
}

/* ------------------------------------------------------------------ visite : cadre */

async function pageVisite(id, step) {
  if (!S.visit || S.visit.id !== id) S.visit = await api("GET", `/api/visites/${id}`);
  else S.visit = await api("GET", `/api/visites/${id}`);
  const v = S.visit;
  step = step || v.etape || "infos";
  if (!ETAPES.some(([k]) => k === step)) step = "infos";
  if (v.etape !== step) { v.etape = step; save({ etape: step }); }
  app.onclick = null;
  app.innerHTML = `
    <div class="visite-tete">
      <div style="flex:1">
        <h1>${esc(v.admin.stagiaire_nom || "Nouvelle visite")}</h1>
        <div class="muted small">${esc([v.admin.numero ? "Visite n° " + v.admin.numero : "", dateFr(v.admin.date), v.admin.classe, v.admin.ecole].filter(Boolean).join(" · "))}</div>
      </div>
      <span class="sauve" id="sauve">Enregistré automatiquement</span>
    </div>
    <nav class="etapes">${ETAPES.map(([k, l], i) => `<a href="#/visite/${v.id}/${k}" class="${k === step ? "actif" : ""} ${etapeFaite(v, k) ? "fait" : ""}"><span class="num">${etapeFaite(v, k) && k !== step ? "✓" : i + 1}</span>${l}</a>`).join("")}</nav>
    <section id="panneau"></section>
    <div class="pied-etape" id="pied"></div>`;
  const idx = ETAPES.findIndex(([k]) => k === step);
  $("#pied").innerHTML = `
    <span>${idx > 0 ? `<a class="btn" href="#/visite/${v.id}/${ETAPES[idx - 1][0]}">← ${ETAPES[idx - 1][1]}</a>` : ""}</span>
    <span>${idx < ETAPES.length - 1 ? `<a class="btn primaire" href="#/visite/${v.id}/${ETAPES[idx + 1][0]}">${ETAPES[idx + 1][1]} →</a>` : ""}</span>`;
  const renderers = { infos: stepInfos, documents: stepDocuments, entretien: stepEntretien, transcription: stepTranscription, analyse: stepAnalyse, bulletin: stepBulletin, export: stepExport };
  renderers[step]($("#panneau"));
  (v.taches || []).forEach((j) => followJob(j));
}

function etapeFaite(v, k) {
  switch (k) {
    case "infos": return !!(v.admin.stagiaire_nom && v.admin.date && v.admin.classe);
    case "documents": return v.documents.length > 0;
    case "entretien": return v.audios.some((a) => a.etat === "pret");
    case "transcription": return v.transcription.segments.length > 0;
    case "analyse": return !!v.analyse.genere;
    case "bulletin": return !!v.bulletin.valide;
    default: return false;
  }
}

/* --- sauvegarde automatique (les champs data-bind modifient S.visit puis on enregistre) */

function save(partial) {
  clearTimeout(S.saveTimer);
  S.pending = { ...(S.pending || {}), ...partial };
  const el = $("#sauve");
  if (el) el.textContent = "Enregistrement…";
  S.saveTimer = setTimeout(flushSave, 500);
}

async function flushSave() {
  const body = S.pending;
  S.pending = null;
  if (!body || !S.visit) return;
  try {
    await api("PUT", `/api/visites/${S.visit.id}`, body);
    const el = $("#sauve");
    if (el) el.textContent = "Enregistré ✓";
  } catch (_) {
    const el = $("#sauve");
    if (el) el.textContent = "Non enregistré !";
  }
}

function getPath(obj, path) { return path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj); }
function setPath(obj, path, val) {
  const ks = path.split(".");
  let o = obj;
  while (ks.length > 1) { const k = ks.shift(); if (o[k] == null) o[k] = /^\d+$/.test(ks[0]) ? [] : {}; o = o[k]; }
  o[ks[0]] = val;
}

/** Relie automatiquement les champs [data-bind="admin.date"] à la visite. */
function bind(root) {
  root.addEventListener("input", (e) => {
    const el = e.target.closest("[data-bind]");
    if (!el) return;
    const path = el.dataset.bind;
    let val = el.value;
    if (el.type === "checkbox") val = el.checked;
    if (el.dataset.list === "lines") val = el.value.split("\n").map((x) => x.replace(/^[-•]\s*/, "").trim()).filter(Boolean);
    setPath(S.visit, path, val);
    const top = path.split(".")[0];
    save({ [top]: S.visit[top] });
    if (el.tagName === "TEXTAREA") autosize(el);
  });
  root.addEventListener("change", (e) => {
    const el = e.target.closest("[data-bind]");
    if (el && el.type === "radio") {
      setPath(S.visit, el.dataset.bind, el.value);
      const top = el.dataset.bind.split(".")[0];
      save({ [top]: S.visit[top] });
    }
  });
  $$("textarea", root).forEach(autosize);
}

function autosize(t) {
  if (!t.classList.contains("auto")) return;
  t.style.height = "auto";
  t.style.height = t.scrollHeight + 2 + "px";
}

/* ------------------------------------------------------------------ étape 1 : infos */

function stepInfos(p) {
  const v = S.visit, a = v.admin;
  if (!a.formateurs.length) a.formateurs.push({ nom: "", qualite: "" });
  const inp = (path, label, ph = "", type = "text") =>
    `<div><label>${label}</label><input type="${type}" data-bind="${path}" value="${esc(getPath(v, path))}" placeholder="${esc(ph)}"></div>`;
  p.innerHTML = `
    <div class="carte"><h2>Le stagiaire et la classe</h2>
      <div class="grille g4">
        <div class="span2"><label>Nom et prénom du stagiaire</label><input type="text" data-bind="admin.stagiaire_nom" value="${esc(a.stagiaire_nom)}" placeholder="NOM Prénom"></div>
        ${inp("admin.numero", "N° de visite", "1, 2, 3…")}
        ${inp("admin.date", "Date", "", "date")}
        <div class="span4"><label>Statut</label><div class="choix">${STATUTS.map(([k, l]) => `<label><input type="radio" name="statut" data-bind="admin.statut" value="${k}" ${a.statut === k ? "checked" : ""}> ${l}</label>`).join("")}</div></div>
        ${inp("admin.horaire", "Horaire", "8h30 – 10h00")}
        ${inp("admin.classe", "Classe", "CE1, GS/CP…")}
        ${inp("admin.effectif", "Effectif", "24")}
        ${inp("admin.conditions", "Conditions particulières", "AESH, REP, REP+…")}
        <div class="span2">${inp("admin.ecole", "École")}</div>
        ${inp("admin.circonscription", "Circonscription")}
        ${inp("admin.commune", "Commune")}
      </div>
      <div class="ligne" style="margin-top:12px"><button class="btn mini" id="memoStag">Enregistrer ces infos dans la fiche du stagiaire</button><span class="muted small">pour les retrouver à la prochaine visite</span></div>
    </div>
    <div class="carte"><h2>Formateur(s)</h2>
      <div id="formateurs">${a.formateurs.map((f, i) => `
        <div class="grille g3" style="margin-bottom:8px;align-items:end">
          <div><label>Nom et prénom</label><input type="text" data-bind="admin.formateurs.${i}.nom" value="${esc(f.nom)}"></div>
          <div><label>Qualité</label><input type="text" data-bind="admin.formateurs.${i}.qualite" value="${esc(f.qualite)}" placeholder="PEMF, CPC, formateur INSPE…"></div>
          <div>${i > 0 ? `<button class="btn mini danger" data-suppr-form="${i}">Retirer</button>` : ""}</div>
        </div>`).join("")}</div>
      ${a.formateurs.length < 3 ? `<button class="btn mini" id="ajFormateur">+ Ajouter un formateur</button>` : ""}
      <div style="margin-top:12px;max-width:320px">${inp("admin.lieu", "Lieu (signatures)")}</div>
    </div>
    <div class="carte"><h2>Outils présentés</h2>
      <div class="cases">${(S.etat?.outils || []).map((o) => `<label><input type="checkbox" data-bind="outils.${o.cle}" ${v.outils[o.cle] ? "checked" : ""}> ${esc(o.libelle)}</label>`).join("")}</div>
    </div>
    <div class="carte"><h2>Vos notes d'observation de la séance</h2>
      <div class="aide">Notez ici ce que vous observez pendant la séance (déroulement, minutage, points marquants). L'IA s'en servira, au même titre que l'entretien.</div>
      <textarea class="auto" rows="8" data-bind="notes_formatrice" placeholder="Ex. : 8h35 rituel de calcul mental, ardoises, très dynamique…">${esc(v.notes_formatrice)}</textarea>
    </div>`;
  bind(p);
  $("#ajFormateur") && ($("#ajFormateur").onclick = () => { a.formateurs.push({ nom: "", qualite: "" }); save({ admin: a }); stepInfos(p); });
  p.onclick = (e) => {
    const b = e.target.closest("[data-suppr-form]");
    if (b) { a.formateurs.splice(+b.dataset.supprForm, 1); save({ admin: a }); stepInfos(p); }
  };
  $("#memoStag").onclick = async () => { await flushSave(); await api("POST", `/api/visites/${v.id}/stagiaire`); toast("Fiche stagiaire enregistrée."); };
}

/* ------------------------------------------------------------------ étape 2 : documents */

function stepDocuments(p) {
  const v = S.visit;
  const typeLib = { seance: "Fiche de séance", sequence: "Fiche de séquence", autre: "Document complémentaire" };
  p.innerHTML = `
    <div class="carte"><h2>Documents de la stagiaire</h2>
      <div class="aide">Importez la fiche de préparation de séance, la fiche de séquence et les documents complémentaires (Word ou PDF). L'appli reconnaît le type de chaque fiche ; vous pouvez le corriger.</div>
      <div id="jobZone"></div>
      <label class="depot" id="depot">
        <input type="file" id="fichiers" multiple accept=".docx,.pdf,.txt,.odt" hidden>
        <b>Glissez les fichiers ici</b> ou cliquez pour les choisir<br><span class="muted small">Word (.docx), PDF, texte</span>
      </label>
      ${v.documents.map((d) => `
        <div class="doc">
          <div class="ligne">
            <span class="titre">${esc(d.nom)}</span>
            <span class="espace"></span>
            <select data-type="${d.id}" style="width:auto">${Object.entries(typeLib).map(([k, l]) => `<option value="${k}" ${d.type === k ? "selected" : ""}>${l}</option>`).join("")}</select>
            <button class="btn mini danger" data-suppr="${d.id}">Retirer</button>
          </div>
          ${!d.texte ? `<div class="alerte" style="margin:8px 0 0">Texte illisible : document scanné ou protégé. Demandez la version Word.</div>` : ""}
          ${d.analyse ? docAnalyse(d.analyse) : ""}
          ${d.texte ? `<details><summary class="small muted">Voir le texte extrait (${d.texte.length} caractères)</summary><pre>${esc(d.texte)}</pre></details>` : ""}
        </div>`).join("")}
      ${v.documents.some((d) => d.texte) ? `<div class="ligne" style="margin-top:14px"><button class="btn primaire" id="analyserDocs">${v.documents.some((d) => d.analyse) ? "Relire" : "Lire"} les documents avec l'IA</button><span class="muted small">extrait objectifs, compétences et déroulement prévu</span></div>` : ""}
    </div>`;
  const depot = $("#depot"), input = $("#fichiers");
  input.onchange = () => upload(input.files);
  ["dragenter", "dragover"].forEach((ev) => depot.addEventListener(ev, (e) => { e.preventDefault(); depot.classList.add("survol"); }));
  ["dragleave", "drop"].forEach((ev) => depot.addEventListener(ev, (e) => { e.preventDefault(); depot.classList.remove("survol"); }));
  depot.addEventListener("drop", (e) => upload(e.dataTransfer.files));
  async function upload(files) {
    if (!files.length) return;
    const fd = new FormData();
    [...files].forEach((f) => fd.append("fichiers", f));
    const r = await api("POST", `/api/visites/${v.id}/documents`, fd);
    S.visit = { ...r.visite, taches: S.visit.taches };
    if (r.erreurs.length) toast(r.erreurs.join(" "), true);
    stepDocuments(p);
  }
  p.onchange = async (e) => {
    const s = e.target.closest("[data-type]");
    if (s) { S.visit = await api("PATCH", `/api/visites/${v.id}/documents/${s.dataset.type}`, { type: s.value }); toast("Type mis à jour."); }
  };
  p.onclick = async (e) => {
    const b = e.target.closest("[data-suppr]");
    if (b && confirm("Retirer ce document ?")) { S.visit = await api("DELETE", `/api/visites/${v.id}/documents/${b.dataset.suppr}`); stepDocuments(p); }
  };
  $("#analyserDocs") && ($("#analyserDocs").onclick = () => startJob(`/api/visites/${v.id}/documents/analyser`));
}

function docAnalyse(a) {
  const rows = [
    ["Discipline", a.discipline], ["Niveau", a.niveau], ["Titre", a.titre],
    ["Objectifs", (a.objectifs || []).join(" ; ")], ["Compétences", (a.competences || []).join(" ; ")],
    ["Déroulement prévu", (a.deroulement || []).map((d) => `${d.temps} – ${d.deroulement}`).join(" | ")],
    ["Modalités", a.modalites], ["Résumé", a.resume],
  ].filter(([, x]) => x);
  return `<dl class="extrait-doc">${rows.map(([k, x]) => `<dt>${k}</dt><dd>${esc(x)}</dd>`).join("")}</dl>`;
}

/* ------------------------------------------------------------------ étape 3 : entretien (enregistrement) */

function stepEntretien(p) {
  const v = S.visit;
  const recActif = S.rec && S.rec.vid === v.id && S.rec.mr && S.rec.mr.state !== "inactive";
  const orphelins = v.audios.filter((a) => a.etat === "en_cours" && !(recActif && S.rec.id === a.id));
  p.innerHTML = `
    <div class="carte"><h2>Enregistrer l'entretien</h2>
      <div class="aide">Posez le Mac entre vous deux, branché sur secteur, couvercle ouvert. L'enregistrement est sauvegardé sur le Mac toutes les 5 secondes : rien n'est perdu en cas de souci.</div>
      <div class="enregistreur">
        <span class="voyant" id="voyant"></span>
        <span class="chrono" id="chrono">00:00</span>
        <div><div class="niveau"><div id="niveau"></div></div><div class="muted small" style="margin-top:4px">niveau du micro</div></div>
        <span class="espace"></span>
        <button class="btn primaire gros" id="recStart">● Démarrer</button>
        <button class="btn gros" id="recPause" hidden>❚❚ Pause</button>
        <button class="btn gros" id="recResume" hidden>▶ Reprendre</button>
        <button class="btn gros danger" id="recStop" hidden>■ Arrêter</button>
      </div>
      <div id="recMsg" class="muted small" style="margin-top:8px"></div>
    </div>
    ${orphelins.length ? `<div class="alerte">Un enregistrement a été interrompu (fenêtre fermée ?). Le son déjà capté est conservé.
      ${orphelins.map((a) => `<button class="btn mini" data-recup="${a.id}">Récupérer « ${esc(a.nom)} »</button>`).join(" ")}</div>` : ""}
    <div class="carte"><h2>Enregistrements de cette visite</h2>
      ${v.audios.filter((a) => a.etat === "pret").map((a) => `
        <div class="audio-ligne">
          <div style="min-width:220px"><b>${esc(a.nom)}</b><div class="muted small">${hms(a.duree)}</div></div>
          <audio controls preload="metadata" src="/api/visites/${v.id}/audios/${a.id}"></audio>
          <button class="btn mini danger" data-suppr-audio="${a.id}">Supprimer</button>
        </div>`).join("") || `<p class="muted">Aucun enregistrement pour l'instant.</p>`}
      <div class="ligne" style="margin-top:14px">
        <label class="btn" style="margin:0">Importer un fichier audio<input type="file" id="importAudio" accept="audio/*,video/*,.m4a,.mp3,.wav,.webm" hidden></label>
        <span class="muted small">par exemple un mémo vocal de l'iPhone (m4a)</span>
      </div>
    </div>`;
  if (recActif) S.rec.attach();
  else majBoutonsRec("stop");
  $("#recStart").onclick = () => demarrerEnregistrement(v.id);
  $("#recPause").onclick = () => { S.rec.mr.pause(); S.rec.pause(); majBoutonsRec("pause"); };
  $("#recResume").onclick = () => { S.rec.mr.resume(); S.rec.resume(); majBoutonsRec("rec"); };
  $("#recStop").onclick = () => S.rec.stop();
  $("#importAudio").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("fichier", f);
    $("#recMsg").textContent = "Import en cours…";
    S.visit = await api("POST", `/api/visites/${v.id}/audios`, fd);
    toast("Fichier audio importé.");
    stepEntretien(p);
  };
  p.onclick = async (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.supprAudio && confirm("Supprimer cet enregistrement ? Sa transcription sera aussi supprimée.")) {
      S.visit = await api("DELETE", `/api/visites/${v.id}/audios/${b.dataset.supprAudio}`);
      stepEntretien(p);
    }
    if (b.dataset.recup) {
      S.visit = await api("POST", `/api/visites/${v.id}/enregistrement/${b.dataset.recup}/fin`);
      toast("Enregistrement récupéré.");
      stepEntretien(p);
    }
  };
}

function majBoutonsRec(mode) {
  const show = { stop: ["recStart"], rec: ["recPause", "recStop"], pause: ["recResume", "recStop"] }[mode];
  ["recStart", "recPause", "recResume", "recStop"].forEach((id) => { const b = $("#" + id); if (b) b.hidden = !show.includes(id); });
  const voy = $("#voyant"), chrono = $("#chrono");
  if (voy) voy.className = "voyant " + (mode === "stop" ? "" : mode);
  if (chrono) chrono.classList.toggle("rec", mode === "rec");
}

async function demarrerEnregistrement(vid) {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    toast("Ce navigateur ne permet pas d'enregistrer. Utilisez Safari ou Chrome à jour.", true);
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: true, autoGainControl: true } });
  } catch (err) {
    toast("Micro refusé. Autorisez le micro pour cette page (Réglages Système > Confidentialité > Micro), puis réessayez.", true);
    return;
  }
  const mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm", "audio/ogg;codecs=opus"].find((m) => MediaRecorder.isTypeSupported(m)) || "";
  const entry = await api("POST", `/api/visites/${vid}/enregistrement`, { mime });
  const mr = new MediaRecorder(stream, mime ? { mimeType: mime, audioBitsPerSecond: 96000 } : undefined);
  let queue = Promise.resolve(), enAttente = 0, echecs = 0, cumul = 0, debut = Date.now(), raf = null, wake = null, dernierSon = Date.now();
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  ctx.createMediaStreamSource(stream).connect(analyser);
  const buf = new Uint8Array(analyser.fftSize);

  const envoyer = async (blob) => {
    for (let essai = 0; essai < 5; essai++) {
      try {
        const r = await fetch(`/api/visites/${vid}/enregistrement/${entry.id}/morceau`, { method: "POST", body: blob });
        if (r.ok) { echecs = 0; return; }
      } catch (_) {}
      await new Promise((res) => setTimeout(res, 1000 * (essai + 1)));
    }
    echecs++;
    const m = $("#recMsg");
    if (m) m.innerHTML = `<span style="color:var(--rouge)">Attention : un morceau n'a pas pu être sauvegardé. Vérifiez que la fenêtre noire de l'application est toujours ouverte.</span>`;
  };
  mr.ondataavailable = (e) => {
    if (!e.data || !e.data.size) return;
    enAttente++;
    queue = queue.then(() => envoyer(e.data)).finally(() => enAttente--);
  };
  const tick = () => {
    const t = cumul + (mr.state === "recording" ? Date.now() - debut : 0);
    const c = $("#chrono");
    if (c) c.textContent = hms(t / 1000);
    analyser.getByteTimeDomainData(buf);
    let max = 0;
    for (const x of buf) max = Math.max(max, Math.abs(x - 128));
    const n = $("#niveau");
    if (n) n.style.width = Math.min(100, (max / 128) * 160) + "%";
    // Sécurité : si le micro ne capte rien pendant 8 secondes, on prévient tout de suite.
    if (max > 3 || mr.state !== "recording") dernierSon = Date.now();
    const msg = $("#recMsg");
    if (msg) {
      const muet = Date.now() - dernierSon > 8000;
      if (muet && !msg.dataset.muet) { msg.dataset.muet = "1"; msg.innerHTML = `<span style="color:var(--rouge);font-weight:600">Le micro ne capte aucun son depuis 8 secondes. Vérifiez le micro choisi (Réglages Système > Son > Entrée).</span>`; }
      if (!muet && msg.dataset.muet) { delete msg.dataset.muet; msg.textContent = "Enregistrement en cours. Le son est bien capté."; }
    }
    raf = requestAnimationFrame(tick);
  };
  try { wake = await navigator.wakeLock?.request("screen"); } catch (_) {}

  S.rec = {
    vid, id: entry.id, mr,
    pause() { cumul += Date.now() - debut; },
    resume() { debut = Date.now(); },
    attach() { majBoutonsRec(mr.state === "paused" ? "pause" : "rec"); },
    async stop() {
      const m = $("#recMsg");
      if (m) m.textContent = "Finalisation de l'enregistrement…";
      await new Promise((res) => { mr.onstop = res; mr.stop(); });
      await queue;
      cancelAnimationFrame(raf);
      stream.getTracks().forEach((t) => t.stop());
      ctx.close();
      try { wake && wake.release(); } catch (_) {}
      S.rec = null;
      S.visit = await api("POST", `/api/visites/${vid}/enregistrement/${entry.id}/fin`);
      toast("Enregistrement sauvegardé sur le Mac.");
      if (location.hash.includes(`/visite/${vid}/entretien`)) stepEntretien($("#panneau"));
    },
  };
  mr.start(5000);
  debut = Date.now();
  majBoutonsRec("rec");
  tick();
  const m = $("#recMsg");
  if (m) m.textContent = "Enregistrement en cours. Pensez à prévenir la stagiaire.";
}

/* ------------------------------------------------------------------ étape 4 : transcription */

function stepTranscription(p) {
  const v = S.visit;
  const segs = v.transcription.segments;
  const prets = v.audios.filter((a) => a.etat === "pret");
  const partiel = prets.some((a) => !(v.transcription.progression || {})[a.id]) && segs.length > 0;
  const nbQ = segs.filter((s) => s.locuteur === "?").length;
  p.innerHTML = `
    <div class="carte"><h2>Transcription</h2>
      <div id="jobZone"></div>
      ${!prets.length ? `<div class="alerte">Enregistrez ou importez d'abord l'entretien (étape « Entretien »).</div>` : ""}
      <div class="outils-trans">
        ${prets.length && !segs.length ? `<button class="btn primaire" id="transcrire">Lancer la transcription</button><span class="muted small">Sur ce Mac, sans Internet. Comptez quelques minutes pour 45 min d'entretien.</span>` : ""}
        ${segs.length ? `
          <button class="btn" id="transcrire">${partiel ? "Reprendre / compléter la transcription" : "Transcrire les nouveaux enregistrements"}</button>
          <button class="btn" id="locuteurs">Identifier qui parle (IA)</button>
          <button class="btn" id="corriger">Corriger les fautes évidentes (IA)</button>
          <span class="espace"></span>
          <button class="btn lien danger" id="recommencer">Tout retranscrire à nouveau</button>` : ""}
      </div>
      ${segs.length ? `
        <div class="legende" style="margin-bottom:8px">
          <span>Cliquez sur l'heure pour réécouter.</span>
          <span>Cliquez sur l'étiquette pour changer d'interlocuteur.</span>
          <span>⊘ = passage hors sujet (écarté du compte rendu).</span>
          ${nbQ ? `<span class="badge orange">${nbQ} passage(s) sans interlocuteur</span>` : ""}
        </div>
        <div id="segs">${segs.map((s, i) => segHtml(s, i)).join("")}</div>` : ""}
    </div>`;
  $$("#segs textarea").forEach((t) => { t.classList.add("auto"); autosize(t); });
  const on = (id, fn) => $("#" + id) && ($("#" + id).onclick = fn);
  on("transcrire", () => startJob(`/api/visites/${v.id}/transcrire`, {}));
  on("recommencer", () => confirm("Effacer la transcription actuelle (et vos corrections) et tout retranscrire ?") && startJob(`/api/visites/${v.id}/transcrire`, { recommencer: true }));
  on("locuteurs", () => startJob(`/api/visites/${v.id}/interlocuteurs`));
  on("corriger", () => startJob(`/api/visites/${v.id}/corriger`));
  const zone = $("#segs");
  if (!zone) return;
  zone.addEventListener("input", (e) => {
    const t = e.target.closest("textarea[data-i]");
    if (!t) return;
    const s = segs[+t.dataset.i];
    s.texte = t.value;
    s.verrouille = true;
    autosize(t);
    saveSegments();
  });
  zone.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    const i = +b.dataset.i, s = segs[i];
    if (b.classList.contains("t")) jouer(s);
    if (b.classList.contains("loc")) {
      s.locuteur = { "?": "F", F: "S", S: "F" }[s.locuteur || "?"];
      s.verrouille = true;
      b.className = "loc " + s.locuteur;
      b.textContent = libLoc(s.locuteur);
      saveSegments();
    }
    if (b.classList.contains("hsbtn")) {
      s.hors_sujet = !s.hors_sujet;
      s.verrouille = true;
      b.classList.toggle("on", s.hors_sujet);
      b.closest(".seg").classList.toggle("hs", s.hors_sujet);
      saveSegments();
    }
    if (b.dataset.annuler !== undefined) {
      s.texte = s.texte_original;
      delete s.texte_original;
      saveSegments();
      stepTranscription(p);
    }
  });
}

function segHtml(s, i) {
  return `<div class="seg ${s.hors_sujet ? "hs" : ""}">
    <button class="t" data-i="${i}" title="Réécouter">${hms(s.debut)}</button>
    <div><button class="loc ${s.locuteur}" data-i="${i}">${libLoc(s.locuteur)}</button></div>
    <div><textarea rows="1" data-i="${i}">${esc(s.texte)}</textarea>
      ${s.texte_original ? `<div class="corr">corrigé par l'IA · <button class="btn lien mini" data-i="${i}" data-annuler>revenir au texte d'origine</button></div>` : ""}</div>
    <button class="hsbtn ${s.hors_sujet ? "on" : ""}" data-i="${i}" title="Marquer hors sujet">⊘</button>
  </div>`;
}

const libLoc = (l) => ({ F: "Formatrice", S: "Stagiaire" }[l] || "? qui parle");

function saveSegments() {
  clearTimeout(S.segTimer);
  const el = $("#sauve");
  if (el) el.textContent = "Enregistrement…";
  S.segTimer = setTimeout(async () => {
    try {
      await api("PUT", `/api/visites/${S.visit.id}`, { segments: S.visit.transcription.segments });
      const el = $("#sauve");
      if (el) el.textContent = "Enregistré ✓";
    } catch (_) {}
  }, 700);
}

function jouer(s) {
  const a = $("#lecteur");
  const src = `/api/visites/${S.visit.id}/audios/${s.audio}`;
  if (!a.src.endsWith(src)) a.src = src;
  const go = () => { a.currentTime = Math.max(0, (s.debut_audio ?? s.debut) - 0.3); a.play(); };
  if (a.readyState >= 1) go(); else a.addEventListener("loadedmetadata", go, { once: true });
  a.load && a.readyState < 1 && a.load();
}

/* ------------------------------------------------------------------ étape 5 : analyse */

const GROUPES = {
  A: ["Points relevés par la stagiaire", { constats: "Ses constats", reussites: "Réussites identifiées", difficultes: "Difficultés rencontrées", analyse_pratique: "Analyse de sa pratique", questionnements: "Questionnements", propositions: "Propositions d'amélioration" }],
  B: ["Points relevés par la formatrice", { points_forts: "Points forts observés", competences_maitrisees: "Compétences maîtrisées", difficultes: "Difficultés constatées", axes_amelioration: "Axes d'amélioration", accompagnement: "Éléments nécessitant un accompagnement" }],
  C: ["Conseils prodigués par la formatrice", { conseils_pedagogiques: "Conseils pédagogiques", preconisations: "Préconisations méthodologiques", remediations: "Pistes de remédiation", ressources: "Supports et ressources conseillés", perspectives: "Perspectives de progression" }],
};

function stepAnalyse(p) {
  const v = S.visit, an = v.analyse;
  const nbKo = Object.keys(GROUPES).reduce((n, g) => n + Object.keys(GROUPES[g][1]).reduce((m, k) => m + (an[g]?.[k] || []).filter((it) => !it.verifie).length, 0), 0);
  const nbQ = v.transcription.segments.filter((s) => s.locuteur === "?" && !s.hors_sujet).length;
  p.innerHTML = `
    <div class="carte"><h2>Analyse réflexive</h2>
      <div id="jobZone"></div>
      <div class="aide">L'IA classe ce qui a été dit selon votre grille (Paramètres). Chaque point cite un extrait : s'il est introuvable dans l'entretien, le point est signalé en orange. Vérifiez-le ou supprimez-le.</div>
      ${nbQ ? `<div class="alerte">${nbQ} passage(s) n'ont pas d'interlocuteur. Pour une analyse juste, identifiez d'abord qui parle (étape Transcription).</div>` : ""}
      <div class="ligne"><button class="btn primaire" id="generer">${an.genere ? "Régénérer l'analyse" : "Générer l'analyse"}</button>
        ${an.genere ? `<span class="muted small">Générée le ${esc(new Date(an.genere).toLocaleString("fr-FR"))}${nbKo ? ` · <span class="badge orange">${nbKo} point(s) à vérifier</span>` : ""}</span>` : ""}</div>
    </div>
    ${an.genere || an.D ? `
      ${Object.entries(GROUPES).map(([g, [titre, rubs]]) => `
        <div class="carte"><h2>${g}. ${titre}</h2>
          ${Object.entries(rubs).map(([k, lib]) => `
            <div class="rubrique"><div class="titre">${lib}</div>
              ${(an[g]?.[k] || []).map((it, i) => `
                <div class="item ${it.verifie ? "" : "ko"}">
                  <textarea class="auto" rows="1" data-bind="analyse.${g}.${k}.${i}.texte">${esc(it.texte)}</textarea>
                  <button class="btn mini danger" data-del="${g}.${k}.${i}" title="Supprimer">✕</button>
                  ${it.extrait ? `<div class="src ${it.verifie ? "" : "ko"}">${it.verifie ? "Source" : "⚠ Extrait introuvable dans l'entretien, à vérifier"} : « ${esc(it.extrait)} »</div>` : `<div class="src ko">⚠ Sans extrait cité, à vérifier</div>`}
                </div>`).join("") || `<div class="muted small">Rien de relevé.</div>`}
              <button class="btn lien mini" data-add="${g}.${k}">+ ajouter</button>
            </div>`).join("")}
        </div>`).join("")}
      <div class="carte"><h2>D. Bilan réflexif</h2>
        <textarea class="auto" rows="10" data-bind="analyse.D" placeholder="${AFAIRE}">${esc(an.D)}</textarea></div>` : ""}`;
  bind(p);
  $("#generer").onclick = () => (!an.genere || confirm("Remplacer l'analyse actuelle (et vos modifications) ?")) && startJob(`/api/visites/${v.id}/analyser`);
  p.onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.del) {
      const [g, k, i] = b.dataset.del.split(".");
      an[g][k].splice(+i, 1);
      save({ analyse: an });
      stepAnalyse(p);
    }
    if (b.dataset.add) {
      const [g, k] = b.dataset.add.split(".");
      an[g] = an[g] || {};
      (an[g][k] = an[g][k] || []).push({ texte: "", extrait: "Ajouté par la formatrice", verifie: true });
      save({ analyse: an });
      stepAnalyse(p);
    }
  };
}

/* ------------------------------------------------------------------ étape 6 : bulletin */

function stepBulletin(p) {
  const v = S.visit, b = v.bulletin;
  while (b.points.length < 3) b.points.push({ titre: "", analyse: "", ressources: "" });
  const m2 = v.admin.statut === "mi_temps_m2";
  const radios = (path, cur) => `<div class="niveaux">${NIV.map((n) => `<label title="${NIV_LIB[n]}"><input type="radio" name="${path}" data-bind="${path}" value="${n}" ${cur === n ? "checked" : ""}>${n}</label>`).join("")}
    <button class="btn lien mini" data-efface="${path}">effacer</button></div>`;
  p.innerHTML = `
    <div class="carte"><h2>Bulletin de visite</h2>
      <div id="jobZone"></div>
      <div class="aide">L'IA propose les rubriques à partir des fiches, de vos notes et de l'analyse. Le positionnement, la note et la maîtrise de la langue restent votre décision. Un champ vide reste vide sur le bulletin.</div>
      <div class="ligne"><button class="btn primaire" id="preremplir">${b.prerempli ? "Préremplir à nouveau" : "Préremplir le bulletin"}</button>
        ${!v.analyse.genere ? `<span class="muted small">Conseil : générez d'abord l'analyse (étape précédente).</span>` : ""}</div>
    </div>
    <div class="carte"><h2>Enseignements observés ce jour</h2>
      <label>Domaine ou discipline, objectifs de la (des) séance(s)</label>
      <textarea class="auto" rows="2" data-bind="bulletin.enseignements" placeholder="${AFAIRE}">${esc(b.enseignements)}</textarea>
      <label style="margin-top:12px">Description de la (des) séance(s) présentée(s)</label>
      <textarea class="auto" rows="4" data-bind="bulletin.description" placeholder="${AFAIRE}">${esc(b.description)}</textarea>
      <h3>Déroulement</h3>
      <table class="table-der"><thead><tr><th style="width:16%">Temps (minutage/phase)</th><th>Déroulement</th><th style="width:16%">Dispositif</th><th style="width:20%">Organisation matérielle</th><th style="width:34px"></th></tr></thead>
        <tbody>${b.deroulement.map((r, i) => `<tr>${["temps", "deroulement", "dispositif", "organisation"].map((k) => `<td><textarea class="auto" rows="2" data-bind="bulletin.deroulement.${i}.${k}">${esc(r[k])}</textarea></td>`).join("")}<td><button class="btn mini danger" data-del-row="${i}">✕</button></td></tr>`).join("")}</tbody></table>
      <button class="btn mini" id="ajLigne" style="margin-top:6px">+ Ajouter une phase</button>
    </div>
    <div class="carte"><h2>Remarques et conseils portant sur la (les) séance(s)</h2>
      ${b.points.slice(0, 3).map((pt, i) => `
        <div class="point"><h4>POINT DISCUTÉ ${i + 1}</h4>
          <div class="grille" style="gap:8px">
            <div><label>Intitulé</label><input type="text" data-bind="bulletin.points.${i}.titre" value="${esc(pt.titre)}" placeholder="${AFAIRE}"></div>
            <div><label>Éléments d'analyse et conseils</label><textarea class="auto" rows="3" data-bind="bulletin.points.${i}.analyse" placeholder="${AFAIRE}">${esc(pt.analyse)}</textarea></div>
            <div><label>Supports et ressources conseillés</label><textarea class="auto" rows="1" data-bind="bulletin.points.${i}.ressources" placeholder="${AFAIRE}">${esc(pt.ressources)}</textarea></div>
          </div></div>`).join("")}
    </div>
    <div class="carte"><h2>Avis sur le déroulement de l'entretien</h2>
      <div class="grille g2">
        <div><label>Points positifs (un par ligne)</label><textarea class="auto" rows="4" data-bind="bulletin.positifs" data-list="lines" placeholder="${AFAIRE}">${esc(b.positifs.join("\n"))}</textarea></div>
        <div><label>Points à améliorer (un par ligne)</label><textarea class="auto" rows="4" data-bind="bulletin.ameliorer" data-list="lines" placeholder="${AFAIRE}">${esc(b.ameliorer.join("\n"))}</textarea></div>
      </div></div>
    <div class="carte"><h2>Maîtrise de la langue</h2>
      <div class="grille g2">
        <div><label>Orale</label>${radios("bulletin.langue.orale", b.langue.orale)}</div>
        <div><label>Écrite</label>${radios("bulletin.langue.ecrite", b.langue.ecrite)}</div>
        <div class="span2"><label>Observations</label><textarea class="auto" rows="2" data-bind="bulletin.langue.observations" placeholder="${AFAIRE}">${esc(b.langue.observations)}</textarea></div>
      </div></div>
    <div class="carte"><h2>Évaluation (votre décision)</h2>
      <div class="grille g2">
        <div><label>Positionnement</label>${radios("bulletin.positionnement", b.positionnement)}
          <div class="muted small" style="margin-top:6px">TI : de 0 à 4 · I : de 6 à 10 · S : de 11 à 14 · TS : de 15 à 17</div></div>
        ${m2 ? `<div><label>Proposition de note M2 M2E (sur 20)</label><input type="number" min="0" max="20" step="0.5" data-bind="bulletin.note" value="${esc(b.note)}" style="max-width:120px"></div>` : `<div class="muted small">La note sur 20 ne concerne que le statut « mi-temps M2 M2E ».</div>`}
        <div><label>Date des signatures</label><input type="date" data-bind="bulletin.date_signature" value="${esc(b.date_signature || v.admin.date)}" style="max-width:200px"></div>
      </div>
      ${b.positionnement && m2 && b.note !== "" && !noteCoherente(b.positionnement, +b.note) ? `<div class="alerte" style="margin-top:12px">La note ${esc(b.note)} ne correspond pas à la fourchette du positionnement ${esc(b.positionnement)}.</div>` : ""}
      <div class="valider"><label><input type="checkbox" data-bind="bulletin.valide" ${b.valide ? "checked" : ""}> J'ai relu l'ensemble et je valide ce bulletin.</label></div>
    </div>`;
  bind(p);
  $("#preremplir").onclick = () => (!b.prerempli || confirm("Remplacer les rubriques déjà rédigées par une nouvelle proposition ? (positionnement, note et langue sont conservés)")) && startJob(`/api/visites/${v.id}/preremplir`);
  $("#ajLigne").onclick = () => { b.deroulement.push({ temps: "", deroulement: "", dispositif: "", organisation: "" }); save({ bulletin: b }); stepBulletin(p); };
  p.onclick = (e) => {
    const x = e.target.closest("button");
    if (!x) return;
    if (x.dataset.delRow) { b.deroulement.splice(+x.dataset.delRow, 1); save({ bulletin: b }); stepBulletin(p); }
    if (x.dataset.efface) { setPath(v, x.dataset.efface, ""); save({ bulletin: b }); stepBulletin(p); }
  };
}

function noteCoherente(pos, note) {
  const r = { TI: [0, 4], I: [6, 10], S: [11, 14], TS: [15, 17] }[pos];
  return !r || (note >= r[0] && note <= r[1]);
}

/* ------------------------------------------------------------------ étape 7 : export */

async function stepExport(p) {
  const v = S.visit;
  await flushSave();
  const manque = await api("GET", `/api/visites/${v.id}/manquants`);
  const choix = [
    ["bulletin_docx", "Bulletin officiel complété (Word)", true],
    ["bulletin_pdf", "Bulletin officiel (PDF)", S.etat?.pdf],
    ["transcription", "Retranscription intégrale de l'entretien (Word)", true],
    ["bilan", "Bilan réflexif détaillé (Word)", true],
    ["synthese", "Synthèse : points forts, axes d'amélioration, conseils (Word)", true],
  ];
  p.innerHTML = `
    <div class="carte"><h2>Exporter les documents</h2>
      ${!v.bulletin.valide ? `<div class="alerte">Le bulletin n'est pas encore marqué comme validé (étape Bulletin).</div>` : `<div class="succes">Bulletin validé.</div>`}
      ${manque.length ? `<div class="alerte"><b>Rubriques vides</b> (elles resteront vides sur le bulletin) : ${esc(manque.join(", "))}.</div>` : ""}
      <div class="cases" style="grid-template-columns:1fr">
        ${choix.map(([k, l, ok]) => `<label><input type="checkbox" value="${k}" ${ok ? "checked" : "disabled"}> ${l}${!ok ? ` <span class="muted small">— installez LibreOffice ou Word pour le PDF</span>` : ""}</label>`).join("")}
      </div>
      <div class="ligne" style="margin-top:14px"><button class="btn primaire gros" id="exporter">Créer les documents</button></div>
    </div>
    <div id="resultat"></div>`;
  $("#exporter").onclick = async () => {
    const types = $$("input[type=checkbox]:checked", p).map((c) => c.value);
    if (!types.length) return toast("Cochez au moins un document.", true);
    $("#exporter").disabled = true;
    $("#exporter").textContent = "Création…";
    try {
      const r = await api("POST", `/api/visites/${v.id}/exporter`, { types });
      $("#resultat").innerHTML = `<div class="carte"><h2>Documents prêts</h2>
        ${r.erreurs.map((e) => `<div class="erreur">${esc(e)}</div>`).join("")}
        <div class="fichiers">${r.fichiers.map((f) => `<a href="/api/visites/${v.id}/fichiers/${encodeURIComponent(f)}" download>📄 <span style="flex:1">${esc(f)}</span><span class="muted small">Télécharger</span></a>`).join("")}</div>
        <div class="ligne"><button class="btn" id="ouvrir">Ouvrir le dossier dans le Finder</button><span class="muted small">${esc(r.dossier)}</span></div></div>`;
      $("#ouvrir").onclick = () => api("POST", `/api/visites/${v.id}/ouvrir-dossier`);
    } finally {
      $("#exporter").disabled = false;
      $("#exporter").textContent = "Créer les documents";
    }
  };
}

/* ------------------------------------------------------------------ tâches longues */

async function startJob(url, body) {
  await flushSave();
  const job = await api("POST", url, body ?? {});
  followJob(job);
}

function followJob(job) {
  if (S.polling[job.id]) return;
  const LIB = { transcription: "Transcription", interlocuteurs: "Identification des interlocuteurs", corrections: "Correction", analyse: "Analyse réflexive", bulletin: "Préremplissage du bulletin", documents: "Lecture des documents" };
  const draw = (j) => {
    const z = $("#jobZone");
    if (!z) return;
    z.innerHTML = `<div class="tache"><div class="msg">${esc(LIB[j.type] || "Traitement")} — ${esc(j.message)}</div>
      <div class="barre"><div style="width:${Math.round(j.progression * 100)}%"></div></div>
      <div class="muted small" style="margin-top:6px">Vous pouvez continuer à travailler sur d'autres étapes. Laissez l'application ouverte.</div></div>`;
    $$("#panneau button.btn.primaire, #transcrire, #locuteurs, #corriger, #recommencer").forEach((b) => (b.disabled = true));
  };
  draw(job);
  S.polling[job.id] = setInterval(async () => {
    let j;
    try { j = await api("GET", `/api/taches/${job.id}`, undefined, { silent: true }); } catch (_) { clearInterval(S.polling[job.id]); delete S.polling[job.id]; return; }
    if (j.etat === "termine" || j.etat === "erreur") {
      clearInterval(S.polling[job.id]);
      delete S.polling[job.id];
      if (j.etat === "erreur") toast(j.erreur, true); else toast(`${LIB[j.type] || "Traitement"} terminé(e).`);
      if (S.visit && S.visit.id === j.visite && location.hash.includes(`/visite/${j.visite}`)) route();
    } else draw(j);
  }, 1500);
}

/* ------------------------------------------------------------------ utilitaires */

function hms(sec) {
  sec = Math.max(0, Math.floor(sec || 0));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  const mm = String(m).padStart(2, "0"), ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}
function dateFr(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso || "";
}
function libStatut(k) { return (STATUTS.find(([x]) => x === k) || [, ""])[1]; }

/* ------------------------------------------------------------------ démarrage */

refreshEtat().then(route);
setInterval(refreshEtat, 30000);
