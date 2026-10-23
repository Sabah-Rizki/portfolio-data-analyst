# Sanitoral : tableau de bord de suivi de projets

**Contexte.** Le service PMO de Sanitoral (entreprise fictive) suit des projets IT et Marketing dans 4 régions du monde, de 2018 à 2022. Les directeurs veulent repérer vite les projets qui dérapent.

**Ma mission.** Formaliser les besoins, préparer les données et construire un tableau de bord Power BI mis à jour chaque semaine.

**Outils.** Power BI, Power Query, DAX, Product Strategy Canvas.

## Ce que j'ai construit

- **Besoins formalisés** dans un Product Strategy Canvas : 3 profils (directeur général, régional, pays) et une règle d'alerte commune, un écart de plus de 15 % entre prévu et réel sur les coûts, les délais ou les livrables.
- **Préparation automatique** dans Power Query : la mise à jour hebdomadaire se fait en remplaçant le fichier Excel puis en actualisant.
- **Modèle en étoile** de 7 tables autour du plan de projets (prévisionnel) et de trois tables de réalisé (coûts, durées, livrables).
- **Tableau de bord** : carte mondiale des alertes, analyse coûts-délais par phase, filtres par région, pays et type de projet, exploration détaillée d'un pays (drill-through).
- **Sécurité par rôle (RLS)** : chaque directeur ne voit que son périmètre.

## Fichiers

- [tableau_de_bord_sanitoral.pbix](tableau_de_bord_sanitoral.pbix) : à ouvrir avec Power BI Desktop (gratuit).

*Données fournies par OpenClassrooms, entreprise fictive.*
