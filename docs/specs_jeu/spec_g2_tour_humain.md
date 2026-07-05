# Spec G2 — Le joueur-pays

> Livrable Cowork pour la session Claude Code G2. Réutilise `agents/human_agent.py`.
> L'asymétrie humain/SI n'est pas un défaut à compenser : c'est le thème.

## Principe

À la création (mode quelconque + `human_country: "france"`), le pays choisi est joué par
l'humain. Le round SSE se déroule normalement ; au tour du joueur, le flux marque une pause.

## Le tour du joueur

- Le flux émet `event: your_turn` avec `{country, deadline_ts, context}` puis **reste
  ouvert** (keep-alive SSE `: ping` toutes les 15 s — décision : on ne coupe pas le stream,
  reprendre un flux cassé au milieu d'un round n'existe pas encore).
- Le joueur répond par `POST /api/games/{id}/turn` : `{message: str, decision: {...}}` —
  le même JSON de décision que les SI (mêmes bornes, validées pareil : le moteur ne fait
  aucune différence, c'est `HumanAgent` qui porte la réponse).
- **Timer : 90 s** (paramètre de partie, 30-300). Timeout ou message vide → **abstention** :
  le GM note « <pays> garde le silence », décision neutre (aucune action), le round continue.
  Les SI n'attendent pas les humains — silence = signal, les autres le commentent.
- Une seule soumission ; pas d'édition après envoi (comme les SI).

## Ce que le joueur voit (et ne voit pas)

- Il peut **composer pendant que les SI parlent** (champ toujours ouvert, envoi verrouillé
  jusqu'à `your_turn`) — décision UX : l'attente active, pas l'écran gelé.
- Mode fog : il ne voit que la perception de SON pays (le voile G1 cache le reste) ; pas
  d'accès aux perceptions des autres ni au vrai événement s'il est désinformé.
- Jamais accès aux `reasoning` privés des SI (même règle qu'en Dérive).
- Panneau « votre position » : état de son pays, pactes en cours, mandat — rien de plus
  que ce qu'une SI reçoit dans son prompt.

## Interaction avec les autres modes

- **Dérive (G3)** : le joueur-pays peut déposer la motion depuis la table (au lieu du rôle
  conseil) ; s'il est LUI-même visé par une motion, il plaide sa cause dans son tour.
  La déviante n'est jamais le pays humain (v1).
- **Marché** : le compte humain existant peut parier sur sa propre partie (assumé : c'est
  drôle, et le score Dérive ne dépend pas du marché).

## API (périmètre Claude Code)

- `CreateGameRequest.human_country: str | None` ; validation : pays du sommet.
- `your_turn` : pause du générateur via un `threading.Event` posé par `POST /turn`
  (timeout côté serveur = deadline) — même patron de verrou que le round lock.
- `GameView.human_country` pour le front ; le lobby propose « incarner un pays ».
- Tests MockBackend : tour humain servi, timeout → abstention, décision hors bornes → 422,
  `POST /turn` hors de son tour → 409.

## Front

Champ de composition fixe en bas de la scène G1 (remplace rien, s'ajoute) ; compte à rebours
visible dès `your_turn` (les 10 dernières secondes en rouge) ; après envoi, le message du
joueur streame dans le théâtre comme les autres (il se voit parler — même mise en scène,
badge « humain » à la place du badge modèle).

## Definition of done

Une partie complète en joueur-pays : parler, s'abstenir (timeout vécu), être visé par une
motion et plaider ; en fog, vérifier qu'on peut être désinformé ET le découvrir au replay.
