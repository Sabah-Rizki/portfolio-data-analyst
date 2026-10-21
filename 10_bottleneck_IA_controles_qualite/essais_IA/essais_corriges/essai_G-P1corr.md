Voici l'implémentation complète avec Pandera. Elle utilise le mode `lazy=True` pour collecter l'intégralité des erreurs sans interrompre l'exécution, valide à la fois les contraintes unitaires, les règles métier multi-colonnes (ex. : cohérence des stocks, marges, doublons de produits hors images) et l'intégrité référentielle entre les trois tables.

```python
import numpy as np
import pandas as pd
import pandera as pa
from pandera import Check, Column, DataFrameSchema
from pandera.errors import SchemaErrors


def _extraire_anomalies(err: SchemaErrors, nom_fichier: str) -> list[dict]:
    """Extrait et normalise les erreurs générées par Pandera en mode lazy."""
    anomalies = []
    fc = err.failure_cases
    if fc is None or fc.empty:
        return anomalies

    for _, row in fc.iterrows():
        schema_context = str(row.get("schema_context", ""))
        col = row.get("column")
        check = str(row.get("check", "validation_error"))
        idx = row.get("index")
        val = row.get("failure_case")

        # Si l'erreur porte sur le DataFrame entier ou un check multi-colonnes
        if pd.isna(col) or col is None:
            col = "DataFrame" if schema_context == "DataFrameSchema" else str(col)

        # Si l'erreur est structurelle (ex: colonne manquante, type global de colonne)
        if pd.isna(idx) or idx is None:
            idx_val = -1
        else:
            idx_val = idx

        anomalies.append(
            {
                "fichier": nom_fichier,
                "regle": check,
                "colonne": str(col),
                "index_ligne": idx_val,
                "valeur": val,
            }
        )
    return anomalies


def valider(
    erp: pd.DataFrame, web: pd.DataFrame, liaison: pd.DataFrame
) -> pd.DataFrame:
    """
    Valide les trois DataFrames bruts (erp, web, liaison) avec Pandera.
    Retourne un DataFrame consolidé de toutes les anomalies détectées.
    """
    anomalies: list[dict] = []

    # =========================================================================
    # 1. SCHÉMA DE VALIDATION : ERP (erp.xlsx)
    # =========================================================================
    schema_erp = DataFrameSchema(
        columns={
            "product_id": Column(
                 object,  # Permet d'exécuter les checks ligne par ligne même si le dtype brut est altéré
                checks=[
                    Check(lambda s: s.notna(), name="product_id_non_null", ignore_na=False),
                    Check(
                        lambda s: pd.to_numeric(s, errors="coerce").notna()
                        & (pd.to_numeric(s, errors="coerce") % 1 == 0),
                        name="product_id_entier_valide",
                    ),
                    Check(
                        lambda s: pd.to_numeric(s, errors="coerce") > 0,
                        name="product_id_strictement_positif",
                    ),
                    Check(
                        lambda s: ~s.duplicated(keep=False),
                        name="product_id_unique",
                    ),
                ],
                nullable=True,
            ),
            "onsale_web": Column(
                object,
                checks=[
                    Check(lambda s: s.notna(), name="onsale_web_non_null", ignore_na=False),
                    Check.isin([0, 1], name="onsale_web_booleen_0_ou_1"),
                ],
                nullable=True,
            ),
            "price": Column(
                object,
                checks=[
                    Check(lambda s: s.notna(), name="price_non_null", ignore_na=False),
                    Check(
                        lambda s: pd.to_numeric(s, errors="coerce") > 0,
                        name="price_strictement_positif",
                    ),
                ],
                nullable=True,
            ),
            "stock_quantity": Column(
                object,
                checks=[
                    Check(lambda s: s.notna(), name="stock_quantity_non_null", ignore_na=False),
                    Check(
                        lambda s: pd.to_numeric(s, errors="coerce").notna()
                        & (pd.to_numeric(s, errors="coerce") % 1 == 0),
                        name="stock_quantity_entier_valide",
                    ),
                    Check(
                        lambda s: pd.to_numeric(s, errors="coerce") >= 0,
                        name="stock_quantity_superieur_ou_egal_0",
                    ),
                ],
                nullable=True,
            ),
            "stock_status": Column(
                object,
                checks=[
                    Check(lambda s: s.notna(), name="stock_status_non_null", ignore_na=False),
                    Check.isin(
                        ["instock", "outofstock"], name="stock_status_domaine_valide"
                    ),
                ],
                nullable=True,
            ),
            "purchase_price": Column(
                object,
                checks=[
                    Check(lambda s: s.notna(), name="purchase_price_non_null", ignore_na=False),
                    Check(
                        lambda s: pd.to_numeric(s, errors="coerce") > 0,
                        name="purchase_price_strictement_positif",
                    ),
                ],
                nullable=True,
            ),
        },
        checks=[
            # Cohérence entre la quantité en stock et le statut affiché
            Check(
                lambda df: (
                    (
                        (pd.to_numeric(df["stock_quantity"], errors="coerce") > 0)
                        & (df["stock_status"] == "instock")
                    )
                    | (
                        (pd.to_numeric(df["stock_quantity"], errors="coerce") == 0)
                        & (df["stock_status"] == "outofstock")
                    )
                ),
                name="coherence_stock_quantity_et_status",
            ),
            # Cohérence financière : prix de vente >= prix d'achat
            Check(
                lambda df: pd.to_numeric(df["price"], errors="coerce")
                >= pd.to_numeric(df["purchase_price"], errors="coerce"),
                name="coherence_prix_vente_superieur_prix_achat",
            ),
        ],
        strict=False,
        coerce=False,
    )

    # =========================================================================
    # 2. SCHÉMA DE VALIDATION : LIAISON (liaison.xlsx)
    # =========================================================================
    schema_liaison = DataFrameSchema(
        columns={
            "product_id": Column(
                object,
                checks=[
                    Check(lambda s: s.notna(), name="product_id_non_null", ignore_na=False),
                    Check(
                        lambda s: pd.to_numeric(s, errors="coerce") > 0,
                        name="product_id_strictement_positif",
                    ),
                    Check(
                        lambda s: ~s.duplicated(keep=False),
                        name="product_id_unique_dans_liaison",
                    ),
                ],
                nullable=True,
            ),
            "id_web": Column(
                object,
                checks=[
                    Check(lambda s: s.notna(), name="id_web_non_null", ignore_na=False),
                    Check(
                        lambda s: s.astype(str).str.strip() != "",
                        name="id_web_non_vide",
                    ),
                    Check(
                        lambda s: ~(s.notna() & s.duplicated(keep=False)),
                        name="id_web_unique_hors_null",
                    ),
                ],
                nullable=True,
            ),
        },
        strict=False,
        coerce=False,
    )

    # =========================================================================
    # 3. SCHÉMA DE VALIDATION : WEB (web.xlsx)
    # =========================================================================
    schema_web = DataFrameSchema(
        columns={
            "sku": Column(
                object,
                checks=[
                    Check(lambda s: s.notna(), name="sku_non_null", ignore_na=False),
                    Check(
                        lambda s: s.astype(str).str.strip() != "",
                        name="sku_non_vide",
                    ),
                ],
                nullable=True,
            ),
            "virtual": Column(
                object,
                checks=[Check.isin([0, 1], name="virtual_booleen_0_ou_1")],
                nullable=True,
            ),
            "downloadable": Column(
                object,
                checks=[Check.isin([0, 1], name="downloadable_booleen_0_ou_1")],
                nullable=True,
            ),
            "rating_count": Column(
                object,
                checks=[
                    Check(
                        lambda s: pd.to_numeric(s, errors="coerce") >= 0,
                        name="rating_count_positif_ou_nul",
                    )
                ],
                nullable=True,
            ),
            "average_rating": Column(
                object,
                checks=[
                    Check(
                        lambda s: (pd.to_numeric(s, errors="coerce") >= 0)
                        & (pd.to_numeric(s, errors="coerce") <= 5),
                        name="average_rating_entre_0_et_5",
                    )
                ],
                nullable=True,
            ),
            "total_sales": Column(
                object,
                checks=[
                    Check(lambda s: s.notna(), name="total_sales_non_null", ignore_na=False),
                    Check(
                        lambda s: pd.to_numeric(s, errors="coerce") >= 0,
                        name="total_sales_positif_ou_nul",
                    ),
                ],
                nullable=True,
            ),
            "tax_status": Column(
                object,
                checks=[
                    Check.isin(
                        ["taxable", "shipping", "none"],
                        name="tax_status_domaine_valide",
                    )
                ],
                nullable=True,
            ),
            "tax_class": Column(object, nullable=True),
            "post_author": Column(
                object,
                checks=[Check(lambda s: s.notna(), name="post_author_non_null", ignore_na=False)],
                nullable=True,
            ),
            "post_date": Column(
                object,
                checks=[
                    Check(
                        lambda s: pd.to_datetime(s, errors="coerce").notna(),
                        name="post_date_valide",
                    )
                ],
                nullable=True,
            ),
            "post_date_gmt": Column(
                object,
                checks=[
                    Check(
                        lambda s: pd.to_datetime(s, errors="coerce").notna(),
                        name="post_date_gmt_valide",
                    )
                ],
                nullable=True,
            ),
            "post_content": Column(object, nullable=True),
            "product_type": Column(
                object,
                checks=[Check(lambda s: s.notna(), name="product_type_non_null", ignore_na=False)],
                nullable=True,
            ),
            "post_title": Column(
                object,
                checks=[
                    Check(lambda s: s.notna(), name="post_title_non_null", ignore_na=False),
                    Check(
                        lambda s: s.astype(str).str.strip() != "",
                        name="post_title_non_vide",
                    ),
                ],
                nullable=True,
            ),
            "post_excerpt": Column(object, nullable=True),
            "post_status": Column(
                object,
                checks=[
                    Check.isin(
                        ["publish", "draft", "private", "pending", "inherit"],
                        name="post_status_domaine_valide",
                    )
                ],
                nullable=True,
            ),
            "comment_status": Column(
                object,
                checks=[
                    Check.isin(
                        ["open", "closed"], name="comment_status_domaine_valide"
                    )
                ],
                nullable=True,
            ),
            "ping_status": Column(
                object,
                checks=[
                    Check.isin(["open", "closed"], name="ping_status_domaine_valide")
                ],
                nullable=True,
            ),
            "post_password": Column(object, nullable=True),
            "post_name": Column(
                object,
                checks=[Check(lambda s: s.notna(), name="post_name_non_null", ignore_na=False)],
                nullable=True,
            ),
            "post_modified": Column(
                object,
                checks=[
                    Check(
                        lambda s: pd.to_datetime(s, errors="coerce").notna(),
                        name="post_modified_valide",
                    )
                ],
                nullable=True,
            ),
            "post_modified_gmt": Column(
                object,
                checks=[
                    Check(
                        lambda s: pd.to_datetime(s, errors="coerce").notna(),
                        name="post_modified_gmt_valide",
                    )
                ],
                nullable=True,
            ),
            "post_content_filtered": Column(object, nullable=True),
            "post_parent": Column(object, nullable=True),
            "guid": Column(
                object,
                checks=[Check(lambda s: s.notna(), name="guid_non_null", ignore_na=False)],
                nullable=True,
            ),
            "menu_order": Column(object, nullable=True),
            "post_type": Column(
                object,
                checks=[
                    Check(lambda s: s.notna(), name="post_type_non_null", ignore_na=False),
                    Check.isin(
                        ["product"],
                        name="post_type_doit_etre_product_non_attachment",
                    ),
                ],
                nullable=True,
            ),
            "post_mime_type": Column(object, nullable=True),
            "comment_count": Column(
                object,
                checks=[
                    Check(
                        lambda s: pd.to_numeric(s, errors="coerce") >= 0,
                        name="comment_count_positif_ou_nul",
                    )
                ],
                nullable=True,
            ),
        },
        checks=[
            # Dans WooCommerce, un SKU doit être unique parmi les lignes "product"
            Check(
                lambda df: ~(
                    (df["post_type"] == "product")
                    & df["sku"].notna()
                    & df.duplicated(subset=["sku", "post_type"], keep=False)
                ),
                name="sku_unique_pour_post_type_product",
            ),
            # Cohérence temporelle : la date de modification >= date de création
            Check(
                lambda df: (
                    pd.to_datetime(df["post_modified"], errors="coerce")
                    >= pd.to_datetime(df["post_date"], errors="coerce")
                )
                | pd.to_datetime(df["post_modified"], errors="coerce").isna()
                | pd.to_datetime(df["post_date"], errors="coerce").isna(),
                name="coherence_post_modified_superieur_post_date",
            ),
        ],
        strict=False,
        coerce=False,
    )

    # =========================================================================
    # 4. EXÉCUTION DES VALIDATIONS INTRA-FICHIERS
    # =========================================================================
    jeux_de_donnees = [
        ("erp.xlsx", erp, schema_erp),
        ("liaison.xlsx", liaison, schema_liaison),
        ("web.xlsx", web, schema_web),
    ]

    for nom_fichier, df, schema in jeux_de_donnees:
        try:
            schema.validate(df, lazy=True)
        except SchemaErrors as err:
            anomalies.extend(_extraire_anomalies(err, nom_fichier))

    # =========================================================================
    # 5. VALIDATION INTER-FICHIERS (INTÉGRITÉ RÉFÉRENTIELLE AVEC PANDERA)
    # =========================================================================
    erp_ids = (
        set(erp["product_id"].dropna().unique())
        if "product_id" in erp.columns
        else set()
    )
    liaison_pids = (
        set(liaison["product_id"].dropna().unique())
        if "product_id" in liaison.columns
        else set()
    )
    liaison_web_ids = (
        set(liaison["id_web"].dropna().astype(str).unique())
        if "id_web" in liaison.columns
        else set()
    )
    web_skus = (
        set(web["sku"].dropna().astype(str).unique())
        if "sku" in web.columns
        else set()
    )

    # 5a. ERP -> LIAISON : Tout product_id de l'ERP doit exister dans liaison
    if "product_id" in erp.columns:
        schema_ref_erp = DataFrameSchema(
            columns={
                "product_id": Column(
                    object,
                    checks=Check(
                        lambda s: s.isna() | s.isin(liaison_pids),
                        name="integrite_product_id_absent_de_liaison",
                    ),
                    nullable=True,
                )
            }
        )
        try:
            schema_ref_erp.validate(erp, lazy=True)
        except SchemaErrors as err:
            anomalies.extend(_extraire_anomalies(err, "erp.xlsx"))

    # 5b. LIAISON -> ERP & WEB : Clés étrangères dans la table de liaison
    cols_ref_liaison = {}
    if "product_id" in liaison.columns:
        cols_ref_liaison["product_id"] = Column(
            object,
            checks=Check(
                lambda s: s.isna() | s.isin(erp_ids),
                name="integrite_product_id_absent_de_erp",
            ),
            nullable=True,
        )
    if "id_web" in liaison.columns:
        cols_ref_liaison["id_web"] = Column(
            object,
            checks=Check(
                lambda s: s.isna() | s.astype(str).isin(web_skus),
                name="integrite_id_web_absent_de_web",
            ),
            nullable=True,
        )
    if cols_ref_liaison:
        try:
            DataFrameSchema(columns=cols_ref_liaison).validate(liaison, lazy=True)
        except SchemaErrors as err:
            anomalies.extend(_extraire_anomalies(err, "liaison.xlsx"))

    # 5c. WEB -> LIAISON : Tout SKU présent dans web doit être référencé dans liaison
    if "sku" in web.columns:
        schema_ref_web = DataFrameSchema(
            columns={
                "sku": Column(
                    object,
                    checks=Check(
                        lambda s: s.isna() | s.astype(str).isin(liaison_web_ids),
                        name="integrite_sku_absent_de_liaison",
                    ),
                    nullable=True,
                )
            }
        )
        try:
            schema_ref_web.validate(web, lazy=True)
        except SchemaErrors as err:
            anomalies.extend(_extraire_anomalies(err, "web.xlsx"))

    # =========================================================================
    # 6. FORMATAGE DU DATAFRAME DE SORTIE
    # =========================================================================
    colonnes_sortie = ["fichier", "regle", "colonne", "index_ligne", "valeur"]
    if not anomalies:
        return pd.DataFrame(columns=colonnes_sortie)

    df_anomalies = pd.DataFrame(anomalies)[colonnes_sortie]
    return df_anomalies.sort_values(
        by=["fichier", "index_ligne", "colonne", "regle"], ignore_index=True
    )

```