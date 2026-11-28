"""Exports : bulletin Word/PDF, transcription, bilan réflexif, synthèse."""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from . import analysis, bulletin

BLEU = RGBColor(0x1F, 0x3A, 0x68)


def _safe(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_") or "stagiaire"


def base_name(visit: dict) -> str:
    adm = visit.get("admin", {})
    date = adm.get("date") or visit.get("cree", "")[:10]
    num = f"_visite{adm['numero']}" if adm.get("numero") else ""
    return f"{date}_{_safe(adm.get('stagiaire_nom', ''))}{num}"


def _new_doc(title: str, visit: dict):
    d = docx.Document()
    st = d.styles["Normal"]
    st.font.name = "Arial"
    st.font.size = Pt(10.5)
    h = d.add_paragraph()
    r = h.add_run(title)
    r.bold = True
    r.font.size = Pt(15)
    r.font.color.rgb = BLEU
    adm = visit.get("admin", {})
    info = " – ".join(x for x in (
        adm.get("stagiaire_nom", ""), adm.get("classe", ""), adm.get("ecole", ""),
        bulletin._date_fr(adm.get("date", "")),
    ) if x)
    if info:
        p = d.add_paragraph(info)
        p.runs[0].italic = True
    d.add_paragraph(
        "Document confidentiel – généré localement, à relire et valider par la formatrice."
    ).runs[0].font.size = Pt(8)
    return d


def _heading(d, text, size=12.5):
    p = d.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(size)
    r.font.color.rgb = BLEU
    return p


def _photos(d, visit: dict, out_dir: Path, titre: str = "Les activités des élèves en images") -> None:
    """Planche des photos de la séance : 2 par ligne, légende sous chaque photo."""
    from docx.shared import Cm
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    pdir = out_dir.parent / "photos"
    # Numérotation identique à celle donnée à l'IA (« voir photo 2 »)
    numeros = {p["id"]: n for n, p in enumerate(visit.get("photos", []), 1)}
    items = [p for p in visit.get("photos", []) if (pdir / p.get("fichier", "")).exists()]
    if not items:
        return
    _heading(d, titre)
    table = d.add_table(rows=0, cols=2)
    # Pas de bordures : une simple planche
    tblpr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tblpr.append(borders)
    largeur = Cm(7.8)
    hauteur_max = Cm(7.0)
    for i in range(0, len(items), 2):
        cells = table.add_row().cells
        for cell, p in zip(cells, items[i:i + 2]):
            para = cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            w, h = p.get("largeur") or 4, p.get("hauteur") or 3
            run = para.add_run()
            # On limite la hauteur des photos en portrait pour garder une planche régulière
            if largeur * h / w > hauteur_max:
                run.add_picture(str(pdir / p["fichier"]), height=hauteur_max)
            else:
                run.add_picture(str(pdir / p["fichier"]), width=largeur)
            leg = cell.add_paragraph()
            leg.alignment = WD_ALIGN_PARAGRAPH.CENTER
            leg.paragraph_format.space_after = Pt(8)
            num = leg.add_run(f"Photo {numeros.get(p['id'], '')}" + (" — " if p.get("legende") else ""))
            num.bold = True
            num.font.size = Pt(9)
            r = leg.add_run(p.get("legende") or "")
            r.italic = True
            r.font.size = Pt(9)


def export_bulletin_docx(visit: dict, out_dir: Path, avec_photos: bool = False) -> Path:
    photos = []
    if avec_photos:
        pdir = out_dir.parent / "photos"
        photos = [
            (pdir / p["fichier"], f"Photo {n}" + (f" — {p['legende']}" if p.get("legende") else ""))
            for n, p in enumerate(visit.get("photos", []), 1) if (pdir / p.get("fichier", "")).exists()
        ]
    return bulletin.fill_bulletin(visit, out_dir / f"{base_name(visit)}_bulletin.docx", photos=photos)


def export_transcription(visit: dict, out_dir: Path) -> Path:
    d = _new_doc("Retranscription intégrale de l'entretien", visit)
    segs = visit.get("transcription", {}).get("segments", [])
    if not segs:
        d.add_paragraph("Aucune transcription.")
    for t in analysis.turns(segs, include_hors_sujet=False):
        p = d.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(f"{analysis.LOC.get(t['locuteur'], '?')} ({analysis.hms(t['debut'])}) : ")
        r.bold = True
        p.add_run(t["texte"])
    nb_hs = sum(1 for s in segs if s.get("hors_sujet"))
    if nb_hs:
        d.add_paragraph(f"({nb_hs} passage(s) hors sujet écarté(s) de cette retranscription.)").runs[0].italic = True
    path = out_dir / f"{base_name(visit)}_transcription.docx"
    d.save(str(path))
    return path


def export_bilan(visit: dict, out_dir: Path) -> Path:
    d = _new_doc("Bilan réflexif de la visite", visit)
    a = visit.get("analyse", {})
    _seance(d, visit)
    _photos(d, visit, out_dir)
    for g in ("A", "B", "C"):
        _heading(d, f"{g}. {analysis.TITRES[g]}")
        vide = True
        for k in analysis.CLES[g]:
            items = a.get(g, {}).get(k, [])
            if not items:
                continue
            vide = False
            p = d.add_paragraph()
            p.add_run(analysis.TITRES[k]).bold = True
            for it in items:
                d.add_paragraph(it.get("texte", ""), style="List Bullet")
        if vide:
            d.add_paragraph("Aucun élément relevé.").runs[0].italic = True
    _heading(d, "D. Bilan réflexif")
    if a.get("D"):
        for para in a["D"].split("\n"):
            if para.strip():
                d.add_paragraph(para.strip())
    else:
        d.add_paragraph("À compléter.").runs[0].italic = True
    _references(d, visit)
    path = out_dir / f"{base_name(visit)}_bilan_reflexif.docx"
    d.save(str(path))
    return path


def _seance(d, visit: dict) -> None:
    """La séance observée : enseignements, description détaillée, déroulement horodaté."""
    b = visit.get("bulletin", {})
    _heading(d, "La séance observée")
    if not (b.get("enseignements") or b.get("description") or b.get("deroulement")):
        d.add_paragraph("À compléter (étape Bulletin).").runs[0].italic = True
        return
    if b.get("enseignements"):
        p = d.add_paragraph()
        p.add_run("Enseignements observés : ").bold = True
        p.add_run(b["enseignements"])
    for para in (b.get("description") or "").split("\n"):
        if para.strip():
            d.add_paragraph(para.strip())
    lignes = [r for r in b.get("deroulement", []) if any(str(v).strip() for v in r.values())]
    if lignes:
        p = d.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.add_run("Déroulement").bold = True
        t = d.add_table(rows=1, cols=5)
        t.style = "Table Grid"
        for cell, titre in zip(t.rows[0].cells, ("Horaire / durée", "Déroulement observé",
                                                 "Analyse et conseil de la formatrice", "Dispositif",
                                                 "Organisation matérielle")):
            cell.text = ""
            run = cell.paragraphs[0].add_run(titre)
            run.bold = True
            run.font.size = Pt(9.5)
        for r in lignes:
            cells = t.add_row().cells
            for cell, k in zip(cells, ("temps", "deroulement", "remarque", "dispositif", "organisation")):
                cell.text = ""
                run = cell.paragraphs[0].add_run(str(r.get(k, "")))
                run.font.size = Pt(9.5)
        # Colonnes de texte plus larges (largeur utile d'une page A4 : environ 16 cm)
        from docx.shared import Cm

        t.autofit = False
        largeurs = (2.5, 4.6, 4.6, 2.2, 2.4)
        for col, w in zip(t.columns, largeurs):
            col.width = Cm(w)  # grille du tableau (lue par LibreOffice)
        for row in t.rows:
            for cell, w in zip(row.cells, largeurs):
                cell.width = Cm(w)  # largeur de chaque cellule (lue par Word)


def references(visit: dict) -> list[str]:
    """Références à communiquer à la stagiaire : celles du bulletin, puis celles citées dans les conseils."""
    vues, out = set(), []
    b, a = visit.get("bulletin", {}), visit.get("analyse", {})
    sources = [r.get("texte", "") if isinstance(r, dict) else str(r) for r in b.get("references", [])]
    sources += [it.get("texte", "") for it in a.get("C", {}).get("ressources", [])]
    sources += [pt.get("ressources", "") for pt in b.get("points", [])]
    for r in sources:
        r = (r or "").strip()
        cle = analysis._norm(r)
        if r and cle not in vues and not any(cle in v or v in cle for v in vues):
            vues.add(cle)
            out.append(r)
    return out


def _references(d, visit: dict) -> None:
    _heading(d, "Références à communiquer à la stagiaire")
    refs = references(visit)
    if not refs:
        d.add_paragraph("Aucune référence relevée.").runs[0].italic = True
    for r in refs:
        d.add_paragraph(r, style="List Bullet")


def export_synthese(visit: dict, out_dir: Path) -> Path:
    d = _new_doc("Synthèse de la visite", visit)
    a = visit.get("analyse", {})
    _seance(d, visit)
    _photos(d, visit, out_dir)
    groupes = [
        ("Points forts", [("B", "points_forts"), ("B", "competences_maitrisees"), ("A", "reussites")]),
        ("Axes d'amélioration", [("B", "axes_amelioration"), ("B", "difficultes"), ("B", "accompagnement")]),
        ("Conseils", [("C", "conseils_pedagogiques"), ("C", "preconisations"), ("C", "remediations"),
                      ("C", "perspectives")]),
    ]
    for titre, cles in groupes:
        _heading(d, titre)
        items = [it for g, k in cles for it in a.get(g, {}).get(k, [])]
        if not items:
            d.add_paragraph("Aucun élément relevé.").runs[0].italic = True
        for it in items:
            d.add_paragraph(it.get("texte", ""), style="List Bullet")
    _references(d, visit)
    path = out_dir / f"{base_name(visit)}_synthese.docx"
    d.save(str(path))
    return path


# ------------------------------------------------------------------ PDF

class PDFImpossible(Exception):
    pass


def _soffice() -> str | None:
    for c in (
        shutil.which("soffice"), shutil.which("libreoffice"),
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ):
        if c and Path(c).exists():
            return c
    return None


def docx_to_pdf(src: Path) -> Path:
    """Convertit en PDF avec LibreOffice, ou à défaut Microsoft Word (Mac)."""
    dst = src.with_suffix(".pdf")
    so = _soffice()
    if so:
        r = subprocess.run(
            [so, "--headless", "--convert-to", "pdf", "--outdir", str(src.parent), str(src)],
            capture_output=True, timeout=180,
        )
        if r.returncode == 0 and dst.exists():
            return dst
    if platform.system() == "Darwin" and Path("/Applications/Microsoft Word.app").exists():
        script = f'''
        tell application "Microsoft Word"
            set theDoc to open file name (POSIX file "{src}" as text)
            save as theDoc file name (POSIX file "{dst}" as text) file format format PDF
            close theDoc saving no
        end tell'''
        r = subprocess.run(["osascript", "-e", script], capture_output=True, timeout=180)
        if r.returncode == 0 and dst.exists():
            return dst
    raise PDFImpossible(
        "Impossible de créer le PDF automatiquement : installez LibreOffice (gratuit) ou Microsoft Word. "
        "Vous pouvez aussi ouvrir le bulletin Word et faire Fichier > Exporter > PDF."
    )


def open_in_finder(path: Path) -> None:
    if platform.system() == "Darwin":
        subprocess.Popen(["open", str(path)])
    elif os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])
