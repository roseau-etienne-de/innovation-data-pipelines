# 🚀 Innovation Data Pipelines

Application moderne pour l'orchestration et l'exécution de pipelines de données sur GCP. Remplace une architecture monolithique legacy **data-pipelines** par une architecture microservices utilisant **Cloud Run Jobs** et **Cloud Workflows**.

Pipelines de données (ETL/ELT) hébergés sur GCP avec :
- **Python** + **dbt** pour les transformations
- **Cloud Run Jobs** pour l'exécution
- **Cloud Workflows** + **Cloud Scheduler** pour l'orchestration
- Logs centralisés dans **Cloud Logging**

## I. Context legacy

A l'origine, **data-pipelines** un application hébergée sur GCP, dédiée à la récupération et à la transformation de données.<br>
L'execution des pipelines se fait sur sur une VM **compute engine**. Elle est constituée d'une image **Jenkins** et d'une image **Python** qui permettent, respectivement, l'orchestration et l'execution. Les transformations type ELT sont pour la plupart traitées avec **dbt**.<br>
**BigQuery** accueille les données transformées, cleanées et standardisées. L'exploitation se fait via DataStudio (Looker), Gsheet ou Xcel.<br>
Un programme `app.py` est appelé pour chaque job Python. Il dirige le job vers son `runner.py` en fonction des arguments reçus en ligne de commande.<br>

*Exemple de pipeline typique :*<br>
1. (runner.py = job1) Extraction API + upload sur GCS
2. (runner.py = job2) Transformation depuis gcs API + upload sur BigQuery
3. (model dbt = job3) Transformation SQL

### Why `innovation-data-pipelines` ?

L'application legacy **data-pipelines** est un monolithe de part sa disposition (dépendances des `runner.py` au fichier central `app.py`). Cela entraine des problèmes de dépendances qui fragilisent le programme et augmentent les besoins de maintenance.
Jenkins est un outil rigide qui n'est pas dédié à l'orchestration. Il augmente aussi la taille de l'image qui met plus de 30 minutes à se construire. Son interface complique le debugage des pipelines et empeche la récupération des logs<br>
La diversité et le nombre de pipelines (~20) rendent cet ecosysteme instable et fastidieux à maintenir. La VM est sous exploitée, la totalité du compute ne prend qu'1/3 de 24h. *(Pour 3VM exploitées le cout réel devrait etre seulement de ~70€ pour 200€ actuels).*<br>
💡 Pour la même utilisation avec **innovation-data-pipelines**, le CRJ ne représente qu'environ 40€ et Artifact Registry 100€*

Ce projet est très contextuel et ne peut s'appliquer à n'importe quelle organisation. Il s'agit avant tout d'un poc destiné à montrer les avantages d'une architecture micro-services.

La modernisation de l'application a pour but de faciliter le développement collaboratif, l'utilisation des différents pipelines, l'orchestration et le monitoring.

Le principal changement est une architecture orientée microservices. Les pipelines ne sont plus dépendants les uns des autres (legacy = 1 VM, 1 image Jenkins, 1 fichier `app.py`), mais constitués de **Cloud Run Jobs (CRJ)**, orchestrés par **Cloud Workflow**.

### Résumé

| Aspect | Legacy | Innovation |
|--------|--------|-----------|
| Orchestration | Jenkins | Cloud Workflows |
| Exécution | VM unique + Docker | Cloud Run Jobs |
| Temps build image | ~30 min | ~3-5 min |
| Dépendances | Monolithe (app.py central) | Microservices (indépendants) |
| Logs | Dispersés | Cloud Logging centralisé |
| Scaling | Manuel | Automatique (serverless) |


## II. Fonctionnement

### 1. Concepts clés

Cette application exécute des images **python** et **dbt**.
- Les jobs python contiennent un fichier .py
- Les jobs dbt un ou plusieurs models (fichiers .sql)

#### pipeline

Ici, un **pipeline** est un mouvement de données type ETL et/ou ELT. Un pipeline est constitué de **jobs** (CRJ), eux-mêmes constitués de **reports**.
```shell
┌──────────────────────────────────────────────────────────────────┐
│ Pipeline                                                         │
│ ┌───────────────────────────────────┐  ┌───────────────────────┐ │
│ │ Job (CRJ)                         │->│ Job (CRJ)             │ │
│ │ ┌────────┐ ┌────────┐ ┌────────┐  │  │ ┌────────┐ ┌────────┐ │ │
│ │ │ Report │>│ Report │>│ Report │  │  │ │ Report │>│ Report │ │ │
│ │ └────────┘ └────────┘ └────────┘  │  │ └────────┘ └────────┘ │ │
│ └───────────────────────────────────┘  └───────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

#### job

Un **job** est une unité actionnable du pipeline. Chaque job a son image (python ou dbt), hébergée par Artifact Registry et exécutée par CRJ.

#### report

Un report est une partie d'un job. Exemple : si un job va chercher 2 sources de données, un report pourrait être l'extract de la *source 1*, et le 2e l'extract de la *source 2*<br>
Ils peuvent être déclenchés indépendamment pour ajouter en flexibilité (rattrapage, test, analyse ...).<br>
Ils représentent un argument du CRJ.

### 2. Architecture

Les pipelines sont déclenchés par **Cloud Scheduler** et orchestrés par **Cloud Workflow**.<br>
Ils sont une succession de **Cloud Run Jobs**, leurs logs sont disponibles dans **Cloud Logging**.
```shell
┌─────────────────┐        ┌─────────────────┐        ┌───────────────┐
│ Cloud Scheduler |───────▶│                 |        | Cloud Run Job |
└─────────────────┘        │                 │───────▶│ Job1          │        ┌───────────────┐
                           │ Cloud Workflows │───────▶│ Job2          │───────▶│ Cloud Logging |
                           │                 │───────▶│ Job3          │        └───────────────┘
                           │                 │        │ ...           │
                           └─────────────────┘        └───────────────┘
```

### 3. Flexibilité

- Pour un éventuel rattrapage, un job ou même un seul report peut être lancé indépendamment du pipeline, plusieurs méthodes existent :
```shell
# gcloud :
gcloud run jobs execute $(CRJ_NAME) \
	--project=$(PROJECT) \
	--region=$(LOCATION) \
	--args=$"--reports,report_1,report_2"

# makefile (ici, seulement le report e_feedbacks_android est lancé) :
make crj_run \
FILE_PATH="data_pipelines/openweather/02_load" \
ARGS_CRJ="--reports,e_feedbacks_android"

# on peut le déclencher depuis la console également
```
Le workflow contient la liste exhaustive des reports qui composent les jobs à lancer.<br>
Cela peut paraître redondant, mais permet de diminuer l'abstraction, et de comprendre le pipeline à la simple lecture du `workflow.yml`.

## III. Structure du Programme

Voici une vue d'ensemble de la structure du projet :

```
.
├── config_dbt/                     # dbt configuration
│   ├── dbt_project.yml             # Global dbt config
│   ├── Dockerfile.dbt              # Dbt environment image
│   ├── macros/                     # SQL utility functions for labeling, deleting tmp tables
│   │  ...
│   │   └── schema.yml              # Macros description
│   ├── models/                     # Dbt data models (host job models)
│   └── profiles.yml                # Database connection profiles
├── config_python/                  # Python configuration
│   ├── customIO/                   # Connectors for jobs (APIs, databases)
│   │   ├── apis/                   # Third-party API connectors (feedback, Google Sheets)
│   │   │   ├── feedbackAppConn.py  # Feedback app API connection
│   │   │   └── secretManager.py    # Cloud secret management
│   │   └── database/               # BigQuery connectors
│   │       └── bigquery_v2.py      # BigQuery v2 connector
│   ├── Dockerfile.python           # Python environment image
│   └── helper/                     # Global python utilities
│       ├── cloud_logger_manager.py # Cloud logging utilities
│       └── helper.py               # General helper functions
├── data_pipelines/                 # Gathers all the pipelines
│   ├── app_stores/                 # Pipeline
│   │   ├── 01_e_feedbacks/         # Job (python)
│   │   │   ├── job_requirements.txt
│   │   │   └── job.py
│   │   ├── 02_traitement/          # Job (dbt)
│   │   │   └── t_feedbacks.sql
│   │   ├── config_pipeline/        # Pipeline config
│   │   │   ├── config_noprod.json  # Dev config
│   │   │   ├── config_prod.json    # Prd config
│   │   │   ├── sources.yml         # Sources for dbt
│   │   │   └── workflow.yml        # Orchestration infos, contient le cron du Cloud Scheduler
│   │   └── README.md
│   └── openweather/                # Pipeline
│       ├── 01_extract/             # Job (python)
│       │   ├── job_requirements.txt
│       │   └── job.py
│       ├── 02_load/                # Job (python)
│       │   ├── job_requirements.txt
│       │   └── job.py
│       ├── 03_transform/           # Job (dbt)
│       │   ├── dbt_test_1.sql
│       │   └── dbt_test_2.sql
│       ├── config_pipeline/
│       │   ├── config_noprod.json
│       │   ├── config_prod.json
│       │   ├── sources.yml
│       │   └── workflow.yml
│       └── README.md
├── Makefile                        # Project automation commands
├── new_README.md
└── README.md
```

### 1. .github/

Contient les workflows CICD et la [documentation dédiée](.github/workflows/README.md).

### 2. config_dbt/

Ce dossier rassemble les configs globales et les job specs (dossier `models`) après `docker build`. Le dossier `models` sera unique à l'image, il contiendra les models du job correspondant (fichiers `.sql`) ex: `openweather/03_transform/*.sql`.

#### Dockerfile.dbt

- l3 s'assure que l'image Docker est toujours x86_64-compatible, peut importe la machine
- l28 évite de créer 2 couches de fichiers ; une par autorisation -> *(une couche root et l'autre appuser)*

### 3. config_python/

Ce dossier rassemble les connecteurs utiles dans `customIO`, ils sont facultatifs.
Le dossier `helper` est obligatoire, il contient la gestion des logs pour CRJ et le fichier `helper.py` qui permet de lire les paramètres associés à l'exécution (`--env`, `--reports`, etc.)

#### Dockerfile.python

Le dockerfile est divisé en 2 multi-stages (`builder` et `runner`) pour diminuer sa taille finale. On utilise le même digest pour faciliter sa maintenance.
On copie uniquement les requirements dans le stage 2. 
Un `USER appuser` est créée pour éviter les failles de sécurité.
On copie et a ajoute les droits au appuser en même temps pour éviter de dupliquer les couches docker. 

### 4. data_pipelines/

Ce dossier contient le cœur de l'application : les pipelines chargés des mouvements et modifications de données. Chaque **pipeline** est représenté par un dossier, celui-ci contient les **jobs** (python ou dbt). Les jobs sont des dossiers contenant des executables python (job.py) ou dbt (*.sql) rassemblant les **reports**.

- Les dossiers **pipelines** suivent la convention de nommage snake_case `^[a-z_]+$`
- Même chose pour les dossiers **jobs**, avec un suffixe obligatoire (2 chiffres indiquant leur rang) `^\d{2}[a-z_]+$`
  - dbt : Les exécutables **job dbt** sont des fichiers .sql en snake_case. Il peut y en avoir plusieurs par dossier job.
  - python : contient un seul exécutable nommé `job.py`. Le requirements appelé `job-requirements.txt` est facultatif.

### 5. Makefile

Ce fichier est essentiel, il permet de lancer les différentes commandes liées à la **CICD**, il contient également la **configuration** DevOps.

Il permet également de relancer certains jobs ou reports manuellement (backfill, fail, analyse ...)
```sh
make crj_run \
FILE_PATH=data_pipelines/openweather/02_load \
ARGS_CRJ=--reports,e_feedbacks_android,--rattrapage_debut,20260101,--rattrapage_fin,20270101
```
Ainsi que de vérifier la configuration ou se connecter plus rapidement (`make vars`, `make login_gcp`, etc).

## IV. CICD

La CICD est responsable du déploiement, elle est constituée 
- du dossier `.github/workflows`
- du `Makefile`

En fonction du job (python ou dbt), une image est construite puis déployée.
Toute la documentation CICD est disponible [ici](.github/workflows/README.md).

## V. Infrastructure

Le deploiement d'un pipeline passe par les étapes suivantes

### 1. Artifact Registry

2 repos (dev et prd) renseignés dans le [Makefile](Makefile) hébergent les images des **Cloud Run Jobs**.<br>
- Le repo **dev** hébergent jusqu'à 20 images
- Le repo **prd** jusqu'à 5

### 2. Cloud Run Job

Les CRJ sont déployés juste après l'envoie de l'image.

### 3. Cloud Workflows

Un **Cloud Workflows** est déployé pour chaque pipeline, il dépend du fichier de config `workflow.yml`.

### 4. Cloud Sheduler

Il est déployé après le `workflow.yml` et permet de le déclencher. Le **cron** du **Cloud Scheduler** est renseigné en 1ere ligne du fichier `workflow.yml`.
```yml
# cloud_scheduler_cron=0 6 * * *
```

### 5. Récap

1 pipeline =
- min(1) Artifact Registry
- min(1) CRJ
- 1 Cloud Workflows
- 1 Cloud Sheduler

## VI. Prérequis et Configuration

- Python 3.12+
- dbt 1.9+
- Docker
- Google Cloud SDK (gcloud)
- Make

### 1. Local development

- En **python** vous pouvez développer à la racine. Activez bien votre **venv** au préalable.
- Avec **dbt** vous pouvez tester vos models en les copiant (avec les sources.yml si besoin) directement dans le dossier `config_dbt/models`. Attention à bien les supprimer avant de **commit**.
```shell
# Un seul modèle
dbt run --select t_feedbacks NONNNNNN

# Plusieurs modèles spécifiques
dbt run --select t_feedbacks,autre_model

# Tous les modèles d'un job dbt
dbt run --select app_stores
```

> [!WARNING]
> Il est interdit de déployer manuellement en **dev** ou **prd**. Cette action passe obligatoirement par la **CICD**.

## VII. IAM

3 services-comptes (SA) sont au service
- de la CICD
- de l'execution des pipelines
- de l'orchestration

### 1. SA CICD
`sa-ar-innovation-dp-cicd` permet de déployer la CICD.
- Artifact Registry Writer
- Cloud Run Admin
- Cloud Scheduler Admin
- Service Account User sur `sa-crj-innovation-dp-runner` *(pour administrer le SA `sa-ar-innovation-dp-cicd` en tant que runner du Cloud Run Job)*
- Workflows Editor

### 2. SA exécution
`sa-crj-innovation-dp-runner` est responsable de l'exécution du CRJob.
- Artifact Registry Reader
- BigQuery Data Editor
- BigQuery Job User
- Cloud Run Invoker
- Logs Writer
- Secret Manager Secret Accessor
- Storage Bucket Viewer (Beta)
- Storage Object User

### 3. SA orchestration
`sa-wf-innovation-dp-trigger` permet au workflows de déclencher les CRJ.
- Cloud Run Developer
- Workflows Invoker *(permet à Scheduler de trigger le Workflow)*

## VIII. Roadmap & Améliorations futures

### 1. Gestion des resources obsolètes

Si une ressource (un CRJ, ou même tout un pipeline) devient obsolète, il faut la supprimer manuellement : 
- job:
  - supprimer l'image dans AR
  - supprimer le CRJ associé

- orchestration:
  - supprimer le workflow.yml
  - supprimer le scheduler associé

- sur le repo supprimer et modifier les fichiers correspondants

💡 Il faudrait créer un trigger CICD qui supprimerait les ressources GCP en fonction de :
1. l'apparition d'un pipeline dans un folder nommé `archive`
2. la disparition du même job ou pipeline dans le dossier `data_pipelines`

### 2. Déploiement CICD

Le déploiement actuel via Github Action (yaml files) est difficile à lire et à comprendre.

💡 Utiliser **terraform** aiderait grandement, mais c'est un chantier très important qui remet en cause toute la CICD actuelle.

### 3. Développements en équipe

Si 2 développeurs travaillent sur le même job sans se synchroniser, ils risquent de déployer (en dev) leurs propres features sans tenir compte des autres. Si le 2e développeur ne pull pas les modifications du 1er, il risque de downgrade le job du 1er en pushant sa branche. Même si ce cas est rare, il est nécessaire de pull très fréquemment et de communiquer avec les autres développeurs.<br>
Le peer-coding est encouragé si vous travaillez sur le même pipeline.

### 4. Fail de la CD

Actuellement, le fail de la **CD** n'entraîne pas l'arrêt de la **CI**. Autrement dit, si un déploiement échoue alors le code problématique est malgré tout actualisé par le push sur le repo remote.
Le code désormais actualisé (HEAD) ne correspondra pas aux ressources GCP, celles-ci seront affiliées au dernier commit valide.<br>

### 5. Isolation des env

Les environnements dev et prd se côtoient sur le même projet GCP.<br>

💡 Il faudrait **évidemment** isoler ces 2 environnements dans des projets différents et dédiés.

### 6. Gouvernance

💡 Il ne faudrait autoriser que le **SA CICD** à écrire sur le repo `<env>-ar-innovation-data-pipelines`.<br>
De même pour les pipelines, seul le **SA éxecution** devrait pouvoir lancer les CRJ.<br>
Il faudrait 3 projets : 
 - 2 completement isolés (innovation-data-pipelines dev et prod) interdits aux users
 - 1 projet test (users) pour les POCs et les déploiements manuels

### 7. Composition des CRJ

Ici les besoins hardware des pipelines sont assez équivalents, mais cela pourrait changer.

💡 Il faudrait intégrer dans chaque job un paramère récupéré par la CICD permettant de configurer le CRJ lors du déploiement.

### 8. Test des fichiers avant déploiement

💡 Les jobs python et dbt devraient etre testés lors de la CI. La constitutions des différents dossiers (pipelines/, jobs/) et fichiers devraient également etre verifiée.

- Ajouter un fichier `.pre-commit-config.yml`
  - vérifier la constitution du dossier `data_pipelines/pipeline/` :
    - chaque dossier de job = `"^\d\d_[a-z0-9_]+$"`
    - un `README.md`
    - un seul dossier `config_pipeline/` par `pipeline/` qui contient uniquement des fichiers .sql, .yml ou .json
    - vérifier la constitution des dossiers de jobs python et dbt
    - vérifier la syntaxe dans les `workflow.yml`, en particulier la clé `name:` (chemin CRJ long et complexe)
- Versionning : Ajouter un tag à chaque merge sur master
- Pour dbt, vérifier que `models/` est vide (uniquement un `.gitkeep`)
- Le Makefile ne peut être modifié que pour une raison spécifique.

## IX Good to know

### 1. Logs

Vous pouvez visualiser les logs d'une exécution de pipeline en copiant cette requête dans la **console logs gcp** (https://console.cloud.google.com/logs) avec cette requête : 
```shell
resource.type="cloud_run_job"
AND labels."run.googleapis.com/execution_name"=~".+<nom du pipeline>"
```

### 2. Cloud Scheduler location

**cloud scheduler** doit être dans la même localisation que **cloud workflows** pour le trigger.

### 3. Pas de gestion du cache CICD

Plusieurs tests au niveau des images docker on été fait pour conserver le cache lors des builds pendant les Github Action. Les images étant assez réduites la mep d'une conservation de cache faisait perdre un petit peu plus de temps.

### 4. Limite des déploiements Docker en parallèle

Afin d'éviter cette erreur :
```shell
ERROR: (gcloud.auth.docker-helper) There was a problem refreshing your current auth tokens: ('Unable to retrieve Identity Pool subject token', 'upstream connect error or disconnect/reset before headers. reset reason: overflow')
```
Les déploiements d'image **Docker** sur **Artifact Registry** sont limités à 4 en parallèles.

# Annexes

## Liens importants

- Suivi de projet, idées et organisations : [Google Slides](https://docs.google.com/presentation/d/1Be43_RKEN2hPyZq2Tl3qiqVdIGih1rDzq9bx9pEF0ew/edit?slide=id.p#slide=id.p)
- Documentation [Cloud Run Job](https://docs.cloud.google.com/run/docs/create-jobs?hl=fr)
- Documentation [gcloud run jobs execute](https://cloud.google.com/sdk/gcloud/reference/run/jobs/execute)
- Documentation [Docker](https://docs.docker.com/get-started/docker-overview/)

# TODO
strategy:
  max-parallel: 5 # Adjust this number based on your total matrix size
  matrix:
