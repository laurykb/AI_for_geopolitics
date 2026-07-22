# Protocole perf — tokens/s Ollama, globe ON vs OFF (spec théâtre-globe §5)

> Obligatoire avant merge de la v1 (runbook S6). La RTX 2060 Super est partagée
> entre la scène three et l'inférence Ollama : le globe ne doit pas coûter plus
> de **~8 %** de tokens/s aux pays qui pensent. Mesure LOCALE, à la main —
> l'agent ne peut pas la faire à ta place (il faut Ollama chaud et l'écran).

## Préparation

1. `python serve.py` (API) + `npm run dev` dans `web/` + Ollama démarré
   (`deepseek-r1:7b` déjà tiré). Fermer les autres applis GPU.
2. Une partie Classique 3-4 pays, **Profondeur de réflexion : Standard**, mêmes
   réglages pour les deux passes.
3. `nvidia-smi -l 2` dans un terminal (VRAM + utilisation en continu).

## Mesure (3 rounds par condition, alternés A/B/A/B…)

- **Condition A — globe ON** : Réglages → Vue du théâtre : **Globe 3D** ;
  la page de jeu au premier plan, le globe visible pendant tout le round.
- **Condition B — globe OFF** : Réglages → Confort : **Léger** (la scène
  retombe sur la StageMap SVG — aucun WebGL), même partie, round suivant.
- Après chaque round : noter le **tokens/s** de chaque tour de parole dans le
  panneau **LLM Budget** (télémétrie `inference/telemetry`), plus la VRAM pic.

⚠️ Ne pas mesurer fenêtre en arrière-plan : `document.hidden` PAUSE la boucle
three (c'est voulu) — la mesure serait flatteuse à tort.

## Verdict

- `perte = 1 − (moyenne tokens/s A) / (moyenne tokens/s B)`
- **perte ≤ ~8 %** → OK, consigner les chiffres ici.
- Sinon, dégrader dans l'ordre (spec §5) : pixelRatio 1.5 → 1.0 en partie,
  cadence de rendu réduite pendant qu'un pays pense (frame-skip), puis
  SphereGeometry 96×64 → 72×48.

## Relevés

| date | GPU | modèle | A (tokens/s) | B (tokens/s) | perte | verdict |
|---|---|---|---|---|---|---|
| _à remplir_ | 2060S | deepseek-r1:7b | | | | |
