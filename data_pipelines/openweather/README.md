# openweather

## Intro
Ce pipeline est l'exemple standard d'une execution sur CRJ.
Il extrait des données de l'api Openweather, les load et les transforme dans BQ.

## Elements
Contient 3 jobs

- **extract** : extrait de la donnée depuis l'API openweather et la load sur GCS.
- **load** : prend la donnée depuis GCS et l'injecte dans BQ.
- **transform** : transforme la donnée BQ avec 2 models dbt.

```shell
pipeline : openweather
┌─────────────────────────┐    ┌──────────────────────┐    ┌─────────────────────────┐
│job (python) : 01_extract│ ─▶ │job (python) : 02_load│ ─▶ │job (dbt) : 03_transform │
│-------------------------│    │----------------------│    │-------------------------│
│report : - extract       │    │report : - load       │    │models : - dbt_test1     │
│                         │    │                      │    │         - dbt_test2     │
└─────────────────────────┘    └──────────────────────┘    └─────────────────────────┘
```