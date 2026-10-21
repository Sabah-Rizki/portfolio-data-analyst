# 11 · Veille automatisée

**Le besoin.** Suivre les nouveautés des outils que j'utilise (Pandera, pandas, Great Expectations), la réglementation (CNIL, IA) et mon métier (gestion des stocks), sans y passer du temps chaque jour.

**Outils.** Google Alertes (flux RSS), Python (bibliothèque standard et pandas), Planificateur de tâches Windows. Entièrement gratuit.

## Comment ça marche

1. **7 alertes Google** livrées en flux RSS, avec des requêtes affinées pour éviter les homonymes (par exemple `pandera python "data validation" -vuelta -cyclisme`, car « Pandera » est aussi une étape du Tour d'Espagne).
2. **3 flux GitHub** des nouvelles versions de Pandera, pandas et Great Expectations.
3. **`veille.py`** lit les 10 flux, garde les nouveautés de moins de 30 jours, élimine les doublons et les ajoute à `journal_veille.xlsx`. Une source en panne est notée sans bloquer les autres.
4. **Le Planificateur de tâches** lance le script chaque lundi à 8 h.
5. **30 minutes le lundi** pour qualifier chaque ligne : lu, retenu ou écarté, pertinence de 1 à 3, une phrase sur l'impact.

## Améliorations apportées en conditions réelles

- Le flux RSS de la CNIL refusait le script (erreur 503) : remplacé par une alerte Google `site:cnil.fr`.
- Les titres étaient coupés au premier mot en gras : corrigé.
- Google date parfois un article du 1er janvier 1970 quand la date est inconnue : ces articles ne sont plus écartés par erreur.

## Fichiers

- [veille.py](veille.py) : le script.
- [sources_exemple.csv](sources_exemple.csv) : la liste des sources. Les adresses de mes flux d'alertes, personnelles, sont remplacées par un repère.
- [journal_veille_exemple.xlsx](journal_veille_exemple.xlsx) : le journal après le premier lancement.
- [LISEZMOI_veille.md](LISEZMOI_veille.md) : la mise en place pas à pas.
