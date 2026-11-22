# Visites stagiaires

Application Mac pour les visites formatives des fonctionnaires stagiaires :
fiche du stagiaire → fiches pédagogiques → enregistrement de l'entretien → transcription →
analyse réflexive → bulletin officiel 2026-2027 prérempli → exports Word et PDF.

**Tout reste sur le Mac.** Aucun son, aucun texte, aucune donnée de stagiaire n'est envoyé sur Internet.
Internet ne sert qu'une fois, à l'installation (téléchargement des modèles).

## Installation (une seule fois, avec Internet)

1. Copier le dossier `visites-stagiaires` sur le Mac (par exemple dans *Documents*).
2. Clic droit sur `installer.command` → **Ouvrir** → **Ouvrir**.
   (La première fois, macOS demande une confirmation, car le fichier ne vient pas de l'App Store.)
3. Attendre le message « Installation terminée » (15 à 40 min).

L'installateur choisit l'IA selon la mémoire du Mac :

| Mémoire du Mac | IA installée | Qualité de rédaction |
|---|---|---|
| 32 Go et plus | mistral-small3.2 (15 Go) | très bonne |
| 16 Go | mistral-nemo (7 Go) | bonne |
| 8 Go | qwen2.5:3b (2 Go) | moyenne |

## Utilisation

Double-cliquer sur **« Visites stagiaires »** sur le Bureau. La page s'ouvre dans le navigateur
(Safari ou Chrome). Laisser la petite fenêtre noire ouverte pendant l'utilisation.

1. **Infos** : stagiaire, classe, école, statut, outils présentés, vos notes d'observation.
2. **Documents** : fiche de séance, fiche de séquence, autres documents (Word ou PDF).
3. **Entretien** : Démarrer / Pause / Reprendre / Arrêter. Sauvegarde automatique toutes les 5 s.
   On peut aussi importer un mémo vocal de l'iPhone.
4. **Transcription** : sur le Mac, sans Internet. Puis « Identifier qui parle » et
   « Corriger les fautes évidentes ». Tout est modifiable à la main ; cliquer sur l'heure pour réécouter.
5. **Analyse** : points de la stagiaire (A), de la formatrice (B), conseils (C), bilan (D).
   Chaque point cite un extrait ; s'il est introuvable dans l'entretien, il est signalé en orange.
6. **Bulletin** : préremplissage, relecture, positionnement et note (choix de la formatrice uniquement).
7. **Export** : bulletin Word et PDF, transcription, bilan réflexif, synthèse.

La grille d'analyse et vos attentes se règlent une fois dans **Paramètres**.

## Où sont les données ?

`Documents/Visites stagiaires/` (une visite = un dossier). À sauvegarder régulièrement
(Time Machine ou clé USB). Une visite supprimée part dans le sous-dossier `corbeille`.

## PDF

Le PDF est créé avec LibreOffice (gratuit) ou Microsoft Word s'ils sont installés.
Sinon : ouvrir le bulletin Word puis *Fichier > Exporter > PDF*.

## Limites connues (version 1)

- L'IA locale est moins fine que ChatGPT ou Claude : relire chaque proposition.
- L'identification « qui parle » est une proposition de l'IA, à vérifier.
- Le Mac doit rester ouvert et branché pendant l'enregistrement.

## Pour le développeur

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt pytest httpx
.venv/bin/python -m pytest -q
VISITES_DATA_DIR=/tmp/visites .venv/bin/python -m app.main   # http://127.0.0.1:8765
```

Structure : `app/main.py` (serveur local), `app/bulletin.py` (remplissage du modèle Word officiel,
`app/modeles/`), `app/audio.py` (enregistrement et Whisper), `app/analysis.py` (prompts IA et
vérification des extraits), `app/llm.py` (Ollama, refuse toute adresse hors du Mac),
`app/static/` (interface).
