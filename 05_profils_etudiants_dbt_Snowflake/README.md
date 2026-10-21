# 05 · Évolution des profils des étudiants Data (dbt + Snowflake)

**Contexte.** OpenClassrooms veut objectiver l'évolution du profil de ses étudiants Data entre 2022 et 2025 : âge, genre, région.

**Ma mission.** Construire un pipeline de transformation fiable et conforme au RGPD, puis comparer les profils aux données publiques de l'INSEE.

**Outils.** Snowflake (entrepôt), dbt (transformations et tests), SQL.

## Démarche

1. Chargement dans Snowflake des 4 647 inscriptions et de 3 tables INSEE.
2. Pipeline dbt : 1 modèle de préparation (`stg_students`), 3 tables d'agrégats (âge, genre, région), 1 comparaison avec l'INSEE.
3. Tests automatiques : 5 tests de non-nullité, tous passés.
4. **RGPD** : minimisation des variables, identifiant pseudonymisé et exclu de l'export, export uniquement agrégé (862 lignes).

## Résultats

- Inscriptions : 1 696 en 2022, 850 en 2024, puis reprise à 951 en 2025.
- Rajeunissement : les 20-24 ans passent de 21 à 81 inscrits.
- Part des femmes : de 18 % à 31 %.
- L'Île-de-France est sur-représentée de 18 points par rapport à l'emploi national.

## Fichiers

- [dbt_project/](dbt_project/) : le projet dbt complet et commenté (modèles, sources, tests).
- [setup_snowflake.sql](setup_snowflake.sql) : création de la base, du schéma et des tables.
- [Guide_Utilisateur_dbt_Snowflake.md](Guide_Utilisateur_dbt_Snowflake.md) : mode d'emploi pas à pas.
- [export_agrege_insee.csv](export_agrege_insee.csv) : l'export final, agrégé et sans donnée individuelle.
- [presentation.pdf](presentation.pdf) : la restitution.
