# Vague 2 — La fenêtre de pensée en direct

> PR empilée : base **feat/briefs-gameplay-6pts** (Vague 1) — à merger APRÈS elle.

## Ce que change cette PR

La promesse du réglage « **Pensée à découvert** » est enfin tenue à l'écran — et la pensée
native devient une donnée durable du jeu.

- **Fenêtre de pensée en direct** : pendant le tour d'une SI, sa pensée native streame dans
  une fenêtre rétractable (« Pensée de {pays} · en cours ⋯ ») au-dessus de son message —
  fermée par défaut (corps non rendu fermée), queue de 4 000 caractères pendant le stream,
  choix mémorisé (`localStorage`), `<details>` natif sans aria-live, `TurnBubble` mémoïsé
  (fini le re-rendu de toute la page à chaque token). À la fin du tour, le Journal de
  délibération observable prend le relais au même endroit. Le libellé suit la donnée :
  une pensée qui streame ne peut pas prétendre au huis clos.
- **La pensée brute survit** : nouvelle colonne `transcripts.thinking` (SQLite + Supabase,
  migrations idempotentes) alimentée par le canal `<think>` natif (passes privée + secours +
  publique). Jamais dans une trame SSE (retrait inconditionnel à la source) ; vidée en
  relecture tant que la partie est scellée ; **verbatim en fin de partie** — le reveal peut
  désormais montrer ce que le traître pensait vraiment ; section « Pensée brute (verbatim) »
  dans le journal de relecture.
- **La Campagne transmet le réglage** : `expose_thinking` accepté au lancement d'un chapitre
  (le garde-fou existant déclasse la partie — mode observation assumé).
- **Suivi du scroll intra-tour** : la croissance de la pensée et des tokens publics garde le
  théâtre épinglé en bas quand on suit le direct.

## Validation

- **Suites** : 1266 pytest + 347 vitest, tsc / eslint / ruff / `next build` propres.
- **Méthode** : plan TDD 7 tâches, un agent frais par tâche + revue spec/qualité par tâche,
  revue finale whole-branch (fixes appliqués : ordre ALTER/CREATE du schema Supabase,
  libellé data-driven, prop morte) ; correctifs prouvés par mutation.
- **Live (Ollama deepseek-r1:7b)** : partie Pensée à découvert réelle — fenêtre observée en
  stream, journal au done, `thinking` persisté (3,2-5,9 k caractères verbatim par tour),
  round complet U 0,50→0,49, console navigateur sans erreur.

## Suivi hors branche

- **RLS Supabase** (puce dédiée) : la policy propriétaire expose `reasoning`/`thinking`
  scellés via REST direct en partie courante — défense en profondeur à poser avant tout
  déploiement Supabase réel avec jeu classé (dette de classe pré-existante).
- Mineurs consignés : test unitaire du join deux-passes ; `useMemo` du lens Glass Box.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
