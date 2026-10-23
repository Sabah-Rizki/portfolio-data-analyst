# Veille automatisée — mode d'emploi

Trois fichiers, à garder dans un même dossier (par exemple `Documents\P13_veille`) :

| Fichier | Rôle |
| --- | --- |
| `veille.py` | Le script : lit les flux, ajoute les nouveautés au journal |
| `sources.csv` | La liste des sources (modifiable dans Excel) |
| `journal_veille.xlsx` | Créé au premier lancement : une ligne par nouveauté |

## Étape 1 — Créer les alertes Google (gratuit, 10 minutes)

1. Va sur **google.com/alerts**, connecté à ton compte Google.
2. Dans la zone en haut, colle la première requête : `pandera python "data validation" -vuelta -cyclisme`.
3. Clique sur **Afficher les options** :
   - Fréquence : **Une fois par semaine au maximum**
   - Langue : **Toutes les langues** (ou Français, puis refais une alerte en Anglais)
   - Nombre de résultats : **Uniquement les meilleurs résultats**
   - Distribuer à : choisis **Flux RSS** si l'option est proposée, sinon ton adresse e-mail
4. Clique sur **Créer l'alerte**.
5. Recommence pour les autres requêtes (copie-les telles quelles, guillemets compris) :
   - `"great expectations" ("data quality" OR "data validation" OR "data pipeline")`
   - `"data quality" pandas validation -job -hiring -emploi`
   - `"package hallucination" OR "hallucinated packages" OR "slopsquatting"`
   - `CNIL "intelligence artificielle"`
   - `"gestion des stocks" ("analyse de données" OR "data analyst" OR "supply chain") -emploi -recrutement -postes`

   Puis les 4 alertes **métier** (marché du vin) :
   - `"marché du vin" (consommation OR ventes OR prix) -emploi`
   - `("vente de vin en ligne" OR "e-commerce du vin" OR "caviste en ligne") -emploi -recrutement`
   - `site:franceagrimer.fr vin`
   - `"vente d'alcool" (internet OR "en ligne") (loi OR réglementation)`

   Vérifie l'**aperçu** sous chaque requête : s'il parle d'autre chose que de données (film, sport, emploi…), ajoute un mot à exclure avec le signe moins, par exemple `-film`.
6. Si tu as choisi **Flux RSS** : sur la page google.com/alerts, à côté de chaque alerte, une **icône RSS** apparaît. Fais un clic droit dessus → **Copier l'adresse du lien**, puis colle-la dans `sources.csv`, colonne `url`, sur la ligne de l'alerte correspondante.
7. Fais une **capture d'écran** de la page google.com/alerts avec toutes tes alertes : c'est une preuve pour le PDF.

## Étape 2 — Premier lancement du script (2 minutes)

1. Ouvre **Anaconda Prompt** (touche Windows, tape « Anaconda Prompt »).
2. Va dans le dossier : `cd %USERPROFILE%\Documents\P13_veille`
3. Lance : `python veille.py`
4. Le script affiche le bilan par source et crée `journal_veille.xlsx`. Fais une **capture** de ce bilan et du fichier Excel ouvert.

## Étape 3 — Lancement automatique chaque lundi (5 minutes)

1. Touche Windows, tape **Planificateur de tâches**, ouvre-le.
2. À droite, clique sur **Créer une tâche de base…**
3. Nom : `Veille P13` → **Suivant**.
4. Déclencheur : **Chaque semaine** → **Suivant** → coche **lundi**, heure **08:00** → **Suivant**.
5. Action : **Démarrer un programme** → **Suivant**.
6. Remplis les trois champs :
   - Programme/script : `C:\Users\sabah\anaconda3\python.exe`
   - Ajouter des arguments : `veille.py`
   - Commencer dans : `C:\Users\sabah\Documents\P13_veille`
7. **Suivant** → **Terminer**.
8. Pour tester tout de suite : dans la liste du Planificateur, clic droit sur **Veille P13** → **Exécuter**, puis ouvre `journal_veille.xlsx`.
9. Fais une **capture** de la tâche dans le Planificateur : c'est la preuve de l'automatisation.

## Chaque lundi (30 minutes)

Ouvre `journal_veille.xlsx`, lis les lignes « à lire », puis remplis :
- `statut` : lu / retenu / écarté
- `pertinence` : 1 (faible) à 3 (forte)
- `note` : ce que ça change pour tes projets (une phrase)

Les lignes « retenu » alimentent la page Veille de ton portfolio.

## Si une source échoue

Le bilan affiche `ÉCHEC` et le détail est dans `veille.log`. Les autres sources continuent d'être lues. Vérifie l'adresse dans `sources.csv`.
