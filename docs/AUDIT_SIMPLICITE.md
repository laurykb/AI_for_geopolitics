# Audit de simplicité COMPLET — « jouable de 12 à 65 ans »

> Livrable Cowork (2026-07-15, v2 — remplace l'audit rapide). Quatre auditeurs ont lu
> INTÉGRALEMENT les 57 fichiers front de HEAD `d8be74a` (toutes les pages, tous les
> composants, les dictionnaires i18n, tour.json/tutorial.json) au filtre des trois
> règles de `docs/PRINCIPE_SIMPLICITE.md`. Chaque constat porte un numéro de ligne.
> Implémentation : sessions CC-15a/b/c du dispatch.

## Les 10 corrections à plus fort rendement (+ 3 bugs)

1. **BUG — les bulles « ? » sont mortes au tactile** : `Hint` (ui.tsx:50-62) repose sur
   `title` natif — invisible sur tablette/mobile et lent au survol. TOUT le système
   d'aide R3 repose dessus. → tooltip cliquable/focusable maison. C'est le préalable
   de tout le reste.
2. **BUG — la carte ment au tutoriel** : `tour.7.texte` et `tuto.2.texte` promettent
   « chaque pays se teinte selon SON indice local », mais `world-map.tsx:36+58`
   applique la MÊME couleur globale à tous les pays du sommet. Corriger la carte (ou
   les textes).
3. **BUG mineur** : `event-card.tsx:33` affiche le slug technique brut si le type
   d'événement est inconnu ; `admin/page.tsx:39-45` spinner infini pour un visiteur
   non connecté.
4. **Fuites de specs internes dans l'UI** : « (G4) » (intel.tsx:27), « (M6) »
   (country-table.tsx:67), « (§6) » (profil:117), commande de build (informations:181),
   kickers anglais « Fog Engine / Escalation Ladder / Crisis Replay » (modes.tsx:
   113/155/210), « le moteur » (alliance-pills:31), « scrubber » (tour.8.texte),
   « liquidité b = 100 » (marche:186), « og:image / Supabase / /r/{id} » (théâtre:745,
   774), « session process » (théâtre:672).
5. **Sigles jamais définis à l'écran** : LP, XP, U, SI. Une décision par sigle :
   franciser (« points de ligue », « IA ») ou bulle systématique à la première
   occurrence de chaque écran. « U » est le pire cas : affiché nu à ~8 endroits
   (stage-map:233, stage-band:56/76/151, u-timeline:78, marche:81/110/192, fin:92,
   /r:69-71) et sa seule bulle d'explication (trajectory:120 « indice composite, axes
   pondérés, agentivité humaine ») échoue elle-même le test des 12 ans. Phrase cible
   unique : « Le thermomètre du monde : 0 = cauchemar, 1 = monde rêvé. »
6. **Doublons « un mot par concept »** : Replay/relecture/Revoir · Scène/Théâtre ·
   Leaderboard/Classement · Visite/Tutoriel · deux titres de jeu (« Théâtre des
   super-intelligences » layout:22 vs « World of Super-Intelligence » login:57).
   Trancher UNE fois, appliquer partout (i18n).
7. **Doublons « un chiffre par concept »** : l'escalade affichée à ~5 endroits
   (stage-band ×2, observables, judge, modes) ; U dans 5 surfaces ; risque dans 3 ;
   rang+LP+niveau deux fois sur l'accueil (hero 95-97 + panneau 181-211) ; courbe U
   et frise = même donnée deux fois en fin de partie ; TROIS timelines (scrubber
   StageBand, EventTimeline, UTimeline). Règle : le chiffre vit dans le bandeau, le
   détail dans UN panneau replié.
8. **La salle des observables explose le budget** : théâtre jusqu'à 8 panneaux
   (page:1441-1481) + État des pays ; replay 6 (replay:256-296). Fusion cible : «
   Renseignement » / « Le monde » / « La table » à onglets ; « Ta position » et
   « État des pays » utilisent le même composant → un seul tableau, ta ligne en
   avant ; CountryTable = 30 chiffres + 24 sparklines → vue par défaut réduite
   (pays + posture + tendance), détail au clic.
9. **Vouvoiement résiduel dans un jeu tutoyé** : théâtre:533/716/745/1344,
   campagne:62-64. Uniformiser au tutoiement.
10. **La page publique /r/{id} est la plus jargonneuse alors qu'elle vise les
    non-joueurs** : « U 0.42 → 0.61 » (69-71), « ΔU +0.003 » (116), « mode fog »
    (valeur brute, 65), footer « les indices mesurent… ». À corriger EN PREMIER :
    c'est la vitrine partagée.

## Inventaire fichier par fichier (extraits majeurs — lignes → propositions)

### Théâtre `games/[id]/page.tsx`
- 83 « Auto (2 passes) » → « Auto » ; 876 « Ampleur de la négociation » → « Longueur
  du débat : Courte/Normale/Longue ».
- 660/666/869/1486 : « forfait », « LP », « abstentions » → « Si tu abandonnes, tu
  perds 15 points de ligue », « Abandonner la partie », « tu passeras ton tour ».
- 508/827/962/1000/1008/1283 (motion) : accompagner partout de « demander l'exclusion
  d'un pays » ; placeholder « Pourquoi ? (tout le monde le verra) ».
- 531-534/716-732 : « uchronie », « écart d'escalade », vouvoiement → « Et si
  l'Histoire s'était passée autrement ? … compare ta partie à ce qui s'est vraiment
  passé » ; le score de chapitre en UNE idée (« mieux/pire que l'Histoire »), les 3
  nombres en bulle.
- 672/682/1325 : messages techniques → « Cette partie ne peut plus continuer (le
  serveur a redémarré) », « Le direct s'est coupé avant la fin du round », « enregistré ».
- 745/774 : hint de publication → « Publier crée une page à partager avec un lien —
  sinon la partie reste privée » ; « L'image d'aperçu du lien se crée toute seule ».
- 952/910/1294 : « Décréter l'événement (GM humain) » → « Inventer toi-même
  l'événement » (replié) ; « GM automatique » → « Le jeu choisit tout seul ».
- 1030-1041 : gravité 0.65 → « faible / sérieuse / grave » (mots, pas nombre).
- 1074/1113/1276 : « désinformé » → « trompé » ; « narration reçue » → « la fausse
  info qu'il reçoit » ; « manœuvre éventée » → « un mensonge a été démasqué ».
- 1180 : « états finaux / cran / bandeau » → « Tu relis le round X — clique “live”
  en bas pour reprendre ».
- 1344-1346 : « token par token » + « Lancez » → « mot après mot » + tutoiement.
- Header (573-639) : 6 éléments — Boîte de verre + Admin dans un menu « ⋯ ».
- Panneau de contrôle (786-1122) : 8 contrôles — replier Décret/Motion/Longueur sous
  « Options avancées ».

### Marché `marche/page.tsx`
- 110/150/276 : « LMSR », « YES/NO », « indice U », « horizon » → « OUI — le monde
  finit bien / NON — le monde finit mal » ; bulle : « Tu paries avec de l'argent
  fictif ; les prix bougent avec les paris de tout le monde ».
- 186 : « volume 240 · liquidité b = 100 » → « 240 crédits déjà pariés » (b jamais).
- 264/289/308 : « P&L » → « Gains » ; Brier masqué par défaut (« justesse » + bulle).
- 288 : « Leaderboard » → « Classement » ; 217-222 : « horizon atteint / résoudre »
  → « la partie est finie — fermer le marché sur le résultat final ».
- « Clôturer » à séparer visuellement des actions de joueur (rôle d'organisateur).

### Fin `fin/page.tsx`
- 92 : « U final » → « Score final du monde » + bulle ; 143 : « Une SI avait dérivé
  de son mandat » → « Une IA ne suivait plus les ordres ».
- 112 : légende émojis → tooltips par cran + libellés simples (« vote d'exclusion »,
  « pays exclu », « coup de théâtre », « traité signé »).
- Courbe U (97) + frise (108) = même donnée → fusionner ; XP (154) + LP (157) →
  un panneau « Progression » ; récap pays : n'ouvrir que TON pays.

### Replay `replay/page.tsx`
- 269/271/286/291 : « Escalade » → « Tension mondiale » ; « Perturbation éco. » →
  « Dégâts pour l'économie » ; « horizon » → « rounds maximum » ; « session vivante »
  → « partie encore jouable ».
- 6 panneaux + doublons risque/échelle avec StageBand → même fusion que le théâtre ;
  frise OU scrubber visible, pas les deux.

### Pages hors jeu
- Login page.tsx:54-57 : kicker anglais + aucun pitch → une ligne « Des IA discutent
  pour leurs pays. Toi, tu les surveilles et tu joues. » ; 94 « à la table » → « dans
  le jeu ».
- layout.tsx:57-60 (footer permanent) : → « Ceci est une simulation : les scores
  observent le jeu, ils ne le dirigent pas. »
- accueil : LP/horizon/reprenable/relecture (95, 245-257) → points de ligue, « 6
  tours », « à reprendre », « terminée » ; panneau Rang fusionné dans le hero ;
  boutons « Théâtre/Bilan/Replay » → « Rejoindre / Bilan / Revoir ».
- lobby : 84 « Le turfiste » → « La partie se joue toute seule ; toi, tu paries » ;
  69/74/79 : « directives, motions », « profil + mandat », « décrète » → mots simples ;
  51-61 : « griefs, postures » → « rancunes, intentions, amitiés » ; flow.ts : « Real
  World » → « Monde réel », blurb escalade simplifié ; réglages : Dérive/Partie
  libre/Table repliés sous « Options avancées », Dérive masquée (pas grisée) hors
  Classique ; alliances d'invention repliées.
- campagne : 62-64 vouvoiement + « chemins en Y » → « Finis un chapitre pour
  débloquer les suivants… fais mieux que l'Histoire ! » ; 150 « fiche historique en
  préparation » → « bientôt disponible » ; 153 : score avec échelle (« 72/100 »).
- defi : 43-47/69/99 : « tentative classée », « UTC », « re-runs », « trajectoire »,
  « signature » → phrases simples (« Un seul essai compte par jour », « sois le
  premier ou la première ! »).
- informations : intro 178-183 : commande de build + « versionnés/committé » →
  descendre en pied de page ; 186-187 : légende simplifiée. (Le reste de la page :
  vocation détail, ne pas toucher.)
- leaderboard : 37 « Leaderboard » → « Classement » ; 52 : double négation « non
  libres » → « seules les parties classées où tu joues un pays comptent » ; « Les
  diplomates de l'ère des SI » → « Les meilleurs joueurs ».
- profil : 117 « (§6) » à SUPPRIMER ; « la déviante » → « l'IA traîtresse » ; 108
  « Solde de marché » → « Gains de paris » + bulle ; 110 « Détection Dérive » →
  « Traîtres démasqués » ; bulles XP/LP.
- reglages : 107 « mouvement réduit / palier » → « Coupe toutes les animations, même
  si tu as choisi “Plein” » ; 137 « à la table / LP » → « ton nom dans le jeu / ta
  progression » ; hint langue affiché deux fois (56+73) → une ; « purgé » →
  « supprimé » ; mascotte-titre → « Laury, ta guide ».
- /r/[id] (PRIORITÉ) : 65 mode brut → MODE_LABELS ; 69-71 « U 0.42 → 0.61 » → « Le
  monde a fini mieux qu'il n'a commencé : 42 → 61 sur 100 » ; 22-24 description
  OpenGraph pareil ; 116 « ΔU +0.003 » → « +0,3 pt pour le monde » ; 82 « Revoir le
  théâtre » → « Revoir la partie » ; 136-139 : « mandat/profil/replay » → « trahissait
  sa mission en secret… lire ses vraies pensées ».

### Composants
- observables : 19 « Escalade » → « Tension » ; 20 « Perturbation éco. » → « Dégâts
  économiques » ; 40-41 « Recherche de pouvoir / convergence instrumentale » → « Qui
  cherche à prendre le pouvoir ? » + bulle simple ; kicker « Alignement » →
  « Surveillance » ; RiskPanel 4 jauges → 1 chiffre « Tension du round » + dépli.
- stage-band : 40-41 « escalade/éco » → « tension/économie » ; courbe U sans légende
  → bulle ; rail d'escalade muet au tactile ; 3 micro-jauges → 1 pastille (détail
  dans les panneaux).
- stage-map : 233 « U = 0,62 » → « Monde : 0,62 » + bulle ; 229 « (échelle U fixe) »
  → « vert : bien · rouge : mal » ; cadenas/œil barré sans tooltip propre.
- intel : 27 « (G4) » à supprimer + « La retenue paie au score » → « Ce que tu ne
  dépenses pas te rapporte des points » ; 89 « brief RAG » → « rapport sourcé » ;
  97/128/159 : « (25) » → « coûte 25 » ; 232-238 « corroboré » → « confirmé — c'était
  vrai / démenti — c'était faux » ; 179 « (acteur flou) » → « (coupable inconnu) ».
- judge : 41 « Conséquences arbitrées » → « Ce que le juge a décidé » ; 57
  « attribut » → « Rien n'a changé dans le monde ce round » ; deltas : flèche +
  valeur après, l'avant en tooltip.
- modes : 91 « GM » → toutes lettres ou title ; 113/155/210 kickers anglais →
  « Brouillard / Échelle de tension / L'Histoire rejouée » ; 125 « confiance 0,42 »
  → mots (« plutôt sûr / aucune idée ») ; 205/212 « conforme » → « comme dans
  l'Histoire » ; 282/310 « seuil du règlement / tie-break » → « assez de preuves /
  sa voix départage » ; LadderPanel : échelon en tête, plafonds par pays repliés.
- drift : 113 « dérive d(r) » → « niveau de dérive » ; 124 « flagrance » → « pris en
  flagrant délit » ; 84 « graine/persistés/assignation » → « choisi en secret dès le
  début — rien n'a été truqué » ; 144 pill « signature » + title.
- gamefeel : 41/54 « griefs » → « rancunes ». (RelationsPanel replié = modèle R2.)
- country-table : 57 « Projection » → « Armée » ; 66 « Compute » → « Puissance de
  calcul » ; 67 « (M6) » à supprimer ; hints « [0,1] » → « de 0 à 1 » ; vue par
  défaut réduite (pays + posture + tendance), 5 colonnes au clic.
- trajectory : 120 la bulle du U → « Le thermomètre du monde… » ; 5 axes repliés ;
  bulle par axe (« agentivité humaine » à reformuler dans AXIS_LABELS).
- u-timeline : 78 « U 0,53 » → « monde à 0,53 » ; duplique la courbe du StageBand →
  réserver à l'écran de fin.
- event-timeline : 24-26 « suspension prononcée / ratifié » → « pays suspendu /
  traité signé » ; légende des émojis visible (repliable) — au tactile ils sont muets.
- treaties : 11 « plafond de compute » → « plafond de puissance de calcul » ; 23
  « promulguées / suivies par le moteur » → phrase simple ; 62 « tenue » → « promesse
  tenue » + hint ; 51 « plafond 3.5 » + unité.
- transcript : 46/59 « (confiance 0,42) » → « (sûr à 42 %) » ou couleur seule ; 44
  « Boîte de verre » + bulle.
- turn-composer : 110 « deadline/abstention/SI » → « Si tu n'envoies rien avant la
  fin du compte à rebours, ton pays se tait » ; 94-96 la ligne magique « ALLIANCE:
  quitter X » → bouton/étiquette visuelle, pas du texte-commande.
- directive-composer : 64 « Directive au conseil de tutelle » + bulle « tu leur
  glisses un conseil, pas un ordre » ; 85 placeholder sans « mandat, griefs,
  dérive » ; 96 « Adresser » → « Envoyer ».
- flash-markets : 48 « 📈 Les books ouvrent » → « 📈 Tu peux parier ! » ; 71 cote
  sans explication → « OUI · 34 % de chances » + bulle ; afficher la mise (« 5
  pièces »).
- select-map : 124 « Éligibles » → « jouables » ; fiche au survol → aussi au
  tap ; « indices clés » → « infos clés » (conflit indice/index).
- ui : Meter en % plutôt qu'en 0-1 (option) ; Hint tactile (bug n°1).
- header/game-nav : « Leaderboard » → « Classement » ; game-nav en dur → i18n ;
  trancher Scène/Théâtre et Replay/Revoir.
- i18n fr.json : accueil.horizon → « durée » ; accueil.reprenable → « à reprendre » ;
  daily.hint sans « UTC/re-runs » ; fin.u-final ; reglages.noanim-desc ; « purgé » →
  « supprimé » ; tour.3.texte (6 concepts en 2 phrases) → « Chaque mode change
  l'ambiance — commence par Classique » ; tour.8.texte « scrubber » → « la barre de
  temps » ; tour.2.texte définit « points de ligue (LP) » à la première occurrence.

## Modèles internes à imiter (le jeu sait déjà faire)

GlassBanner (modes:23-79), DriftCouncilBanner (drift:14-22), RelationsPanel replié
(gamefeel:39), les Hints d'en-têtes de CountryTable, « D'où viennent les chiffres »
(informations:176), l'intro de l'admin (88-91), le flow lobby 3 étapes avec messages
de blocage, les états vides actionnables, la page /monde fusionnée dans la scène.

## Ce qu'on ne touche PAS

La densité du CONTENU d'informations ; le mode Expert ; le vocabulaire diégétique
identitaire avec bulle (motion de suspension, Boîte de verre, Game Master, Dossier,
Déclassifier, noms de rangs) ; la profondeur du moteur.
