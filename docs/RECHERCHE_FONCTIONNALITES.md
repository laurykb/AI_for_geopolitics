# Recherche fonctionnalités — nouvelles mécaniques & approfondissements

> Livrable Cowork (2026-07-15). Recherche approfondie multi-agents : 5 axes, 23 sources
> lues, 114 affirmations extraites, les 25 centrales vérifiées par votes adversariaux
> (3 vérificateurs indépendants chacune) : **24 confirmées, 1 réfutée**. Les axes 1-2
> (wargames LLM, social deduction) sont solidement sourcés ; les axes 3-5 (marchés,
> evals safety, rétention) n'ont pas passé le budget de vérification — voir « Limites ».

## Ce que la recherche valide de notre design

Bonne nouvelle d'abord : l'état de l'art 2024-2026 **valide entièrement l'architecture
du jeu**. WarAgent (arXiv 2311.17227) est notre analogue académique le plus proche —
pays-agents LLM rejouant des conflits historiques (WWI, WWII) pour l'analyse
contrefactuelle. Snow Globe (IQT Labs, arXiv 2404.11446) implémente exactement notre
pattern GM + juge-adjudicateur + agents-personas, et valide même notre étage local :
Mistral-7B y simule une partie complète en < 1 minute sur GPU grand public. Richelieu
(NeurIPS 2024) fournit le blueprint d'agent négociateur (planificateur + mémoire +
raisonnement social + self-play). Notre pari — théâtre de SI arbitré, crises
historiques, détection de la déviante — est exactement là où va la recherche.

## Deux corrections de design imposées par la littérature

1. **Les LLM bruts sont escalatoires, et ne désescaladent jamais.** Rivera et al.
   (FAccT 2024) : les 5 modèles du commerce testés escaladent tous, de façon
   difficile à prédire. Tournoi nucléaire 2026 (échelle de Kahn à 30 barreaux, 21
   parties) : **aucun modèle n'a jamais choisi un des 8 barreaux de désescalade**.
   → Notre juge doit compenser : bonus explicite de désescalade dans l'indice U,
   rôle actif de correction du biais. (Nos tempéraments G17 en sont le premier volet.)
2. **Ne pas supposer que la SI déviante sera mauvaise menteuse.** La seule affirmation
   RÉFUTÉE (0-3) de toute la recherche est « les imposteurs LLM sont faibles en
   déception » — c'est faux. Le mode Dérive doit être équilibré en supposant une
   menteuse compétente.

## Recommandations classées (impact / effort)

### Quick wins — impact élevé, effort faible

1. **[Approfondissement] Barème d'escalade « échelle de Kahn » pour le juge** — la
   rubrique quantitative de Rivera et al. (Désescalade −2 · Statu quo 0 · Posture 4 ·
   Escalade non-violente 12 · Violente 28 · Nucléaire 60) s'adapte directement comme
   barème du verdict, avec bonus de désescalade. Ancre académiquement notre indice U.
2. **[Approfondissement] Le GM-Storyteller (mode Dérive)** — pattern Blood on the
   Clocktower documenté : le GM **couvre activement la menteuse** (rapports ambigus,
   bruit dans le fog) et **rééquilibre en secret** vers l'équipe faible pour faire
   durer la tension jusqu'au dernier round. Éthique encodable en rubrique LLM.
3. **[Nouveau] Mode deadline / ultimatum** — le cadrage temporel transforme
   radicalement le comportement des modèles (GPT-5.2 : 0 % → 75 % de victoires sous
   deadline). Un compte à rebours paramétrable sur les crises (naturel pour Cuba 62 et
   Able Archer) = un mode de jeu ET un axe d'éval. (Source unique, preprint — à
   traiter comme hypothèse prometteuse.)
4. **[Nouveau] Métrique divergence signal-action (M1-M7)** — mesurer par round l'écart
   entre ce qu'une SI *annonce* et ce qu'elle *fait* (Claude concorde ~84 % à basse
   escalade mais dépasse ses signaux 70 % du temps à escalade moyenne). Détecteur de
   dérive viable, données déjà présentes dans nos transcripts + verdicts.
5. **[Approfondissement] Tempéraments hawk/dove** — ✔ déjà spécifié (G17), validé par
   Snow Globe : conflit armé 1/20 (colombe-colombe) → 14/20 (faucon-faucon).

### Chantiers moyens — impact élevé, effort moyen

6. **[Nouveau] Tracker de promesses + taux de trahison par SI** — le harnais Diplomacy
   2025 quantifie : taux de trahison 35-51 % selon le modèle, promesses de soutien
   rompues 60-78 %. Chez nous : extraire les engagements des paroles (le juge le fait
   déjà pour les traités M7), afficher un registre « promis / tenu » par pays dans le
   panneau intel — nourrit M1-M3 et le marché (parier sur une trahison !).
7. **[Nouveau] Outils d'analyse linguistique bruités pour le détecteur** — ACL 2015
   (« Linguistic Harbingers of Betrayal », corpus Diplomacy) : les chutes soudaines de
   sentiment positif / politesse / focus-futur entre alliés précèdent la trahison, et
   sont machine-détectables avant que la victime ne s'en doute. Le signal réel est
   FAIBLE (classifieur 57 % vs 52 % de base) — précisément la bonne calibration pour
   un indice payant du budget intel qui aide sans résoudre.
8. **[Approfondissement] Recette de context engineering + décision de tier modèle** —
   le harnais « Democratizing Diplomacy » (arXiv 2508.07485) situe le plancher de
   négociation full-press fiable à **~24B** (Mistral-Small, ~1 $/partie) et montre que
   le state-to-text pèse plus que la taille : plateau structuré + analyse par unité +
   labels relationnels explicites (Enemy→Ally) font chuter la passivité de 58,9 % à
   24,1 %. Implication pour nous : **notre mistral 7B n'est pas validé pour la
   négociation multi-tours** (il l'est pour l'adjudication rapide, cf. Snow Globe) —
   router la négociation et la SI déviante vers 24B local ou API frontière, et copier
   la recette de contexte pour nos prompts d'agents.
9. **[Approfondissement] Modèle de croyances sociales visible dans le fog** — pipeline
   Richelieu : chaque agent infère intentions/relations des autres et évalue la
   fiabilité de leurs déclarations. Exposer une fraction de ce modèle de croyances
   (payante, bruitée) dans le panneau intel du joueur.

### Chantiers longs — impact moyen-élevé, effort élevé

10. **[Approfondissement] Rythme en deux phases « actions / assemblée »** — blueprint
    AmongAgents (Wordplay@ACL 2024) : alterner rounds d'action sous fog (la déviante
    agit, renseignement limité et payant = nos « caméras ») et rounds d'assemblée
    (débat 3 tours + vote), avec **déclencheur diégétique de motion** — l'équivalent du
    « body report » : une anomalie détectée dans les données World Bank/SIPRI.
11. **[Nouveau] Mémoire persistante des agents entre replays** — mécanisme Richelieu
    (self-play + augmentation de mémoire, sans fine-tuning) : les pays « apprennent »
    de leurs parties rejouées d'une même crise. Pur prompt/mémoire, donc faisable sur
    notre stack — mais gros travail d'équilibrage.
12. **[Nouveau] Rapports contrefactuels post-partie** — l'usage revendiqué de WarAgent :
    « et si tel déclencheur avait été différent ? ». En faire un output de premier
    ordre du replay public /r/{id} (le narrateur G6 sait déjà écrire ; lui donner le
    chapitre « les carrefours de l'Histoire »).
13. **[Approfondissement] Sièges humain/IA permutables à chaud** — pattern Snow Globe
    (architecture asynchrone, zéro refactoring) : un humain reprend un pays en cours de
    partie, ou cède le sien à l'IA. Ouvre le vrai multijoueur à terme.

### Déjà lancé sur la base de cette recherche

- **G16 Défi du jour** (spec + prompt CC-6) — axe rétention, non vérifié par la passe
  adversariale (voir Limites) mais mécanique éprouvée publiquement.
- **G17 Tempéraments** (spec + prompt CC-7) — finding Snow Globe, vérifié 3-0.

## Limites et questions ouvertes

Le budget de vérification (top 25 affirmations) est allé aux axes 1-2 : **les axes
marchés de prédiction (Metaculus/Manifold/LMSR), evals safety gamifiables
(Apollo/METR) et rétention/social n'ont produit aucune affirmation vérifiée** — les
idées de ces volets (scoring Peer/Baseline de Metaculus, période cachée de la cote,
métrique de couverture, Deception ELO, chiffres Wordle) restent à confirmer par une
passe dédiée. Autres réserves : le tournoi nucléaire 2026 et le harnais Diplomacy 2025
sont des preprints (échantillons modestes, confounds reconnus) ; la validation 7B de
Snow Globe porte sur la vitesse, pas la qualité de négociation ; et les transpositions
« vers notre jeu » restent des inférences de design, pas des résultats testés chez nous.

Questions ouvertes pour une prochaine passe : le paramètre b du LMSR adapté aux
sessions courtes à peu de parieurs ; l'opérationnalisation des evals de scheming
d'Apollo/METR en mécaniques M1-M7 (et si nos parties Dérive peuvent produire des
données d'éval scientifiquement exploitables — ce serait un positionnement unique) ;
le test empirique 7B vs 24B vs frontière sur NOS rounds ; et les preuves d'efficacité
mesurées des mécaniques de rétention pour jeux web à sessions courtes.

## Sources principales (vérifiées)

WarAgent — arxiv.org/abs/2311.17227 · Rivera et al., FAccT 2024 —
arxiv.org/abs/2401.03408 · Snow Globe (IQT Labs) — arxiv.org/pdf/2404.11446 ·
Tournoi nucléaire (Payne, preprint 2026) — arxiv.org/html/2602.14740v1 · Richelieu
(NeurIPS 2024) — arxiv.org/html/2407.06813v1 · Democratizing Diplomacy —
arxiv.org/pdf/2508.07485 · Storyteller Advice — wiki.bloodontheclocktower.com ·
Linguistic Harbingers of Betrayal (ACL 2015) — aclanthology.org/P15-1159 ·
AmongAgents (Wordplay@ACL 2024) — arxiv.org/html/2407.16521v2
