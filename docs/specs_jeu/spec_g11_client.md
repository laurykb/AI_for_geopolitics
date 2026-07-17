# Spec G11 — Le Client « World of Super-Intelligence » (WoSI)

> Livrable Cowork. La coquille du jeu, inspirée du client League of Legends : connexion,
> accueil personnalisé, flow de création séquentiel, points de ligue, fin de partie.
> Décisions actées avec Laury (juillet 2026). **Supersède `spec_g8_roles.md`** (les rôles
> sont refondus ici ; la mécanique de directive de G8 reste valable telle quelle).
> Découpage : 4 sessions Claude Code (G11-a → G11-d, prompts en fin de spec).

## 0. Vocabulaire acté

- Le jeu s'appelle **World of Super-Intelligence** (WoSI).
- Modes renommés : **Classique** (classic), **Campagne** (crisis replay — le GM rejoue
  les événements d'un fait historique round par round), **Real World** (escalation
  ladder), **Chaotique** (fog / fake news).
- **Transversaux à tous les modes** : la Dérive (toggle « une des SI peut dériver »),
  la motion de censure + vote, l'intel, le marché, les directives (selon rôle).
- **Classé** = uniquement solo « Jouer un pays ». Tout le reste est non classé.
- L'« architecte » (consignes sur toutes les SI) n'est plus un rôle : c'est un pouvoir
  du rôle **Game Master** et des **parties libres** (non classées).

## 1. Les écrans (machine à états)

```
S0 Connexion → S1 Accueil → S2 Mode → S3 Rôle → S4 Pays → S5 Théâtre → S6 Fin de partie
                   ↑______________________________________________________|
Transitions S1→S2→S3→S4→S5 : animation du globe (dézoom → rotation → rezoom),
≤ 1,5 s, skippable au clic, désactivée si prefers-reduced-motion.
```

### S0 — Connexion
Le globe qui tourne (l'accueil actuel) + panneau : pseudo + mot de passe, boutons
« Se connecter / Créer un compte ». **Auth Supabase** (identifiant technique dérivé du
pseudo, ex. `<pseudo>@wosi.local` — l'utilisateur ne voit jamais d'email ; session
persistée, reconnexion automatique). Hors-ligne/local sans Supabase : repli localStorage
(même UI, flag `offline`).

### S1 — Accueil (personnalisé)
« **Laury, bienvenue sur World of Super-Intelligence** ». Contenu :
- Son **rang de ligue** (blason + LP + barre vers le rang suivant) ;
- **Démarrer** (→ S2) ; **Reprendre la partie** si une partie `resumable` lui appartient ;
- Ses dernières parties (à LUI — remplace l'observatoire) ; sa chronique de campagne ;
- Liens : Leaderboard, Informations (conservé, tout le monde), Admin (si `is_admin` :
  accès à TOUTES les parties — l'ex-observatoire devient la vue admin).
- L'onglet **Observatoire public est supprimé**.

### S2 — Choix du mode
4 cartes (Classique / Campagne / Real World / Chaotique : visuel, une phrase, ce qu'on y
apprend). Sous les cartes, les réglages transversaux :
- **Dérive** : on/off (on par défaut) ;
- **Rounds** : curseur 3-20 (l'amplitude G9 §4 s'indexe dessus) ;
- **Difficulté** : Débutant / Intermédiaire / Expert (§4) ;
- **Partie libre** : off par défaut ; on = non classé + consignes globales autorisées.
Campagne → sélection du chapitre/de la crise (remplace S4, pays imposés par la fiche).

### S3 — Choix du rôle
3 cartes : **Jouer un pays** (badge « Classé » si les conditions du §3 sont réunies),
**Créer son pays** (country_forge, non classé, badge « Libre »), **Game Master** (décrète
les événements, consignes globales, non classé). Le choix conditionne S4.

### S4 — Choix des pays (la carte)
La carte du monde d3 : les 21 pays éligibles en **blanc**, clic → **jaune**, re-clic →
retire. Compteur « 5/7 ». Le bouton **Jouer** reste grisé jusqu'à 7 exactement, puis
passe jaune et cliquable. Rôle « Jouer un pays » : après les 7, il clique son drapeau
parmi les 7 (halo doré). « Créer son pays » : 6 sur la carte + l'étape forge. GM : 7 pays,
pas de drapeau. Survol d'un pays : mini-fiche (capacité unique G7, indices clés).

### S5 — Théâtre
Existant (G1). Ajouts :
- **Accélérer** : « Jouer 3 rounds » (menu 1/3/5) avec barre de progression et bouton
  Stop entre les rounds ; en classé, avertissement « vos tours seront des abstentions ».
- Le bandeau d'échéances G7 et le badge de filiation GM G9 restent tels quels.

### S6 — Fin de partie (transversale à TOUS les modes)
La partie a une fin explicite — plus jamais de « le round s'arrête et rien ». Séquence :
1. Bandeau résultat (« Le monde penche vers l'utopie — U 0,68 ») ;
2. **Courbe U animée** de la partie entière (tracé progressif) ;
3. **Récap pays** : grille des 7 avec sparklines et delta début→fin des attributs clés
   (vert/rouge) — l'évolution de TOUS les pays, pas que le sien ;
4. Révélation Dérive si active (écran G3 existant, inséré ici) ;
5. **Si classé : l'animation LP** (compteur qui monte/descend, barre de rang qui se
   remplit, fanfare de promotion / fracas de relégation) ;
6. Actions : Lire le récit (G6), Revoir le théâtre, Rejouer (mêmes réglages), Accueil.

### S7 — Leaderboard
Classement global (pseudo, blason, LP, parties jouées), son propre rang épinglé en haut.
Vue Supabase publique (pseudo + LP uniquement, jamais l'historique des autres).

## 2. Points de ligue (classé uniquement)

**Formule** (paramètres dans `data/gamefeel/params.json`) :
```
LP = round( K × [ w_monde × (U_final − U_initial) + w_pays × P ] × M_difficulté )
K = 100 · w_monde = 0.6 · w_pays = 0.4
P = moyenne des variations relatives des indices 0-1 de SON pays (stabilité, économie,
    techno, énergie), bornée [−0.5, +0.5]
M = 0.5 (Débutant) · 1.0 (Intermédiaire) · 1.5 (Expert)
```
Négatif possible (« si le monde/son pays finit pire, il perd des LP ») ; plancher 0 LP au
total. Abandon de partie classée = défaite forfaitaire (−15 LP) — sinon on quitte avant
la fin dès que ça tourne mal.

**Rangs** (seuils LP) : Attaché 0 · Émissaire 100 · Diplomate 250 · Ambassadeur 450 ·
Ministre 700 · Chancelier 1000 · Éminence 1400. **En Débutant, gains plafonnés au rang
Diplomate** (anti-farm) ; au-delà, jouer Intermédiaire ou Expert.

**Données** : `players` (id auth, pseudo, is_admin, lp), `lp_history`
(player_id, game_id, delta, ts), vue `leaderboard` (pseudo, lp). `games` gagne
`owner_id`, `ranked`, `difficulty`, `drift_enabled`. RLS : chacun lit SES parties ;
leaderboard public ; admin lit tout (claim `is_admin`).

## 3. Conditions du classé (verrouillées à la création)

Classé ⟺ rôle « Jouer un pays » ET partie libre OFF ET pays non inventé ET pas de mode
admin (G7-c) ET partie jouée jusqu'au bout (ou forfait). Le badge « Classé » n'apparaît
à S3 que si tout est réuni — jamais de surprise en fin de partie.

## 4. Difficulté (asymétrie d'information et d'économie — jamais de changement de modèle)

| Levier | Débutant | Intermédiaire | Expert |
|---|---|---|---|
| Brief gratuit / round | 1 | 0 | 0 |
| Postures + griefs des SI visibles | tout | postures seules | rien |
| Budget intel (G4) | 150 | 100 | 60 |
| Seuil d'actes du juge (motions) | 2 | 2 | 3 |
| Vitesse de dérive k (G3) | 0.09 | 0.12 | 0.16 |
| Contexte des SI | réduit (pas d'analyse du joueur) | normal | + résumé des actions passées du joueur (elles le lisent) |
| Amplitude A (G9 §4) | 0.4 | 0.5 | 0.6 |
| Multiplicateur LP | ×0.5 (plafond Diplomate) | ×1.0 | ×1.5 |

Tout vit dans `data/gamefeel/params.json` (bloc `difficulty`) — équilibrable sans code.

## 5. Ce qui est supprimé / migré

- **Observatoire public** → supprimé ; devient la vue Admin (toutes les parties).
- **Onglet Informations** → conservé pour tous, tel quel.
- **Rôle architecte (G8)** → fondu dans GM + parties libres. Les directives (G8) :
  inchangées techniquement, autorisation par rôle mise à jour.
- Anciennes parties sans owner → visibles par l'admin seulement.

## 6. Découpage Claude Code (4 sessions, dans l'ordre)

**G11-a — Auth + Accueil + navigation** : S0 (Supabase auth pseudo/mdp + repli offline),
S1 personnalisé, suppression observatoire → vue admin, `players`/`owner_id`/RLS,
garde d'authentification sur toutes les routes. Branche `feat/jeu-g11a-client-auth`.

**G11-b — Flow de création + transitions** : S2/S3/S4 séquentiels (machine à états,
retour arrière sans perte), renommage des modes, toggle Dérive transversal, carte de
sélection 7-exactement, transitions globe skippables. Branche `feat/jeu-g11b-flow`.

**G11-c — Fin de partie + LP + leaderboard** : S6 transversal (détection de fin de
partie explicite dans l'API : `game_over` SSE + `games.result_json`), formule LP,
`lp_history`, animations LP/promotion, S7. Branche `feat/jeu-g11c-ligue`.

**G11-d — Difficulté + accélération** : table de difficulté branchée sur les params,
multi-rounds avec progression/stop/avertissement classé. Branche `feat/jeu-g11d-difficulte`.

Chaque session : lire cette spec + PLAN_JEU, tests dédiés (auth gate, 7-exactement,
LP 4 cas — gain/perte/plancher/forfait, classé verrouillé §3, difficulté appliquée),
vérification au front en local.

## Definition of done

Laury se connecte, lit « Laury, bienvenue sur World of Super-Intelligence », voit son
blason ; crée une partie Classique/Expert/classée en 4 clics et 2 rotations de globe ;
la finit ; la courbe U s'anime, ses +23 LP tombent avec la fanfare, le leaderboard
l'affiche premier. Un autre pseudo ne voit RIEN de ses parties. Et l'admin voit tout.
