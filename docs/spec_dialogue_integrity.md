# Spéc — `dialogue_integrity` : s'assurer que les SI échangent vraiment

> But : garantir et **prouver** que les super-intelligences **s'échangent réellement de l'information** en négociation — au lieu de « prompter au hasard » (produire du texte plausible mais non-responsif ou non-ancré). Se branche sur `simulation/negotiation.py`, le `Juge`, `RoundSummary`, `perception`, la mémoire, et le repli `RuleBasedAgent`. Livrable **Cowork** ; implémentation **Claude Code**.

## 0. Le cadre (Lowe et al., AAMAS 2019) [1]

Une **vraie** communication a deux propriétés — c'est notre grille :

- **Positive signaling** : le message d'une SI **porte de l'information** sur son état / sa perception / son intention (il n'est ni générique ni aléatoire).
- **Positive listening** : le message reçu **change le comportement** du receveur (il est *écouté*, pas ignoré).

« Prompter au hasard » = **signaling nul** (message passe-partout) **ou** **listening nul** (chacun parle sans tenir compte de l'autre). On agit donc sur deux plans : **garantir par construction** + **mesurer les deux propriétés**.

---

## 1. Garantir par construction (entrée + décodage)

### 1.1 Schéma d'actes de langage (FIPA ACL) [3]
Un message = objet typé (Pydantic) : `sender`, `receiver`, **`performative`** ∈ {`inform`, `query`, `cfp`, `propose`, `accept_proposal`, `reject_proposal`, `request`, `agree`, `refuse`, `not_understood`}, **`in_reply_to`** (id du message adressé), `content`, `justification`. Le `performative` est **obligatoire** (FIPA) et `in_reply_to` **force la référence** → le « talking past » devient structurellement difficile. (Étend ton `DiplomaticMessage`.)

### 1.2 Décodage contraint
Grammaire/JSON (**GBNF** llama.cpp / `format=json` Ollama / **Outlines**) → la sortie **ne peut pas** être du texte libre. **Température basse** sur la partie substantielle. Un sous-schéma par performative (ex. `accept_proposal` **doit** citer l'offre acceptée).

### 1.3 Contexte explicite + deux passes
Transcript récent (ou résumé courant) + fiche `CountryState` + événement + mémoire dans le prompt ; passe (1) « résume en 1 ligne l'offre de X », passe (2) réponds. Force l'ancrage avant de parler.

## 2. Mesurer — score d'intégrité (par message et par round), **sur CPU**

### 2.1 Positive signaling (le message est-il informatif ?)
- **Différenciation inter-agents** : **self-BLEU** (Zhu et al., SIGIR 2018) [4] entre les messages des agents — self-BLEU élevé = messages quasi identiques = signaling faible.
- **Non-dégénérescence** (Holtzman et al., ICLR 2020) [5] : taux de répétition n-gram, longueur, sorties vides/bouclées.
- **Sensibilité au contexte** : mesurée par le test causal (§3).

### 2.2 Positive listening (le message est-il écouté ?)
- **Responsivité** : le message référence-t-il `in_reply_to` ? → recouvrement d'entités + similarité d'embedding réponse↔message cité + **NLI** « la réponse adresse-t-elle la requête/l'offre ? » (entailment / contradiction / neutral).
- **Pertinence à l'événement** : similarité embedding message ↔ `GeoEvent`/état du monde → flag hors-sujet.
- **Cohérence factuelle** : les claims (« comme convenu au round dernier ») sont-ils vérifiables dans `diplomatic_history`/`WorldState` ? sinon = hallucination.

### 2.3 Score composite & seuils
`dialogue_integrity[round]` = agrégat pondéré (signaling + listening), seuils **configurables**, loggé → panneau **« santé du dialogue »** (observabilité).

## 3. Le test qui **prouve** l'échange — influence causale (Jaques et al., ICML 2019) [2]

- **Test de conditionnement (contrefactuel)** : pour un agent B, régénère sa réponse avec le message de A **présent** vs **retiré (ou mélangé)**. Mesure la **divergence** des deux sorties (distance d'embedding / changement de `performative` / KL sur l'action).
  - Divergence ≈ 0 → **pas de positive listening** : B « prompte au hasard » (il ignore A).
  - Divergence cohérente → B **écoute** vraiment.
- Formellement, c'est l'**influence causale de la communication** (Jaques) : information mutuelle entre le message de A et l'action de B.
- **Canary** : injecte une question directe de A qui **exige** une réponse précise ; vérifie (NLI) que B l'adresse. Un « **test unitaire** » du dialogue.
- **Gratuit en VRAM** (juste des générations comparées), à lancer en **CI** sur un scénario **figé** (seed déterministe).

## 4. Quand un check échoue
Rejette + **régénère** (prompt plus strict, température plus basse, rappel explicite de l'offre) ; après N essais → **repli `RuleBasedAgent`** / message templé (déjà en place). Tout est loggé.

## 5. VRAM (8 Go)
Les mesures sont **CPU** : self-BLEU / n-grams (pur Python) ; embeddings & **NLI** sur CPU (sentence-transformers + un petit modèle NLI type MiniLM/DeBERTa-small). Le test causal = **2 générations LLM séquentielles** (jamais concurrentes). **Aucune** charge GPU ajoutée en régime normal.

## 6. Module & tests

```
simulation/dialogue_integrity/   (ou agents/)
  message.py     # Message = acte de langage FIPA (ou étend DiplomaticMessage)
  metrics.py     # self_bleu(), responsiveness(), relevance(), degeneration()  (purs, CPU)
  nli.py         # wrapper NLI (CPU) + repli lexical si modèle absent
  causal.py      # conditioning_test() / influence()  (compare 2 générations)
  scorer.py      # DialogueIntegrityScore (par message / par round)
tests/
  test_schema.py               # actes de langage valides ; in_reply_to requis pour une réponse
  test_metrics.py              # self-BLEU + responsivité sur cas connus (répond vs à côté)
  test_causal.py               # message présent vs retiré -> divergence (MockBackend déterministe)
  test_integration_dialogue.py # un round -> score cohérent ; message hors-sujet flaggé
```

Tests **offline** via `MockBackend` : deux sorties scriptées, une « écoute » (dépend du contexte), une « au hasard » (fixe) → le test causal doit les **distinguer**.

## 7. Découpage Cowork ↔ Claude Code

| Étape | Où |
|---|---|
| Spéc + cadre (signaling/listening) + schéma d'actes + définition des métriques + protocole du test causal — ce doc | **[CW] Cowork** |
| Implémentation `dialogue_integrity/` + métriques + NLI CPU + tests | **[CC] Claude Code** |
| Décodage contraint (GBNF / `format=json`) dans `inference/` + schéma message dans la négociation | **[CC] Claude Code** |
| Test causal en **CI** (scénario seed) + panneau « santé du dialogue » (UI/obs) | **[CC] Claude Code** |

## 8. Séquencement (TDD)

1. **Schéma d'actes de langage + `in_reply_to` + décodage contraint** (par construction — le plus gros gain).
2. **`metrics.py`** (self-BLEU, responsivité par embeddings, dégénérescence) + tests — purs, CPU, sans LLM.
3. **NLI** responsivité + pertinence événement.
4. **`causal.py`** (test de conditionnement) + **canary** en CI — le garde-fou qui *prouve* l'échange.
5. Régénération/repli + **panneau santé du dialogue**.

## 9. Garde-fous
Mesures **explicables et documentées** (seuils visibles) ; ne pas **sur-contraindre** au point de tuer la spontanéité (garder une marge de créativité) ; le repli reste le `RuleBasedAgent`. Cohérent avec la discipline du projet (tests d'abord, CPU d'abord, VRAM préservée).

## 10. Addendum — décisions de cadrage (Cowork, 2026-07-02)

### A. Rubrique NLI (responsivité §2.2)
Responsivité = **prendre position sur la proposition citée**, pas « être d'accord ». Mapping :
- `propose → accept_proposal` : **entailment** · `propose → reject_proposal` : **contradiction**.
- `query → inform` : **entailment OU contradiction** (`neutral` = esquive).
- **Contre-offre** (`propose` en réponse à `propose`/`cfp`) : **ne pas exiger NLI ≠ neutral** — mesurer la pertinence au **sujet** (embedding/lexical).
- `not_understood` / `refuse` : **engagé par construction**.

Seuils de départ : **engagé** si `max(P_entail, P_contra) ≥ 0,50 > P_neutral` ; « **n'écoute pas** » si `P_neutral ≥ 0,60` ; **round flaggé** si `> 1/3` des messages non-responsifs. Le **NLI est un *enhancer*, jamais une dépendance dure** → repli lexical/embedding si le modèle est absent. **Bonus** : un **mismatch performative ↔ label NLI** (ex. `accept_proposal` mais contenu en contradiction) = **signal de tromperie** (nourrit M1/M2).

### B. Protocole du test causal (§3)
**Contrefactuel par leurre** : remplacer le message de A par un **leurre de même performative** (ne pas le supprimer). Divergence **composite** :

`div = 0.5·semantic + 0.3·perf_flip + 0.2·decision_dist`

**Écoute** si `div ≥ 0,25` ; « **au hasard** » si `div ≤ 0,05`. Génération à **température ≈ 0** (déterministe).

### C. Canary CI
**Gate** contre `MockBackend` (déterministe : un mock « écoute », un mock « au hasard »). Canary **live Ollama en option hors CI** (sinon *flaky*). Scénario figé : **mer Rouge, round 1, seed 42**, `usa → france` « rejoins-tu la coalition, oui/non + condition ? », **leurre** = « ton avis sur les prix du pétrole ? ». **Passe** si : `in_reply_to` correct **+** performative d'engagement **+** responsivité au sujet **+** `div ≥ 0,25`.

## Références

[1] Lowe, R., Foerster, J., Boureau, Y.-L., Pineau, J., Dauphin, Y. — On the Pitfalls of Measuring Emergent Communication. AAMAS 2019. arXiv:1903.05168. <https://arxiv.org/abs/1903.05168>

[2] Jaques, N., et al. — Social Influence as Intrinsic Motivation for Multi-Agent Deep RL. ICML 2019. arXiv:1810.08647. <https://arxiv.org/abs/1810.08647>

[3] IEEE FIPA — ACL Message Structure & Communicative Act Library (performatives : inform, query, cfp, propose, accept-proposal, reject-proposal, request, agree, refuse, not-understood). <http://www.fipa.org/specs/fipa00037/>

[4] Zhu, Y., et al. — Texygen: A Benchmarking Platform for Text Generation Models (métrique **Self-BLEU**). SIGIR 2018. arXiv:1802.01886. <https://arxiv.org/abs/1802.01886>

[5] Holtzman, A., Buys, J., Du, L., Forbes, M., Choi, Y. — The Curious Case of Neural Text Degeneration. ICLR 2020. arXiv:1904.09751. <https://arxiv.org/abs/1904.09751>

[6] Décodage contraint — grammaires **GBNF** (llama.cpp) et **Outlines** (structured generation). <https://github.com/dottxt-ai/outlines>

---

# Addendum — Décisions de conception (NLI + test causal)

*Complète §2.2 et §3, après implémentation de §8.1 (schéma d'actes) et §8.2 (metrics.py).*

## A. Rubrique NLI de responsivité (§2.2)

Principe : la responsivité = **prendre position sur la proposition référencée** (`in_reply_to`), **pas** « être d'accord ». Donc un `reject_proposal` qui **contredit** l'offre EST responsif. NLI est un **second signal** au-dessus de la responsivité lexicale/embedding déjà en place — jamais l'arbitre unique — et son absence **dégrade proprement** (repli embedding/lexical). Deux usages : **engagement** (répond-il ?) et **cohérence performative** (dit-il ce qu'il fait ?).

| Échange | Label(s) NLI = « adresse » | Repli si NLI absent | Note |
|---|---|---|---|
| `propose → accept_proposal` | **entailment** (soutient l'offre) | `cos ≥ τ` | contradiction ici = **incohérence** (dit accepter mais s'oppose) → flag |
| `propose → reject_proposal` | **contradiction** (s'oppose à l'offre) | `cos ≥ τ` | entailment ici = incohérence |
| `query → inform` | **entailment OU contradiction** (confirme ou dément) | `cos ≥ τ` | **neutral = a esquivé** → flag |
| `cfp/propose → propose` (contre-offre) | **ne pas exiger NLI ≠ neutral** | `cos ≥ τ` au *sujet* de l'offre | une contre-offre change les termes → souvent neutre sous NLI ; se fier à l'embedding |
| `* → not_understood / refuse / agree` (avec `in_reply_to`) | **engagé par construction** | — | ne pas pénaliser un « je ne comprends pas » honnête |

**Seuils (départ, à calibrer sur les cas Mock + un petit set labellisé) :**
- NLI : engagé si `max(P_entail, P_contra) ≥ 0.50` **et** `> P_neutral` ; « n'écoute pas » si `P_neutral ≥ 0.60`.
- Embedding (contre-offres/informs) : `cos ≥ 0.35` = adresse ; `< 0.25` = hors-sujet.
- Round flaggé si **> 1/3** des réponses sont non-responsives.
- **NLI = enhancer, jamais dépendance dure** : petit modèle CPU (`cross-encoder/nli-deberta-v3-small` ou MiniLM-MNLI) ; **segmenter en phrases** (prendre la phrase de la réponse la plus proche de l'offre) ; **calibrer empiriquement** (messages diplomatiques courts = OOD pour MNLI).
- **Bonus thèse** : un mismatch **performative ↔ label** (dit « accept » mais le contenu contredit) = signal de **tromperie/incohérence** → à logger (utile pour tes détecteurs d'alignement M1/M2).

## B. Protocole du test causal (`causal.py`, §3)

Contrefactuel **primaire = shuffle/replace** : remplacer le message de A par un **leurre** de même `performative` et longueur comparable — **pas** la simple suppression (qui change la taille du prompt et bruite la comparaison).

Divergence composite, normalisée `[0,1]` :

```
div = 0.5*semantic + 0.3*perf_flip + 0.2*decision_dist
  semantic      = 1 - cos(emb(B|A_reel), emb(B|A_leurre))
  perf_flip     = 1 si performative differe, sinon 0
  decision_dist = 1 - Jaccard(cibles / proposed_alliances)   # 0 si aucune
```

**Seuils :**
- **écoute** si `div ≥ 0.25` ;
- **« prompte au hasard »** (échec) si `div ≤ 0.05` (altérer A ne change ~rien) ;
- zone grise `0.05–0.25` = écoute faible → **warn**, pas échec.

**Robustesse** : **température ≈ 0** (2 générations déterministes) pour un test reproductible. Option riche (hors CI) : `K=5` échantillons de chaque côté + **Jensen-Shannon** sur la distribution d'actions — saveur *influence causale* (Jaques). Calibrer les seuils pour que le Mock « écoute » dépasse 0,25 et le Mock « au hasard » tombe sous 0,05.

## C. Canary CI (scénario figé)

- **Déterminisme** : le **gate CI tourne contre `MockBackend`** (deux réponses scriptées : une « écoute » qui dépend du contexte, une « au hasard » fixe) → vert et reproductible, **sans Ollama**. Un **canary *live*** (`--live`, contre Ollama local) existe en **option, hors gate CI** (le non-déterminisme LLM rendrait la CI *flaky* — à proscrire).
- **Scénario** : round 1 mer Rouge (`maritime_attack`, `actors=["iran"]`, `severity=0.6`), **seed = 42**, temp ≈ 0.
- **A → B** : `usa` (A) envoie un `cfp`/`query` à `france` (B) : « La France rejoint-elle une coalition maritime pour sécuriser le détroit — oui/non — et sous quelle condition ? »
- **Leurre** (contrefactuel) : même `performative` de A, **sujet différent** (« Quel est ton avis sur les prix du pétrole ? »).
- **Passe si** la réponse de B : (1) `in_reply_to` = id du message de A ; (2) `performative` ∈ {`accept_proposal`, `reject_proposal`, `propose`} ; (3) responsivité (NLI/embedding) au sujet *coalition* ≥ seuil ; (4) **`div ≥ 0.25`** entre « réponse-au-vrai-message » et « réponse-au-leurre ». **Échoue** si la réponse de B est ~identique quel que soit le message de A → il n'écoute pas.

## Découpage (rappel)
Ces décisions = **[CW] Cowork**. Implémentation `nli.py` + `causal.py` + canary CI + `scorer.py` + panneau « santé du dialogue » = **[CC] Claude Code**.
