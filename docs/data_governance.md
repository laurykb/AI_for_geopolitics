# Gouvernance des données — Phase 4

> Provenance, années de référence, méthode de normalisation, licences et limites des `data/countries/*.json`. Objectif P4 : remplacer les valeurs saisies à la main (P0) par des valeurs **sourcées depuis des datasets**, et documenter honnêtement le **statut** de chaque champ.

Acteurs couverts : `usa`, `china`, `france`, `egypt`, `iran`, `saudi_arabia` (crise mer Rouge),
et depuis juillet 2026 (extension roster, §2 bis, ajustée §2 ter) : `japan`, `russia`,
`germany`, `uk`, `spain`, `italy`, `mexico`, `brazil`, `india`, `south_africa`, `australia`,
`morocco`, `ukraine`, `canada`, `turkey`, `israel`, `south_korea`, puis l'extension du
18 juillet 2026 (§2 quinquies) : `algeria`, `argentina`, `democratic_republic_congo`,
`mali`, `senegal`, `singapore`, `tunisia`, `united_arab_emirates`, puis l'extension
scientifique nucléaire : `north_korea`, `pakistan` — **33 acteurs**
(`denmark` retiré du roster le 7 juillet 2026, décision produit).
Période de référence principale : **2024** (PIB, croissance, défense), avec quelques indices 2023–2025 (détaillés ci-dessous).
Recherche initiale : **1ᵉʳ juillet 2026** ; extension actualisée le **18 juillet 2026**.

## 1. Statut de chaque champ (résumé)

| Champ `CountryState` | Source | Année | Confiance |
|---|---|---|---|
| `economy.gdp` | World Bank, *GDP (current US$)* | 2024 | **Élevée** |
| `economy.growth` | World Bank, *GDP growth (annual %)* | 2024 | **Élevée** |
| `military.defense_budget` | SIPRI, *Military Expenditure Database* | 2024 | **Élevée** |
| `military.nuclear_power` | Fait établi (statut nucléaire militaire) | — | **Élevée** |
| `technology_level` | WIPO, *Global Innovation Index* (rang) | 2024 | **Élevée** (dérivé d'un rang) |
| `economy.trade_dependency` | World Bank, *Trade (% of GDP)* | ~2023 | Moyenne (normalisé) |
| `resources.oil_dependency` / `energy_independence` | EIA / IEA (profils énergie) ; ref. World Bank *Energy imports, net* | ~2023 | Moyenne (dérivé) |
| `political_stability` | World Bank, *WGI — Political Stability* (rang percentile) | 2023 | Faible-moyenne (approx.) |
| `military.projection` | Estimation analyste informée par *Global Firepower* + structure de forces | 2025 | **Faible** (subjectif) |
| `alliances` | **Dérivé du registre sourcé** `data/sources/alliances.json` (§2 quater) — adhésions vérifiées aux sources officielles | 2026-07 | **Élevée** (sauf notes) |
| `rivals`, `political_system`, `ideology`, `strategic_priorities` | Codage qualitatif analyste | — | Mixte |

## 2. Valeurs « dures » sourcées (par pays)

| Pays | PIB 2024 (USD) | Croissance réelle 2024 | Défense 2024 (USD) | Innovation (GII 2024) |
|---|---|---|---|---|
| États-Unis | 28 750 Md | 2,8 % | 997,0 Md | 3ᵉ / 133 |
| Chine | 18 740 Md | 5,0 % | 314,0 Md (est.) | 11ᵉ |
| France | 3 162 Md | 1,1 % | 64,7 Md | 12ᵉ |
| Arabie saoudite | 1 238 Md | 1,3 % | 80,3 Md | 47ᵉ |
| Iran | 437 Md | 3,5 % | 7,9 Md | 64ᵉ |
| Égypte | 389 Md | 2,4 % | 2,40 Md | 86ᵉ |

PIB : World Bank *GDP (current US$)* 2024 [1]. Croissance : IMF *WEO* (avril 2025), real GDP growth 2024 [2]. Défense : SIPRI *Military Expenditure* 2024 (publié avril 2025) [3]. Innovation : WIPO *GII 2024* [4].

## 2 bis. Extension roster — 15 acteurs (juillet 2026)

| Pays | PIB 2024 (USD) | Croissance 2024 | Défense 2024 (USD) | GII 2024 |
|---|---|---|---|---|
| Japon | 4 026 Md | 0,1 % | 55,3 Md | 13ᵉ |
| Russie | 2 184 Md | 4,1 % | 149,0 Md (est.) | 59ᵉ |
| Allemagne | 4 660 Md | −0,2 % | 88,5 Md | 9ᵉ |
| Royaume-Uni | 3 644 Md | 1,1 % | 81,8 Md | 5ᵉ |
| Espagne | 1 731 Md | 3,2 % | 24,6 Md | 28ᵉ |
| Italie | 2 376 Md | 0,7 % | 30,8 Md | 26ᵉ |
| Mexique | 1 852 Md | 1,2 % | 12,0 Md (approx.) | 56ᵉ |
| Brésil | 2 179 Md | 3,4 % | 25,0 Md (approx.) | 50ᵉ |
| Inde | 3 910 Md | 6,5 % | 86,1 Md | 39ᵉ |
| Afrique du Sud | 403 Md | 0,6 % | 3,3 Md | 69ᵉ |
| Australie | 1 690 Md | 1,0 % | 33,8 Md | 23ᵉ |
| Maroc | 157 Md | 3,2 % | 5,8 Md (approx.) | 66ᵉ |
| Danemark *(retiré du roster, §2 ter)* | 412 Md | 3,7 % | 9,9 Md (approx.) | 10ᵉ |
| Ukraine | 191 Md | 3,5 % | 64,7 Md | 60ᵉ |
| Canada | 2 241 Md | 1,5 % | 29,3 Md | 14ᵉ |

Mêmes sources et même normalisation que §2/§3. **Limites spécifiques de cette extension** :
- Valeurs SIPRI marquées *(approx.)* : à figer depuis la base SIPRI (les grands
  budgets — Russie, Allemagne, UK, Japon, Inde, Ukraine — sont confirmés par le fact sheet 2024).
- **Ukraine** : économie de guerre — PIB, croissance et budget défense (dopé par l'aide
  extérieure) sont volatils ; `wgi_stability_percentile` ≈ 3 reflète l'invasion en cours.
  Confiance globale plus faible que le reste du roster, à traiter comme instantané 2024.
- Nouveaux tags d'alliances introduits : `QUAD`, `AUKUS`, `USMCA` (mêmes règles de pacte
  que les tags existants). `rivals` reste conservateur (paires actives seulement :
  russie↔ukraine/usa, inde↔chine, japon/australie↔chine, allemagne/uk↔russie).
- `compute` reste **illustratif** (échelle relative usa=100), comme au §1.

## 2 ter. Ajustement roster — 7 juillet 2026 (−Danemark, +Turquie, Israël, Corée du Sud)

Décision produit : `denmark` sort du roster jouable (fiche conservée au §2 bis pour
traçabilité) ; trois acteurs entrent. Valeurs 2024, mêmes sources et normalisation que
§2/§3, **compilées de mémoire par l'assistant (état des connaissances janv. 2026) — à
figer depuis les bases World Bank/IMF/SIPRI/GII comme le reste du roster** :

| Pays | PIB 2024 (USD) | Croissance 2024 | Défense 2024 (USD) | GII 2024 |
|---|---|---|---|---|
| Turquie | 1 322 Md (approx.) | 3,2 % | 25,0 Md (approx.) | 37ᵉ |
| Israël | 542,3 Md | 1,0 % | 45,92 Md | 15ᵉ |
| Corée du Sud | 1 870 Md | 2,0 % | 47,6 Md | 6ᵉ |

Limites spécifiques :
- **Israël** : `nuclear_power = true` reflète le **statut assessé** (arsenal non déclaré,
  politique d'ambiguïté — pas un fait reconnu par l'État) ; économie et stabilité 2024
  marquées par la guerre (WGI ≈ 13, instantané).
- **Corée du Sud** : `wgi_stability_percentile ≈ 60` est un instantané qui précède pour
  l'essentiel la crise politique de décembre 2024 (loi martiale avortée) — à réviser.
- **Turquie** : PIB en USD sensible à la forte inflation/dépréciation de la livre ;
  `wgi_stability_percentile ≈ 10` (approx.).
- **Matrice `rivals`** : ajout de la paire active `iran ↔ israel` (frappes directes
  d'avril et octobre 2024 — critère « paires actives seulement » du §2 bis). La Turquie
  reste sans rival déclaré (rupture diplomatique Turquie–Israël jugée sous le seuil).

## 2 quinquies. Extension internationale — 18 juillet 2026 (+8 fiches, Israël consolidé)

Israël était déjà jouable : sa fiche a été **mise à jour**, sans créer de doublon. Les
huit autres profils ont été ajoutés à la source d'indicateurs, au build reproductible,
au moteur, à la carte, au lobby, à l'onglet Informations et aux lexiques linguistiques.

| Pays | PIB 2024 (USD) | Croissance 2024 | Défense 2024 (USD) | Commerce 2023 (% PIB) | WGI stabilité 2023 | GII 2024 |
|---|---:|---:|---:|---:|---:|---:|
| Algérie | 269,3 Md | 3,7 % | 21,81 Md | 44 % | 23,22 | 115ᵉ |
| Argentine | 638,4 Md | −1,3 % | 4,18 Md | 27 % | 41,71 | 76ᵉ |
| RDC | 75,7 Md | 6,1 % | 0,90 Md | 87 % | 5,21 | non classée → 133ᵉ imputé |
| Mali | 26,8 Md | 5,0 % | 0,93 Md | 58 % | 0,47 | 131ᵉ |
| Sénégal | 32,2 Md | 6,5 % | 0,64 Md | 72 % | 41,23 | 92ᵉ |
| Singapour | 572,9 Md | 5,3 % | 15,33 Md | 324 % | 97,16 | 4ᵉ |
| Tunisie | 51,4 Md | 1,6 % | 1,32 Md | 112 % | 22,27 | 81ᵉ |
| Émirats arabes unis | 552,3 Md | 4,0 % | 22,8 Md *(est.)* | 199 % | 70,14 | 32ᵉ |

Les PIB, croissances et ratios de commerce proviennent des séries World Bank [1][2][5] ;
les percentiles de stabilité, du WGI [6] ; les rangs d'innovation, du rapport WIPO GII
2024 [4] ; les dépenses militaires, du classeur SIPRI 2025 portant sur 2024 [3]. Les
montants conservent la précision machine dans `indicators.json` mais sont arrondis ici.

Limites particulières :

- **RDC** : absente des 133 économies classées par le GII 2024. Le moteur exige une
  valeur sur la même échelle ; le rang-plancher 133 est donc imputé, et cette limite est
  affichée sur la fiche Informations.
- **EAU** : SIPRI ne fournit plus de série exploitable depuis 2014. Le budget de défense
  2024 est une estimation analyste de 22,8 Md USD, signalée comme incertaine dans l'UI.
- **Commerce supérieur à 100 % du PIB** (Singapour, EAU, Tunisie) : phénomène possible
  pour les économies très ouvertes ; la règle historique du jeu plafonne toutefois
  `trade_dependency` à 1.
- `projection`, énergie et `compute` restent des calibrages analyste sur l'échelle du
  roster existant. Ils ne sont pas présentés comme des statistiques officielles.

Alliances ajoutées ou étendues, à partir des listes officielles : Union africaine,
MERCOSUR, ASEAN, SADC, EAC, CEDEAO, AES, OPEP, FPDA et I2U2 ; ajout des nouveaux membres
aux BRICS, à la Ligue arabe, au CCG, au CPTPP, au RCEP et aux Accords d'Abraham. Deux
statuts 2026 sont explicitement traités : retrait effectif du Mali de la CEDEAO en 2025
et retrait des EAU de l'OPEP au 1ᵉʳ mai 2026. Le Mali reste membre de l'Union africaine
mais sa participation demeure suspendue ; le registre porte la note au lieu de masquer
ce statut.

## 2 sexies. Couverture nucléaire mondiale — 18 juillet 2026 (+Pakistan, Corée du Nord)

Le roster couvre désormais les **neuf États dotés de l'arme nucléaire recensés au début
de 2025 par le SIPRI** [21] : Chine, États-Unis, France, Inde, Israël, Pakistan, Royaume-Uni,
Russie et Corée du Nord. Les deux nouvelles fiches sont jouables dans tous les modes et
présentes dans le lobby, les cartes, les lexiques, les relations et le laboratoire.

| Pays | PIB 2024 | Croissance | Défense 2024 | Commerce | WGI stabilité | GII 2024 |
|---|---:|---:|---:|---:|---:|---:|
| Pakistan | 371,57 Md USD | 3,0 % | 10,7 Md USD *(dérivé SIPRI)* | 28,47 % | 4,64 | 91ᵉ |
| Corée du Nord | 32,05 Md USD *(est. BOK)* | 3,7 % *(est. BOK)* | 8 Md USD *(imputé)* | 8,42 % *(dérivé)* | 21,23 | non classée → 133ᵉ imputé |

Le Pakistan utilise les séries Banque mondiale, WGI et WIPO, plus le total SIPRI. Pour la
Corée du Nord, l'absence de statistiques comparables impose une provenance par pays :
l'API et l'UI remplacent donc la source globale par l'estimation 2024 de la Banque de
Corée [22]. Celle-ci avertit que son PIB est calculé avec des prix et ratios de valeur
ajoutée sud-coréens et **ne doit pas être comparé directement** aux PIB des autres pays.

Le budget militaire nord-coréen de 8 Md USD est une variable de scénario égale à 25 % du
PIB estimé. Ce n'est pas une mesure : les analyses doivent tester au minimum 20 %, 25 % et
30 %. Le commerce (8,42 %) est le ratio des 2,7 Md USD d'échanges de biens BOK/KOTRA au
PIB estimé ; les flux non observés ou illicites n'y figurent pas. Le rang GII plancher est
également imputé. Ces limites sont affichées sur la fiche pays, attribut par attribut.

Le registre ajoute l'adhésion du Pakistan à l'OCS et les traités Chine–RPDC (1961,
réaffirmé en 2026) [23] et Russie–RPDC (signé et ratifié en 2024) [24].

## 2 quater. Alliances & traités — registre sourcé (actualisé le 18 juillet 2026)

L'attribut `alliances` de chaque pays n'est **plus codé à la main** : il est **dérivé**
(par `ingestion.build`) du registre machine-lisible `data/sources/alliances.json` —
28 accords/traités/blocs réels, chacun avec nom, domaine (militaire/économique/politique),
traité fondateur daté, **URL officielle** et membres (restreints au roster). Les mêmes
données alimentent l'onglet Informations et les prompts de négociation (les SI citent les
traités par leur nom).

Accords couverts : OTAN, UE, BRICS, OCS, QUAD, AUKUS, ACEUM/USMCA, G7, Union africaine,
MERCOSUR, ASEAN, SADC, EAC, CEDEAO, AES, OPEP, Ligue arabe, CCG, CPTPP, RCEP, Accords
d'Abraham, FPDA, I2U2, traités de défense bilatéraux États-Unis–Japon (1960) et
États-Unis–Corée du Sud (1953), Chine–RPDC (1961), Russie–RPDC (2024), plus le bloc
`Western` (marqué `informal` : **codage
analyste d'affinité, pas un traité**).

Limites documentées :
- **Arabie saoudite / BRICS** : listée par la présidence du bloc depuis 2025 mais adhésion
  jamais formalisée publiquement — comptée membre avec note, à réviser.
- Le QUAD et le G7 n'ont **pas de traité fondateur** (dialogues/forums) : le champ `basis`
  le précise ; ne pas les traiter comme des engagements de défense collective.
- Les pactes conclus **en partie** (`pact:a+b`, moteur de diplomatie) s'ajoutent à cet
  attribut en cours de jeu et n'appartiennent pas au registre.
- **Poids moteur (7 juillet 2026)** : un traité **militaire** partagé avec un acteur de
  l'événement donne +0,15 d'engagement (solidarité) ; un traité **militaire ou
  économique** partagé donne +0,15 de soutien au communiqué (cohésion). Les forums sans
  traité et les blocs informels ne pèsent pas. Spéc :
  `docs/superpowers/specs/2026-07-07-alliances-moteur-pastilles-design.md`.

## 3. Méthode de normalisation des indices 0–1

- **`technology_level`** = 1 − (rang_GII − 1) / (133 − 1), où 133 = nombre d'économies classées au GII 2024. (Ex. USA 3ᵉ → 0,98 ; Égypte 86ᵉ → 0,36.)
- **`economy.trade_dependency`** = *Trade (% of GDP)* / 100, plafonné à 1 (World Bank `NE.TRD.GNFS.ZS`, dernière année dispo) [5].
- **`political_stability`** = rang percentile WGI *Political Stability and Absence of Violence/Terrorism* (2023) / 100 [6]. **Valeurs approximatives** — à figer depuis le DataBank WGI.
- **`military.projection`** = estimation analyste (porte-avions, bases à l'étranger, capacité expéditionnaire) **informée** par le rang *Global Firepower 2025* [7]. **Champ le plus subjectif** : à traiter comme ordre de grandeur.
- **`resources.oil_dependency` / `energy_independence`** = dérivés du **statut net importateur/exportateur d'énergie** (profils EIA/IEA [8][9] ; référence World Bank *Energy imports, net (% of energy use)* `EG.IMP.CONS.ZS`). Ex. Arabie saoudite/Iran exportateurs → `oil_dependency` ≈ 0, `energy_independence` ≈ 1 ; USA net exportateur depuis 2019 ; France faible indépendance fossile mais électricité nucléaire.

## 4. Licences

- **World Bank Open Data** (PIB, commerce, WGI, énergie) : **CC BY 4.0** — réutilisation libre avec attribution [1][5][6].
- **IMF World Economic Outlook** : réutilisation avec attribution [2].
- **SIPRI Military Expenditure Database** : gratuit pour la **recherche/usage non commercial** avec attribution ; redistribution encadrée — citer SIPRI, ne pas re-publier la base brute [3].
- **WIPO Global Innovation Index** : © WIPO, usage avec attribution [4].
- **IEA** : conditions restrictives sur la redistribution des données [9]. **EIA** (gouvernement US) : domaine public [8].
- **Global Firepower** : indice propriétaire, usage indicatif avec attribution [7].

## 5. Limites et biais

- **Années mixtes.** PIB/croissance/défense = 2024 ; WGI = 2023 ; rangs GII = 2024, GFP = 2025. À homogénéiser si besoin de cohérence stricte.
- **Iran : forte incertitude.** Le PIB en USD est très sensible au taux de change (taux multiples, sanctions) ; le budget défense est difficile à estimer (SIPRI lui-même prudent). Traiter ces valeurs comme des ordres de grandeur.
- **Indices subjectifs.** `projection` surtout, et dans une moindre mesure `political_stability` : ce sont des **estimations**, pas des mesures directes. Ne pas sur-interpréter les décimales.
- **Biais de couverture.** Les indices fondés sur la presse/perceptions (WGI, et plus tard GDELT) sur-représentent les sources anglophones.
- **GDELT non utilisé ici.** GDELT (événements/tensions) relève du **niveau scénario** (génération de `GeoEvent` et de tensions initiales), pas du `CountryState`. À brancher lors de la construction des scénarios (étape suivante), pas dans les profils pays.

## 6. Note de coordination (P4 ↔ branches locales)

- Les champs **qualitatifs** (`alliances`, `rivals`, `political_system`, `ideology`,
  `strategic_priorities`) sont codés ou dérivés de façon explicite ; une extension du
  roster peut donc modifier les interactions entre nouveaux voisins et partenaires.
- En revanche, plusieurs **valeurs numériques changent** vs P0 (ex. Chine `trade_dependency` 0,70 → **0,37** ; budgets défense ; PIB). L'agent rule-based a des seuils (`gdp ≥ 1e12`, `trade_dependency ≥ 0.6`, `projection ≥ 0.6`) : la Chine passe désormais **sous** 0,6 en `trade_dependency` (médiation → neutralité dans certains cas). **À faire côté Claude Code local** : relancer `pytest`, ajuster toute assertion couplée à une donnée précise, puis committer sur une branche `feat/p4-data`.

## 7. Reproductibilité (build déterministe)

Les profils `data/countries/*.json` ne sont plus saisis à la main : ils sont **reproductibles**
depuis des entrées sourcées machine-lisibles `data/sources/indicators.json` (valeurs brutes +
provenance), via le package `ingestion/` qui applique les normalisations du §3.

```bash
python -m ingestion.build            # --check (défaut) : vérifie la reproductibilité
python -m ingestion.build --write    # (re)génère data/countries/*.json (format canonique)
```

`tests/test_ingestion_build.py` garantit en CI que chaque profil committé **est bien le produit**
du build depuis les sources (égalité sémantique). Les valeurs « dures » (PIB, croissance, défense,
GII, commerce, WGI) vivent dans `indicators.json` ; quand elles seront rafraîchies depuis les API
(World Bank/IMF…), il suffira de mettre à jour ce fichier et de relancer le build. *NB : l'egress
`--refresh` live n'est pas encore implémenté ; l'extension du 18 juillet a été vérifiée
depuis les API et classeurs officiels avant saisie.*

## 8. IA opérationnelle, Palantir et Maven — niveaux de preuve

Le registre machine-lisible `data/sources/strategic_technology.json` documente les
sources publiques utilisées pour les mécaniques d'aide à la décision, de fusion de
renseignement, de contrôle humain et de résilience. Il applique quatre règles :

1. Une documentation Palantir est une **source primaire sur ce que le fournisseur
   revendique**, pas une preuve indépendante d'efficacité.
2. Une annonce contractuelle du Department of Defense établit un montant, un objet et
   une date publics ; elle ne permet pas d'inférer les performances ni les usages
   classifiés.
3. Le Form 10-K déposé à la SEC établit des chiffres financiers et des risques déclarés,
   pas un effet militaire.
4. Toute traduction en mécanique de jeu est identifiée comme une **hypothèse testable** :
   qualité et fraîcheur des données, brouillard de guerre probabiliste, compression du
   temps de décision, biais d'automatisation, approbation humaine, traçabilité, coût et
   dépendance fournisseur.

Les sources actuellement couvertes sont la documentation officielle Ontology/AIP,
le Form 10-K 2025 de Palantir, trois annonces contractuelles publiques Maven Smart
System (2024–2025) et une analyse publique du DoD sur l'IA/ML dans l'image
opérationnelle commune. Le registre est exposé par `GET /api/sources` afin que les
limites restent visibles dans le produit.

## Références

[1] World Bank — GDP (current US$). <https://data.worldbank.org/indicator/NY.GDP.MKTP.CD>

[2] World Bank — GDP growth (annual %). <https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG>

[3] SIPRI — Military Expenditure Database / Fact Sheet 2024 (avril 2025). <https://www.sipri.org/databases/milex>

[4] WIPO — Global Innovation Index 2024. <https://www.wipo.int/web-publications/global-innovation-index-2024/en/gii-2024-results.html>

[5] World Bank — Trade (% of GDP). <https://data.worldbank.org/indicator/NE.TRD.GNFS.ZS>

[6] World Bank — Worldwide Governance Indicators (Political Stability). <https://www.worldbank.org/en/publication/worldwide-governance-indicators>

[7] Global Firepower — 2025 Military Strength Ranking. <https://www.globalfirepower.com/countries-listing.php>

[8] U.S. EIA — International energy data. <https://www.eia.gov/international/>

[9] IEA — Countries & Regions. <https://www.iea.org/countries>

[10] Union africaine — Member States. <https://au.int/en/member_states/countryprofiles2>

[11] MERCOSUR — Countries. <https://www.mercosur.int/en/about-mercosur/countries/>

[12] ASEAN — Member States. <https://asean.org/member-states/>

[13] SADC — Member States. <https://www.sadc.int/member-states>

[14] EAC — Partner States. <https://www.eac.int/eac-partner-states>

[15] CEDEAO — Member States. <https://www.ecowas.int/member_states/>

[16] Confédération AES — Présentation. <https://aes.ml/a-propos-de-laes/>

[17] FPDA — Five Power Defence Arrangements. <https://www.fivepowerdefencearrangements.org/>

[18] Présidence des BRICS — About the BRICS. <https://brics.br/en/about-the-brics>

[19] EIA — Retrait des EAU de l'OPEP au 1ᵉʳ mai 2026. <https://www.eia.gov/todayinenergy/detail.php?id=67804>

[20] EAU, ministère des Affaires étrangères — coopération I2U2. <https://www.mofa.gov.ae/en/mediahub/news/2023/9/21/21-9-2023-uae-yemen-usa-uae>

[21] SIPRI Yearbook 2025 — World nuclear forces. <https://www.sipri.org/yearbook/2025/06>

[22] Banque de Corée — *Gross Domestic Product Estimates for North Korea in 2024*.
<https://www.bok.or.kr/eng/bbs/E0000634/view.do?menuNo=400423&nttId=10093293>

[23] Ministère chinois des Affaires étrangères — 65ᵉ anniversaire du traité
Chine–RPDC. <https://www.mfa.gov.cn/eng/xw/zyxw/202607/t20260713_11980494.html>

[24] Présidence de la Fédération de Russie — ratification du traité Russie–RPDC.
<https://en.kremlin.ru/catalog/countries/KP/events/by-date/27.02.2025>
