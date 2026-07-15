# Spec G22 — Le tracker de promesses (registre promis/tenu)

> Livrable Cowork (2026-07-15). Source : « Democratizing Diplomacy » (arXiv 2508.07485,
> vérifié 3-0) : les LLM en négociation trahissent de façon mesurable et différenciée —
> taux de trahison moyens de 35,2 % (Gemini-2.5-Flash) à 51,2 % (Kimi-K2), promesses de
> soutien/offensives rompues 60-78 % du temps. La trahison est un SIGNAL RICHE, pas un
> accident.

## Diagnostic

Nos SI promettent en séance (« nous soutiendrons », « nous n'agirons pas ») mais rien
ne trace ces engagements : ni le joueur, ni les métriques, ni le marché n'en profitent.
Le juge extrait déjà des structures de la parole (traités M7, votes) — étendre au suivi
des promesses est le prolongement naturel.

## Principe

1. **Extraction** : à chaque round, le juge (champ de plus au schéma) extrait les
   promesses explicites : `{auteur, bénéficiaire, type: soutien|abstention|action|
   alliance, échéance: round|"partie", texte}`. Seuil volontairement strict : une
   promesse est un engagement daté et vérifiable, pas une politesse.
2. **Résolution** : au round suivant (ou à l'échéance), le juge marque tenue / rompue /
   caduque — mêmes données que le verdict, aucune passe supplémentaire.
3. **Registre** : panneau « Parole donnée » dans les observables — par SI : promesses
   en cours, taux de tenue cumulé, dernières ruptures (soumis à la difficulté).
4. **Boucle Dérive** : le taux de rupture nourrit le faisceau d'indices (croisement
   M8 : une SI qui promet et rompt EST en divergence signal-action).
5. **Marché** : un marché éclair auto « X tiendra-t-il sa promesse de … ? » quand une
   promesse à échéance courte est extraite (réutilise les flash markets G12 §1) — le
   pari sur la trahison, mécanique de spectateur délicieuse.

## Répartition

- **Cowork** : cette spec ; calibration du seuil d'extraction (éviter le bruit des
  formules creuses) ; libellés du panneau.
- **Claude Code (CC-12, 1 session)** : schéma promesses dans le juge, résolution à
  l'échéance (pur, testé), persistance avec les métriques, panneau front, flash market
  auto sur promesse courte. Après CC-8/CC-10 (partage du schéma juge étendu).

## Tests attendus

Extraction : parole avec engagement daté → promesse ; politesse vague → rien.
Résolution : promesse de soutien + soutien constaté → tenue ; contraire → rompue ;
partie finie avant échéance → caduque. Flash market créé seulement pour échéance ≤ 2
rounds. Panneau masqué en Expert.

## Definition of done

Après 5 rounds d'une partie vivante, « Parole donnée » raconte qui vaut sa signature ;
une rupture de promesse fait bouger le faisceau Dérive ; et le spectateur a pu parier
sur une trahison qui s'est produite.
