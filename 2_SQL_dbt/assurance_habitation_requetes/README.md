# Assurance habitation : requêter une base de données en SQL

**Contexte.** Un assureur veut mieux connaître son portefeuille de contrats d'assurance habitation et le marché par territoire.

**Ma mission.** Modéliser une base relationnelle à partir de deux fichiers, la créer, la charger, puis répondre à 12 questions métier en SQL.

**Outils.** SQL Power Architect (modélisation), MySQL et MySQL Workbench, SQL.

## Démarche

1. **Dictionnaire de données** : 14 colonnes pour la table des contrats, 8 pour le référentiel géographique ; types et contraintes définis.
2. **Schéma relationnel** : deux tables reliées par clé étrangère sur le code commune (une commune, plusieurs contrats).
3. **Création et chargement** : 30 335 contrats et 38 916 communes, nombre de lignes vérifié après import.
4. **12 requêtes d'analyse**, chacune avec son objectif, son raisonnement et son résultat : contrats d'une commune, surface moyenne à Paris, prix moyen par département, communes d'au moins 150 contrats, nombre de contrats par région, etc.

## Fichiers

- [document_technique.pdf](document_technique.pdf) : dictionnaire, schéma, code de création des tables, vérifications.
- [liste_requetes_SQL.pdf](liste_requetes_SQL.pdf) : les 12 requêtes, leur cheminement et leurs résultats.
- [presentation_methodologie.pdf](presentation_methodologie.pdf) : la méthodologie présentée.

*Données fournies par OpenClassrooms et référentiel géographique public ; non redistribuées ici.*
