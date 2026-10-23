ONCFM - Application de détection de faux billets
===================================================

Contenu de ce dossier :
- predict_billets.py   : application principale (script en ligne de commande)
- app_streamlit.py      : interface graphique optionnelle pour démonstration
- model/                : pipeline entraîné (scaler + régression logistique)
                          et modèle d'imputation de margin_low (joblib)
- requirements.txt      : dépendances Python nécessaires

Installation :
    pip install -r requirements.txt

Utilisation en ligne de commande
---------------------------------

1) Prédire sur un fichier CSV contenant plusieurs billets :
    python predict_billets.py --csv billets_production.csv
    python predict_billets.py --csv billets_production.csv --output resultats.csv

   Le CSV attendu contient les colonnes : diagonal, height_left, height_right,
   margin_low, margin_up, length (une colonne "id" est optionnelle).
   Séparateur "," ou ";" accepté automatiquement.

2) Prédire sur un seul billet à partir de ses mesures :
    python predict_billets.py --diagonal 171.81 --height_left 104.86 \
        --height_right 104.95 --margin_low 4.52 --margin_up 2.89 --length 112.83

Interface graphique (démonstration) :
    streamlit run app_streamlit.py

Le modèle retenu (régression logistique) et sa justification sont détaillés
dans le notebook d'analyse et le support de présentation livrés séparément.
