# \# Analyse Sociodémographique des Étudiants Data — OpenClassrooms

# 

### \*\*Auteur\*\* : Sabah Rizki — Data Analyst

#### \*\*Période analysée\*\* : 2022 – 2025

#### \*\*Outils\*\* : DBT Cloud · Snowflake · Python · Données INSEE

# 

##### \---

##### 

##### \## Contexte

# 

OpenClassrooms souhaite mieux comprendre l'évolution du profil sociodémographique de ses étudiants inscrits aux parcours Data sur 4 ans, afin d'objectiver plusieurs tendances (répartition par âge, genre, région) et d'alimenter les réflexions stratégiques sur l'accessibilité et l'égalité des chances.



Ce projet analyse \*\*4 647 étudiants\*\* entre 2022 et 2025, enrichi par \*\*3 sources de données publiques INSEE\*\* pour contextualiser les résultats à l'échelle nationale.



\---

# 

##### \## Architecture du pipeline

##### 

##### ```

SOURCES (Snowflake — schéma RAW)

│

├── STUDENTS\_RAW          ← 4 647 étudiants OC (CSV importé)

├── INSEE\_POPULATION\_AGE  ← Taux d'activité par âge (INSEE 2022)

├── INSEE\_FEMMES\_NUMERIQUE← Part des femmes dans le numérique (INSEE 2023)

└── INSEE\_EMPLOI\_REGION   ← Emploi par région (INSEE fin 2022)

&#x20;        │

&#x20;        ▼

\[STAGING] stg\_students.sql

&#x20;  → Nettoyage des valeurs manquantes (coalesce GENDER → 'Non renseigné')

&#x20;  → Filtrage sur la période 2022–2025

&#x20;  → Calcul de l'ancienneté (YEARS\_SINCE\_START)

&#x20;        │

&#x20;        ▼

\[MARTS]

├── mart\_age.sql              ← Agrégation par tranche d'âge × année

├── mart\_genre.sql            ← Agrégation par genre × année

├── mart\_region.sql           ← Agrégation par région × année

└── mart\_comparaison\_insee.sql← Jointure OC ↔ INSEE + calcul des écarts

&#x20;        │

&#x20;        ▼

\[EXPORT]

└── CSV final enrichi (862 lignes — RGPD conforme)

```



\\---



##### \\## Structure des fichiers



```
---

models/

├── staging/

│   ├── sources.yml           ← Déclaration des 4 sources Snowflake

│   ├── stg\_students.sql      ← Modèle de nettoyage (matérialisé en vue)

│   └── schema.yml            ← Définition des 5 tests qualité

└── marts/

&#x20;   ├── mart\_age.sql          ← Table analytique par tranche d'âge

&#x20;   ├── mart\_genre.sql        ← Table analytique par genre

&#x20;   ├── mart\_region.sql       ← Table analytique par région

&#x20;   └── mart\_comparaison\_insee.sql ← Comparaison OC vs INSEE

dbt\_project.yml               ← Configuration globale du projet

README.md                     ← Ce fichier

```



\\---



##### \\## Règles de nettoyage appliquées



| Colonne | Problème détecté | Règle appliquée |

|---|---|---|

| `GENDER` | 1 246 valeurs NULL (26.8%) | `coalesce(GENDER, 'Non renseigné')` |

| `YEAR\\\_PATH\\\_STARTED` | Hors périmètre possible | `WHERE YEAR\\\_PATH\\\_STARTED BETWEEN 2022 AND 2025` |

| `YEARS\\\_SINCE\\\_START` | Colonne absente | Calcul : `2025 - YEAR\\\_PATH\\\_STARTED` |



\\---



##### \\## Tests de qualité



| Colonne testée | Test | Résultat | Durée |

|---|---|---|---|

| `USER\\\_ID` | `not\\\_null` | ✅ Pass | 1.31s |

| `YEAR\\\_PATH\\\_STARTED` | `not\\\_null` | ✅ Pass | 1.31s |

| `REGION` | `not\\\_null` | ✅ Pass | 1.37s |

| `GENDER` | `not\\\_null` | ✅ Pass | 1.44s |

| `AGE\\\_GROUP` | `not\\\_null` | ✅ Pass | 1.30s |



\*\*\\\*\\\*5/5 tests passés — 0 erreur — 0 avertissement\\\*\\\*\*\*



> Le test `not\\\_null` sur `GENDER` valide que la règle `coalesce()` a bien remplacé toutes les valeurs NULL.



\\---



##### \\## Conformité RGPD



| Principe | Application dans ce projet |

|---|---|

| \\\*\\\*Minimisation\\\*\\\* | Seules les variables utiles à l'analyse sont conservées. `PATH\\\_CATEGORY\\\_NAME` exclue du CSV final. |

| \\\*\\\*Pseudonymisation\\\*\\\* | `USER\\\_ID` conservé uniquement en staging pour les jointures internes. Exclu du CSV final. |

| \\\*\\\*Agrégation\\\*\\\* | Le CSV final contient uniquement des `COUNT(\\\*)` par groupe. Aucune donnée individuelle exposée. |

| \\\*\\\*Données publiques\\\*\\\* | Les 3 sources INSEE sont librement accessibles sur insee.fr. Aucune donnée personnelle. |



\\---



##### \\## Paramètres de connexion Snowflake



| Paramètre | Valeur |

|---|---|

| Account | `GFIQOMI-FB14065` |

| Database | `OPENCLASSROOMS\\\_DB` |

| Schema source | `RAW` |

| Schema dev DBT | `DEV` |

| Warehouse | `DBT\\\_WH` (X-Small, auto-suspend 60s) |

| Username | `SABAHRIZKI` |

| Version DBT | Fusion Stable |



\\---



##### \\## Commandes pour reproduire le pipeline



```bash

\\# 1. Vérifier la connexion à Snowflake

dbt debug



\\# 2. Exécuter tous les modèles

dbt run



\\# 3. Lancer tous les tests qualité

dbt test



\\# 4. Tout en une commande (recommandé)

dbt build

```



\---



##### \## Sources de données



###### \### Données internes OC

\- \*\*Fichier\*\* : `DATASET\\\_MAJ\\\_P8\\\_DA\\\_DATA.csv`

\- \*\*Contenu\*\* : 4 647 étudiants inscrits aux parcours Data

\- \*\*Colonnes\*\* : USER\_ID, PATH\_CATEGORY\_NAME, AGE\_GROUP, GENDER, REGION, YEAR\_PATH\_STARTED

\- \*\*Période\*\* : 2022 à 2025



###### \### Données externes INSEE

| Table | Source | Contenu | Lignes |

|---|---|---|---|

| `INSEE\\\_POPULATION\\\_AGE` | INSEE Enquête Emploi 2022 | Taux d'activité par tranche d'âge | 9 |

| `INSEE\\\_FEMMES\\\_NUMERIQUE` | INSEE Enquêtes Emploi 2021-2023 | Part des femmes dans le numérique | 8 |

| `INSEE\\\_EMPLOI\\\_REGION` | INSEE Estimations d'emploi fin 2022 | Emploi et population par région | 13 |



\---



##### \## Principaux résultats



###### \### Évolution globale

| Année | Étudiants | Évolution |

|---|---|---|

| 2022 | 1 696 | — (référence) |

| 2023 | 1 150 | -32% |

| 2024 | 850 | -26% (creux) |

| 2025 | 951 | +12% (reprise) |



###### \### Âge — Rajeunissement progressif

\- \*\*30-34 ans\*\* : tranche dominante chaque année

\- \*\*20-24 ans\*\* : ×4 en 4 ans (21 → 81 étudiants, \*\*+286%\*\*)

\- \*\*45 ans et plus\*\* : -58% (361 → 153 étudiants)



###### \### Genre — Féminisation progressive

\- \*\*2022\*\* : 18% de femmes → \*\*2025\*\* : 31% de femmes

\- Dépasse la \*\*moyenne INSEE du secteur numérique (24%)\*\*

\- Taux "Non renseigné" : 42% → 7% (amélioration de la fiabilité)



###### \### Région — Comparaison INSEE

| Région | % Étudiants OC | % Emploi France (INSEE) | Écart |

|---|---|---|---|

| Île-de-France | 41.1% | 23.0% | \*\*+18.1 pts\*\* |

| Nouvelle-Aquitaine | 5.4% | 8.6% | -3.2 pts |

| Pays de la Loire | 2.9% | 5.7% | -2.8 pts |

| Auvergne-Rhône-Alpes | 9.8% | 12.3% | -2.5 pts |

| DROM | 1.7% | 3.0% | -1.3 pts |



\---



##### \## Livrables



| # | Fichier | Description |

|---|---|---|

| 1 | `Rizki\\\_Sabah\\\_1\\\_fichier\\\_052025.csv` | CSV final enrichi (862 lignes, données OC + INSEE) |

| 2 | `Rizki\\\_Sabah\\\_2\\\_workflow\\\_052025.zip` | Workflow DBT complet (modèles, tests, documentation) |

| 3 | `analyse\\\_sociodemographique\\\_OC\\\_v4.pptx` | Présentation 15 slides avec captures d'écran |



\---



\*Projet réalisé dans le cadre du parcours Data Analyst — OpenClassrooms — Mai 2025\*

