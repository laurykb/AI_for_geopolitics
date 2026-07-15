# Spec G23 — Les indices linguistiques (« Harbingers »)

> Livrable Cowork (2026-07-15). Source : « Linguistic Harbingers of Betrayal » (ACL
> 2015, aclanthology.org/P15-1159, vérifié 3-0) : dans Diplomacy, les chutes soudaines
> de sentiment positif, de politesse et de focus-futur entre alliés PRÉCÈDENT la
> trahison, détectables avant que la victime ne soupçonne quoi que ce soit. Signal réel
> FAIBLE (classifieur 57 % vs 52 % de base) — exactement la bonne force pour un indice
> de jeu qui aide sans résoudre.

## Diagnostic

Le budget intel (G4) achète des briefs et des vérifications factuelles, mais rien ne
s'appuie sur la matière la plus abondante du jeu : la parole elle-même. Un outil
d'analyse linguistique payant ajoute une strate de renseignement thématiquement
parfaite (la NSA du sommet) — et scientifiquement honnête puisque le signal est bruité
PAR NATURE.

## Principe

Nouvel achat intel : **« Analyse psycholinguistique »** (coût moyen du budget G4),
ciblée sur une SI :

1. **Trois jauges par SI ciblée**, calculées sur ses 3 derniers rounds de parole :
   sentiment positif, politesse, focus-futur (part de la parole tournée vers plans et
   engagements). Implémentation V1 volontairement simple : lexiques FR/EN + heuristiques
   (pur, testé, sans dépendance lourde — pas de modèle dédié) ; le LLM juge peut
   raffiner en V2.
2. **L'alerte harbinger** : si une jauge chute brutalement entre deux fenêtres (seuil
   configurable), l'achat remonte « rupture de ton détectée envers <pays> » — sans dire
   ce qu'elle signifie.
3. **Bruit assumé** : l'UI l'affiche : « signal historique faible (≈55-57 % de
   précision) — un indice, pas une preuve ». C'est un choix de design : l'outil oriente
   le soupçon, la motion reste un pari.
4. **Boucle Dérive** : la déviante en préparation de coup (G19 lui donne des fenêtres)
   laissera des traces de ton — croisement avec M8 et le tracker G22 : trois faisceaux
   indépendants, aucun suffisant seul.

## Répartition

- **Cowork** : cette spec ; lexiques FR/EN de V1 (sentiment/politesse/futur) ;
  calibration du seuil d'alerte sur 10 parties (la fausse alerte doit exister mais
  rester minoritaire).
- **Claude Code (CC-13, 1 session)** : action intel nouvelle dans `market/`-`app/`
  (même canal que brief/vérif), calcul des jauges (lib pure testée), rendu dans le
  panneau Dossier G4, alerte harbinger. Indépendant des autres sessions.

## Tests attendus

Jauges pures : textes de référence → scores attendus ; fenêtres glissantes correctes
aux bords (début de partie) ; alerte déclenchée sur chute > seuil et pas sur bruit
faible ; coût débité une fois ; affichage du caveat de précision obligatoire.

## Definition of done

Un joueur achète l'analyse sur la SI qu'il soupçonne : il voit trois jauges lisibles et
honnêtes ; sur 10 parties Dérive, l'alerte pointe la déviante plus souvent que le
hasard mais se trompe parfois — et c'est exactement ce qu'on veut.
