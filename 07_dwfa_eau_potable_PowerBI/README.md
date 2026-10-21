# 07 · DWFA : tableau de bord sur l'accès à l'eau potable

**Contexte.** Drinking Water For All (ONG fictive) veut identifier les pays où agir en priorité pour l'accès à l'eau potable.

**Ma mission.** Concevoir puis réaliser un tableau de bord Power BI à partir de 6 fichiers publics : accès à l'eau, régions, population, stabilité politique, mortalité liée à l'eau, urbanisation.

**Outils.** Power BI, Power Query, blueprint et maquettes basse fidélité.

## Ce que j'ai construit

- **Blueprint** : besoins des utilisateurs, mesures calculées, choix de visuels et maquettes de trois vues (monde, continent, pays).
- **Préparation** : 6 fichiers joints sur la table d'accès à l'eau (194 pays) par jointure externe gauche, pour ne perdre aucun pays ; harmonisation des noms de pays.
- **Tableau de bord** : accès basique et « géré en toute sécurité », population, stabilité politique, urbanisation, de 2000 à 2017 (mortalité liée à l'eau disponible pour 2016 seulement).
- **Filtres** : stabilité politique minimale, continent, zone urbaine ou rurale, année, pays.
- **Accessibilité** : thème bleu à haut contraste.

## Fichiers

- [tableau_de_bord_eau_potable.pbix](tableau_de_bord_eau_potable.pbix) : à ouvrir avec Power BI Desktop (gratuit).
- [blueprint.docx](blueprint.docx) : la conception du tableau de bord.
- [theme_haut_contraste.json](theme_haut_contraste.json) : le thème Power BI.
