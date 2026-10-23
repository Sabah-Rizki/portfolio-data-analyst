#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ONCFM - Application de détection automatique de faux billets
================================================================

Application finale livrée à l'ONCFM. Elle réutilise le pipeline entraîné dans
le notebook d'analyse (standardisation + régression logistique) pour prédire,
à partir des six mesures géométriques d'un billet, s'il s'agit d'un vrai ou
d'un faux billet.

Deux modes d'utilisation, conformément au cahier des charges :

1) Un fichier CSV contenant plusieurs billets :

    python predict_billets.py --csv billets_production.csv

   Le CSV attendu contient au minimum les colonnes suivantes (séparateur ','
   ou ';', accepté dans n'importe quel ordre) :
       diagonal, height_left, height_right, margin_low, margin_up, length
   Une colonne d'identifiant (ex. "id") est optionnelle et, si présente, est
   reportée dans le résultat.

2) Les valeurs géométriques d'un seul billet, passées directement en ligne de
   commande :

    python predict_billets.py --diagonal 171.81 --height_left 104.86 \\
        --height_right 104.95 --margin_low 4.52 --margin_up 2.89 --length 112.83

Dans les deux cas, l'application affiche pour chaque billet une prédiction
binaire (Vrai / Faux) ainsi que la probabilité associée, utilisée pour
confirmer / nuancer le résultat. Le résultat peut aussi être exporté en CSV
avec --output.

Auteur : Sab (Rizki Sabah) - Data Analyst, mission ONCFM
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
import joblib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, "model", "final_pipeline.joblib")
IMPUTER_PATH = os.path.join(SCRIPT_DIR, "model", "margin_low_imputer.joblib")

GEOM_COLS = ["diagonal", "height_left", "height_right", "margin_low", "margin_up", "length"]
IMPUTE_FEATURES = ["diagonal", "height_left", "height_right", "margin_up", "length"]


def load_artifacts():
    """Charge le pipeline de prédiction (scaler + régression logistique) et le
    modèle d'imputation de margin_low, sauvegardés lors de l'analyse."""
    if not os.path.exists(MODEL_PATH):
        sys.exit(f"Erreur : modèle introuvable à {MODEL_PATH}. "
                  f"Le dossier 'model/' doit être livré à côté de ce script.")
    pipeline = joblib.load(MODEL_PATH)
    imputer = joblib.load(IMPUTER_PATH) if os.path.exists(IMPUTER_PATH) else None
    return pipeline, imputer


def read_billets_csv(path):
    """Lit un fichier CSV de billets en gérant automatiquement le séparateur
    (',' ou ';') et en validant la présence des colonnes attendues."""
    if not os.path.exists(path):
        sys.exit(f"Erreur : fichier introuvable : {path}")

    df = pd.read_csv(path, sep=None, engine="python")

    missing_cols = [c for c in GEOM_COLS if c not in df.columns]
    if missing_cols:
        sys.exit(
            "Erreur : colonnes manquantes dans le CSV : " + ", ".join(missing_cols) +
            f"\nColonnes attendues (au minimum) : {GEOM_COLS}"
            f"\nColonnes trouvées : {list(df.columns)}"
        )
    return df


def impute_missing_margin_low(df, imputer):
    """Impute les valeurs manquantes de margin_low avec le modèle de régression
    linéaire entraîné en amont (mêmes variables explicatives que le notebook)."""
    if imputer is None or df["margin_low"].isna().sum() == 0:
        return df
    mask = df["margin_low"].isna()
    n_missing = mask.sum()
    if n_missing:
        print(f"[info] {n_missing} valeur(s) manquante(s) de margin_low imputée(s) "
              f"par régression linéaire.")
        df.loc[mask, "margin_low"] = imputer.predict(df.loc[mask, IMPUTE_FEATURES])
    return df


def predict(df, pipeline, imputer):
    """Applique le pipeline de production sur un DataFrame de billets et
    renvoie un DataFrame de résultats (prédiction binaire + probabilité)."""
    df = df.copy()
    df = impute_missing_margin_low(df, imputer)

    X = df[GEOM_COLS]
    preds = pipeline.predict(X)                 # sortie binaire (True = vrai billet)
    probas = pipeline.predict_proba(X)[:, 1]     # probabilité d'être un vrai billet

    result = pd.DataFrame(index=df.index)
    if "id" in df.columns:
        result["id"] = df["id"]
    result["is_genuine"] = preds
    result["prediction"] = np.where(preds, "Vrai billet", "Faux billet")
    result["probabilite_vrai"] = probas.round(4)
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Détection automatique de faux billets (ONCFM) - "
                    "prédit si un ou plusieurs billets sont vrais ou faux "
                    "à partir de leurs mesures géométriques."
    )
    parser.add_argument("--csv", type=str, help="Chemin vers un fichier CSV contenant plusieurs billets.")
    parser.add_argument("--output", type=str, default=None,
                        help="Chemin d'un fichier CSV pour sauvegarder les résultats (optionnel).")

    single = parser.add_argument_group("Billet unique (alternative à --csv)")
    single.add_argument("--diagonal", type=float, help="Diagonale du billet (mm)")
    single.add_argument("--height_left", type=float, help="Hauteur côté gauche (mm)")
    single.add_argument("--height_right", type=float, help="Hauteur côté droit (mm)")
    single.add_argument("--margin_low", type=float, help="Marge basse (mm)")
    single.add_argument("--margin_up", type=float, help="Marge haute (mm)")
    single.add_argument("--length", type=float, help="Longueur du billet (mm)")

    return parser.parse_args()


def main():
    args = parse_args()
    pipeline, imputer = load_artifacts()

    if args.csv:
        df = read_billets_csv(args.csv)
    else:
        provided = {k: v for k, v in vars(args).items() if k in GEOM_COLS and v is not None}
        required_for_single = [c for c in GEOM_COLS if c != "margin_low"]
        missing = [c for c in required_for_single if provided.get(c) is None]
        if missing or len(provided) == 0:
            sys.exit(
                "Erreur : fournissez soit --csv <fichier.csv>, soit les valeurs géométriques "
                "d'un billet via --diagonal --height_left --height_right --margin_low "
                "--margin_up --length (margin_low est optionnel, imputé si absent).\n\n"
                "Utilisez --help pour plus de détails."
            )
        row = {c: provided.get(c, np.nan) for c in GEOM_COLS}
        df = pd.DataFrame([row])

    result = predict(df, pipeline, imputer)

    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 120)
    print()
    print(result.to_string(index=False))
    print()
    n_fake = (~result["is_genuine"]).sum()
    n_genuine = result["is_genuine"].sum()
    print(f"Résumé : {n_genuine} vrai(s) billet(s), {n_fake} faux billet(s) sur {len(result)} analysé(s).")

    if args.output:
        result.to_csv(args.output, index=False)
        print(f"\nRésultats sauvegardés dans : {args.output}")


if __name__ == "__main__":
    main()
