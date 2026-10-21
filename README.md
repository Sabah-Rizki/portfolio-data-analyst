# Portfolio Data Analyst — Sabah Rizki

**20 ans de supply chain et de logistique, reconvertie en Data Analyst.**
Je transforme des données d'exploitation (stocks, ventes, achats, flux) en décisions chiffrées, vérifiées et compréhensibles par un comité de direction.

Master 2 Supply Chain Internationale (Paris Dauphine-PSL) · Certification HEC Paris · Parcours Data Analyst OpenClassrooms (2025-2026) · Île-de-France

---

## Projets

| # | Projet | Problème métier | Outils | Résultat clé |
|---|---|---|---|---|
| 01 | [Rapport mensuel des ventes e-commerce](01_ecommerce_rapport_ventes_Excel/) | Une boutique a changé d'offre : la transition est-elle réussie ? | Excel, PowerPoint | Taux de conversion passé de 10,2 % à 5,0 % : priorité au tunnel d'achat |
| 02 | [DATAImmo : base de données immobilière](02_dataimmo_base_donnees_SQL/) | Centraliser les ventes immobilières françaises pour les analyser | SQL (SQLite), Power Query, modélisation | Schéma normalisé en 3NF, 4 tables, 12 requêtes d'analyse |
| 03 | [BottleNeck : stocks et ventes d'un caviste](03_bottleneck_analyse_stocks_Python/) | Rapprocher l'ERP et la boutique en ligne pour piloter le stock | Python, pandas | 714 produits rapprochés, CA web de 143 680 € |
| 04 | [Sanitoral : suivi de projets](04_sanitoral_dashboard_PowerBI/) | Visualiser l'avancement, les coûts et les délais d'un portefeuille de projets | Power BI, DAX, Power Query | Tableau de bord avec sécurité par rôle (RLS) et exploration détaillée |
| 05 | [Profils des étudiants Data](05_profils_etudiants_dbt_Snowflake/) | Objectiver l'évolution des profils sur 4 ans, dans le respect du RGPD | dbt, Snowflake, SQL | Pipeline testé (5 modèles, 5 tests), 4 647 étudiants, export agrégé |
| 06 | [Lapage : ventes d'une librairie en ligne](06_lapage_ventes_statistiques_Python/) | Comprendre l'activité et les clients sur deux ans | Python, statistiques | 21,5 % des références font 80 % du CA ; tests du khi-deux, de Spearman et de Kruskal-Wallis |
| 07 | [DWFA : accès à l'eau potable](07_dwfa_eau_potable_PowerBI/) | Aider une ONG à cibler les pays prioritaires | Power BI, conception de tableau de bord | 3 vues (monde, continent, pays), 194 pays, 2000-2017 |
| 08 | [Export international : où vendre ?](08_export_international_clustering_Python/) | Choisir les pays cibles pour exporter des poulets bio | Python, ACP, classification | 164 pays, 4 groupes, 3 marchés recommandés |
| 09 | [Détection de faux billets](09_faux_billets_machine_learning/) | Repérer automatiquement les faux billets | Python, scikit-learn | Régression logistique : 121 faux sur 125 détectés, aucune fausse alerte |
| 10 | [BottleNeck amélioré avec l'IA](10_bottleneck_IA_controles_qualite/) | Fiabiliser les données avec l'IA, de façon critique et mesurée | Python, Pandera, Claude, Gemini | 64 règles de contrôle, 325 anomalies détectées, IA évaluée sur banc de test |
| 11 | [Veille automatisée](11_veille_automatisee/) | Rester à jour sans chercher | Python, Google Alertes, Planificateur Windows | 10 sources lues chaque lundi, journal Excel qualifié |

Les projets 03 et 10 portent sur le même client : le 10 reprend le 03 avec un regard critique, des contrôles automatisés et une IA évaluée.

## Compétences

- **Préparer et fiabiliser les données** : nettoyage, jointures vérifiées, règles de qualité, traçabilité des décisions (projets 03, 05, 06, 10).
- **Analyser** : statistiques descriptives et tests, Pareto et classification ABC, ACP et classification, modèles prédictifs (06, 08, 09).
- **Modéliser et transformer** : bases relationnelles normalisées, pipelines dbt testés (02, 05).
- **Restituer** : tableaux de bord Power BI accessibles, présentations pour un comité de direction (01, 04, 07).
- **Travailler avec l'IA de façon critique** : comparaison d'outils sur critères mesurés, vérification systématique du code produit (10).
- **Respecter le RGPD** : minimisation, pseudonymisation, agrégation des exports (02, 05, 10).
- **Piloter** : Kanban, backlog estimé, jalons, registre des risques (10).

## Veille

Une veille automatisée tourne chaque lundi : alertes Google en flux RSS, versions de Pandera, pandas et Great Expectations sur GitHub, actualités de la CNIL. Le script `veille.py` collecte les nouveautés dans un journal Excel que je qualifie chaque semaine. Détails et mode d'emploi dans [11_veille_automatisee](11_veille_automatisee/).

## À propos des données

Les jeux de données des projets sont fournis par OpenClassrooms ou issus de l'open data. Les entreprises et personnes citées sont fictives. Les données brutes ne sont pas redistribuées dans ce dépôt : les notebooks sont publiés avec leurs résultats, lisibles directement sur GitHub.

## Contact

GitHub : [Sabah-Rizki](https://github.com/Sabah-Rizki)
