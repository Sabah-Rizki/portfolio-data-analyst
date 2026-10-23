-- ============================================================================
-- setup_snowflake.sql -- À exécuter dans un Worksheet Snowflake (compte neuf).
-- Recrée la base, le schéma RAW, le warehouse et les 4 tables sources.
-- Ensuite : charger chaque CSV dans sa table via "Load Data" (interface Snowflake).
-- ============================================================================

CREATE DATABASE IF NOT EXISTS OPENCLASSROOMS_DB;
CREATE SCHEMA  IF NOT EXISTS OPENCLASSROOMS_DB.RAW;
CREATE WAREHOUSE IF NOT EXISTS DBT_WH
    WAREHOUSE_SIZE = 'X-SMALL' AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;

USE DATABASE OPENCLASSROOMS_DB;
USE SCHEMA RAW;

-- Étudiants (fichier DATASET ... DATA.csv)
CREATE OR REPLACE TABLE STUDENTS_RAW (
    USER_ID            VARCHAR,
    PATH_CATEGORY_NAME VARCHAR,
    AGE_GROUP          VARCHAR,
    GENDER             VARCHAR,
    REGION             VARCHAR,
    YEAR_PATH_STARTED  INTEGER
);

-- INSEE emploi par région (insee_emploi_region.csv)
CREATE OR REPLACE TABLE INSEE_EMPLOI_REGION (
    SOURCE                   VARCHAR,
    ANNEE                    INTEGER,
    REGION                   VARCHAR,
    EMPLOI_MILLIERS          NUMBER,
    PART_EMPLOI_NATIONAL_PCT FLOAT,
    POPULATION_MILLIERS      NUMBER,
    PART_POP_NATIONALE_PCT   FLOAT
);

-- INSEE femmes numérique (insee_femmes_numerique.csv)
CREATE OR REPLACE TABLE INSEE_FEMMES_NUMERIQUE (
    SOURCE     VARCHAR,
    ANNEE      INTEGER,
    INDICATEUR VARCHAR,
    VALEUR_PCT FLOAT,
    NOTE       VARCHAR
);

-- INSEE population active par âge (insee_population_active_age.csv)
CREATE OR REPLACE TABLE INSEE_POPULATION_AGE (
    SOURCE              VARCHAR,
    ANNEE               INTEGER,
    TRANCHE_AGE         VARCHAR,
    TAUX_ACTIVITE_PCT   FLOAT,
    POP_ACTIVE_MILLIERS NUMBER
);

-- Contrôle après chargement (doit afficher 4647) :
-- SELECT count(*) FROM OPENCLASSROOMS_DB.RAW.STUDENTS_RAW;
