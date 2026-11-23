"""Lecture des documents pédagogiques importés (Word, PDF, texte) et détection de leur type."""

from __future__ import annotations

import re
from pathlib import Path

EXTENSIONS = {".docx", ".pdf", ".txt", ".md", ".odt"}


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".docx":
        return _docx_text(path)
    if ext == ".pdf":
        return _pdf_text(path)
    if ext == ".odt":
        return _odt_text(path)
    if ext in {".txt", ".md"}:
        raw = path.read_bytes()
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
    raise ValueError(f"Format non pris en charge : {ext}. Formats acceptés : Word (.docx), PDF, texte.")


def _docx_text(path: Path) -> str:
    import docx
    from docx.oxml.ns import qn

    d = docx.Document(str(path))
    lines = []
    # On parcourt le corps dans l'ordre (paragraphes ET tableaux), ce que python-docx ne fait pas seul.
    for el in d.element.body.iterchildren():
        if el.tag == qn("w:p"):
            t = "".join(x.text or "" for x in el.iter(qn("w:t"))).strip()
            if t:
                lines.append(t)
        elif el.tag == qn("w:tbl"):
            for tr in el.iter(qn("w:tr")):
                cells = []
                for tc in tr.findall(qn("w:tc")):
                    ct = " ".join(
                        "".join(x.text or "" for x in p.iter(qn("w:t"))).strip()
                        for p in tc.iter(qn("w:p"))
                    ).strip()
                    cells.append(ct)
                if any(cells):
                    lines.append(" | ".join(cells))
    return "\n".join(lines)


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [(p.extract_text() or "") for p in reader.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError(
            "Ce PDF ne contient pas de texte lisible (c'est sans doute une photo ou un scan). "
            "Demandez la version Word à la stagiaire, ou recopiez l'essentiel dans les notes."
        )
    return text


def _odt_text(path: Path) -> str:
    import zipfile

    with zipfile.ZipFile(path) as z:
        xml = z.read("content.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</text:p>|</text:h>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml).strip()


def guess_type(text: str, filename: str = "") -> str:
    """Devine « seance », « sequence » ou « autre » à partir de mots-clés.

    Une fiche de séquence liste plusieurs séances ; une fiche de séance détaille
    les phases d'une seule séance (durées, déroulement, consignes).
    """
    t = (filename + "\n" + text).lower()
    name = filename.lower()
    if re.search(r"s[ée]quence", name) and not re.search(r"s[ée]ance", name):
        return "sequence"
    if re.search(r"s[ée]ance|pr[ée]p", name) and not re.search(r"s[ée]quence", name):
        return "seance"
    n_seances = len(set(re.findall(r"s[ée]ance\s*(?:n°|no|n)?\s*(\d{1,2})", t)))
    score_seq = 0
    score_sea = 0
    # Titre du document (trames INSPE : « Fiche de préparation de séquence / de séance »)
    debut = t[:400]
    if re.search(r"(fiche|pr[ée]paration|plan)\s+(de\s+)?(pr[ée]paration\s+de\s+)?(la\s+)?s[ée]quence|s[ée]quence\s+d.apprentissage", debut):
        score_seq += 5
    if re.search(r"(fiche|pr[ée]paration)\s+(de\s+)?(pr[ée]paration\s+de\s+)?(la\s+)?s[ée]ance", debut):
        score_sea += 5
    if re.search(r"nombre\s+de\s+s[ée]ances", t):
        score_seq += 3
    if re.search(r"s[ée]ance\s*(n°|no)?\s*\d{1,2}\s*(sur|/)\s*\d{1,2}", t):
        score_sea += 3  # « Séance n° 2 sur 5 » : on est dans UNE séance d'une séquence
    if re.search(r"fiche\s+(de\s+)?s[ée]quence|plan\s+de\s+s[ée]quence", t):
        score_seq += 2
    if n_seances >= 3:
        score_seq += 3
    if re.search(r"t[âa]che\s+finale|[ée]valuation\s+(finale|sommative)", t):
        score_seq += 1
    if re.search(r"fiche\s+(de\s+)?s[ée]ance|pr[ée]paration\s+de\s+s[ée]ance", t):
        score_sea += 2
    if re.search(r"\b\d{1,2}\s*(min|mn|')", t):
        score_sea += 2
    if re.search(r"d[ée]roulement|phase|consigne|mise\s+en\s+commun|institutionnalisation", t):
        score_sea += 1
    if score_seq == 0 and score_sea == 0:
        return "autre"
    return "sequence" if score_seq > score_sea else "seance"


TYPE_LABELS = {"seance": "Fiche de séance", "sequence": "Fiche de séquence", "autre": "Document complémentaire"}
