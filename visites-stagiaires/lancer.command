#!/bin/bash
# Lance « Visites stagiaires ». Laissez cette fenêtre ouverte pendant l'utilisation.
cd "$(dirname "$0")" || exit 1

# Confidentialité : on interdit tout téléchargement de modèle, rien ne sort du Mac.
export HF_HUB_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export DO_NOT_TRACK=1

if [ ! -x .venv/bin/python ]; then
  echo "L'application n'est pas installée. Double-cliquez d'abord sur « installer.command »."
  read -r; exit 1
fi

# Démarre l'IA locale si elle ne tourne pas déjà
if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  for p in "/Applications/Ollama.app" "$HOME/Applications/Ollama.app"; do
    [ -d "$p" ] && open -g -a "$p" && break
  done
fi

# Si l'application est déjà ouverte, on se contente d'afficher la page
if curl -s http://127.0.0.1:8765/api/etat >/dev/null 2>&1; then
  open "http://127.0.0.1:8765/"
  exit 0
fi

clear
echo "Visites stagiaires"
echo "------------------"
exec .venv/bin/python -m app.main
