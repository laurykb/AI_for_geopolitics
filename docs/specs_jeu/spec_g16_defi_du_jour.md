# Spec G16 — Le Défi du jour (« Le Sommet du jour »)

> Livrable Cowork (2026-07-15), issu de la recherche fonctionnalités (axe rétention).
> Le mécanisme « même puzzle pour tout le monde, une fois par jour, résultat partageable »
> est le levier de rétention le mieux documenté des jeux à session courte (effet
> Wordle : ~90 joueurs → 3 M en quelques mois, porté par le partage du résultat).
> Chez nous, TOUT existe déjà : crises scriptées qui avancent avec les rounds (CC-5),
> leaderboard, LP, marché LMSR, page publique /r/{id} avec og:image.

## Principe

Chaque jour, **un même sommet pour tout le monde** : même crise (scriptée ou seedée),
mêmes 7 pays, même pays imposé au joueur, même horizon court (4-5 rounds), même graine
aléatoire côté moteur. Une **seule tentative classée par jour et par joueur**. Le score
du jour (score de chapitre existant : trajectoire + verrous) alimente un **classement du
jour**, et l'écran de fin propose une **carte de partage** (la frise G15 en miniature +
rang du jour), sans spoiler l'événement du jour dans le texte partagé.

## Découpage

- **Backend** (`app/daily_api.py`, ~1 endpoint + 1 module) :
  - `GET /api/daily` → le défi du jour : `{date, crisis_id, countries, play_as, horizon,
    seed, attempted: bool, leaderboard: [{pseudo, score, rank}]}`. Le défi est **dérivé
    déterministe de la date** (hash date → choix dans le pool de crises jouables +
    rotation des pays) — aucun contenu nouveau à produire chaque jour.
  - `POST /api/daily/start` → crée la partie (réutilise `game_api.create_game` avec
    `scenario="daily:<date>"`, difficulté fixée, ranked spécial « daily ») ; 409 si déjà
    tentée ce jour.
  - À la fin de partie (hook existant de fin) : enregistre le score dans
    `daily_scores(date, player_id, score)` — même mécanique que `campaign_scores`.
- **Front** :
  - Accueil : carte « Le Sommet du jour » sous le hero (date, crise anonymisée « ??? »
    tant que non jouée, bouton Jouer / « déjà joué : voir le classement », compte à
    rebours jusqu'au prochain).
  - `/defi` : classement du jour + les précédents (7 derniers jours).
  - Fin de partie d'un défi : bloc « Ton rang du jour : #12 sur 87 » + bouton
    « Partager » (copie un texte façon Wordle : date, score, mini-frise en émojis
    U/rounds — jamais le titre de la crise).
- **Marché** : le marché LMSR de la partie du jour est ouvert aux **spectateurs de la
  veille** (ceux qui ont déjà joué) — le pari du jour sans spoiler pour soi-même.
  (Option V2, ne bloque pas la V1.)

## Garde-fous

Une tentative classée/jour (les re-runs passent en partie libre non scorée) ; le défi
n'utilise que des crises dont la fiche est prête ; fuseau : date UTC affichée clairement
(« le défi tourne à minuit UTC ») ; le texte de partage ne spoile jamais l'événement.

## Tests attendus

Déterminisme : même date → même défi (hash testé) ; 2e tentative → 409 + re-run libre ;
score enregistré une seule fois ; leaderboard trié/borné ; le texte de partage ne
contient ni titre ni description de la crise. Front : la carte accueil affiche
joué/pas-joué, le compte à rebours ne dépend pas de l'horloge du serveur au rendu.

## Definition of done

Deux comptes jouent le même jour : ils reçoivent la même crise et les mêmes pays, leurs
scores apparaissent sur le même classement du jour, chacun n'a qu'une tentative classée,
et le texte partagé donne envie sans rien révéler. Le lendemain, le défi a changé tout
seul.
