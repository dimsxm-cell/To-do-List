"""Photos de la séance (tableau, productions d'élèves, affichages) : import et préparation.

Chaque photo est remise droite (orientation du téléphone), convertie en JPEG et
réduite à 1600 pixels maximum : le fichier reste léger dans les documents Word.
Les photos HEIC de l'iPhone sont acceptées.
"""

from __future__ import annotations

from pathlib import Path

EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
TAILLE_MAX = 1600


def _ouvrir(path: Path):
    from PIL import Image

    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    return Image.open(path)


def preparer(src: Path, dst: Path) -> tuple[int, int]:
    """Convertit src en JPEG propre dans dst. Renvoie (largeur, hauteur)."""
    from PIL import ImageOps

    with _ouvrir(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        im.thumbnail((TAILLE_MAX, TAILLE_MAX))
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst, "JPEG", quality=85, optimize=True)
        return im.size
