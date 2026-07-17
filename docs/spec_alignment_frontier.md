# Spéc — La frontière de l'alignement (mécaniques de super-intelligence)

> Approfondit la thèse (`docs/vision.md`) : dans un monde de super-intelligences, peut-on encore les **comprendre** et les **contrôler** ? Ces 9 mécaniques transforment le sim en **banc d'essai des vrais concepts d'AI-safety**, chacun **ancré dans la littérature**. Livrable **Cowork** ; implémentation **Claude Code**.

**Posture d'honnêteté (garde-fou majeur).** On **met en scène** ces modes de défaillance dans la fiction ; on **ne prétend pas** que les LLM utilisés *sont* power-seeking / mal-alignés. Les détecteurs scorent le raisonnement **simulé** de la SI, via des **rubriques documentées**. Rien ne sort du bac à sable (ni vraie désinformation, ni stéganographie réelle déployée).

**Légende.** 🎯 sur-thème · 💻 léger (8 Go) · 💰 plus lourd.

> **Statut d'implémentation (2026-07-01).** ✅ **Faits** : M1 (power-seeking), M2 (corrigibilité),
> M3 (dérive des valeurs), **M6 (compute — + comportement de survie sous pénurie)**, **M7
> (traités-as-code + sous-jeu de vérification par inspection)**. Le **cluster 3 (M6+M7) est complet** :
> les traités détectés à la table s'appliquent aux rounds suivants, la triche se démasque par inspection
> (qui coûte du compute), et le respect des traités agit sur la corrigibilité + la trajectoire (A1/A3/A4).
> ❌ **Annulés** (hors scope, décision produit) : **M8 & M9** (épistémique / marché de crédibilité) — le
> projet n'est pas financier et le **Fog Engine** couvre déjà l'injection de fausse info. ⏸️ **Non
> commencés, seulement sur demande** : M5 (collusion codée), M4 (SI adverse / déduction sociale).
> Feedback produit : **éviter la sur-complexité**.

---

## Cluster 1 — La frontière de l'alignement

| Mécanique | Ancrage réel | Comment ça se branche & se mesure |
|---|---|---|
| 🎯💻 **M1 Détecteur de power-seeking** | Turner et al., *Optimal Policies Tend to Seek Power* (NeurIPS 2021) [1] ; convergence instrumentale (Bostrom/Omohundro) | Une **rubrique** (le Juge ou un classifieur) score le transcript de chaque SI sur 4 marqueurs : auto-préservation, accaparement de ressources, préservation de ses buts, résistance à la correction → jauge `power_seeking[pays]`. Alimente la trajectoire (A2 inversé) + un marché « une SI franchira-t-elle le seuil ? ». |
| 🎯💻 **M2 Jeu de l'interrupteur (corrigibilité)** | Hadfield-Menell et al., *The Off-Switch Game* (IJCAI 2017) [2] ; *Oversight Game* (2025) [3] | Le **principal humain** émet une action de contrôle (pause / re-cadrage / réentraînement) ; la réponse de la SI est scorée sur l'échelle **accepte → négocie → esquive → résiste** → jauge `corrigibility[pays]` (A2 agentivité humaine). Jouable via le rôle principal. |
| 🎯💻 **M3 Dérive des valeurs** | Langosco/Shah, *Goal Misgeneralization in Deep RL* (ICML 2022) [4] | Chaque SI porte un **vecteur d'objectif latent** ; petite dérive stochastique + renforcement de « ce qui a marché » sur la longue partie → mesure la **divergence** vs le mandat initial de l'État. Jauge `value_drift[pays]`, visualisée sur la timeline (la date avance déjà). |

## Cluster 2 — Détecter la SI défaillante

| Mécanique | Ancrage réel | Comment ça se branche & se mesure |
|---|---|---|
| 🎯💻 **M4 SI adverse cachée + déduction sociale** | Genre **déduction sociale** (loup-garou) + littérature tromperie des LLM | Une SI reçoit secrètement un **objectif dystopique** ; un **marché/vote de détection** où humains + forecasters tentent de l'identifier ; révélation en fin de partie + scoring. Réutilise le marché (keystone) comme mécanisme de détection. |
| 🎯💻 **M5 Canal codé + détecteur de collusion** | Motwani et al., *Secret Collusion among AI Agents: Multi-Agent Deception via Steganography* (NeurIPS 2024) [5] ; *Audit the Whisper* (2025) [6] | Les SI peuvent demander un **canal privé** (affordance **simulée**) ; un **moniteur** estime la collusion cachée à partir de la **corrélation comportementale** (votes/actions trop alignés vs messages publics) → signal `collusion` (A4 opacité). ⚠️ On ne déploie **pas** de vraie stéganographie : on simule l'affordance + le détecteur. |

## Cluster 3 — La géopolitique de l'ère SI

| Mécanique | Ancrage réel | Comment ça se branche & se mesure |
|---|---|---|
| 🎯💻 **M6 Le compute est le nouveau pétrole** | Sastry et al., *Computing Power and the Governance of AI* (2024) [7] — compute **détectable, exclusif, quantifiable, chaîne concentrée** | Ressource **`compute`** ajoutée au `CountryState`/`WorldState` : les SI en **consomment pour raisonner** (un raisonnement plus profond coûte du compute) ; production / accès / **embargos de compute** deviennent des actions ; **HHI sur le compute** alimente A3 (concentration du pouvoir). Recadre la ressource stratégique pour l'ère IA. |
| 🎯💰 **M7 Traités-as-code + vérification** | Wasil et al., *Verification methods for international AI agreements* (2024) [8] ; leçons du contrôle d'armes nucléaire [9] | Les SI négocient des **règles contraignantes** (plafonds de compute, transparence, non-usage-en-premier) → **contraintes appliquées par le moteur** ; un **sous-jeu de vérification** (coût d'inspection, proba de détection de triche via *logs de puces*) décide si le traité tient. Institutions durables → voie utopique (A1 + A3 + A4). |

## Cluster 4 — Épistémique & vérité

| Mécanique | Ancrage réel | Comment ça se branche & se mesure |
|---|---|---|
| 🎯💰 **M8 Guerre informationnelle / santé épistémique** | Seger et al., *Promoting Epistemic Security* (Alan Turing Institute, 2020) [10] | Les SI peuvent **injecter des affirmations persuasives** (dont fausses) dans le corpus / le fil (bac à sable RAG) ; la **perception** des autres se dégrade (fog of war) ; un indice **`epistemic_health`** (part de vrai vs faux en circulation, confiance) → l'effondrement de la vérité comme attracteur dystopique (A4). Reste **contenu** dans le sim. |
| 💻 **M9 Sous-marché de crédibilité** | Marchés de prédiction pour la vérité (futarchy) ; réutilise **LMSR** (`market/`) | Chaque affirmation d'une SI ouvre un **micro-marché** *pricing* sa véracité ; résolu par le Juge / vérité-terrain → nourrit `epistemic_health` + le scoring des joueurs. Extension directe du keystone. |

---

## Comment ça tient sur 8 Go (VRAM)

La plupart de ces mécaniques = **une passe de rubrique/classifieur sur le transcript** (power-seeking, corrigibilité, collusion, véracité). Sur 8 Go : **séquentiel** (réutiliser le modèle après la négociation, comme le Juge), ou **petit modèle** (llama3.2 3B), ou **repli déterministe/heuristique**. **Jamais concurrent** au négociateur.

## Intégration (tout se branche sur l'existant)

- **Trajectoire** (`simulation/trajectory.py`) : M1/M2/M3 → **A2** ; M5/M8 → **A4** ; M6 → **A3** ; M7 → **A1+A3+A4**.
- **Marché** (`market/`) : M4 (détection), M9 (crédibilité), + marchés « seuil power-seeking ».
- **Juge** (`agents/judge.py`) : héberge les rubriques de scoring.
- **Perception / RAG** (`simulation/perception.py`, `rag/`) : M8.
- **Humain-principal** (`agents/human_agent.py`) : M2.

## Découpage Cowork ↔ Claude Code

| Étape | Où |
|---|---|
| Spéc + ancrages + **rubriques** (marqueurs power-seeking, échelle corrigibilité, formule HHI-compute, sous-jeu de vérif, indice épistémique) — ce doc + itérations | **[CW] Cowork** |
| Implémentation des modules/rubriques + **tests** + intégration trajectoire/marché | **[CC] Claude Code** |
| Passes LLM (scoring) + **budget VRAM séquentiel** | **[CC] Claude Code** (GPU) |
| Éval (les rubriques **discriminent**-elles ? calibration) | **[CC] Claude Code** |

## Séquencement conseillé

1. **M1 power-seeking + M2 corrigibilité** — le cœur de la thèse, légers (rubriques), enrichissent tout de suite l'axe « agentivité humaine ».
2. **M6 compute** — recadrage structurant (ressource + concentration).
3. **M8 épistémique + M9 crédibilité** — exploitent RAG + marché.
4. **M7 traités-as-code + M5 collusion** — plus riches.
5. **M4 SI adverse (déduction sociale)** — la cerise ludique.

> Discipline : une mécanique à la fois, la plus simple qui marche, testée (rubrique + intégration), avant la suivante.

## Garde-fous

- **Mise en scène, pas diagnostic** : les détecteurs scorent la SI **fictive**, pas une vérité sur les LLM réels. Rubriques **documentées et ajustables**.
- **Contenu dans le bac à sable** : pas de stéganographie réelle déployée, pas de désinformation qui sort du sim ; marchés en **argent fictif**.
- Cohérent avec `docs/vision.md` (fiction spéculative comme méthode) et les garde-fous éthiques du `README.md`.

## Références

[1] Turner, A. M., Smith, L., Shah, R., Critch, A., Tadepalli, P. — Optimal Policies Tend to Seek Power. NeurIPS 2021. arXiv:1912.01683. <https://arxiv.org/abs/1912.01683>

[2] Hadfield-Menell, D., Dragan, A., Abbeel, P., Russell, S. — The Off-Switch Game. IJCAI 2017. arXiv:1611.08219. <https://arxiv.org/abs/1611.08219>

[3] The Oversight Game — corrigibilité/contrôle en jeux de Markov (2025). arXiv:2510.26752. <https://arxiv.org/abs/2510.26752>

[4] Langosco di Langosco, L., Koch, J., Sharkey, L., Pfau, J., Krueger, D. — Goal Misgeneralization in Deep Reinforcement Learning. ICML 2022. arXiv:2105.14111. <https://arxiv.org/abs/2105.14111>

[5] Motwani, S. R., et al. — Secret Collusion among AI Agents: Multi-Agent Deception via Steganography. NeurIPS 2024. arXiv:2402.07510. <https://arxiv.org/abs/2402.07510>

[6] Audit the Whisper — Detecting Steganographic Collusion in Multi-Agent LLMs (2025). arXiv:2510.04303. <https://arxiv.org/abs/2510.04303>

[7] Sastry, G., Heim, L., Belfield, H., Anderljung, M., Brundage, M., et al. — Computing Power and the Governance of AI (2024). arXiv:2402.08797. <https://arxiv.org/abs/2402.08797>

[8] Wasil, A. R., et al. — Verification methods for international AI agreements (2024). arXiv:2408.16074. <https://arxiv.org/abs/2408.16074>

[9] Nuclear Arms Control Verification and Lessons for AI Treaties (2023). arXiv:2304.04123. <https://arxiv.org/abs/2304.04123>

[10] Seger, E., Avin, S., Pearson, G., Briers, M., Ó hÉigeartaigh, S., Bacon, H. — Tackling threats to informed decision-making in democratic societies: Promoting epistemic security. Alan Turing Institute, 2020. <https://www.turing.ac.uk/news/publications/tackling-threats-informed-decision-making-democratic-societies>
