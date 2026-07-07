# Gouvernance des données — Phase 4

> Provenance, années de référence, méthode de normalisation, licences et limites des `data/countries/*.json`. Objectif P4 : remplacer les valeurs saisies à la main (P0) par des valeurs **sourcées depuis des datasets**, et documenter honnêtement le **statut** de chaque champ.

Acteurs couverts : `usa`, `china`, `france`, `egypt`, `iran`, `saudi_arabia` (crise mer Rouge),
et depuis juillet 2026 (extension roster, §2 bis, ajustée §2 ter) : `japan`, `russia`,
`germany`, `uk`, `spain`, `italy`, `mexico`, `brazil`, `india`, `south_africa`, `australia`,
`morocco`, `ukraine`, `canada`, `turkey`, `israel`, `south_korea` — **23 acteurs**
(`denmark` retiré du roster le 7 juillet 2026, décision produit).
Période de référence principale : **2024** (PIB, croissance, défense), avec quelques indices 2023–2025 (détaillés ci-dessous).
Recherche réalisée : **1ᵉʳ juillet 2026**.

## 1. Statut de chaque champ (résumé)

| Champ `CountryState` | Source | Année | Confiance |
|---|---|---|---|
| `economy.gdp` | World Bank, *GDP (current US$)* | 2024 | **Élevée** |
| `economy.growth` | IMF, *World Economic Outlook* (real GDP growth) | 2024 | **Élevée** |
| `military.defense_budget` | SIPRI, *Military Expenditure Database* | 2024 | **Élevée** |
| `military.nuclear_power` | Fait établi (statut nucléaire militaire) | — | **Élevée** |
| `technology_level` | WIPO, *Global Innovation Index* (rang) | 2024 | **Élevée** (dérivé d'un rang) |
| `economy.trade_dependency` | World Bank, *Trade (% of GDP)* | ~2023 | Moyenne (normalisé) |
| `resources.oil_dependency` / `energy_independence` | EIA / IEA (profils énergie) ; ref. World Bank *Energy imports, net* | ~2023 | Moyenne (dérivé) |
| `political_stability` | World Bank, *WGI — Political Stability* (rang percentile) | 2023 | Faible-moyenne (approx.) |
| `military.projection` | Estimation analyste informée par *Global Firepower* + structure de forces | 2025 | **Faible** (subjectif) |
| `alliances`, `rivals`, `political_system`, `ideology`, `strategic_priorities` | Codage qualitatif (appartenances factuelles ; reste analyste) — **inchangé depuis P0** | — | Mixte |

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
| Israël | 541 Md | 0,9 % (approx.) | 46,5 Md | 15ᵉ |
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

- Les champs **qualitatifs** (`alliances`, `rivals`, `political_system`, `ideology`, `strategic_priorities`) sont **inchangés depuis P0** → le comportement des phases P1–P3 est préservé.
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
réseau vers `api.worldbank.org` n'est pas disponible dans l'environnement de dev actuel — un mode
`--refresh` live pourra être ajouté quand il le sera.*

## Références

[1] World Bank — GDP (current US$). <https://data.worldbank.org/indicator/NY.GDP.MKTP.CD>

[2] IMF — World Economic Outlook (real GDP growth). <https://www.imf.org/external/datamapper/NGDP_RPCH@WEO>

[3] SIPRI — Military Expenditure Database / Fact Sheet 2024 (avril 2025). <https://www.sipri.org/databases/milex>

[4] WIPO — Global Innovation Index 2024. <https://www.wipo.int/web-publications/global-innovation-index-2024/en/gii-2024-results.html>

[5] World Bank — Trade (% of GDP). <https://data.worldbank.org/indicator/NE.TRD.GNFS.ZS>

[6] World Bank — Worldwide Governance Indicators (Political Stability). <https://www.worldbank.org/en/publication/worldwide-governance-indicators>

[7] Global Firepower — 2025 Military Strength Ranking. <https://www.globalfirepower.com/countries-listing.php>

[8] U.S. EIA — International energy data. <https://www.eia.gov/international/>

[9] IEA — Countries & Regions. <https://www.iea.org/countries>
