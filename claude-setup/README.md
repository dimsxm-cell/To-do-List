# claude-code-setup

Configuration de mon environnement Claude Code cloud (environnement « Default »).

`setup.sh` est une copie du script de démarrage enregistré sur l'environnement : il tourne à chaque nouveau conteneur et réinstalle les outils ci-dessous. Chaque étape est non bloquante.

## Outils installés

| Outil | Type | Rôle |
|---|---|---|
| Claude-Mem | plugin | Mémoire entre sessions |
| MarkItDown | MCP | Conversion de fichiers en Markdown |
| One Page Love | MCP HTTP | Inspiration : 9 000+ sites one-page |
| Impeccable (`pbakaus/impeccable`) | plugin | Design front-end, détection du « design IA » (`/impeccable`) |
| HyperFrames (`heygen-com/hyperframes`) | plugin | Vidéo écrite en HTML/GSAP, rendue en MP4 (`/hyperframes:hyperframes`) |
| Agent Reach | skill | Lecture de contenus sur les réseaux sociaux |
| Graphify | skill | Graphe de connaissances |
| gstack | skills | Revue, QA, déploiement, navigateur |

## Réseau

Hôte autorisé en plus du défaut (registres de paquets) : `api.onepagelove.com`.

## Journal

### 2026-11-18
- Ajout du MCP **One Page Love** + autorisation réseau de `api.onepagelove.com`. Vérifié : `claude mcp get onepagelove` → Connected.
- Tentative d'autoriser `mcp.vercel.com`, `mcp.supabase.com`, `mcp.figma.com` pour les versions plugin : abandonnée (OAuth impossible en session cloud), hôtes retirés. Ces services restent disponibles via les connecteurs claude.ai.
- Ajout de **Impeccable** 4.9.2 et **HyperFrames** 0.9.67 (marketplaces officielles). Vérifié :
  - Impeccable : `impeccable detect` repère bien la police Inter sur une page de test.
  - HyperFrames : `hyperframes init` + `render` produit un MP4 de 10 s (Node 22, FFmpeg 6.1 présents).
- Source : vidéo TikTok @chase_ai_ « 5 plugins gratuits pour Claude Code ». Non retenus : Claudex Loop (nécessite OpenAI), Playwright MCP (déjà couvert), Last 30 Days (couvert par Agent Reach / vidIQ).
