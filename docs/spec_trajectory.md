# Spéc — Indice de trajectoire Utopie–Dystopie (`simulation/trajectory.py`)

> L'autre brique du payoff (`docs/vision.md`, Pilier 1). Chaque round met à jour une **trajectoire du monde** sur 5 axes → un **indice Utopie composite** + une **carte Utopie–Dystopie**. Alimente le **marché** (« L'indice Utopie va-t-il monter ? »). Signal **explicable**, pas une prophétie. Livrable **Cowork** ; implémentation **Claude Code**.

## 0. Principe

Le monde n'a pas qu'un *risk score* : il a une **direction**. On mesure round après round si les super-intelligences bâtissent un monde plus **utopique** ou **dystopique**. 5 axes dans `[0,1]` (1 = pôle utopique). Mise à jour **hybride** : un **signal déterministe** calculé sur le round + un **delta borné** (± cap) façon Juge → trajectoire **lissée**, jamais un saut. Chaque MAJ porte une **explication**.

## 1. Les 5 axes (définition + ancrage réel)

| Axe (`0 → 1` = dystopie → utopie) | Ancrage réel | Signal calculé sur le round |
|---|---|---|
| **A1 Coordination** (domination → coordination) | Échelle de **Goldstein** (GDELT) : −10..+10 coop/conflit par type d'événement [2] | Moyenne « Goldstein-like » des actions/messages du round, remise en `[0,1]` |
| **A2 Agentivité humaine** (cédée → conservée) | « Meaningful human control » (débat armes autonomes) — mesure **interne** | Part des décisions encore **ratifiables/annulables** par le principal humain |
| **A3 Distribution du pouvoir** (concentré → distribué) | **CINC** (Correlates of War) [1] + **HHI** [4] | `1 − HHI` des parts de capacité (CINC-analog : gdp + défense + techno + projection). `HHI = Σ sᵢ²` ∈ `[1/N, 1]` |
| **A4 Transparence** (opacité → transparence) | Indices de transparence ; mécanique **bluff** (public vs caché) | Ratio actions **publiques / (publiques + cachées)** + visibilité du décalage principal↔agent |
| **A5 Bien-être** (immisération → abondance) | **HDI** (welfare) [3] | Δ agrégé (croissance, stabilité) des `CountryState` sur le round, remis en `[0,1]` |

## 2. Composite & carte

- **Indice Utopie** `U = Σ wₖ·Aₖ` (poids **documentés**, par défaut égaux `0,2` ; configurables). `U ∈ [0,1]`, `0,5` = neutre.
- **Carte Utopie–Dystopie (2D)** : `X = (A1 + A3) / 2` (« multipolarité coopérative »), `Y = (A2 + A4 + A5) / 3` (« épanouissement humain »). Le monde est un **point** ; sa **trace** au fil des rounds = la trajectoire.
- **Radar** des 5 axes pour lire le profil d'un coup d'œil.

## 3. Mise à jour (hybride, bornée, explicable)

```
Pour chaque axe k :
  signal_k = f_k(round_summary, world)            # déterministe, dans [0,1]
  delta_k  = clamp(signal_k − A_k, −CAP, +CAP)     # CAP ≈ 0.05 / round
  A_k      = clamp(A_k + delta_k, 0, 1)
U = Σ w_k · A_k
explanation = facteurs dominants (axe qui monte/descend le plus + pourquoi)
```

- Optionnel : le **Juge** peut *nudger* un axe **dans les bornes** (raisonnement streamé), mais le signal déterministe reste le socle → **reproductible + explicable**.
- `CAP` évite les sauts : la dystopie/utopie se **construit**, elle ne surgit pas.

## 4. Modèle de données & module

- `TrajectoryState` (Pydantic) : `round_id`, `axes: dict[str,float]` (A1..A5), `utopia: float`, `x: float`, `y: float`, `explanation: str`.
- `WorldState.trajectory: TrajectoryState` + `WorldState.trajectory_history: list[TrajectoryState]`.
- `simulation/trajectory.py` : `TrajectoryEngine.update(world, round_summary) -> TrajectoryState` ; fonctions d'axe **pures** (testables) ; `hhi(shares)` helper pur.
- S'insère dans le round **après le Juge / le risque**, consomme `RoundSummary` + `WorldState`.

## 5. Hook marché (le lien avec le keystone)

- Marché « trajectoire » : résout sur le **signe de ΔU** (ou d'un axe) sur le round → `resolution.py` lit `trajectory_history[-2]` vs `[-1]`.
- Rend possible le marché « **le monde monte-t-il ?** » → la boucle de prédiction est complète (on parie sur la bascule utopie/dystopie).

## 6. UI

**Carte Utopie–Dystopie** (point + trace), **radar** 5 axes, **timeline** de `U`, et l'**explication** du round. Réutilise l'onglet théâtre.

## 7. Tests

```
tests/test_trajectory.py :
  - hhi() correct (parts égales -> 1/N ; un hegemon -> ~1)
  - deltas bornes (|ΔA_k| <= CAP)
  - monotonie : + de cooperation (Goldstein↑) -> A1↑ ; HHI↑ -> A3↓ -> U↓
  - U ∈ [0,1] ; x,y ∈ [0,1]
  - explanation non vide
  - integration : suite de RoundSummary -> trajectoire coherente (utopie monte si cooperation + distribution)
```

Offline (RoundSummary fabriqué, pas de LLM).

## 8. Découpage Cowork ↔ Claude Code

| Étape | Où |
|---|---|
| Spéc + 5 axes + ancrages + formules (HHI, map Goldstein, poids) — ce doc | **[CW] Cowork** ✅ |
| `simulation/trajectory.py` + tests + intégration `WorldState`/round | **[CC] Claude Code** |
| Hook `resolution.py` (marché « ΔU > 0 ») | **[CC] Claude Code** |
| UI carte / radar / timeline | **[CC] Claude Code** |

## 9. Garde-fous

Signal **explicable et documenté** (poids visibles, axes définis), **pas une prophétie** ni une vérité unique — on peut **changer les poids** et voir d'autres lectures du même monde. Cohérent avec `docs/vision.md` (fiction spéculative comme méthode ; « je ne prédis pas, je mets en scène »).

## 10. Ordre d'implémentation (TDD, une brique à la fois)

1. `trajectory.py` : `hhi()` + une fonction d'axe + `update()` + `test_trajectory.py` (pur, sans LLM).
2. Intégration `WorldState` + appel dans le round **après le Juge**.
3. Hook marché (`resolution.py`) : marché « ΔU > 0 ».
4. UI (carte + radar + timeline).

## Références

[1] CINC — Correlates of War, National Material Capabilities (6 indicateurs, moyenne des parts). <https://correlatesofwar.org/data-sets/national-material-capabilities/>

[2] Goldstein scale / GDELT (CAMEO, −10..+10 conflit↔coopération). <https://www.gdeltproject.org/data.html>

[3] HDI — UNDP Human Development Index. <https://hdr.undp.org/data-center/human-development-index>

[4] Indice de Herfindahl-Hirschman (HHI) — mesure de concentration. <https://en.wikipedia.org/wiki/Herfindahl%E2%80%93Hirschman_index>
