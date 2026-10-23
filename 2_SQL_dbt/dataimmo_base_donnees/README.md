# DATAImmo : base de données du marché immobilier

**Contexte.** Laplace Immo (entreprise fictive) veut une base centralisée pour analyser les ventes immobilières françaises, à partir des Demandes de Valeurs Foncières (open data DGFiP) du 1er semestre 2020.

**Ma mission.** Concevoir une base relationnelle propre, l'alimenter, puis répondre à 12 questions métier en SQL.

**Outils.** Power Query (nettoyage), SQL Power Architect (modélisation), SQLite et DB Browser (base et requêtes).

## Démarche

1. **Nettoyage** de 3 sources : valeurs foncières (DGFiP), communes (INSEE), référentiel géographique (MEN-ESR).
2. **RGPD** : la colonne « nom de l'acquéreur » est supprimée dès la première étape, avant tout traitement.
3. **Modélisation** en troisième forme normale (3NF) : 4 tables liées (Région, Commune, Bien, Vente), avec clés primaires et étrangères. Séparer *Bien* et *Vente* permet de suivre les reventes d'un même bien.
4. **Chargement** par table temporaire, dédoublonnage, puis contrôles d'intégrité : aucune vente sans bien, aucun bien sans commune.
5. **12 requêtes d'analyse** : nombre de ventes par région, prix au m² par département, répartition par nombre de pièces, etc.

## Fichiers

- [presentation_DATAImmo.pdf](presentation_DATAImmo.pdf) : la démarche, le schéma, le dictionnaire de données et les 12 requêtes avec leurs résultats.

*Données open data (DGFiP, INSEE, MEN-ESR) ; la base n'est pas redistribuée ici.*
