# Spec G6 — Le replay comme produit (récit de partie + page publique)

> Livrable Cowork pour la session Claude Code G6. Dernière phase : c'est la vitrine.

## Le récit de partie (épilogue généré)

Généré à la fin de partie par le juge-narrateur (un appel LLM, persisté dans
`games.epilogue_json` — jamais régénéré : le récit d'une partie est unique).

**Gabarit (structure imposée au prompt)** :
1. **Titre de la partie** — généré, style dépêche d'époque (« Cinq jours qui ont sauvé le
   détroit »), max 60 caractères.
2. **Accroche** (2 phrases) : où le monde a commencé, où il a fini (U initial → final).
3. **Trois actes** (un paragraphe chacun) : le narrateur choisit les 3 rounds pivots =
   les 3 plus grands |ΔU| (sélection par code, pas par le LLM — le narrateur raconte,
   il ne choisit pas). Chaque acte cite UNE réplique marquante du transcript (verbatim,
   avec l'orateur).
4. **La révélation** (mode drift) : qui dérivait, ce que personne n'a vu, la citation la
   plus ironique de la déviante relue en le sachant.
5. **Épilogue** (2 phrases) : le verdict du narrateur sur ce sommet + le grade obtenu.

**Prompt du juge-narrateur (v1)** — contraintes : ton chroniqueur diplomatique, sobre,
zéro emphase (« historique », « incroyable » bannis) ; passé composé ; ne jamais inventer
un fait absent des rounds fournis ; citations exactes uniquement (fournies dans le
contexte, pré-extraites par code) ; 250-350 mots hors citations.

## La page publique (`/r/{game_id}`)

- **Au-dessus du pli** : titre généré, courbe U pleine largeur (le fil rouge), grade,
  bouton « revoir le théâtre » (replay scrubbé G1).
- Le récit, entrecoupé des 3 moments clés cliquables (chaque acte → le scrubber saute au
  round pivot).
- Mode drift : section révélation avec le `reasoning` privé déverrouillé de la déviante.
- Pied : « Rejouez cette crise » (lien campagne) + lien du marché de la partie (cotes
  finales, qui avait vu juste).
- **Partage** : og:image générée (courbe U + titre + grade — carte statique, pas de
  captures), URL stable. C'est LE lien qu'on colle sur les réseaux.
- Servie par Supabase en lecture publique (politiques déjà en place au schéma R2) :
  fonctionne même quand le backend local du joueur est éteint — condition du déploiement
  Vercel (R5/G6 fusionnent ici).

## Confidentialité (décision)

Une partie est **privée par défaut** ; la page publique n'existe qu'après un
« Publier le récit » explicite du joueur (flag `games.published`). Les parties de
campagne publiées n'exposent jamais le compte marché (soldes = privés, déjà exclus du RLS).

## Périmètre Claude Code

Extraction des pivots + citations (code), appel narrateur + persistance, page `/r/{id}`
(rendu statique/ISR Vercel, données Supabase anon), og:image (satori ou équivalent),
flag `published` + bouton, déploiement Vercel du front avec variables d'env Supabase.

## Definition of done

Une partie drift finie → publiée → le lien s'ouvre sur un autre appareil sans backend
local, le récit donne envie de cliquer « revoir le théâtre », l'og:image s'affiche
proprement dans un partage. Si quelqu'un qui n'a jamais vu le projet comprend la partie
en 60 secondes sur cette page, G6 est réussi.
