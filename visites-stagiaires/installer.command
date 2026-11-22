#!/bin/bash
# Installation de « Visites stagiaires » sur Mac.
# À lancer UNE fois, avec Internet. Ensuite, l'application fonctionne sans Internet.
# Durée : 15 à 40 minutes selon la connexion (téléchargement d'environ 6 à 16 Go).

set -u
cd "$(dirname "$0")" || exit 1
DOSSIER="$(pwd)"

titre() { printf "\n\033[1;34m== %s\033[0m\n" "$1"; }
ok()    { printf "\033[0;32m   ✓ %s\033[0m\n" "$1"; }
alerte(){ printf "\033[0;33m   ! %s\033[0m\n" "$1"; }
stop()  { printf "\n\033[0;31m   ✗ %s\033[0m\n\nAppuyez sur Entrée pour fermer." "$1"; read -r; exit 1; }

clear
echo "Installation de Visites stagiaires"
echo "-----------------------------------"
echo "Laissez cette fenêtre ouverte jusqu'au message « Installation terminée »."

# ---------------------------------------------------------------- 0. Mac
titre "Vérification du Mac"
[ "$(uname)" = "Darwin" ] || stop "Cet installateur est prévu pour macOS."
PUCE="$(uname -m)"
RAM_GO=$(( $(sysctl -n hw.memsize) / 1073741824 ))
ok "Puce : $PUCE — Mémoire : ${RAM_GO} Go — macOS $(sw_vers -productVersion)"
if [ "$PUCE" != "arm64" ]; then
  alerte "Mac à processeur Intel : tout fonctionnera, mais la transcription et l'IA seront lentes."
fi

if   [ "$RAM_GO" -ge 32 ]; then MODELE="mistral-small3.2"; CONTEXTE=32768
elif [ "$RAM_GO" -ge 16 ]; then MODELE="mistral-nemo";     CONTEXTE=16384
else
  MODELE="qwen2.5:3b"; CONTEXTE=8192
  alerte "Seulement ${RAM_GO} Go de mémoire : on installe une petite IA. La rédaction sera de qualité moyenne."
fi
ok "IA choisie pour ce Mac : $MODELE"

# ---------------------------------------------------------------- 1. Python (via uv)
titre "1/4 Outils de base"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh || stop "Impossible d'installer uv (vérifiez Internet)."
  export PATH="$HOME/.local/bin:$PATH"
fi
ok "uv installé"
uv venv --python 3.12 --allow-existing .venv >/dev/null 2>&1 || uv venv --python 3.12 .venv || stop "Impossible de préparer Python."
uv pip install --python .venv/bin/python -r requirements.txt || stop "Impossible d'installer les bibliothèques."
ok "Bibliothèques installées"

# ---------------------------------------------------------------- 2. Ollama (IA locale)
titre "2/4 IA locale (Ollama)"
OLLAMA_APP=""
for p in "/Applications/Ollama.app" "$HOME/Applications/Ollama.app"; do [ -d "$p" ] && OLLAMA_APP="$p"; done
if [ -z "$OLLAMA_APP" ]; then
  echo "   Téléchargement d'Ollama…"
  TMP="$(mktemp -d)"
  curl -L --fail -o "$TMP/Ollama.zip" https://ollama.com/download/Ollama-darwin.zip || stop "Téléchargement d'Ollama impossible."
  ditto -x -k "$TMP/Ollama.zip" "$TMP" || stop "Décompression d'Ollama impossible."
  if mv "$TMP/Ollama.app" /Applications/ 2>/dev/null; then OLLAMA_APP="/Applications/Ollama.app"
  else mkdir -p "$HOME/Applications" && mv "$TMP/Ollama.app" "$HOME/Applications/" && OLLAMA_APP="$HOME/Applications/Ollama.app"; fi
fi
ok "Ollama : $OLLAMA_APP"
open -a "$OLLAMA_APP"
echo "   Démarrage d'Ollama (si une fenêtre s'ouvre, vous pouvez la fermer)…"
for i in $(seq 1 60); do curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break; sleep 2; done
curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || stop "Ollama ne démarre pas. Ouvrez Ollama à la main, puis relancez l'installation."
ok "Ollama démarré"

echo "   Téléchargement de l'IA « $MODELE » (plusieurs Go, patience)…"
OLLAMA_BIN="$OLLAMA_APP/Contents/Resources/ollama"
if [ -x "$OLLAMA_BIN" ]; then
  "$OLLAMA_BIN" pull "$MODELE" || stop "Téléchargement du modèle impossible."
else
  curl -s http://127.0.0.1:11434/api/pull -d "{\"model\":\"$MODELE\",\"stream\":false}" | grep -q success || stop "Téléchargement du modèle impossible."
fi
ok "IA téléchargée"

# ---------------------------------------------------------------- 3. Whisper (transcription)
titre "3/4 Transcription (Whisper)"
echo "   Téléchargement du modèle de transcription (environ 1,6 Go)…"
.venv/bin/python - <<'EOF' || stop "Téléchargement du modèle de transcription impossible."
import platform
if platform.system() == "Darwin" and platform.machine() == "arm64":
    from huggingface_hub import snapshot_download
    snapshot_download("mlx-community/whisper-large-v3-turbo")
else:
    from faster_whisper.utils import download_model
    download_model("large-v3-turbo")
print("   ok")
EOF
ok "Modèle de transcription prêt"

# ---------------------------------------------------------------- 4. Réglages + raccourci
titre "4/4 Réglages"
.venv/bin/python - "$MODELE" "$CONTEXTE" <<'EOF'
import sys
sys.path.insert(0, ".")
from app import storage
s = storage.get_settings()
s["ia"]["modele"] = sys.argv[1]
s["ia"]["contexte"] = int(sys.argv[2])
storage.save_settings(s)
print("   Données rangées dans :", storage.data_dir())
EOF
chmod +x "$DOSSIER/lancer.command"
RACCOURCI="$HOME/Desktop/Visites stagiaires.command"
cat > "$RACCOURCI" <<EOF
#!/bin/bash
exec "$DOSSIER/lancer.command"
EOF
chmod +x "$RACCOURCI"
ok "Raccourci créé sur le Bureau : « Visites stagiaires »"

printf "\n\033[1;32mInstallation terminée.\033[0m\n"
echo "Pour ouvrir l'application : double-cliquez sur « Visites stagiaires » sur le Bureau."
echo "À partir de maintenant, Internet n'est plus nécessaire."
echo
echo "Appuyez sur Entrée pour ouvrir l'application maintenant."
read -r
exec "$DOSSIER/lancer.command"
