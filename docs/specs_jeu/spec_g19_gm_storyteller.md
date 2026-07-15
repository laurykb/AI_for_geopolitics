# Spec G19 — Le GM-Storyteller (mode Dérive)

> Livrable Cowork (2026-07-15). Source : guide officiel du Storyteller de Blood on the
> Clocktower (wiki.bloodontheclocktower.com/Storyteller_Advice), vérifié 3-0. Rappel
> critique : la seule affirmation réfutée de la recherche est « les imposteurs LLM
> mentent mal » — la SI déviante sait mentir, c'est l'ÉQUILIBRE de la partie que le GM
> doit tenir.

## Diagnostic

Aujourd'hui le GM pose les événements mais ne joue aucun rôle dans la dramaturgie de la
Dérive : si l'humain flaire la déviante au round 2, la partie est finie de fait ; s'il
est perdu, rien ne l'aide. Le pattern Storyteller, éprouvé par le meilleur jeu à
traître du genre, prescrit exactement ce qui manque.

## Principe

Le GM du mode Dérive reçoit deux mandats cachés, encodés en rubrique dans son prompt :

1. **Couvrir la menteuse** — quand la SI déviante prend un risque (vote incohérent,
   power-seeking visible), le GM peut générer une **couverture plausible** : un rapport
   d'incident ambigu, un deuxième pays au comportement suspect, du bruit dans le fog
   (« Evil players rely on you to help make their lies sound like the truth »).
2. **Rééquilibrer en secret vers le camp faible** — humain trop en avance : la déviante
   reçoit une fenêtre discrète (événement qui justifie son agenda) ; humain perdu : un
   indice supplémentaire fuite (audit, câble diplomatique, anomalie de données).
   Objectif dramatique explicite : **la partie doit rester ouverte jusqu'aux derniers
   rounds** (« get the game to last until the final day if you can »).

Garde-fous (rubrique d'éthique d'intervention, auto-check du GM à chaque round) :
jamais de mensonge factuel du GM sur l'état du monde ; les interventions passent par le
fog et les événements, pas par la falsification des verdicts du juge ; chaque
intervention est **journalisée en interne** et révélée dans l'écran de révélation de
fin (« ce que le GM a fait dans l'ombre ») — le joueur découvre la dramaturgie a
posteriori, comme un bon Storyteller qui se dévoile.

## Mesure de l'équilibre

Compteur interne de « tension » : estimation par le GM (0-1) de la probabilité que
l'humain ait identifié la déviante (fondée sur ses achats intel, ses motions, sa
parole). Intervention de couverture si tension > 0,7 avant le round h−2 ; indice
supplémentaire si tension < 0,3 après la moitié de l'horizon. Les seuils vivent dans
la config (équilibrage Cowork).

## Répartition

- **Cowork** : cette spec ; rédaction de la rubrique du GM (les 2 mandats + éthique) ;
  équilibrage des seuils sur 10 parties Dérive.
- **Claude Code (CC-9, 1 session)** : rubrique dans le prompt GM (mode drift
  uniquement), estimation de tension (appel juge léger ou heuristique sur les actions
  humaines), journal des interventions + section « l'ombre du GM » dans
  DriftRevealPanel. Tests : interventions journalisées, jamais en mode non-drift,
  seuils configurables.

## Definition of done

Sur 10 parties Dérive auto (humain simulé faible/fort), la durée moyenne avant
résolution augmente et se concentre sur les 2 derniers rounds ; l'écran de révélation
raconte les interventions du GM ; et aucune intervention n'apparaît dans une partie
classique.
