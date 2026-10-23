#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ONCFM - Détection de faux billets - interface de démonstration (Streamlit)
============================================================================

Interface graphique optionnelle, pratique pour la démonstration en direct
(soutenance) de l'application décrite dans predict_billets.py. Elle réutilise
exactement le même pipeline de production.

Lancement :
    streamlit run app_streamlit.py
"""
import os

import numpy as np
import pandas as pd
import joblib
import streamlit as st

from predict_billets import GEOM_COLS, IMPUTE_FEATURES, load_artifacts, predict, read_billets_csv

st.set_page_config(page_title="ONCFM - Détection de faux billets", page_icon="💶", layout="centered")

st.title("💶 Détection automatique de faux billets")
st.caption("Organisation nationale de lutte contre le faux-monnayage (ONCFM)")

pipeline, imputer = load_artifacts()

tab_csv, tab_manuel, tab_apropos = st.tabs(["📄 Fichier CSV", "✍️ Billet unique", "ℹ️ À propos"])

with tab_csv:
    st.write("Déposez un fichier CSV de billets (format `billets_production.csv` : "
             "colonnes `diagonal, height_left, height_right, margin_low, margin_up, length`, "
             "`id` optionnel, séparateur `,` ou `;`).")
    uploaded = st.file_uploader("Fichier CSV", type=["csv"])
    if uploaded is not None:
        tmp_path = "/tmp/_uploaded_billets.csv"
        with open(tmp_path, "wb") as f:
            f.write(uploaded.getbuffer())
        try:
            df = read_billets_csv(tmp_path)
            result = predict(df, pipeline, imputer)

            def highlight(row):
                color = "#d4edda" if row["is_genuine"] else "#f8d7da"
                return [f"background-color: {color}"] * len(row)

            st.dataframe(result.style.apply(highlight, axis=1), use_container_width=True)

            n_genuine = int(result["is_genuine"].sum())
            n_fake = int((~result["is_genuine"]).sum())
            c1, c2 = st.columns(2)
            c1.metric("Vrais billets", n_genuine)
            c2.metric("Faux billets", n_fake)

            csv_out = result.to_csv(index=False).encode("utf-8")
            st.download_button("Télécharger les résultats (CSV)", csv_out, "resultats_billets.csv", "text/csv")
        except SystemExit as e:
            st.error(str(e))

with tab_manuel:
    st.write("Saisissez les mesures géométriques d'un billet (en mm).")
    col1, col2 = st.columns(2)
    with col1:
        diagonal = st.number_input("diagonal", value=171.90, format="%.2f")
        height_left = st.number_input("height_left", value=104.00, format="%.2f")
        height_right = st.number_input("height_right", value=103.90, format="%.2f")
    with col2:
        margin_low = st.number_input("margin_low", value=4.30, format="%.2f")
        margin_up = st.number_input("margin_up", value=3.10, format="%.2f")
        length = st.number_input("length", value=113.00, format="%.2f")

    if st.button("Analyser ce billet", type="primary"):
        row = pd.DataFrame([{
            "diagonal": diagonal, "height_left": height_left, "height_right": height_right,
            "margin_low": margin_low, "margin_up": margin_up, "length": length,
        }])
        result = predict(row, pipeline, imputer)
        pred = result.iloc[0]
        if pred["is_genuine"]:
            st.success(f"✅ Vrai billet — probabilité {pred['probabilite_vrai']:.2%}")
        else:
            st.error(f"🚫 Faux billet — probabilité d'être vrai : {pred['probabilite_vrai']:.2%}")
        st.progress(float(pred["probabilite_vrai"]))

with tab_apropos:
    st.markdown("""
    **Modèle :** régression logistique (variables standardisées), entraînée sur
    1500 billets scannés (1000 vrais / 500 faux) fournis par l'ONCFM.

    **Traitement des valeurs manquantes :** la variable `margin_low`, si absente,
    est imputée par régression linéaire à partir des 5 autres mesures
    géométriques.

    **Performance en validation croisée (10 plis) :** accuracy ≈ 99,1 %,
    recall sur les faux billets ≈ 98,2 %.

    Pour le détail des analyses, traitements et comparaisons de modèles
    (K-means, régression logistique, KNN, random forest), voir le notebook
    d'analyse fourni séparément.
    """)
