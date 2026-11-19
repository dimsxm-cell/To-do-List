#!/bin/bash
# Installe les outils Claude Code : Claude-Mem, MarkItDown, One Page Love, Impeccable, HyperFrames, Agent Reach, Graphify, gstack.
# Chaque etape est non bloquante : un echec ne doit pas empecher la session de demarrer.
export HOME="${HOME:-/root}"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"
cd "$HOME" || exit 0
step() { echo "== $1"; }
warn() { echo "!! echec: $1 (on continue)"; }

step "Bun (requis par gstack)"
command -v bun >/dev/null || { curl -fsSL https://bun.sh/install | bash || warn bun; }

step "1. Claude-Mem"
npx -y claude-mem install </dev/null || warn claude-mem
MP="$HOME/.claude/plugins/marketplaces/thedotmack"
if [ -d "$MP" ]; then
  claude plugin marketplace add "$MP" || warn "claude-mem marketplace"
  claude plugin install claude-mem@thedotmack || warn "claude-mem plugin"
fi
"$HOME/.local/bin/claude-mem" stop >/dev/null 2>&1 || true

step "2. MarkItDown"
pip install -q --break-system-packages 'markitdown[all]' markitdown-mcp || warn markitdown
claude mcp get markitdown >/dev/null 2>&1 || claude mcp add -s user markitdown -- markitdown-mcp || warn "markitdown mcp"

step "2b. One Page Love MCP"
claude mcp get onepagelove >/dev/null 2>&1 || claude mcp add -s user --transport http onepagelove https://api.onepagelove.com/mcp || warn "onepagelove mcp"

step "2c. Impeccable (design front-end)"
claude plugin marketplace add pbakaus/impeccable || warn "impeccable marketplace"
claude plugin install impeccable@impeccable || warn "impeccable plugin"

step "2d. HyperFrames (video en HTML)"
claude plugin marketplace add heygen-com/hyperframes || warn "hyperframes marketplace"
claude plugin install hyperframes@hyperframes || warn "hyperframes plugin"

step "3. Agent Reach"
npx -y skills add Panniantong/Agent-Reach@agent-reach -y -g </dev/null || warn agent-reach

step "4. Graphify"
pip install -q --break-system-packages graphifyy && graphify install </dev/null || warn graphify

step "5. gstack"
G="$HOME/.claude/skills/gstack"
[ -d "$G/.git" ] || git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git "$G" || warn "gstack clone"
[ -x "$G/setup" ] && (cd "$G" && ./setup </dev/null) || warn "gstack setup (navigateur: voir ci-dessous)"

step "Navigateur gstack -> Chromium preinstalle"
if [ -x /opt/pw-browsers/chromium ]; then
  python3 -I - <<'EOF' || warn "settings env"
import json, os
p = os.path.expanduser("~/.claude/settings.json")
d = json.load(open(p)) if os.path.exists(p) else {}
d.setdefault("env", {}).update({"GSTACK_CHROMIUM_PATH": "/opt/pw-browsers/chromium", "GSTACK_CHROMIUM_NO_SANDBOX": "1"})
json.dump(d, open(p, "w"), indent=2)
EOF
fi

echo "== Termine"
exit 0
