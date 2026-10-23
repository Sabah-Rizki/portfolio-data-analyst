# Veille automatisée

**Le besoin.** Suivre, sans y passer du temps chaque jour, deux types d'information :

- **le métier** : marché du vin (consommation, vente en ligne, offre), réglementation de la vente d'alcool, gestion des stocks ;
- **la technique** : outils de validation de données (Pandera, pandas, Great Expectations), risques de l'IA, CNIL.

**Outils.** Google Alertes (flux RSS), Python (bibliothèque standard et pandas), Planificateur de tâches Windows. Entièrement gratuit.

## Comment ça marche

1. **11 alertes Google** livrées en flux RSS : 4 métier (par exemple `"marché du vin" (consommation OR ventes OR prix) -emploi`) et 7 techniques ou réglementaires, avec des requêtes affinées pour éviter les homonymes (par exemple `pandera python "data validation" -vuelta -cyclisme`, car « Pandera » est aussi une étape du Tour d'Espagne).
2. **3 flux GitHub** des nouvelles versions de Pandera, pandas et Great Expectations.
3. **`veille.py`** lit les 14 flux, garde les nouveautés de moins de 30 jours, élimine les doublons et les ajoute à `journal_veille.xlsx`. Une source en panne est notée sans bloquer les autres.
4. **Le Planificateur de tâches** lance le script chaque lundi à 8 h.
5. **30 minutes le lundi** pour qualifier chaque ligne : lu, retenu ou écarté, pertinence de 1 à 3, une phrase sur l'impact.

## Ce que la veille métier a apporté au projet BottleNeck

| Constat (source) | Conséquence pour l'analyse |
|---|---|
| Consommation de vin en France : 40 L par habitant en 2024 contre 46,2 L en 2019 ([FranceAgriMer, déc. 2025](https://www.franceagrimer.fr/sites/default/files/2025-12/20251121_CC%20VITI%20VINICOLE%20%202025.pdf)) | Une couverture calculée sur les ventes passées est optimiste : le surstock de plus de 24 mois est prioritaire |
| Vente de vin en ligne : −8 % en valeur en 2023 après le pic de 2021 ([FranceAgriMer et Xerfi, déc. 2024](https://www.franceagrimer.fr/chiffre-et-analyses-economiques/commercialisation-de-vin-par-internet-en-france-e-commerce)) | Le canal en ligne ne compensera pas : agir sur le réassort et les promotions ciblées |
| Arrachage aidé à 4 000 €/ha, 27 926 ha demandés ([FranceAgriMer, juin 2026](https://www.franceagrimer.fr/actualites/le-dispositif-darrachage-definitif-de-vignes-est-lance)) | Offre excédentaire et prix sous pression : corriger d'abord les ventes sous prix d'achat |
| Consommation mondiale : −2,7 % en 2025 ([OIV, mai 2026](https://www.oiv.int/sites/default/files/2026-05/OIV_EN_Press_release_State-of_the_World-Wine_Sector_1.pdf)) | La baisse n'est pas propre à la France |

## Améliorations apportées en conditions réelles

- Le flux RSS de la CNIL refusait le script (erreur 503) : remplacé par une alerte Google `site:cnil.fr`.
- Les titres étaient coupés au premier mot en gras : corrigé.
- Google date parfois un article du 1er janvier 1970 quand la date est inconnue : ces articles ne sont plus écartés par erreur.

## Fichiers

- [veille.py](veille.py) : le script.
- [sources_exemple.csv](sources_exemple.csv) : la liste des sources. Les adresses de mes flux d'alertes, personnelles, sont remplacées par un repère.
- [journal_veille_exemple.xlsx](journal_veille_exemple.xlsx) : le journal après le premier lancement.
- [LISEZMOI_veille.md](LISEZMOI_veille.md) : la mise en place pas à pas.
