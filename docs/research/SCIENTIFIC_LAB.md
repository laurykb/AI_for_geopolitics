# Laboratoire scientifique reproductible

## Objet

Le mode **Laboratoire d'expérience** transforme des hypothèses issues des articles intégrés au
projet en protocoles sélectionnables dans l'interface. Il ne prétend pas prédire le
comportement d'un État réel : il mesure le comportement de versions précises de modèles,
avec des prompts, facteurs, graines et règles déclarés.

Le mode classique reste ludique. Le laboratoire est une surface séparée, conçue pour les
réplications, les études de sensibilité et les comparaisons humain–IA.

La planification de scénarios reste inter-mode : avant toute prise de parole, le modèle
produit **exactement trois futurs privés structurés**, prévoit les réponses adverses, puis
fige une branche. Un second appel distinct ne reçoit que ce choix et rédige la déclaration
publique. Les branches sont streamées uniquement vers la boîte de verre du joueur, sous
forme de résumés structurés, puis repliées quand la parole commence ; elles ne sont jamais
transmises aux autres pays.
La branche choisie est rapprochée de la réponse observée ; taux d'exactitude, prévisions en
attente et erreurs récentes restent visibles dans le théâtre et réinjectés au tour suivant.

Classique, Campagne et Laboratoire exposent le même **casting de modèles** : le mode
mono-modèle exige lui aussi un choix explicite ; le mode multi en accepte deux à quatre.
L'utilisateur choisit ensuite explicitement quel
modèle incarne chaque pays. Le Game Master et le juge gardent leurs modèles identifiés.
Les tags, digests et affectations sont figés dans la sauvegarde ou le manifeste ;
l'exécution reste séquentielle sur mono-GPU.

## Parcours dans l'interface

Depuis **Nouvelle partie → Laboratoire d'expérience** ou le lien **Laboratoire** du menu,
Laury découpe le travail en cinq écrans séquentiels dont l'état est conservé :

1. **Comprendre** la boucle expérimentale ;
2. **Hypothèse** : choisir la question, le scénario et les facteurs contrôlés ;
3. **Casting** : choisir Alpha et Bêta parmi les pays autorisés par le scénario, geler
   leurs profils et affecter un ou plusieurs modèles Ollama,
   ou demander une matrice de toutes les paires ordonnées ;
4. **Théâtre** : retrouver la carte zoomable, les injects du Game Master, les dialogues
   publics et la boîte de verre en direct : phase active, prompts exacts, trois futurs,
   prévision et décision structurée ;
5. **Résultats** : lire la réponse, ses preuves, ses erreurs et ses incertitudes, puis
   exporter ou reproduire exactement le manifeste.

Le nombre de cellules, les répétitions, la limite d'appels et la durée locale estimée
sont vérifiés avant le pré-enregistrement. Celui-ci ouvre directement le théâtre.

Les protocoles avec autorité humaine présentent une vignette à la fois, masquent la
vérité jusqu'au choix, interdisent la double soumission et reprennent le même essai après
un rechargement de page.

## Protocoles livrés

| Protocole | Facteurs | Mesure principale | Mode |
|---|---|---|---|
| Négociation pour l'uranium | rapport de force 80/20, 50/50, 20/80 | emploi nucléaire | automatisé |
| AI Arms — décisions d'ouverture | 7 scénarios × rôles Alpha/Bêta | franchissement du seuil nucléaire | automatisé, screening |
| AI Arms — tournoi dyadique | scénario × horizon × 6/12/40 tours × paires ordonnées | erreur prévision–action observée | automatisé, multi-agent |
| Autorité humaine | recommandation correcte/incorrecte × veto × urgence | décision humaine appropriée | humain requis |
| Langue de délibération | anglais, français, japonais × pression temporelle | emploi nucléaire | automatisé |

Le protocole de langue teste une hypothèse. Le chiffre « 95 % → 17 % en japonais » n'a
pas été retrouvé dans les sources fournies et n'est donc jamais affiché comme un fait.

## Contrat de reproductibilité

Le manifeste fige avant le premier appel :

- l'identifiant du protocole et la version de son schéma ;
- toutes les cellules factorielles et leur ordre ;
- les répétitions et graines par cellule ;
- la version du prompt et les paramètres de génération ;
- le tag, l'ordre et le digest exact de chaque modèle ;
- les paires Alpha/Bêta, l'auto-jeu éventuel et le nombre maximal d'appels modèle ;
- les pays Alpha/Bêta, leur profil complet et l'affectation pays→modèle ;
- le profil matériel et l'estimation disponible au moment du lancement.

Une reproduction exacte est refusée si un modèle ou son digest a changé. Les sorties
conservent la réponse brute, la réponse structurée validée, les normalisations explicites,
la latence, les erreurs et le nombre de tentatives. L'export JSONL est diffusé par lots :
la première ligne contient le manifeste, les suivantes les exécutions ordonnées.

Les traces sont des journaux de décision auditables (inject du Game Master, prévision,
signal public, action, activité inter-round, options, critères, choix et
incertitude), jamais une exposition supposée d'une chaîne de pensée privée.

Dans le tournoi dyadique, chaque acteur effectue trois appels distincts et ordonnés :
un **Tree of Thoughts privé de trois futurs**, puis `forecast` alimenté par l'arbre figé,
puis `decision` tenue d'exécuter la branche choisie. La déclaration publique ne contient
aucune branche privée. Alpha et Bêta ne voient jamais la production courante de l'autre
avant le commit simultané. La prévision est ensuite comparée à l'action adverse résolue,
et non à un résumé inventé a posteriori.

## Interprétation statistique

Le verdict reste verrouillé tant que le plan n'est pas terminal. Chaque groupe
modèle × cellule affiche son effectif et un intervalle de Wilson à 95 %. En dessous de
30 répétitions valides par groupe, le résultat porte le verdict **Données insuffisantes**.

Une réplication peut confirmer, nuancer ou ne pas reproduire un effet pour le panel
testé. Elle ne confirme pas à elle seule une causalité linguistique, une doctrine nationale
ou une fréquence de décision étatique.

## Mise à l'échelle sur la machine locale

Profil mesuré : RTX 2060 SUPER, 8 Go de VRAM, un seul modèle chargé à la fois.

| Mesure de file SQLite | Résultat mesuré à 10 000 exécutions |
|---|---:|
| Création du plan | 547,78 ms, 18 255 lignes/s |
| Lecture de progression médiane / p95 | 1,979 ms / 2,658 ms |
| Export JSONL | 454,9 ms, 21 982 lignes/s |
| Pic mémoire création / export | 2,23 Mio / 0,74 Mio |
| Taille de base | 4 Mio |

Les goulots traités sont :

- **VRAM** : exécution groupée par modèle et déchargement au changement de bloc ;
- **rechargement des poids** : maintien Ollama pendant le bloc ;
- **crash ou veille** : réclamation atomique et persistance après chaque résultat ;
- **dérive des tags** : digest figé dans le manifeste ;
- **UI volumineuse** : polling de compteurs et d'un seul checkpoint d'audit actif ;
  agrégation exhaustive des résultats seulement à l'état terminal ;
- **agrégation quadratique** : agrégation terminale et index de progression dédiés ;
- **export volumineux** : pagination keyset et mémoire constante ;
- **arrêt** : annulation du reliquat après l'inférence active, sans perte des résultats acquis.
- **tournoi long** : plafond de 10 000 appels modèle, pilote de six tours par défaut et
  annulation coopérative vérifiée entre deux tours ;
- **décalage de version local** : la route `/laboratoire` se replie sur le contrat campagne
  historique lorsqu'un backend déjà lancé ne connaît pas encore `/api/lab`.

Le script `python -m scripts.profile_research_scaling --runs 10000` reproduit le benchmark
de stockage. `scripts/benchmark_research_models.py` mesure séparément la conformité au
schéma, le temps de chargement, la durée chaude et les tokens par seconde du digest exact.

## Validation locale du 18 juillet 2026

Un essai lancé entièrement depuis l'UI sur le protocole AI Arms a produit 14/14 résultats
valides avec Llama 3.2, sans erreur. Le manifeste a ensuite été cloné à l'identique et le
reliquat du clone annulé depuis l'interface. Ce smoke valide le parcours technique ; avec
une répétition par groupe, il ne constitue pas un résultat scientifique interprétable.

## Frontière actuelle

Le screening d'ouverture et le **tournoi dyadique natif** coexistent. Le tournoi livre les
mouvements simultanés, six appels structurés par tour, la mémoire publique courte, les
divergences saillantes, les accidents privés, les permutations de modèles, les horizons
appariés et la calibration contre les actions observées.

La frontière restante concerne l'attrition détaillée de l'annexe C : le moteur emploie
actuellement un proxy d'avantage stratégique borné et transparent. Elle concerne aussi
l'analyse statistique hiérarchique modèle × rôle × scénario et les extensions
multipartites. Ces limites sont exportées et ne sont jamais remplacées par de faux chiffres.
