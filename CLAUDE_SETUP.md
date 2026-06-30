# Configuration Claude Code — AI for Geopolitics

Setup **curaté et minimal** (esprit « pas d'usine à gaz »), inspiré d'ECC mais réduit à l'utile pour ce projet. Tout est à la racine du repo.

| Fichier | Rôle |
|---|---|
| `CLAUDE.md` | Mémoire projet (archi, phases, principes, stack) — lue à chaque session |
| `.mcp.json` | Serveurs MCP du projet (filesystem, GitHub, Postgres) |
| `.claude/settings.json` | Hooks (format + lint automatiques) |
| `.claude/hooks/format_lint.py` | Hook ruff (non bloquant) sur fichiers Python édités |
| `.gitignore` | Ignore secrets, modèles lourds, caches |

## 1. Skills / plugins à activer

À privilégier (déjà disponibles dans ton environnement) :

- **Construction IA** : `mcp-builder` (créer les serveurs MCP des outils-pays), `skill-creator` (te fabriquer tes propres skills).
- **Ingénierie** (plugin engineering) : `architecture` (ADR pour tes choix techno), `system-design`, `code-review`, `debug`, `testing-strategy`, `tech-debt`, `documentation`.
- **Docs & livrables** : `doc-coauthoring` (pour `docs/architecture.md`, `simulation_model.md`…), `docx` / `pdf` / `xlsx`, `canvas-design` (schémas).

Principe : **active à la demande**, pas tout d'un coup. Un skill ne sert que s'il correspond à la tâche en cours.

## 2. Serveurs MCP (`.mcp.json`)

Claude Code **demande ton approbation** avant d'utiliser un serveur MCP de projet. Prérequis et activation :

- **filesystem** (actif, maintenu) : `npx` l'installe à la volée. Donne accès à `./data` (ton corpus). Optionnel (Claude Code lit déjà le repo).
- **github** : serveur **officiel GitHub MCP** (image Docker `ghcr.io/github/github-mcp-server`). Nécessite **Docker Desktop** et un **Personal Access Token** exporté en variable d'environnement :
  - PowerShell : `setx GITHUB_PERSONAL_ACCESS_TOKEN "ghp_xxx"`
- **postgres** : ⚠️ le serveur de référence `@modelcontextprotocol/server-postgres` a été **archivé en 2025** (non maintenu) mais fonctionne encore pour de l'introspection locale. À **activer en Phase 1** quand la base existe. Alternative maintenue : *Postgres MCP Pro* (`crystaldba/postgres-mcp`). Connexion via `DATABASE_URL` (jamais en dur).

**Sécurité** : ne committe aucun secret. Les tokens passent par **variables d'environnement** (`${GITHUB_PERSONAL_ACCESS_TOKEN}`, `${DATABASE_URL}`). Si un jour tu inlines une valeur, ajoute `.mcp.json` au `.gitignore`.

## 3. Hooks (qualité automatique)

`.claude/settings.json` déclenche `format_lint.py` après chaque `Edit`/`Write` : il lance `ruff format` + `ruff check --fix` sur les fichiers `.py`. **Non bloquant**, rapide.

- Prérequis : `pip install ruff`. (Sur Windows, si `python` n'est pas dans le PATH, remplace par `py` dans `settings.json`.)
- **Volontairement, les tests ne tournent pas à chaque édition** (trop lourd). Lance `pytest` à la main, en pre-commit, ou en CI. Garde les hooks **légers**.

## 4. S'inspirer d'ECC sans l'« usine à gaz »

ECC (`affaan-m/ECC`) est un harness très complet (~66 agents, ~268 skills, hooks, MCP, scan sécurité **AgentShield**). À **picorer**, pas à installer en bloc :

- Idées à reprendre : la discipline *research-first*, l'idée d'un scan de sécurité avant commit, et leurs patterns de skills.
- ⚠️ Un harness tiers **exécute des hooks/scripts** : audite avant d'installer (chaîne d'approvisionnement). Commence par CE setup minimal, ajoute seulement ce qui te manque réellement.

## 5. Démarrage rapide

1. Installer : `pip install ruff pytest` ; Docker Desktop ; (optionnel) Ollama.
2. `git init` puis premier commit du scaffold.
3. Ouvrir le dossier dans Claude Code — il lit `CLAUDE.md` et propose les serveurs `.mcp.json`.
4. Commencer la **Phase 0** (moteur déterministe, sans LLM) en suivant la roadmap de `CLAUDE.md`.
