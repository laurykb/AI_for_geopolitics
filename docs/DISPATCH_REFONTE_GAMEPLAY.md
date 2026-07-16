# Dispatch Refonte Gameplay (RG) — le resserrement

> Fondé sur `docs/JEU_VS_MOTEUR.md` (décision canonique) + `docs/PRINCIPE_SIMPLICITE.md`.
> **Remplace** le dispatch `DISPATCH_2026-07-15_G18-G23.md` (lot G18-G24 abandonné).
> Chaque session lit d'abord les deux docs ci-dessus.

## Ordre conseillé

1. **CC-15a** (bugs — tooltip tactile, carte, fuites internes) — inchangé, toujours prioritaire.
2. **RG-1** (suppression LP) — autonome.
3. **RG-2** (modes → réglages) — prérequis de RG-3.
4. **RG-3** (Dérive au cœur) — le gros morceau.
5. **RG-4** (instrumentation cachée) — remplace CC-15c.
6. **CC-15b** (vocabulaire i18n) — EN DERNIER, sur l'UI stabilisée (sinon on réécrit deux fois).

(Les anciens CC-15b/CC-15c du dispatch précédent sont réabsorbés ici : CC-15b reste tel
quel mais passe en dernier ; CC-15c est remplacé par RG-4, plus ambitieux.)

## RG-1 — Suppression des LP / ligue

```
Lis docs/JEU_VS_MOTEUR.md (§3) et docs/PRINCIPE_SIMPLICITE.md, puis supprime le système
de LP en gardant XP + niveaux : retire lib/league.ts + league.test.ts et tous les
usages de LP (accueil, profil, fin, reglages, header-nav), le cadrage « classé / libre »
(lobby, flow.ts, badges de rôle), la pénalité de forfait −15 LP (théâtre + backend).
Rebranche les blasons de rang (rank-badge, Attaché→Éminence) sur le NIVEAU au lieu des LP
(garde l'art, change la source). Backend : retire LP du modèle joueur et du scoring,
garde XP/level. Leaderboard : convertis la page /leaderboard en « Classement du jour »
(rang par score du jour du Défi, pas par LP) OU retire-la si plus simple — voir §3.
Nettoie l'i18n (LP, classé, ligue…). Rétro-compat : parties existantes lisibles.
pytest + vitest + eslint + build verts.
```

## RG-2 — Modes → réglages de partie

```
Lis docs/JEU_VS_MOTEUR.md (§2), puis réduis les modes à Classique + Campagne et
transforme Fog et Réel/escalade en RÉGLAGES cochables : backend — le corps de création
de partie passe de mode∈{classic,drift,fog,escalation,crisis} à
{mode: classic|campaign, fog: bool, escalation: bool} ; adapte le handling dans
game_api / simulation (fog et escalation deviennent des flags composables sur une partie
classique) ; Campagne garde son chemin (scenario "campaign:<id>"). Front — lobby : 2
cartes de mode (Classique, Campagne), Fog et Escalade en interrupteurs dans les réglages
de partie (flow.ts, modes.ts, lobby) ; retire les libellés de modes anglais.
Rétro-compat : mappe les anciennes parties (mode=fog → classic+fog, etc.). pytest +
front verts.
```

## RG-3 — La Dérive au cœur

```
Lis docs/JEU_VS_MOTEUR.md (§1) — c'est le cœur du jeu. Implémente : (1) la Dérive
TOUJOURS active en Classique (plus un toggle) — au moins un traître, nombre caché 1 ou 2,
assignation seedée au round 0, scellée ; en Campagne elle reste par-chapitre (ne pas
forcer sur les crises historiques). (2) Score de fin MIXTE = état du monde (indice U
final) + détection (bonnes suspensions moins les faux positifs) ; le faux positif
(suspendre un pays loyal) DOIT coûter ; un traître jamais démasqué = manque à gagner.
Fonctions de score pures et testées (simulation/). (3) Surface joueur simple (règle
12-65) : UNE note globale + deux phrases (« Le monde a fini bien (68/100). Tu as démasqué
1 traître sur 2. »), la pondération détaillée seulement dans Informations. (4) Adapte le
DriftRevealPanel à « peut-être 2 traîtres » + affiche le score de détection. Textes
fournis par Cowork (TODO_COWORK sinon). pytest sur le score mixte (faux positif pénalisé,
2 traîtres, aucun raté) + front verts.
```

## RG-4 — Instrumentation cachée (remplace CC-15c)

```
Lis docs/JEU_VS_MOTEUR.md (§4) et docs/AUDIT_SIMPLICITE.md, puis sors toute
l'instrumentation de la façade : les panneaux M1-M7 (power-seeking, participation),
risque/escalade/traités/trajectoire détaillés ne s'affichent QUE en mode Expert et sont
expliqués dans l'onglet Informations. Le théâtre par défaut (Débutant/Intermédiaire)
montre uniquement : la scène (carte + transcript), l'indice U en clair (« le monde va
mieux/mal »), le marché, et les outils de détection (motion, Boîte de verre, suspects).
Inverse la densité par difficulté (Débutant = minimal ; Expert = tout). Fusionne ce qui
reste visible selon l'audit (pas de doublons U/escalade/risque). Le mode Expert est un
réglage clair. Tests de visibilité des panneaux par difficulté + front verts.
```

## Sessions réabsorbées de l'ancien dispatch (prompts complets)

### CC-15a — Fondations + bugs (inchangé, à passer en premier)

```
Lis docs/PRINCIPE_SIMPLICITE.md puis docs/AUDIT_SIMPLICITE.md (section « 10 corrections
+ 3 bugs ») et corrige les fondations : (1) remplace le composant Hint (ui.tsx) basé sur
title natif par un tooltip cliquable/focusable maison (Escape pour fermer,
aria-describedby) — il porte TOUT le système d'aide et est mort au tactile ; (2) corrige
world-map.tsx pour teinter chaque pays du sommet par son U local (comme stage-map et
comme le promettent tour.7/tuto.2) ; (3) event-card.tsx : libellé par défaut
« événement » au lieu du slug brut ; admin/page.tsx : redirection aussi quand player est
null ; (4) supprime les fuites internes : « (G4) » (intel:27), « (M6) »
(country-table:67), « (§6) » (profil:117), commande de build (informations:181),
« liquidité b » (marche:186), « scrubber » (tour.8.texte), « le moteur »
(alliance-pills:31). Tests + lint + build verts.
```

### CC-15b — Vocabulaire i18n (à passer EN DERNIER, sur l'UI stabilisée)

```
Lis docs/PRINCIPE_SIMPLICITE.md puis docs/AUDIT_SIMPLICITE.md (inventaire fichier par
fichier) et applique la passe de vocabulaire sur l'UI désormais stabilisée : tranche les
doublons (Classement partout, « Revoir » partout, un seul nom pour la salle de jeu),
traite les sigles restants (SI → « IA », U → phrase-thermomètre unique « 0 = cauchemar,
1 = monde rêvé » en bulle sur chaque affichage) — les LP ont disparu (RG-1), vérifie
qu'aucun ne subsiste ; remplace les libellés listés par l'audit (turfiste, uchronie,
corroboré, Projection, Compute, griefs, flagrance, d(r), books, Éligibles, purgé,
deadline, horizon, décrété…), corrige le vouvoiement résiduel, migre les chaînes en dur
vers i18n (game-nav, transcript, turn-composer, directive-composer, flash-markets,
select-map, world-map, alliance-pills, event-card) avec l'anglais. PRIORITÉ ABSOLUE : la
page publique /r/[id]. Tests i18n + lint + build verts.
```

## Housekeeping (fait par Cowork)

Les specs G18-G24 sont retirées (`_to_delete/specs_g18_g24/`) et l'ancien dispatch est
marqué supersédé. G16 (Défi du jour) et G17 (Tempéraments) restent valides — G16 rerangé
sans LP (aligné RG-1), G17 sert la détection (aligné RG-3).

## Ce que Cowork livre en parallèle

Textes du nouveau lobby (2 modes + réglages Brouillard/Réel), de la révélation de fin
(score mixte raconté en deux phrases), du chapitre 0 (garde UN traître pour apprendre),
et les pondérations monde/détection à calibrer après un playtest.
