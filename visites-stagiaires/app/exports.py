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


def export_bulletin_docx(visit: dict, out_dir: Path) -> Path:
    return bulletin.fill_bulletin(visit, out_dir / f"{base_name(visit)}_bulletin.docx")


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
    path = out_dir / f"{base_name(visit)}_bilan_reflexif.docx"
    d.save(str(path))
    return path


def export_synthese(visit: dict, out_dir: Path) -> Path:
    d = _new_doc("Synthèse de la visite", visit)
    a = visit.get("analyse", {})
    groupes = [
        ("Points forts", [("B", "points_forts"), ("B", "competences_maitrisees"), ("A", "reussites")]),
        ("Axes d'amélioration", [("B", "axes_amelioration"), ("B", "difficultes"), ("B", "accompagnement")]),
        ("Conseils", [("C", "conseils_pedagogiques"), ("C", "preconisations"), ("C", "remediations"),
                      ("C", "ressources"), ("C", "perspectives")]),
    ]
    for titre, cles in groupes:
        _heading(d, titre)
        items = [it for g, k in cles for it in a.get(g, {}).get(k, [])]
        if not items:
            d.add_paragraph("Aucun élément relevé.").runs[0].italic = True
        for it in items:
            d.add_paragraph(it.get("texte", ""), style="List Bullet")
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
