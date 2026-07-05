# Spec G1 — La carte est la scène

> Livrable Cowork pour la session Claude Code G1. Aucun changement Python.

## Layout cible (desktop)

```
┌────────────────────────────────────────────────┬──────────────────┐
│                                                │  TRANSCRIPT      │
│                CARTE (d3-geo existante)        │  (panneau, 340px)│
│   arcs, pulsations, teintes U par pays         │  auto-scroll,    │
│                                                │  badges modèle   │
├────────────────────────────────────────────────┴──────────────────┤
│  BANDEAU BAS : timeline scrubber (rounds) · courbe U · escalade   │
└───────────────────────────────────────────────────────────────────┘
```

Mobile : carte plein écran, transcript en tiroir bas (swipe), bandeau réduit à la courbe U.
Les pages `/monde` et `/games/{id}` fusionnent en une seule ; `/replay` réutilise la même
scène pilotée par le scrubber au lieu du SSE.

## Mapping événement SSE → mise en scène

| Événement SSE      | Réaction de la scène                                              |
|--------------------|-------------------------------------------------------------------|
| `event`            | Pulsation ambre (2 ondes, 1,2 s) sur les pays `actors` ; carte s'assombrit de 8 % pendant 0,6 s ; carte titre de l'événement en haut. |
| `turn_start`       | Halo doré sur le pays qui parle + **indicateur de frappe** (3 points) sur sa capitale ; arc doré animé vers le(s) pays adressé(s) si identifiable, sinon vers le centre du sommet. |
| `token`            | Le texte coule dans le transcript ; l'arc reste vivant (dash-offset animé) tant que ça streame. |
| `message_done`     | L'arc se fige 0,4 s puis s'estompe ; l'entrée transcript se scelle (chrono affiché). |
| `perceptions` (fog)| Voile bleuté sur les pays désinformés + icône « œil barré » ; tooltip = la fausse narration. |
| `verdict`          | **Temps suspendu** : 0,8 s sans animation, la carte gèle, puis les deltas s'appliquent (pays qui montent en teinte utopie / descendent en dystopie, transition 1,5 s). |
| `ladder` (escalation)| Le rail d'escalade du bandeau s'allume jusqu'au palier atteint ; vibration brève si palier franchi vs round précédent. |
| `suspended`        | Le pays suspendu passe en gris désaturé + cadenas sur la capitale, toute la partie du round. |
| `motion_verdict`   | Bannière pleine largeur 3 s : motion contre X — retenue/rejetée + raisonnement du juge en une ligne. |
| `communique`       | Entrée transcript style « communiqué officiel » (encadré, sceau du juge). |
| `trajectory`       | Le point U du round s'ajoute à la courbe du bandeau (animation de tracé). |
| `risk`             | Micro-jauges du bandeau (escalade, éco, alliances) glissent vers leurs nouvelles valeurs. |
| `done`             | La scène « respire » : dézoom léger 0,4 s, le scrubber gagne un cran. |
| `error` / coupure  | Bannière existante conservée ; la carte reste dans l'état d'avant-round. |
| inconnu            | Ignoré (règle R3 conservée). |

## Timeline scrubber

- Un cran par round joué ; glisser = recharge l'état de ce round depuis `GET /games/{id}`
  (tout est dans `rounds`/`transcripts`, zéro endpoint nouveau).
- En scrub, la scène rejoue les teintes/positions de ce round **sans** les animations de
  streaming (états finaux seulement) ; le transcript saute à ce round.
- Bouton « lecture théâtre » (existant au replay) : rejoue les rounds au scrubber avec
  les animations, vitesse ×1/×2/×4.

## Teintes des pays (échelle U locale)

Échelle fixe (pas de renormalisation par partie, comparabilité entre parties) :
U ≥ 0,7 → vert utopie ; 0,55–0,7 → vert pâle ; 0,45–0,55 → neutre (gris chaud) ;
0,3–0,45 → orange sombre ; < 0,3 → rouge dystopie. Pays hors sommet : retrait actuel.
Transitions de teinte toujours en 1,5 s ease-out (jamais instantané : le monde « encaisse »).

## Sobriété (garde-fous)

- Jamais plus de 2 animations simultanées hors token-flow ; les événements SSE arrivant
  pendant une animation se mettent en file (max 3, ensuite on saute aux états finaux).
- `prefers-reduced-motion` : tout devient transitions d'opacité simples.
- Pas de son en G1 (préparer un hook `onStageEvent` pour plus tard, c'est tout).

## Definition of done

Une partie complète jouée sur la scène fusionnée sans regarder l'ancienne page transcript ;
un replay scrubbé de bout en bout ; zéro régression des pages marché ; lecture fluide
(60 fps sur la carte pendant le streaming, testé avec 6 pays).
