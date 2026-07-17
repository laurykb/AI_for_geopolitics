# Infra — esquisse d'orchestration Kubernetes

> **ESQUISSE, pas une prod.** Ce dossier pose le *squelette* de la piste distribuée
> (roadmap **P6** infra Docker→K8s, puis **P7** MCP/distribué). Le but : pouvoir plus
> tard faire `kind create cluster` puis `kubectl apply -k` et voir la **topologie se
> dresser**. Pour le **dev local quotidien**, on ne passe PAS par ici — on lance :
>
> ```bash
> python serve.py       # API :8000 + front :3000, la façon normale de jouer
> ```

## Ce que ça dessine

```
┌───────────────────────── cluster kind « theatre » ─────────────────────────┐
│  control-plane (+ Ingress nginx)   worker-1            worker-2             │
│        :80/:443 → hôte                                                      │
│                                                                            │
│   Ingress  /      → Service theatre-web  (:3000)  → pod Next.js            │
│            /api/* → Service theatre-api  (:8000)  → pod FastAPI            │
│                                                                            │
│   ConfigMap theatre-config   Secret theatre-secrets (optionnel, SQLite=non)│
│                                                                            │
│   Service « ollama » (ExternalName) ───────────────┐                       │
└────────────────────────────────────────────────────┼───────────────────────┘
                                                      ▼
                                   Ollama de l'HÔTE  (host.docker.internal:11434, GPU)
```

Arborescence :

```
infra/
├── README.md               ← ce fichier
├── kind-cluster.yaml        # 1 control-plane + 2 workers + ports 80/443 → hôte
└── k8s/
    ├── kustomization.yaml    # base ACTIVE (kubectl apply -k infra/k8s)
    ├── namespace.yaml        # namespace « theatre »
    ├── configmap.yaml        # STORE_BACKEND, OLLAMA_HOST, NEXT_PUBLIC_API_BASE…
    ├── secret.example.yaml   # TEMPLATE (CHANGE_ME) — hors base, jamais de vrai secret
    ├── api-deployment.yaml   # theatre-api:dev, :8000, probes /health
    ├── api-service.yaml      # ClusterIP :8000
    ├── web-deployment.yaml   # theatre-web:dev, :3000
    ├── web-service.yaml      # ClusterIP :3000
    ├── ollama.yaml           # Service ExternalName → Ollama de l'hôte
    ├── ingress.yaml          # / → web, /api → api (nginx)
    └── optional/             # FUTUR, hors base
        ├── kustomization.yaml # overlay postgres + redis
        ├── postgres.yaml      # état + event store (quand SQLite ne suffira plus)
        ├── redis.yaml         # cache + broker léger
        └── ollama-in-cluster.yaml  # placeholder GPU-in-cluster (replicas: 0)
```

## Prérequis (pour booter en VRAI)

Ces outils ne sont **pas** tous présents sur le poste aujourd'hui — les installer est un
geste utilisateur :

- **Docker Desktop** — *démarré* (le daemon doit tourner ; il est actuellement éteint).
- **kind** — *à installer* : <https://kind.sigs.k8s.io/docs/user/quick-start/#installation>
  (ex. `choco install kind` ou binaire officiel).
- **kubectl** — déjà présent (v1.34, Kustomize v5.7 intégré).
- **ingress-nginx** — installé *dans* le cluster une fois celui-ci créé (voir plus bas).

## La séquence complète (à faire par l'utilisateur)

```bash
# 0. Depuis la racine du dépôt, Docker Desktop démarré.

# 1. Créer le cluster (1 control-plane + 2 workers, ports 80/443 exposés)
kind create cluster --config infra/kind-cluster.yaml

# 2. Construire les images (⚠️ NEXT_PUBLIC_* est inliné au BUILD côté web)
docker build -t theatre-api:dev .
docker build -t theatre-web:dev --build-arg NEXT_PUBLIC_API_BASE=http://localhost/api web/

# 3. Charger les images dans le cluster kind (pas de registry externe)
kind load docker-image theatre-api:dev --name theatre
kind load docker-image theatre-web:dev --name theatre

# 4. Installer le contrôleur Ingress nginx (variante kind)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller --timeout=120s

# 5. Déployer le jeu (la base kustomize)
kubectl apply -k infra/k8s

# 6. Suivre le démarrage
kubectl -n theatre get pods -w

# 7. Ouvrir le jeu
#    http://localhost/         (front)
#    http://localhost/api/health  → {"status": "ok"}
```

Pour tout retirer : `kind delete cluster --name theatre`.

## Choix d'architecture (assumés)

### Inférence Ollama sur l'HÔTE (pas dans le cluster)

Ollama a besoin du **GPU**. Le passthrough GPU vers un nœud **kind sous Windows** n'est
**pas trivial** (device-plugin NVIDIA + WSL2 au milieu). L'esquisse garde donc l'inférence
sur l'**Ollama de l'hôte** (celui que `python serve.py` fait déjà tourner sur `:11434`),
exposé au cluster par un **Service `ExternalName`** (`infra/k8s/ollama.yaml`) pointant
`host.docker.internal`. Le backend garde ainsi une adresse stable et cluster-native :
`OLLAMA_HOST=http://ollama.theatre.svc.cluster.local:11434`.

Le jour où le GPU-in-cluster est résolu, on bascule sur
`infra/k8s/optional/ollama-in-cluster.yaml` (Deployment `replicas: 0` → `1`, même nom de
Service `ollama`, `OLLAMA_HOST` inchangé) et on retire l'ExternalName de la base.

> **Limite connue :** `host.docker.internal` est fourni par Docker Desktop mais n'est pas
> toujours résolvable depuis un nœud kind. Si l'API ne joint pas Ollama, deux replis :
> mapper `host.docker.internal` sur l'IP de la gateway du réseau kind
> (`docker network inspect kind`), ou pointer `OLLAMA_HOST` directement sur l'IP de l'hôte.

> **RTX 2060 Super = 8 Go VRAM.** Un **seul** modèle 7-8B quantifié Q4 tient à la fois —
> **pas une flotte**. Ne pas espérer scaler l'inférence horizontalement sur ce poste ; le
> cache KV est le premier goulot. La « superintelligence » vient de la *structure*
> (mémoire, corpus, vue longue), pas d'empiler des répliques de modèle.

### Postgres + Redis en OPTIONNEL

Le jeu tourne aujourd'hui en **SQLite** (pod-local, éphémère). Postgres (état + event
store) et Redis (cache + broker) sont **esquissés mais désactivés** sous `optional/` — ils
n'entrent que le jour où la persistance / le multi-répliques deviennent nécessaires (ce qui
suppose aussi de câbler l'app dessus, hors de cette passe infra).

```bash
kubectl kustomize infra/k8s/optional   # aperçu
kubectl apply -k infra/k8s/optional     # activer (plus tard)
```

### Un seul point d'entrée (Ingress)

`http://localhost/` sert le front ; `http://localhost/api/*` route vers l'API, le préfixe
`/api` étant **retiré** par le `rewrite-target` nginx (le backend expose `/health`, `/game`,
`/market`… sans préfixe). Annotations SSE (`proxy-buffering: off`, timeouts longs) parce
qu'un round de négociation dure ~1 min en streaming.

### Secrets

`secret.example.yaml` est un **template** (`CHANGE_ME`), **hors** de la base kustomize : en
mode SQLite aucun secret n'est requis, et le Deployment API référence le Secret en
`optional: true`. Pour brancher Supabase : `cp secret.example.yaml secret.yaml` (git-ignoré),
remplir, `kubectl apply -f`.

## Validation faite (sans cluster ni Docker)

Sur ce poste : `kind` absent, daemon Docker éteint → **aucun cluster ne peut booter ici**
(conforme au cadrage « esquisse »). Ce qui a été **constaté vert**, purement client-side :

```bash
kubectl kustomize infra/k8s            # la base se compile
kubectl kustomize infra/k8s/optional   # l'overlay futur se compile
```

> **Note outillage :** `kubectl apply --dry-run=client` de la v1.34 exige la *discovery*
> auprès d'un API server (RESTMapper) et ne valide donc **pas** entièrement hors-ligne — la
> vraie validation client-side disponible sans cluster est `kubectl kustomize` (build +
> parse YAML + composition kustomize). La validation contre le schéma OpenAPI complet se
> fera au premier `kubectl apply -k` sur un cluster réel (ou avec `kubeconform`, non installé
> ici). Tous les manifests parsent par ailleurs sans erreur.

## Ce qu'une VRAIE mise en prod ajouterait (hors esquisse)

Pour cadrer les attentes — **volontairement absent** de ce squelette :

- **Images** : `output: "standalone"` côté Next (image bien plus légère), scan de vulnérabilités,
  tags versionnés + registry (pas `:dev` + `kind load`).
- **Secrets** : gestionnaire externe (Sealed Secrets, Vault, cloud KMS), rotation — jamais
  de Secret en clair dans le repo.
- **Résilience** : `replicas > 1` derrière un store partagé (Postgres/Redis actifs),
  PodDisruptionBudget, anti-affinité, HPA (autoscaling fin sur CPU/latence).
- **Réseau/sécu** : TLS réel (cert-manager + Let's Encrypt), NetworkPolicies, RBAC serré,
  `securityContext` durci (readOnlyRootFilesystem, drop capabilities).
- **Persistance** : StorageClass + PVC pour Postgres, sauvegardes/restaurations testées.
- **Observabilité** : Prometheus/Grafana, logs centralisés, traces (OpenTelemetry), alerting.
- **GPU** : NVIDIA device-plugin / GPU Operator pour l'inférence in-cluster (le vrai sujet P7).
- **Livraison** : CI/CD (build+push+deploy), Helm ou overlays kustomize par environnement,
  stratégie de rollout (canary/blue-green).
```
