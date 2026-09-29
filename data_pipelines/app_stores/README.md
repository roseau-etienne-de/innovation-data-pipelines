# app_stores
## description
Récupération des reviews (feedbacks) user depuis les app Android et IOS via call API. Merge des données et upload dans une table BQ commune. 
```shell
pipeline : app_stores
┌───────────────────────────────┐    ┌────────────────────────────────┐
│job (python) : 01_e_feedbacks  │ ─▶ │job (dbt) : 02_traitement       │
│-------------------------------│    │--------------------------------│
│reports : - e_feedbacks_android│    │model : - t_feedbacks│
│          - e_feedbacks_ios    │    │                                │
└───────────────────────────────┘    └────────────────────────────────┘
```

## fonction
Le but est de centraliser ces données dans big query pour exploitation et analyse.
## fréquence
Les calls sont exécutés une fois par jour à 6AM. Ils prennent les données de la veille uniquement, à partir de minuit : 00:00:00.<br>
Il est possible de lancer des rattrapages *(voir __ratrapages historiques__)*.
## responsable
[etienne.roseau@converteo.com](etienne.roseau@converteo.com)
## destination
Les données reviews Android sont intégrées à la table `app_stores.e_android`.
Les données reviews IOS sont intégrées à la table `app_stores.e_app_stores_feedbacks_ios_api`.
## ratrapages historiques
Un rattrapage peut être lancé localement en modifiant les parametres `start_date` et `end_date` de la commande d'execution.<br>
Exemple :<br>
`python app.py --pipeline app_stores --report e_feedbacks_ios --start_date 20200101 --end_date 20271201`
L'heure des parametres date est minuit 00:00:00 par défaut.
## particularité
Il est important de distinguer
- le Service Account de la VM `project_number-compute@etc.` (utilisé ici pour l'accès à l'API Android),
- du Service Account par défaut de l'environnement : `acces-bq-gs@<project_id>.iam.gserviceaccount.com`.