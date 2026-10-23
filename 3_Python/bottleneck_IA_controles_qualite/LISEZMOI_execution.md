# BottleNeck — notebook amélioré (P13)

## Contenu
| Fichier | Rôle |
| --- | --- |
| `Rizki_Sabah_1_projet_ameliore_092026.ipynb` | Le notebook amélioré, déjà exécuté |
| `controles_qualite.py` | Les 64 règles de contrôle qualité (Pandera), importées par le notebook |
| `erp.xlsx`, `web.xlsx`, `liaison.xlsx` | Les données brutes du P6, non modifiées |
| `rapport_qualite_donnees.xlsx` | Rapport des anomalies, régénéré à chaque exécution |
| `bottleneck_dataset_clean_P13.xlsx` | Jeu d'analyse final (714 références), régénéré à chaque exécution |
| `requirements.txt` | Versions des librairies utilisées |

## Exécution
1. Garder tous les fichiers dans le même dossier.
2. Installer Pandera une seule fois : `pip install pandera` (Anaconda Prompt).
3. Ouvrir le notebook dans Jupyter, puis **Noyau → Redémarrer et tout exécuter** (environ 10 secondes).

## Origine des règles
`controles_qualite.py` reprend le code de l'essai IA C-P2 (Claude), retenu parmi 6 essais Claude / Gemini notés sur 100.
Les trois ajouts (ERP-22, RGPD-01, WEB-28) sont marqués `[AJOUT P13]` dans le fichier.
