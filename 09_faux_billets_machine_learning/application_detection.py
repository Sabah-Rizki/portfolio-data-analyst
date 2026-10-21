"""
ONCFM - Application de détection de faux billets
=================================================

Prédit si un billet est VRAI ou FAUX à partir de ses 6 mesures géométriques (en mm),
avec le modèle retenu dans le notebook : régression logistique
(pipeline : imputation de margin_low par régression linéaire -> standardisation -> régression logistique).

Utilisation (dans un terminal / Anaconda Prompt, depuis le dossier du projet) :

    1) Un fichier CSV contenant plusieurs billets :
         python Rizki_Sabah_2_Script_application_102026.py --csv billets_production.csv

    2) Les 6 valeurs d'un seul billet, dans cet ordre :
       diagonal height_left height_right margin_low margin_up length
         python Rizki_Sabah_2_Script_application_102026.py --valeurs 171.76 104.01 103.54 5.21 3.30 111.42

    3) Mode interactif (le script pose les questions) :
         python Rizki_Sabah_2_Script_application_102026.py

Depuis Jupyter, remplacer "python" par "%run".

Sortie : pour chaque billet, VRAI ou FAUX (sortie binaire : 1 = faux, 0 = vrai) + la probabilité
d'être faux. Les billets dont la probabilité est entre 0,1 et 0,9 sont signalés « à vérifier ».
Option --sortie resultats.csv pour enregistrer le résultat dans un fichier.

Fichiers nécessaires dans le même dossier : modele_faux_billets.joblib (créé par le notebook).
S'il est absent ou illisible (version de scikit-learn différente), le script ré-entraîne
automatiquement le modèle à partir de billets.csv avec exactement la même méthode.
"""

import argparse
import os
import sys

try:  # évite les erreurs d'affichage des accents/emojis dans certaines consoles Windows
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    import numpy as np
    import pandas as pd
    import joblib
    import sklearn
    from sklearn.experimental import enable_iterative_imputer  # noqa: F401 (nécessaire pour IterativeImputer)
    from sklearn.impute import IterativeImputer
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
except ImportError as erreur:
    sys.exit(
        f"❌ Librairie manquante : {erreur.name}\n"
        f"   Python utilisé : {sys.executable}\n"
        "   Lancez le script depuis l'Anaconda Prompt, AVEC le mot python devant :\n"
        "       python Rizki_Sabah_2_Script_application_102026.py --csv billets_production.csv\n"
        f"   (si l'erreur persiste dans Anaconda : conda install {erreur.name})"
    )

DOSSIER = os.path.dirname(os.path.abspath(__file__))
FICHIER_MODELE = os.path.join(DOSSIER, "modele_faux_billets.joblib")
FICHIER_ENTRAINEMENT = os.path.join(DOSSIER, "billets.csv")

VARIABLES = ["diagonal", "height_left", "height_right", "margin_low", "margin_up", "length"]
SEUIL = 0.5                      # probabilité d'être faux à partir de laquelle on prédit FAUX
ZONE_INCERTITUDE = (0.1, 0.9)    # probabilités pour lesquelles un contrôle manuel est conseillé
C_REGULARISATION = 1             # hyperparamètre retenu par GridSearchCV dans le notebook
RANDOM_STATE = 42


# --------------------------------------------------------------------------- modèle
def entrainer_modele():
    """Ré-entraîne le pipeline final sur billets.csv (même méthode que dans le notebook)."""
    if not os.path.exists(FICHIER_ENTRAINEMENT):
        sys.exit(f"❌ Ni le modèle ni '{FICHIER_ENTRAINEMENT}' ne sont disponibles : impossible de prédire.")
    df = pd.read_csv(FICHIER_ENTRAINEMENT, sep=";")
    X = df[VARIABLES]
    y = (~df["is_genuine"].astype(bool)).astype(int)          # 1 = faux, 0 = vrai
    pipeline = make_pipeline(
        IterativeImputer(estimator=LinearRegression(), random_state=RANDOM_STATE),
        StandardScaler(),
        LogisticRegression(max_iter=1000, C=C_REGULARISATION))
    pipeline.fit(X, y)
    joblib.dump({"pipeline": pipeline, "variables": VARIABLES, "classe_positive": "faux (1)",
                 "seuil": SEUIL, "zone_incertitude": ZONE_INCERTITUDE,
                 "sklearn_version": sklearn.__version__}, FICHIER_MODELE)
    print(f"ℹ️  Modèle ré-entraîné sur {len(df)} billets et sauvegardé dans '{os.path.basename(FICHIER_MODELE)}'.")
    return pipeline


def charger_modele():
    """Charge le modèle sauvegardé ; le ré-entraîne si absent ou incompatible."""
    if os.path.exists(FICHIER_MODELE):
        try:
            sauvegarde = joblib.load(FICHIER_MODELE)
            if sauvegarde.get("sklearn_version") == sklearn.__version__:
                return sauvegarde["pipeline"]
            print(f"ℹ️  Modèle créé avec scikit-learn {sauvegarde.get('sklearn_version')} "
                  f"(installé : {sklearn.__version__}) : ré-entraînement par sécurité.")
        except Exception as erreur:  # fichier corrompu ou version incompatible
            print(f"ℹ️  Modèle illisible ({erreur.__class__.__name__}) : ré-entraînement.")
    else:
        print("ℹ️  Aucun modèle sauvegardé trouvé : entraînement.")
    return entrainer_modele()


# --------------------------------------------------------------------------- données
def lire_csv(chemin):
    """Lit un CSV de billets (séparateur ',' ou ';' détecté automatiquement) et vérifie les colonnes."""
    if not os.path.exists(chemin):
        sys.exit(f"❌ Fichier introuvable : {chemin}")
    df = pd.read_csv(chemin, sep=None, engine="python")      # détection automatique du séparateur
    df.columns = [c.strip() for c in df.columns]
    manquantes = [v for v in VARIABLES if v not in df.columns]
    if manquantes:
        sys.exit(f"❌ Colonnes manquantes dans le fichier : {manquantes}. Colonnes attendues : {VARIABLES}")
    if "id" not in df.columns:
        df["id"] = [f"billet_{i + 1}" for i in range(len(df))]
    df[VARIABLES] = df[VARIABLES].apply(pd.to_numeric, errors="coerce")
    lignes_vides = df[VARIABLES].isna().all(axis=1)
    if lignes_vides.any():
        print(f"⚠️  {lignes_vides.sum()} ligne(s) sans aucune mesure ignorée(s).")
        df = df[~lignes_vides]
    return df


def demander_valeurs():
    """Mode interactif : demande les 6 mesures une par une."""
    print("Saisissez les mesures du billet en mm (virgule ou point acceptés) :")
    valeurs = []
    for var in VARIABLES:
        while True:
            saisie = input(f"  {var} : ").strip().replace(",", ".")
            try:
                valeurs.append(float(saisie))
                break
            except ValueError:
                print("    Valeur invalide, recommencez (exemple : 171.94).")
    return valeurs


# --------------------------------------------------------------------------- prédiction
def predire(modele, df):
    """Renvoie un tableau : id, prédiction binaire, libellé, probabilité d'être faux, alerte."""
    proba_faux = modele.predict_proba(df[VARIABLES])[:, 1]
    bas, haut = ZONE_INCERTITUDE
    return pd.DataFrame({
        "id": df["id"].values,
        "prediction": (proba_faux >= SEUIL).astype(int),                 # sortie binaire : 1 = faux
        "resultat": np.where(proba_faux >= SEUIL, "FAUX", "VRAI"),
        "proba_faux": proba_faux.round(4),
        "controle": np.where((proba_faux > bas) & (proba_faux < haut), "à vérifier", ""),
    })


def afficher(resultats):
    print("\n=== Résultats de la détection ===")
    print(resultats.to_string(index=False, formatters={"proba_faux": lambda p: f"{p:.4f}"}))
    nb_faux = int(resultats["prediction"].sum())
    print(f"\nBilan : {len(resultats)} billet(s) analysé(s) -> {nb_faux} FAUX, {len(resultats) - nb_faux} VRAI(S).")
    nb_douteux = int((resultats["controle"] != "").sum())
    if nb_douteux:
        print(f"⚠️  {nb_douteux} billet(s) en zone d'incertitude : contrôle manuel conseillé.")


def main(arguments=None):
    parser = argparse.ArgumentParser(description="ONCFM - détection de faux billets (régression logistique).")
    groupe = parser.add_mutually_exclusive_group()
    groupe.add_argument("--csv", help="chemin vers un fichier CSV de billets")
    groupe.add_argument("--valeurs", nargs=6, type=float, metavar=("DIAG", "H_G", "H_D", "M_BAS", "M_HAUT", "LONG"),
                        help="les 6 mesures d'un billet : diagonal height_left height_right margin_low margin_up length")
    parser.add_argument("--sortie", help="chemin d'un CSV où enregistrer les résultats (optionnel)")
    args = parser.parse_args(arguments)

    modele = charger_modele()

    if args.csv:
        donnees = lire_csv(args.csv)
    else:
        valeurs = args.valeurs if args.valeurs else demander_valeurs()
        donnees = pd.DataFrame([valeurs], columns=VARIABLES).assign(id="billet_saisi")

    resultats = predire(modele, donnees)
    afficher(resultats)

    if args.sortie:
        resultats.to_csv(args.sortie, index=False, sep=";", encoding="utf-8-sig")
        print(f"💾 Résultats enregistrés dans '{args.sortie}'.")
    return resultats


if __name__ == "__main__":
    main()
