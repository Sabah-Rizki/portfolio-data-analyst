# Guide de prise en main — Pipeline d'analyse sociodémographique sur dbt + Snowflake

Ce guide vous accompagne **pas à pas, de zéro**, pour construire le pipeline qui analyse
le profil des étudiants Data d'OpenClassrooms (2022-2025) et le compare aux références
nationales de l'INSEE. Aucune connaissance préalable de dbt ou Snowflake n'est requise.

À la fin, vous aurez : un entrepôt de données dans Snowflake, un projet dbt qui nettoie,
transforme et teste les données, et un fichier CSV final enrichi prêt à analyser.

---

## Ce dont vous avez besoin avant de commencer

- Les 5 fichiers de données :
  - le dataset des étudiants (`DATASET ... DATA.csv`),
  - `insee_emploi_region.csv`,
  - `insee_femmes_numerique.csv`,
  - `insee_population_active_age.csv`.
- Une adresse e-mail (pour créer les comptes gratuits Snowflake et dbt Cloud).
- Un navigateur web. Tout se fait en ligne, rien à installer.

**Vue d'ensemble en 5 phases :**

1. Snowflake — créer l'entrepôt et y charger les données brutes.
2. dbt Cloud — créer le projet et le connecter à Snowflake.
3. Écrire les modèles — nettoyer et transformer les données.
4. Exécuter et tester le pipeline.
5. Exporter le fichier final.

---

## Phase 1 — Snowflake : créer l'entrepôt de données

Snowflake est une base de données dans le cloud. C'est là que vivront vos données.

### 1.1 Créer votre compte
1. Allez sur **signup.snowflake.com**.
2. Renseignez vos informations, choisissez l'édition **Standard**, le fournisseur **AWS**
   et la région **Europe (Paris)**.
3. Validez votre compte via le lien reçu par e-mail, puis créez votre mot de passe.

> L'essai gratuit offre 30 jours et 400 crédits — largement suffisant pour ce projet.

### 1.2 Créer la base, le schéma et le warehouse
Ouvrez un **Worksheet** (feuille SQL) et exécutez :

```sql
CREATE DATABASE IF NOT EXISTS OPENCLASSROOMS_DB;
CREATE SCHEMA  IF NOT EXISTS OPENCLASSROOMS_DB.RAW;
CREATE WAREHOUSE IF NOT EXISTS DBT_WH
    WAREHOUSE_SIZE = 'X-SMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;

USE DATABASE OPENCLASSROOMS_DB;
USE SCHEMA RAW;
```

- **Database** = le grand classeur (`OPENCLASSROOMS_DB`).
- **Schéma `RAW`** = le tiroir des données brutes.
- **Warehouse** = le moteur de calcul. `X-SMALL` suffit ; `AUTO_SUSPEND = 60` l'éteint
  après 1 minute d'inactivité pour économiser les crédits.

### 1.3 Créer les 4 tables
Toujours dans le Worksheet, créez les tables qui accueilleront les CSV :

```sql
CREATE OR REPLACE TABLE STUDENTS_RAW (
    USER_ID            VARCHAR,
    PATH_CATEGORY_NAME VARCHAR,
    AGE_GROUP          VARCHAR,
    GENDER             VARCHAR,
    REGION             VARCHAR,
    YEAR_PATH_STARTED  INTEGER
);

CREATE OR REPLACE TABLE INSEE_EMPLOI_REGION (
    SOURCE VARCHAR, ANNEE INTEGER, REGION VARCHAR,
    EMPLOI_MILLIERS NUMBER, PART_EMPLOI_NATIONAL_PCT FLOAT,
    POPULATION_MILLIERS NUMBER, PART_POP_NATIONALE_PCT FLOAT
);

CREATE OR REPLACE TABLE INSEE_FEMMES_NUMERIQUE (
    SOURCE VARCHAR, ANNEE INTEGER, INDICATEUR VARCHAR,
    VALEUR_PCT FLOAT, NOTE VARCHAR
);

CREATE OR REPLACE TABLE INSEE_POPULATION_AGE (
    SOURCE VARCHAR, ANNEE INTEGER, TRANCHE_AGE VARCHAR,
    TAUX_ACTIVITE_PCT FLOAT, POP_ACTIVE_MILLIERS NUMBER
);
```

### 1.4 Charger les CSV
Pour chaque table : dans l'explorateur de gauche, faites un clic droit sur la table puis
**Load Data**, sélectionnez le fichier CSV correspondant, vérifiez le mapping des colonnes,
et cliquez sur **Load**.

| Table | Fichier |
|---|---|
| STUDENTS_RAW | DATASET ... DATA.csv |
| INSEE_EMPLOI_REGION | insee_emploi_region.csv |
| INSEE_FEMMES_NUMERIQUE | insee_femmes_numerique.csv |
| INSEE_POPULATION_AGE | insee_population_active_age.csv |

### 1.5 Vérifier
```sql
SELECT count(*) FROM OPENCLASSROOMS_DB.RAW.STUDENTS_RAW;
```
Vous devez obtenir **4647**. Snowflake est prêt.

---

## Phase 2 — dbt Cloud : créer et connecter le projet

dbt est l'outil qui transforme les données dans Snowflake. Il ne stocke rien lui-même :
il lit les tables, applique vos règles en SQL, et réécrit les résultats dans Snowflake.

### 2.1 Créer votre compte
1. Allez sur **cloud.getdbt.com/signup**.
2. Choisissez le plan **Developer** (gratuit), confirmez votre e-mail.
3. Nommez le projet `openclassrooms_sociodemographique`.

### 2.2 Connecter dbt à Snowflake
Dans la configuration de la connexion, choisissez **Snowflake** et renseignez :
- **Account** : votre identifiant de compte Snowflake,
- **Database** : `OPENCLASSROOMS_DB`,
- **Warehouse** : `DBT_WH`,
- vos **identifiants** Snowflake.

Cliquez sur **Test Connection** : le message **COMPLETE** confirme que tout communique.

### 2.3 Initialiser le projet
Cliquez sur **Initialize dbt project** : dbt crée automatiquement les dossiers de base
(`models/`, `analyses/`, `tests/`, `seeds/`, `macros/`, `snapshots/`).

Vérifiez le fichier **dbt_project.yml** : les modèles de staging sont matérialisés en
**vues**, les marts en **tables**.

```yaml
models:
  openclassrooms_sociodemographique:
    staging:
      +materialized: view
    marts:
      +materialized: table
```

> Une **vue** se recalcule à chaque consultation (légère) ; une **table** est stockée
> (plus rapide à interroger). On réserve les tables aux résultats finaux.

---

## Phase 3 — Écrire les modèles

Organisez vos fichiers en deux dossiers : `models/staging/` (nettoyage) et
`models/marts/` (agrégations).

### 3.1 Déclarer les sources — `models/staging/sources.yml`
Ce fichier indique à dbt où trouver les tables brutes dans Snowflake.

```yaml
version: 2

sources:
  - name: raw
    database: OPENCLASSROOMS_DB
    schema: RAW
    tables:
      - name: STUDENTS_RAW
        description: "Données brutes des étudiants parcours Data"
        columns:
          - name: USER_ID
            description: "Identifiant unique de l'étudiant"
          - name: PATH_CATEGORY_NAME
            description: "Catégorie du parcours"
          - name: AGE_GROUP
            description: "Tranche d'âge"
          - name: GENDER
            description: "Genre F/M/null"
          - name: REGION
            description: "Région française"
          - name: YEAR_PATH_STARTED
            description: "Année de début du parcours"

      - name: INSEE_POPULATION_AGE
        description: "Population active par tranche d'âge (INSEE 2022)"
        columns:
          - name: ANNEE
            description: "Année de mesure"
          - name: TRANCHE_AGE
            description: "Tranche d'âge"
          - name: TAUX_ACTIVITE_PCT
            description: "Taux d'activité en %"
          - name: POP_ACTIVE_MILLIERS
            description: "Population active en milliers"

      - name: INSEE_FEMMES_NUMERIQUE
        description: "Part des femmes dans le numérique (INSEE 2021-2023)"
        columns:
          - name: INDICATEUR
            description: "Nom de l'indicateur"
          - name: VALEUR_PCT
            description: "Valeur en %"
          - name: ANNEE
            description: "Année de mesure"

      - name: INSEE_EMPLOI_REGION
        description: "Emploi par région (INSEE fin 2022)"
        columns:
          - name: ANNEE
            description: "Année de mesure"
          - name: REGION
            description: "Région française"
          - name: EMPLOI_MILLIERS
            description: "Nombre d'emplois en milliers"
          - name: PART_EMPLOI_NATIONAL_PCT
            description: "Part de l'emploi national en %"
          - name: PART_POP_NATIONALE_PCT
            description: "Part de la population nationale en %"
```

> On référence ensuite une source par `{{ source('raw', 'STUDENTS_RAW') }}`, et dbt la
> traduit en `OPENCLASSROOMS_DB.RAW.STUDENTS_RAW`.

### 3.2 Nettoyer les données — `models/staging/stg_students.sql`
Première couche de transformation : on traite les valeurs manquantes et on cadre la période.

```sql
with source as (
    select * from {{ source('raw', 'STUDENTS_RAW') }}
),

cleaned as (
    select
        USER_ID,
        PATH_CATEGORY_NAME,
        AGE_GROUP,
        coalesce(GENDER, 'Non renseigné') as GENDER,
        REGION,
        YEAR_PATH_STARTED,
        2025 - YEAR_PATH_STARTED as YEARS_SINCE_START
    from source
    where YEAR_PATH_STARTED between 2022 and 2025
)

select * from cleaned
```

- `coalesce(GENDER, 'Non renseigné')` remplace les genres vides par une valeur explicite.
- Le `where` ne garde que la période 2022-2025.
- `YEARS_SINCE_START` calcule l'ancienneté de l'étudiant.

### 3.3 Agréger par dimension — les 3 marts
Une couche par axe d'analyse. On part toujours du staging via `{{ ref('stg_students') }}`.

`models/marts/mart_age.sql`
```sql
with students as (
    select * from {{ ref('stg_students') }}
),
aggregated as (
    select YEAR_PATH_STARTED, AGE_GROUP, count(*) as nb_etudiants
    from students
    group by YEAR_PATH_STARTED, AGE_GROUP
)
select * from aggregated
order by YEAR_PATH_STARTED, AGE_GROUP
```

`models/marts/mart_genre.sql` (même principe, par genre)
```sql
with students as (
    select * from {{ ref('stg_students') }}
),
aggregated as (
    select YEAR_PATH_STARTED, GENDER, count(*) as nb_etudiants
    from students
    group by YEAR_PATH_STARTED, GENDER
)
select * from aggregated
order by YEAR_PATH_STARTED, GENDER
```

`models/marts/mart_region.sql` (même principe, par région)
```sql
with students as (
    select * from {{ ref('stg_students') }}
),
aggregated as (
    select YEAR_PATH_STARTED, REGION, count(*) as nb_etudiants
    from students
    group by YEAR_PATH_STARTED, REGION
)
select * from aggregated
order by YEAR_PATH_STARTED, REGION
```

> `source()` pointe une table brute ; `ref()` pointe un autre modèle dbt. Dans les marts,
> on utilise `ref('stg_students')` pour partir des données **déjà nettoyées**.

### 3.4 Comparer à l'INSEE — `models/marts/mart_comparaison_insee.sql`
On rapproche la répartition régionale des étudiants 2025 de leur poids dans l'emploi national.

```sql
with insee_region as (
    select
        REGION,
        PART_EMPLOI_NATIONAL_PCT as pct_emploi_france,
        PART_POP_NATIONALE_PCT as pct_pop_france
    from {{ source('raw', 'INSEE_EMPLOI_REGION') }}
    where ANNEE = 2022
),

etudiants_region as (
    select
        REGION,
        sum(NB_ETUDIANTS) as nb_etudiants_oc,
        round(sum(NB_ETUDIANTS) * 100.0 / sum(sum(NB_ETUDIANTS)) over (), 1) as pct_oc
    from {{ ref('mart_region') }}
    where YEAR_PATH_STARTED = 2025
    group by REGION
),

comparaison_region as (
    select
        e.REGION,
        e.nb_etudiants_oc,
        e.pct_oc as pct_etudiants_oc,
        i.pct_emploi_france,
        i.pct_pop_france,
        round(e.pct_oc - i.pct_emploi_france, 1) as ecart_vs_emploi_france
    from etudiants_region e
    left join insee_region i
        on upper(replace(replace(e.REGION, '''', ''), ' ', ''))
         = upper(replace(replace(i.REGION, '''', ''), ' ', ''))
)

select * from comparaison_region
order by pct_etudiants_oc desc
```

> **Astuce jointure** : les libellés de région peuvent différer d'une source à l'autre
> (par ex. « Côte d'Azur » vs « Côte d Azur »). On joint donc sur une clé **normalisée**
> (sans espaces ni apostrophes, en majuscules) pour que toutes les régions correspondent.

### 3.5 Ajouter les tests qualité — `models/staging/schema.yml`
On vérifie qu'aucune colonne clé n'est vide.

```yaml
version: 2

models:
  - name: stg_students
    description: "Modèle de staging nettoyé des étudiants Data OpenClassrooms"
    columns:
      - name: USER_ID
        tests: [ not_null ]
      - name: YEAR_PATH_STARTED
        tests: [ not_null ]
      - name: REGION
        tests: [ not_null ]
      - name: AGE_GROUP
        tests: [ not_null ]
      - name: GENDER
        tests: [ not_null ]
```

---

## Phase 4 — Exécuter et tester

Dans la barre de commande dbt :

```
dbt run     # construit les 5 modèles dans le bon ordre
dbt test    # lance les 5 tests not_null
dbt build   # fait les deux d'un coup (recommandé)
```

- `dbt run` détecte automatiquement les dépendances (le staging avant les marts) grâce
  aux `ref()`. Résultat attendu : **5 modèles créés**.
- `dbt test` doit afficher **5 tests PASS, 0 erreur**.
- `dbt build` enchaîne tout : c'est ce qui rend le pipeline **reproductible en une commande**.

---

## Phase 5 — Exporter le fichier final (862 lignes)

La requête d'export vit dans le projet, en `analyses/export_csv_final.sql`. Elle produit
une ligne par (tranche d'âge × genre × région × année), enrichie des références INSEE par
région — sans aucun identifiant individuel (conforme RGPD).

```sql
with etudiants as (
    select AGE_GROUP, GENDER, REGION, YEAR_PATH_STARTED, count(*) as NB_ETUDIANTS
    from {{ ref('stg_students') }}
    group by 1, 2, 3, 4
),
insee_region as (
    select
        upper(replace(replace(REGION, '''', ''), ' ', '')) as region_key,
        PART_EMPLOI_NATIONAL_PCT as pct_emploi_france,
        PART_POP_NATIONALE_PCT   as pct_pop_france
    from {{ source('raw', 'INSEE_EMPLOI_REGION') }}
    where ANNEE = 2022
),
part_oc_region as (
    select REGION, YEAR_PATH_STARTED,
           round(sum(NB_ETUDIANTS) * 100.0
                 / sum(sum(NB_ETUDIANTS)) over (partition by YEAR_PATH_STARTED), 1) as pct_oc_region
    from etudiants group by 1, 2
),
ecart_region as (
    select p.REGION, p.YEAR_PATH_STARTED, i.pct_emploi_france, i.pct_pop_france,
           round(p.pct_oc_region - i.pct_emploi_france, 1) as ecart_vs_emploi_france
    from part_oc_region p
    left join insee_region i
        on upper(replace(replace(p.REGION, '''', ''), ' ', '')) = i.region_key
)
select e.AGE_GROUP, e.GENDER, e.REGION, e.YEAR_PATH_STARTED, e.NB_ETUDIANTS,
       r.pct_emploi_france      as INSEE_PCT_EMPLOI_REGION,
       r.pct_pop_france         as INSEE_PCT_POP_REGION,
       r.ecart_vs_emploi_france as ECART_VS_EMPLOI_FRANCE
from etudiants e
left join ecart_region r
    on e.REGION = r.REGION and e.YEAR_PATH_STARTED = r.YEAR_PATH_STARTED
order by e.YEAR_PATH_STARTED, e.REGION, e.AGE_GROUP, e.GENDER
```

Pour obtenir le CSV :
1. Dans dbt, lancez **`dbt compile`**.
2. Récupérez le SQL compilé dans `target/compiled/.../analyses/export_csv_final.sql`.
3. Collez-le dans un **Worksheet Snowflake**, exécutez, puis cliquez sur **Download** → CSV.

Résultat : **862 lignes**.

---

## Récapitulatif — la checklist

1. Snowflake : compte → DB + schéma + warehouse → 4 tables → charger les CSV → 4647 lignes.
2. dbt Cloud : compte → connecter Snowflake → initialiser le projet.
3. Modèles : `sources.yml`, `stg_students.sql`, `mart_age/genre/region.sql`,
   `mart_comparaison_insee.sql`, `schema.yml`.
4. `dbt build` → 5 modèles + 5 tests au vert.
5. `analyses/export_csv_final.sql` → `dbt compile` → exécuter dans Snowflake → CSV final.

Tout le projet se rejoue ensuite avec une seule commande : **`dbt build`**.
