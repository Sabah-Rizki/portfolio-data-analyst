# Portfolio Data Analyst — Sabah Rizki

**20 ans de supply chain et de logistique, reconvertie en Data Analyst.**
Je transforme des données d'exploitation (stocks, ventes, achats, flux) en décisions chiffrées, vérifiées et compréhensibles par un comité de direction.

Master 2 Supply Chain Internationale (Paris Dauphine-PSL) · Certification HEC Paris · Parcours Data Analyst OpenClassrooms (2025-2026) · Île-de-France

---

## Projets par outil

### 1. Excel — [voir le dossier](1_Excel/)

| Projet | Problème métier | Résultat clé |
|---|---|---|
| [Rapport mensuel des ventes e-commerce](1_Excel/ecommerce_rapport_ventes/) | Une boutique a changé d'offre : la transition est-elle réussie ? | Taux de conversion passé de 10,2 % à 5,0 % : priorité au tunnel d'achat |

### 2. SQL et dbt — [voir le dossier](2_SQL_dbt/)

| Projet | Problème métier | Outils | Résultat clé |
|---|---|---|---|
| [Assurance habitation : requêtes SQL](2_SQL_dbt/assurance_habitation_requetes/) | Analyser un portefeuille de contrats par territoire | MySQL, SQL Power Architect | Base de 2 tables (30 335 contrats, 38 916 communes), 12 requêtes |
| [DATAImmo : base de données immobilière](2_SQL_dbt/dataimmo_base_donnees/) | Centraliser les ventes immobilières françaises pour les analyser | SQLite, Power Query, modélisation | Schéma normalisé en 3NF, 4 tables, 12 requêtes d'analyse |
| [Profils des étudiants Data](2_SQL_dbt/profils_etudiants_dbt_snowflake/) | Objectiver l'évolution des profils sur 4 ans, dans le respect du RGPD | dbt, Snowflake | Pipeline testé (5 modèles, 5 tests), 4 647 étudiants, export agrégé |

### 3. Python — [voir le dossier](3_Python/)

| Projet | Problème métier | Outils | Résultat clé |
|---|---|---|---|
| [Santé publique : la sous-nutrition dans le monde](3_Python/sante_publique_FAO/) | Comprendre pourquoi la faim persiste alors que la production suffit | pandas, matplotlib | 535,7 millions de personnes sous-alimentées en 2017 ; capacité de 1,23 fois la population |
| [BottleNeck : stocks et ventes d'un caviste](3_Python/bottleneck_analyse_stocks/) | Rapprocher l'ERP et la boutique en ligne pour piloter le stock | pandas | 714 produits rapprochés, CA de 143 680 € |
| [Lapage : ventes d'une librairie en ligne](3_Python/lapage_ventes_statistiques/) | Comprendre l'activité et les clients sur deux ans | pandas, SciPy | 21,5 % des références font 80 % du CA ; tests du khi-deux, de Spearman et de Kruskal-Wallis |
| [Export international : où vendre ?](3_Python/export_international_clustering/) | Choisir les pays cibles pour exporter des poulets bio | ACP, classification | 164 pays, 4 groupes, 3 marchés recommandés |
| [Détection de faux billets](3_Python/faux_billets_machine_learning/) | Repérer automatiquement les faux billets | scikit-learn | 4 modèles au-delà de 98 % ; régression logistique retenue (99,1 % en validation croisée) |
| [BottleNeck amélioré avec l'IA](3_Python/bottleneck_IA_controles_qualite/) | Fiabiliser les données avec l'IA, de façon critique et mesurée | Pandera, Claude, Gemini | 64 règles de contrôle, 325 anomalies détectées, IA évaluée sur banc de test |

Les deux projets BottleNeck portent sur le même client : le second reprend le premier avec un regard critique, des contrôles automatisés et une IA évaluée.

### 4. Power BI — [voir le dossier](4_Power_BI/)

| Projet | Problème métier | Résultat clé |
|---|---|---|
| [Sanitoral : suivi de projets](4_Power_BI/sanitoral_suivi_projets/) | Visualiser l'avancement, les coûts et les délais d'un portefeuille de projets | Tableau de bord avec sécurité par rôle (RLS) et exploration détaillée |
| [DWFA : accès à l'eau potable](4_Power_BI/dwfa_eau_potable/) | Aider une ONG à cibler les pays prioritaires | 3 vues (monde, continent, pays), 194 pays, 2000-2017 |

### 5. Veille automatisée — [voir le dossier](5_Veille_automatisee/)

Une veille **métier** (marché du vin, vente en ligne, réglementation de la vente d'alcool, gestion des stocks) et **technique** (outils de validation de données, risques de l'IA, CNIL). Chaque lundi, un script Python lit 14 flux (alertes Google en RSS, versions publiées sur GitHub) et ajoute les nouveautés à un journal Excel que je qualifie. Outils : Python, Google Alertes, Planificateur de tâches Windows.

---

## Compétences

- **Préparer et fiabiliser les données** : nettoyage, jointures vérifiées, règles de qualité, traçabilité des décisions.
- **Analyser** : statistiques et tests, Pareto et classification ABC, ACP et classification, modèles prédictifs.
- **Modéliser et transformer** : bases relationnelles normalisées, pipelines dbt testés.
- **Restituer** : tableaux de bord Power BI accessibles, présentations pour un comité de direction.
- **Travailler avec l'IA de façon critique** : comparaison d'outils sur critères mesurés, vérification systématique du code produit.
- **Respecter le RGPD** : minimisation, pseudonymisation, agrégation des exports.
- **Piloter** : Kanban, backlog estimé, jalons, registre des risques.

## À propos des données

Les jeux de données des projets sont fournis par OpenClassrooms ou issus de l'open data. Les entreprises et personnes citées sont fictives. Les données brutes ne sont pas redistribuées dans ce dépôt : les notebooks sont publiés avec leurs résultats, lisibles directement sur GitHub.

## Contact

GitHub : [Sabah-Rizki](https://github.com/Sabah-Rizki)
