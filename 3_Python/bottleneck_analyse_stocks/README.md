# BottleNeck : analyse des stocks et des ventes d'un caviste

**Contexte.** BottleNeck, caviste en ligne (fictif), a deux systèmes qui ne se parlent pas : l'ERP (prix, stocks) et la boutique WooCommerce (ventes). Une table de liaison, tenue à la main, fait le lien.

**Ma mission.** Rapprocher les trois fichiers, corriger les erreurs, puis analyser le chiffre d'affaires, les stocks et les marges pour le comité de direction.

**Outils.** Python, pandas, matplotlib, seaborn, Jupyter.

## Résultats

- **714 produits** rapprochés entre l'ERP, la liaison et le site ; 91 produits sans identifiant web et 20 orphelins identifiés.
- **Chiffre d'affaires de 143 680 €**, dont 86 % sur le vin ; 5 751 bouteilles vendues.
- **Stock valorisé à 277 328 €** au prix d'achat, soit près de deux fois le chiffre d'affaires : un stock lourd à travailler en priorité.
- Taux de marge moyen de 48,2 % ; produits vendus sous leur prix d'achat signalés.
- Recommandations pour fiabiliser l'ERP et la table de liaison.

## Pour aller plus loin

Ce projet est repris de façon critique dans le [projet BottleNeck amélioré avec l'IA](../bottleneck_IA_controles_qualite/) : contrôles qualité automatisés, analyse des stocks dormants, hypothèses explicites sur la période des ventes, et correction de plusieurs conclusions de cette première version.

## Fichiers

- [notebook_bottleneck_P6.ipynb](notebook_bottleneck_P6.ipynb) : l'analyse complète, avec ses résultats.
- [presentation_CODIR.pdf](presentation_CODIR.pdf) : la présentation au comité de direction.

*Données fournies par OpenClassrooms, entreprise fictive ; non redistribuées ici.*
