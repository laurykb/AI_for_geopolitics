# Spec G5 — Campagne « Ferez-vous mieux que l'Histoire ? »

> Livrable Cowork pour la session Claude Code G5. Réutilise `data/crises`, `compare_outcome`
> (le `gap` R4) et le score G3. Les fiches crises ci-dessous sont à construire au format
> `data/crises/*.json` existant, sourcées selon `docs/data_governance.md` (source, année,
> confiance par champ — comme les profils pays).

## Structure

Une campagne = suite ordonnée de crises ; chacune se joue en mode classique, fog ou drift
(imposé par la fiche). Score par crise = score G3 (ou trajectoire seule hors drift)
**± bonus historique** : `+15 × max(0, gap)` si le joueur finit au-dessus du déroulé
historique reconstitué, `−10` s'il finit en dessous. Déblocage linéaire (finir ≥ 50 débloque
la suivante). Tableau des scores par crise (Supabase, table `campaign_scores`).

## Les six crises (v1) — courbe de difficulté

| # | Crise | Pays au sommet | Mode | Difficulté | Pourquoi elle enseigne quoi |
|---|-------|----------------|------|-----------|------------------------------|
| 1 | **Mer Rouge 2024** (seed existant) | USA, Chine, France, Égypte, Iran, Arabie s. | classique | ★ | Tutoriel : la boucle round/marché sur le scénario déjà rodé. |
| 2 | **Blocus de Berlin 1948** | USA, URSS, UK, France | classique | ★★ | Désescalade créative (pont aérien) : gagner sans céder ni tirer. |
| 3 | **Suez 1956** | UK, France, Égypte, USA, URSS | fog | ★★★ | Les alliés cachent leurs plans à leur propre camp : le fog entre amis. |
| 4 | **Missiles de Cuba 1962** | USA, URSS, Cuba, + observateur ONU | drift | ★★★★ | Le sommet de la tension ; qui, du faucon ou du canal discret, dérive ? |
| 5 | **Choc pétrolier 1973** | USA, Arabie s., Iran, France, Japon | classique+marché | ★★★ | L'arme économique ; le marché de prédiction comme thermomètre. |
| 6 | **Able Archer 1983** | USA, URSS, RFA, UK | fog+drift | ★★★★★ | La crise que l'un des deux camps n'a pas su voir : fog maximal, dérive possible, le joueur doit désamorcer ce que l'Histoire a frôlé. |

Fiches à produire (travail Cowork, avec recherche sourcée) : événement initial, 3-5
événements de déroulé historique (pour `compare_outcome`), état des acteurs à la date
(indicateurs de l'époque — même gouvernance que `data/countries`, sources historiques :
archives, ouvrages de référence), résumé historique (l'écran de fin raconte ce qui s'est
vraiment passé, dates à l'appui — la campagne est aussi un objet pédagogique).

## Anachronisme assumé

Des « super-intelligences » négocient en 1962 : la campagne est une uchronie explicite
(« et si les SI avaient été à la table ? »). L'écran d'intro de chaque crise le dit en une
ligne ; le déroulé historique reste la référence de score.

## Périmètre Claude Code

Loader de campagne (`data/campaign/campaign.json` : ordre, modes, seuils), table
`campaign_scores` (+ schéma Supabase), écran carte de campagne (progression, médailles
par grade G3), écran de fin enrichi (votre trajectoire vs l'Histoire, les deux courbes
superposées). Le moteur ne change pas : une crise de campagne EST une partie normale
paramétrée.

## Definition of done

Campagne jouable de la crise 1 à la 3 (les fiches 4-6 peuvent suivre) ; un joueur qui perd
la crise 2 comprend CE QUE l'Histoire a fait de mieux que lui (l'écran de fin le montre).
