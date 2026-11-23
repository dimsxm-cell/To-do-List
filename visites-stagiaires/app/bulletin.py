"""Remplissage du bulletin officiel Word (modèle 2026-2027) sans toucher à sa mise en page.

On repère chaque tableau par son contenu (et non par sa position) pour rester
robuste si le modèle change légèrement d'une année à l'autre.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

import docx
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

MODELE = Path(__file__).parent / "modeles" / "bulletin_2026-2027.docx"

FONT = "Marianne"
SIZE_HALF_PT = 18  # 9 pt, comme le modèle

STATUTS = {
    "temps_plein": "TEMPS PLEIN",
    "mi_temps_diu": "MI-TEMPS DIU",
    "mi_temps_m2": "M2 M2E",
}

OUTILS_LABELS = {
    "cahier_journal": "cahier journal",
    "registre_appel": "registre d",
    "fiches_sequences": "fiches de séquences",
    "fiches_seances": "fiches de séances",
    "progressions": "progressions",
    "emploi_du_temps": "emploi du temps",
    "autres": "autres",
    "cahiers_eleves": "cahiers/classeurs",
}

NIVEAUX = ["TI", "I", "S", "TS"]


class ModeleIntrouvable(Exception):
    pass


# ------------------------------------------------------------------ outils XML

def _text(el) -> str:
    return "".join(t.text or "" for t in el.iter(qn("w:t")))


def _norm(s: str) -> str:
    s = (s or "").replace("\xa0", " ").replace("’", "'").lower()
    return re.sub(r"\s+", " ", s).strip()


def _make_run(text: str, bold: bool = False, size: int = SIZE_HALF_PT, font: str = FONT):
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    for att in ("w:ascii", "w:hAnsi", "w:cs"):
        fonts.set(qn(att), font)
    rpr.append(fonts)
    if bold:
        rpr.append(OxmlElement("w:b"))
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(size))
    rpr.append(sz)
    szcs = OxmlElement("w:szCs")
    szcs.set(qn("w:val"), str(size))
    rpr.append(szcs)
    r.append(rpr)
    lines = str(text).split("\n")
    for i, line in enumerate(lines):
        if i:
            r.append(OxmlElement("w:br"))
        t = OxmlElement("w:t")
        t.set(qn("xml:space"), "preserve")
        t.text = line
        r.append(t)
    return r


def _new_paragraph(text: str = "", bold: bool = False, align: str | None = None, like=None):
    """Nouveau paragraphe ; reprend les propriétés de `like` (retraits, puces) si fourni."""
    p = OxmlElement("w:p")
    if like is not None and like.find(qn("w:pPr")) is not None:
        ppr = copy.deepcopy(like.find(qn("w:pPr")))
        # On retire le formatage de marque de paragraphe (gras, majuscules) hérité d'un libellé.
        old_rpr = ppr.find(qn("w:rPr"))
        if old_rpr is not None:
            ppr.remove(old_rpr)
        p.append(ppr)
    if align:
        ppr = p.find(qn("w:pPr"))
        if ppr is None:
            ppr = OxmlElement("w:pPr")
            p.insert(0, ppr)
        jc = ppr.find(qn("w:jc"))
        if jc is None:
            jc = OxmlElement("w:jc")
            ppr.append(jc)
        jc.set(qn("w:val"), align)
    if text:
        p.append(_make_run(text, bold=bold))
    return p


def _append_to_paragraph(p, text: str, bold: bool = False):
    if not text:
        return
    # Le modèle contient de longues séries d'espaces après les libellés : on les retire
    # pour que la valeur s'écrive juste après « École : » au lieu de passer à la ligne.
    for t in reversed(list(p.iter(qn("w:t")))):
        stripped = (t.text or "").rstrip(" \xa0\t")
        t.text = stripped
        if stripped:
            break
    p.append(_make_run(" " + text, bold=bold))


def _insert_after(ref, new):
    ref.addnext(new)
    return new


def _cells(tr):
    return tr.findall(qn("w:tc"))


def _rows(tbl):
    return tbl.findall(qn("w:tr"))


def _clear_cell_text(tc):
    for t in tc.iter(qn("w:t")):
        t.text = ""


def _write_cell(tc, text: str, bold: bool = False, align: str | None = None, keep_label: bool = False):
    """Écrit du texte dans une cellule. Avec keep_label, le texte va sous le libellé existant."""
    if text is None or str(text).strip() == "":
        return
    paras = tc.findall(qn("w:p"))
    lines = [ln for ln in str(text).split("\n")]
    if keep_label:
        anchor = paras[-1]
        for ln in lines:
            anchor = _insert_after(anchor, _new_paragraph(ln, bold=bold, align=align, like=paras[0]))
        return
    _clear_cell_text(tc)
    first = paras[0]
    # On enlève les runs vides du premier paragraphe puis on écrit.
    for r in first.findall(qn("w:r")):
        first.remove(r)
    for extra in paras[1:]:
        if not _text(extra).strip():
            tc.remove(extra)
    if align:
        _set_align(first, align)
    first.append(_make_run(lines[0], bold=bold))
    anchor = first
    for ln in lines[1:]:
        anchor = _insert_after(anchor, _new_paragraph(ln, bold=bold, align=align, like=first))


def _set_align(p, align):
    ppr = p.find(qn("w:pPr"))
    if ppr is None:
        ppr = OxmlElement("w:pPr")
        p.insert(0, ppr)
    jc = ppr.find(qn("w:jc"))
    if jc is None:
        jc = OxmlElement("w:jc")
        # w:jc doit précéder w:rPr dans w:pPr
        rpr = ppr.find(qn("w:rPr"))
        if rpr is not None:
            rpr.addprevious(jc)
        else:
            ppr.append(jc)
    jc.set(qn("w:val"), align)


def _shade(tc, fill="BDD6EE"):
    tcpr = tc.find(qn("w:tcPr"))
    if tcpr is None:
        tcpr = OxmlElement("w:tcPr")
        tc.insert(0, tcpr)
    shd = tcpr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tcpr.append(shd)
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)


# ------------------------------------------------------------------ repérage

class _Doc:
    def __init__(self, path: Path):
        if not path.exists():
            raise ModeleIntrouvable(f"Modèle Word introuvable : {path}")
        self.doc = docx.Document(str(path))
        self.body = self.doc.element.body

    def paragraph_starting(self, prefix: str):
        for el in self.body.iterchildren(qn("w:p")):
            if _norm(_text(el)).startswith(_norm(prefix)):
                return el
        return None

    def table_with(self, needle: str):
        n = _norm(needle)
        for el in self.body.iterchildren(qn("w:tbl")):
            if n in _norm(_text(el)):
                return el
        return None


# ------------------------------------------------------------------ remplissage

def fill_bulletin(visit: dict, out_path: Path, modele: Path = MODELE, photos: list | None = None) -> Path:
    d = _Doc(modele)
    adm = visit.get("admin", {})
    b = visit.get("bulletin", {})

    # --- En-tête : N°
    p = d.paragraph_starting("BULLETIN DE VISITE")
    if p is not None:
        _append_to_paragraph(p, adm.get("numero", ""), bold=True)

    # --- Identification
    t = d.table_with("Nom et prénom du stagiaire")
    if t is not None:
        rows = _rows(t)
        c_nom, c_statut = _cells(rows[0])[0], _cells(rows[0])[1]
        _append_to_paragraph(c_nom.findall(qn("w:p"))[0], adm.get("stagiaire_nom", ""), bold=True)
        _mark_statut(c_statut, adm.get("statut", ""))
        labels = {
            "date": ("date", _date_fr(adm.get("date", ""))),
            "horaire": ("horaire", adm.get("horaire", "")),
            "classe": ("classe", adm.get("classe", "")),
            "effectif": ("effectif", adm.get("effectif", "")),
            "ecole": ("école", adm.get("ecole", "")),
            "circonscription": ("circonscription", adm.get("circonscription", "")),
            "commune": ("commune", adm.get("commune", "")),
            "conditions": ("conditions particuli", adm.get("conditions", "")),
        }
        for tr in rows[1:]:
            for tc in _cells(tr):
                label = _norm(_text(tc))
                for _key, (prefix, value) in labels.items():
                    if label.startswith(_norm(prefix)) and value:
                        _append_to_paragraph(_first_text_paragraph(tc), value)

    # --- Formateurs
    p = d.paragraph_starting("Nom et qualité")
    if p is not None:
        noms = [
            ", ".join(x for x in (f.get("nom", "").strip(), f.get("qualite", "").strip()) if x)
            for f in adm.get("formateurs", [])
            if f.get("nom")
        ]
        _append_to_paragraph(p, " ; ".join(noms))

    # --- Outils présentés
    t = d.table_with("cahier journal")
    if t is not None:
        outils = visit.get("outils", {})
        for tr in _rows(t):
            cells = _cells(tr)
            for i in range(0, len(cells) - 1, 2):
                label = _norm(_text(cells[i]))
                for key, needle in OUTILS_LABELS.items():
                    if label.startswith(_norm(needle)) and outils.get(key):
                        _write_cell(cells[i + 1], "X", bold=True, align="center")

    # --- Enseignements observés + description
    p = d.paragraph_starting("ENSEIGNEMENTS OBSERVÉS")
    if p is not None and b.get("enseignements"):
        anchor = p
        for ln in b["enseignements"].split("\n"):
            anchor = _insert_after(anchor, _new_paragraph(ln))
    p = d.paragraph_starting("Description de la")
    if p is not None and (b.get("description") or photos):
        anchor = p
        for ln in (b.get("description") or "").split("\n"):
            if ln.strip():
                anchor = _insert_after(anchor, _new_paragraph(ln))
        if photos:
            anchor = _inserer_photos(d, anchor, photos)

    # --- Tableau de déroulement
    t = d.table_with("Temps(minutage")
    if t is not None:
        _fill_repeating_rows(
            t, 1,
            [[r.get("temps", ""), r.get("deroulement", ""), r.get("dispositif", ""), r.get("organisation", "")]
             for r in b.get("deroulement", []) if any(str(v).strip() for v in r.values())],
            clear_template=True,
        )

    # --- Trois points discutés
    t = d.table_with("POINT DISCUT")
    if t is not None:
        rows = _rows(t)
        points = (b.get("points") or [])[:3]
        for i, pt in enumerate(points):
            r_ana, r_res = rows[1 + 2 * i], rows[2 + 2 * i]
            if pt.get("titre"):
                _write_cell(_cells(r_ana)[0], pt["titre"], keep_label=True)
            _write_cell(_cells(r_ana)[1], pt.get("analyse", ""))
            _write_cell(_cells(r_res)[1], pt.get("ressources", ""))

    # --- Avis sur l'entretien
    t = d.table_with("POINTS POSITIFS")
    if t is not None:
        pos = [x for x in b.get("positifs", []) if str(x).strip()]
        amel = [x for x in b.get("ameliorer", []) if str(x).strip()]
        n = max(len(pos), len(amel))
        if n:
            data = [[pos[i] if i < len(pos) else "", amel[i] if i < len(amel) else ""] for i in range(n)]
            _fill_repeating_rows(t, 1, data, extra_template_rows=1)

    # --- Maîtrise de la langue
    t = d.table_with("MAITRISE DE LA LANGUE")
    if t is not None:
        rows = _rows(t)
        lang = b.get("langue", {})
        marks = _cells(rows[3])
        for offset, key in ((0, "orale"), (4, "ecrite")):
            if lang.get(key) in NIVEAUX:
                _write_cell(marks[offset + NIVEAUX.index(lang[key])], "X", bold=True, align="center")
        obs_cells = _cells(rows[2])
        if len(obs_cells) > 8 and lang.get("observations"):
            _write_cell(obs_cells[8], lang["observations"])

    # --- Positionnement
    t = d.table_with("De 0 à 4")
    if t is not None and b.get("positionnement") in NIVEAUX:
        idx = NIVEAUX.index(b["positionnement"])
        rows = _rows(t)
        _shade(_cells(rows[1])[idx], "9CC3E6")
        _write_cell(_cells(rows[1])[idx], "X", bold=True, align="center", keep_label=True)

    # --- Note M2 M2E
    t = d.table_with("Proposition de note")
    if t is not None and str(b.get("note", "")).strip():
        tc = _cells(_rows(t)[1])[0]
        for tnode in tc.iter(qn("w:t")):
            if "/20" in (tnode.text or ""):
                tnode.text = tnode.text.replace("/20", f"{str(b['note']).strip()} /20", 1)
                break

    # --- Signatures
    t = d.table_with("LE FONCTIONNAIRE STAGIAIRE")
    if t is not None:
        rows = _rows(t)
        noms = [adm.get("stagiaire_nom", "")] + [f.get("nom", "") for f in adm.get("formateurs", [])][:3]
        date_sig = _date_fr(b.get("date_signature") or adm.get("date", ""))
        lieu = adm.get("lieu", "")
        for col, nom in enumerate(noms):
            if not nom:
                continue
            _append_to_paragraph(_first_text_paragraph(_cells(rows[1])[col]), ": " + nom)
            if date_sig:
                _append_to_paragraph(_first_text_paragraph(_cells(rows[2])[col]), date_sig)
            if lieu:
                _append_to_paragraph(_first_text_paragraph(_cells(rows[3])[col]), ": " + lieu)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    d.doc.save(str(out_path))
    return out_path


def _first_text_paragraph(tc):
    for p in tc.findall(qn("w:p")):
        if _text(p).strip():
            return p
    return tc.findall(qn("w:p"))[0]


def _mark_statut(tc, statut: str):
    needle = STATUTS.get(statut)
    if not needle:
        return
    for p in tc.findall(qn("w:p")):
        if needle.lower() in _text(p).lower():
            for r in p.findall(qn("w:r")):
                if r.find(qn("w:drawing")) is not None:
                    r.addprevious(_make_run("☒", bold=True, size=20, font="MS Gothic"))
                    p.remove(r)
                    return


def _fill_repeating_rows(tbl, template_idx: int, data: list[list[str]], clear_template=False, extra_template_rows=0):
    """Remplit des lignes en dupliquant la ligne modèle autant que nécessaire.

    extra_template_rows : nombre de lignes vierges identiques qui suivent la ligne modèle
    dans le document d'origine (on les retire puis on recrée le bon nombre).
    """
    rows = _rows(tbl)
    template = rows[template_idx]
    for extra in rows[template_idx + 1: template_idx + 1 + extra_template_rows]:
        tbl.remove(extra)
    if not data:
        if clear_template:
            for tc in _cells(template):
                if _text(tc).strip() == ".":
                    _clear_cell_text(tc)
        return
    blank = copy.deepcopy(template)
    anchor = template
    for i, values in enumerate(data):
        tr = template if i == 0 else copy.deepcopy(blank)
        if i:
            anchor.addnext(tr)
        anchor = tr
        for tc, val in zip(_cells(tr), values):
            _clear_cell_text(tc)
            if str(val).strip():
                _write_cell(tc, val)
            else:
                # Cellule vide : on enlève la puce pour ne pas laisser un « • » orphelin.
                for numpr in list(tc.iter(qn("w:numPr"))):
                    numpr.getparent().remove(numpr)


def _date_fr(iso: str) -> str:
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", (iso or "").strip())
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return iso or ""


def champs_manquants(visit: dict) -> list[str]:
    """Liste lisible des rubriques encore vides, à montrer avant l'export."""
    adm, b = visit.get("admin", {}), visit.get("bulletin", {})
    manque = []
    checks = [
        (adm.get("numero"), "N° de visite"),
        (adm.get("stagiaire_nom"), "Nom du stagiaire"),
        (adm.get("statut"), "Statut"),
        (adm.get("date"), "Date"),
        (adm.get("horaire"), "Horaire"),
        (adm.get("classe"), "Classe"),
        (adm.get("effectif"), "Effectif"),
        (adm.get("ecole"), "École"),
        (adm.get("circonscription"), "Circonscription"),
        (adm.get("commune"), "Commune"),
        (any(f.get("nom") for f in adm.get("formateurs", [])), "Formateur(s)"),
        (b.get("enseignements"), "Enseignements observés"),
        (b.get("description"), "Description de la séance"),
        (b.get("deroulement"), "Tableau de déroulement"),
    ]
    for i, pt in enumerate((b.get("points") or [])[:3], 1):
        checks.append((pt.get("analyse"), f"Point discuté {i}"))
    checks += [
        (b.get("positifs"), "Points positifs de l'entretien"),
        (b.get("ameliorer"), "Points à améliorer de l'entretien"),
        (b.get("langue", {}).get("orale"), "Maîtrise de la langue orale"),
        (b.get("langue", {}).get("ecrite"), "Maîtrise de la langue écrite"),
        (b.get("positionnement"), "Positionnement (TI, I, S, TS)"),
    ]
    if adm.get("statut") == "mi_temps_m2":
        checks.append((str(b.get("note", "")).strip(), "Note M2 M2E"))
    for ok, label in checks:
        if not ok:
            manque.append(label)
    return manque


def _inserer_photos(d: "_Doc", anchor, photos: list):
    """Photos de la séance sous la description : 3 par ligne, légendes en dessous (option d'export)."""
    from docx.shared import Cm
    from docx.text.paragraph import Paragraph

    for i in range(0, len(photos), 3):
        lot = photos[i:i + 3]
        p_img = _insert_after(anchor, _new_paragraph(align="center"))
        para = Paragraph(p_img, d.doc._body)
        for chemin, _leg in lot:
            para.add_run().add_picture(str(chemin), height=Cm(4.5))
            para.add_run("   ")
        anchor = _insert_after(p_img, _new_paragraph("   |   ".join(leg for _c, leg in lot), align="center"))
    return anchor
