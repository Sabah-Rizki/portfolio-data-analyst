import pandas as pd
import numpy as np
import pandera as pa
from pandera.errors import SchemaErrors


def _normaliser_cle(serie: pd.Series) -> pd.Series:
    """
    Normalise les clés mixtes (id_web, sku, product_id) lues depuis Excel.
    Gère le cas classique où pandas lit un entier comme un float (ex: 15298.0 -> '15298')
    en raison de la présence de valeurs nulles (NaN) ou de texte dans la colonne.
    """
    s = serie.dropna().astype(str).str.strip()
    return s.str.replace(r"^(-?\d+)\.0$", r"\1", regex=True)


def _est_numerique_strict(serie: pd.Series) -> pd.Series:
    """Vérifie si une valeur brute correspond à un identifiant purement numérique (entier)."""
    s = _normaliser_cle(serie)
    return s.str.match(r"^\d+$")


# ==============================================================================
# 1. SCHÉMA DE VALIDATION : ERP (erp.xlsx)
# ==============================================================================
def _creer_schema_erp() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        columns={
            "product_id": pa.Column(
                nullable=False,
                unique=True,
                checks=[
                    # Justification métier : L'identifiant ERP est la clé primaire maître du référentiel article.
                    pa.Check(
                        lambda s: pd.to_numeric(s, errors="coerce").notna() & (pd.to_numeric(s, errors="coerce") > 0),
                        name="[BLOQUANT] erp_product_id_valide",
                        error="product_id doit être un entier strictement positif",
                    )
                ],
            ),
            "onsale_web": pa.Column(
                nullable=False,
                checks=[
                    # Justification métier : Indicateur binaire servant à déclencher la synchronisation vers WooCommerce.
                    pa.Check.isin(
                        [0, 1],
                        name="[BLOQUANT] erp_onsale_web_binaire",
                        error="onsale_web doit valoir exclusivement 0 ou 1",
                    )
                ],
            ),
            "price": pa.Column(
                nullable=False,
                checks=[
                    # Justification métier : Un prix négatif ou nul sur le nouvel ERP entraînerait des ventes à 0€ ou des rejets comptables.
                    pa.Check(
                        lambda s: pd.to_numeric(s, errors="coerce") > 0,
                        name="[BLOQUANT] erp_price_strictement_positif",
                        error="Le prix de vente HT doit être strictement supérieur à 0",
                    ),
                    # Justification métier : BottleNeck vend des grands crus et vieux spiritueux (un prix élevé est possible),
                    # mais un tarif > 1000€ HT nécessite une vérification humaine pour écarter une erreur de saisie (ex: virgule décalée).
                    pa.Check(
                        lambda s: pd.to_numeric(s, errors="coerce") <= 1000,
                        name="[ALERTE] erp_price_seuil_grand_cru",
                        error="Prix HT > 1000€ : à faire confirmer par le métier (grand cru ou erreur de saisie ?)",
                    ),
                ],
            ),
            "purchase_price": pa.Column(
                nullable=False,
                checks=[
                    # Justification métier : Le coût d'achat HT est indispensable au calcul de la marge brute et à la valorisation du stock.
                    pa.Check(
                        lambda s: pd.to_numeric(s, errors="coerce") > 0,
                        name="[BLOQUANT] erp_purchase_price_strictement_positif",
                        error="Le prix d'achat HT doit être strictement supérieur à 0",
                    )
                ],
            ),
            "stock_quantity": pa.Column(
                nullable=False,
                checks=[
                    # Justification métier : Un stock physique négatif dans l'ERP traduit un écart d'inventaire ou un bug de décrémentation.
                    pa.Check(
                        lambda s: pd.to_numeric(s, errors="coerce") >= 0,
                        name="[BLOQUANT] erp_stock_quantity_non_negatif",
                        error="La quantité en stock ne peut pas être négative",
                    )
                ],
            ),
            "stock_status": pa.Column(
                nullable=False,
                checks=[
                    # Justification métier : Le nouvel ERP n'accepte que les deux statuts normalisés pour gérer la disponibilité.
                    pa.Check.isin(
                        ["instock", "outofstock"],
                        name="[BLOQUANT] erp_stock_status_domaine",
                        error="stock_status doit être 'instock' ou 'outofstock'",
                    )
                ],
            ),
        },
        checks=[
            # Justification métier : Règle de gestion explicite. Si stock_status = 'instock' alors que stock_quantity = 0,
            # le site risque de vendre un produit indisponible.
            pa.Check(
                lambda df: (
                    ((pd.to_numeric(df["stock_quantity"], errors="coerce") > 0) & (df["stock_status"] == "instock"))
                    | ((pd.to_numeric(df["stock_quantity"], errors="coerce") == 0) & (df["stock_status"] == "outofstock"))
                ),
                name="[BLOQUANT] erp_coherence_stock_quantite_statut",
                error="Incohérence entre stock_quantity (>0 vs ==0) et stock_status ('instock' vs 'outofstock')",
            ),
            # Justification métier : Vendre à perte (prix de vente HT < prix d'achat HT) est interdit en France (hors liquidation)
            # et détruit la marge de BottleNeck.
            pa.Check(
                lambda df: pd.to_numeric(df["price"], errors="coerce") >= pd.to_numeric(df["purchase_price"], errors="coerce"),
                name="[BLOQUANT] erp_marge_brute_positive",
                error="Vente à perte détectée : price (PV HT) est inférieur à purchase_price (PA HT)",
            ),
            # Justification métier : Un coefficient multiplicateur > 5 entre l'achat et la vente est atypique en cavisterie ;
            # cela signale souvent une inversion de colonnes ou une erreur d'unité (carton de 6 vs bouteille unitaire).
            pa.Check(
                lambda df: pd.to_numeric(df["price"], errors="coerce") <= (pd.to_numeric(df["purchase_price"], errors="coerce") * 5.0),
                name="[ALERTE] erp_taux_marge_atypique",
                error="Prix de vente > 5x le prix d'achat : vérifier l'unité de conditionnement (bouteille vs carton)",
            ),
        ],
        coerce=False,
        strict=False,
    )


# ==============================================================================
# 2. SCHÉMA DE VALIDATION : WEB / WOOCOMMERCE (web.xlsx)
# ==============================================================================
def _creer_schema_web() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        columns={
            "sku": pa.Column(
                nullable=True,  # Géré par un Check dédié pour personnaliser le nom de la règle
                checks=[
                    # Justification métier : Dans WooCommerce, un produit sans SKU ne peut pas être rattaché à l'ERP.
                    pa.Check(
                        lambda s: s.notna() & (s.astype(str).str.strip() != ""),
                        ignore_na=False,
                        name="[BLOQUANT] web_sku_renseigne",
                        error="Le code article (sku) est manquant sur la ligne web",
                    ),
                    # Justification métier : Le dictionnaire précise que le SKU est "normalement numérique".
                    # Les SKU texte (ex: 'bon-cadeau-25', '13127-1') doivent être validés ou nettoyés avant migration.
                    pa.Check(
                        _est_numerique_strict,
                        ignore_na=True,
                        name="[ALERTE] web_sku_format_numerique",
                        error="Le SKU contient des caractères non numériques (ex: bon cadeau ou déclinaison)",
                    ),
                ],
            ),
            "post_type": pa.Column(
                nullable=False,
                checks=[
                    # Justification métier : L'export ne doit contenir que les fiches produits ('product') et leurs médias ('attachment').
                    pa.Check.isin(
                        ["product", "attachment"],
                        name="[BLOQUANT] web_post_type_domaine",
                        error="post_type doit appartenir à ['product', 'attachment']",
                    )
                ],
            ),
            "total_sales": pa.Column(
                nullable=True,
                checks=[
                    # Justification métier : Le cumul des ventes ne peut pas être négatif.
                    pa.Check(
                        lambda s: pd.to_numeric(s, errors="coerce") >= 0,
                        ignore_na=True,
                        name="[BLOQUANT] web_total_sales_positif",
                        error="total_sales ne peut pas être négatif",
                    )
                ],
            ),
            "average_rating": pa.Column(
                nullable=True,
                checks=[
                    # Justification métier : Les notes clients WooCommerce sont bornées entre 0 et 5 étoiles.
                    pa.Check(
                        lambda s: pd.to_numeric(s, errors="coerce").between(0, 5),
                        ignore_na=True,
                        name="[ALERTE] web_average_rating_bornes",
                        error="La note moyenne (average_rating) doit être comprise entre 0 et 5",
                    )
                ],
            ),
            "rating_count": pa.Column(
                nullable=True,
                checks=[
                    # Justification métier : Le nombre d'avis clients ne peut pas être négatif.
                    pa.Check(
                        lambda s: pd.to_numeric(s, errors="coerce") >= 0,
                        ignore_na=True,
                        name="[ALERTE] web_rating_count_positif",
                        error="Le nombre d'avis (rating_count) ne peut pas être négatif",
                    )
                ],
            ),
        },
        checks=[
            # Justification métier : Une fiche produit ('product') doit obligatoirement avoir un titre et une famille (product_type)
            # pour être affichée sur le site e-commerce.
            pa.Check(
                lambda df: ~(
                    (df["post_type"] == "product")
                    & (df["post_title"].isna() | (df["post_title"].astype(str).str.strip() == "") | df["product_type"].isna())
                ),
                name="[BLOQUANT] web_fiche_produit_complete",
                error="Une ligne avec post_type='product' doit avoir un post_title et un product_type renseignés",
            ),
            # Justification métier : Il ne doit exister qu'une seule fiche produit ('product') par SKU pour éviter
            # de dupliquer les lignes lors des jointures avec l'ERP (qui fausseraient le calcul du chiffre d'affaires).
            pa.Check(
                lambda df: ~(
                    df["sku"].notna()
                    & (df["post_type"] == "product")
                    & df.assign(_sku_norm=_normaliser_cle(df["sku"])).duplicated(subset=["_sku_norm", "post_type"], keep=False)
                ),
                name="[BLOQUANT] web_unicite_couple_sku_product",
                error="Doublon de fiche 'product' pour un même SKU dans web.xlsx",
            ),
            # Justification métier : Le dictionnaire stipule que chaque produit apparaît normalement sur 2 lignes :
            # 1 'product' et 1 'attachment' (son image). S'il manque l'image ou s'il y a plus de 2 lignes, le métier doit vérifier.
            pa.Check(
                lambda df: (
                    df["sku"].isna()
                    | _normaliser_cle(df["sku"]).isin(
                        df.dropna(subset=["sku"])
                        .assign(_sku_norm=_normaliser_cle(df["sku"]))
                        .groupby("_sku_norm")["post_type"]
                        .filter(lambda g: len(g) == 2 and set(g) == {"product", "attachment"})
                        .index.map(lambda idx: _normaliser_cle(df.loc[[idx], "sku"]).iloc[0])
                    )
                ),
                name="[ALERTE] web_structure_paire_product_attachment",
                error="Le SKU n'a pas exactement 1 ligne 'product' et 1 ligne 'attachment' (image manquante ou doublon)",
            ),
            # Justification métier : Dans WordPress, une ligne entièrement vide (hormis d'éventuels champs techniques à 0/NaN)
            # mais avec un post_type ou non est une ligne fantôme issue d'une suppression incomplète en base.
            pa.Check(
                lambda df: ~(df["sku"].isna() & df["post_title"].isna() & df["post_name"].isna()),
                name="[BLOQUANT] web_ligne_fantome_vide",
                error="Ligne fantôme dans l'export WooCommerce (sku, post_title et post_name tous vides)",
            ),
        ],
        coerce=False,
        strict=False,
    )


# ==============================================================================
# 3. SCHÉMA DE VALIDATION : LIAISON (liaison.xlsx)
# ==============================================================================
def _creer_schema_liaison() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        columns={
            "product_id": pa.Column(
                nullable=False,
                unique=True,
                checks=[
                    # Justification métier : La table de liaison étant maintenue à la main, il faut garantir qu'aucun
                    # product_id n'a été saisi deux fois ou oublié.
                    pa.Check(
                        lambda s: pd.to_numeric(s, errors="coerce").notna() & (pd.to_numeric(s, errors="coerce") > 0),
                        name="[BLOQUANT] liaison_product_id_valide",
                        error="product_id dans liaison.xlsx doit être un entier positif unique",
                    )
                ],
            ),
            "id_web": pa.Column(
                nullable=True,  # Peut être vide pour un produit pas encore mis en ligne
                checks=[
                    # Justification métier : Deux produits ERP distincts ne peuvent pas pointer vers le même SKU web,
                    # sinon les stocks et prix des deux produits s'écraseraient mutuellement sur le site.
                    pa.Check(
                        lambda s: ~_normaliser_cle(s).duplicated(keep=False),
                        ignore_na=True,
                        name="[BLOQUANT] liaison_id_web_unique",
                        error="Doublon d'id_web dans liaison.xlsx : deux product_id pointent vers le même SKU",
                    ),
                    # Justification métier : Comme pour web.sku, id_web est normalement numérique. Une valeur texte
                    # dans un fichier tenu à la main signale souvent une note interne ou un code atypique.
                    pa.Check(
                        _est_numerique_strict,
                        ignore_na=True,
                        name="[ALERTE] liaison_id_web_format_numerique",
                        error="id_web non numérique dans la table de liaison",
                    ),
                ],
            ),
        },
        coerce=False,
        strict=False,
    )


# ==============================================================================
# 4. SCHÉMAS DE VALIDATION INTER-FICHIERS (INTÉGRITÉ RÉFÉRENTIELLE & MÉTIER)
# ==============================================================================
def _valider_inter_fichiers(erp: pd.DataFrame, web: pd.DataFrame, liaison: pd.DataFrame) -> list[dict]:
    """
    Exécute les contrôles croisés entre les 3 fichiers via des DataFrameSchemas Pandera
    appliqués sur des vues enrichies (conservant l'index d'origine du fichier contrôlé).
    """
    anomalies_inter = []

    erp_ids = set(_normaliser_cle(erp["product_id"])) if "product_id" in erp else set()
    liaison_erp_ids = set(_normaliser_cle(liaison["product_id"])) if "product_id" in liaison else set()
    liaison_web_ids = set(_normaliser_cle(liaison["id_web"])) if "id_web" in liaison else set()
    web_skus = set(_normaliser_cle(web["sku"])) if "sku" in web else set()

    # Map id_web -> product_id pour vérifier le rattachement de bout en bout
    map_web_to_erp = {}
    if {"product_id", "id_web"}.issubset(liaison.columns):
        df_l_clean = liaison.dropna(subset=["id_web", "product_id"])
        map_web_to_erp = dict(zip(_normaliser_cle(df_l_clean["id_web"]), _normaliser_cle(df_l_clean["product_id"])))

    # Map product_id -> id_web pour vérifier les produits en vente sur le web
    map_erp_to_web = {}
    if {"product_id", "id_web"}.issubset(liaison.columns):
        df_l_clean = liaison.dropna(subset=["id_web", "product_id"])
        map_erp_to_web = dict(zip(_normaliser_cle(df_l_clean["product_id"]), _normaliser_cle(df_l_clean["id_web"])))

    # --- A. Contrôles inter-fichiers portés par ERP ---
    schema_inter_erp = pa.DataFrameSchema(
        columns={
            "product_id": pa.Column(
                nullable=True,
                checks=[
                    # Justification métier : Tout article de l'ERP devrait être référencé dans la table de liaison.
                    pa.Check(
                        lambda s: s.map(lambda x: _normaliser_cle(pd.Series([x])).iloc[0] in liaison_erp_ids if pd.notna(x) else False),
                        name="[BLOQUANT] inter_erp_absent_de_liaison",
                        error="product_id présent dans erp.xlsx mais absent de liaison.xlsx",
                    ),
                    # Justification métier : Si onsale_web == 1, le produit est censé être vendu en ligne :
                    # il doit impérativement avoir un id_web renseigné dans liaison.xlsx.
                    pa.Check(
                        lambda s: pd.Series(
                            [
                                not (onsale == 1 and (_normaliser_cle(pd.Series([pid])).iloc[0] not in map_erp_to_web))
                                for pid, onsale in zip(s, erp["onsale_web"])
                            ],
                            index=s.index,
                        ),
                        name="[BLOQUANT] inter_erp_onsale_sans_id_web",
                        error="Produit marqué onsale_web=1 dans l'ERP mais sans id_web dans liaison.xlsx",
                    ),
                    # Justification métier : Si onsale_web == 1 et qu'un id_web existe, ce SKU doit exister dans l'export WooCommerce (web.xlsx).
                    pa.Check(
                        lambda s: pd.Series(
                            [
                                not (
                                    onsale == 1
                                    and (_normaliser_cle(pd.Series([pid])).iloc[0] in map_erp_to_web)
                                    and (map_erp_to_web[_normaliser_cle(pd.Series([pid])).iloc[0]] not in web_skus)
                                )
                                for pid, onsale in zip(s, erp["onsale_web"])
                            ],
                            index=s.index,
                        ),
                        name="[BLOQUANT] inter_erp_onsale_absent_du_web",
                        error="Produit marqué onsale_web=1 dans l'ERP mais son SKU est introuvable dans web.xlsx",
                    ),
                    # Justification métier : Si onsale_web == 0 mais que le produit possède un id_web actif sur le site,
                    # il s'agit d'une désynchronisation (ancien produit retiré de la vente ou oubli d'activation).
                    pa.Check(
                        lambda s: pd.Series(
                            [
                                not (
                                    onsale == 0
                                    and (_normaliser_cle(pd.Series([pid])).iloc[0] in map_erp_to_web)
                                    and (map_erp_to_web[_normaliser_cle(pd.Series([pid])).iloc[0]] in web_skus)
                                )
                                for pid, onsale in zip(s, erp["onsale_web"])
                            ],
                            index=s.index,
                        ),
                        name="[ALERTE] inter_erp_offsale_mais_present_web",
                        error="Produit marqué onsale_web=0 dans l'ERP mais pourtant présent dans l'export web.xlsx",
                    ),
                ],
            )
        },
        coerce=False,
    )
    anomalies_inter.extend(_executer_validation(erp, schema_inter_erp, "erp.xlsx"))

    # --- B. Contrôles inter-fichiers portés par LIAISON ---
    schema_inter_liaison = pa.DataFrameSchema(
        columns={
            "product_id": pa.Column(
                nullable=True,
                checks=[
                    # Justification métier : Une ligne de liaison ne doit pas référencer un product_id inexistant dans l'ERP.
                    pa.Check(
                        lambda s: s.map(lambda x: _normaliser_cle(pd.Series([x])).iloc[0] in erp_ids if pd.notna(x) else True),
                        name="[BLOQUANT] inter_liaison_product_id_orphelin",
                        error="product_id de liaison.xlsx introuvable dans erp.xlsx",
                    )
                ],
            ),
            "id_web": pa.Column(
                nullable=True,
                checks=[
                    # Justification métier : Un id_web renseigné dans liaison mais absent de web.xlsx correspond
                    # à un produit créé dans l'ERP/liaison mais jamais publié ou supprimé de WooCommerce.
                    pa.Check(
                        lambda s: s.map(lambda x: _normaliser_cle(pd.Series([x])).iloc[0] in web_skus if pd.notna(x) else True),
                        ignore_na=True,
                        name="[ALERTE] inter_liaison_id_web_absent_du_web",
                        error="id_web renseigné dans liaison.xlsx mais absent de web.xlsx",
                    )
                ],
            ),
        },
        coerce=False,
    )
    anomalies_inter.extend(_executer_validation(liaison, schema_inter_liaison, "liaison.xlsx"))

    # --- C. Contrôles inter-fichiers portés par WEB ---
    schema_inter_web = pa.DataFrameSchema(
        columns={
            "sku": pa.Column(
                nullable=True,
                checks=[
                    # Justification métier : Tout SKU vendu sur le site doit être rattaché à l'ERP via liaison.xlsx,
                    # sinon ses ventes et son stock ne remontent pas en comptabilité.
                    pa.Check(
                        lambda s: s.map(
                            lambda x: (
                                _normaliser_cle(pd.Series([x])).iloc[0] in map_web_to_erp
                                and map_web_to_erp[_normaliser_cle(pd.Series([x])).iloc[0]] in erp_ids
                            )
                            if pd.notna(x)
                            else True
                        ),
                        ignore_na=True,
                        name="[BLOQUANT] inter_web_sku_orphelin_dans_erp",
                        error="SKU présent sur le site (web.xlsx) mais non rattaché à un product_id valide dans liaison/erp",
                    )
                ],
            )
        },
        coerce=False,
    )
    anomalies_inter.extend(_executer_validation(web, schema_inter_web, "web.xlsx"))

    return anomalies_inter


# ==============================================================================
# 5. MOTEUR D'EXÉCUTION PANDERA ET FORMATAGE DES ANOMALIES
# ==============================================================================
def _executer_validation(df: pd.DataFrame, schema: pa.DataFrameSchema, nom_fichier: str) -> list[dict]:
    """
    Valide un DataFrame avec `lazy=True` et convertit le `failure_cases` de Pandera
    au format standard attendu : fichier, regle, colonne, index_ligne, valeur.
    """
    anomalies = []
    try:
        schema.validate(df, lazy=True)
    except SchemaErrors as err:
        fc = err.failure_cases.copy()

        # Mapping des colonnes principales associées aux checks au niveau DataFrame (schema_context == "DataFrameSchema")
        colonnes_par_regle_df = {
            "[BLOQUANT] erp_coherence_stock_quantite_statut": "stock_status",
            "[BLOQUANT] erp_marge_brute_positive": "price",
            "[ALERTE] erp_taux_marge_atypique": "price",
            "[BLOQUANT] web_fiche_produit_complete": "post_title",
            "[BLOQUANT] web_unicite_couple_sku_product": "sku",
            "[ALERTE] web_structure_paire_product_attachment": "sku",
            "[BLOQUANT] web_ligne_fantome_vide": "sku",
        }

        # Lorsque Pandera évalue un Check au niveau DataFrame (lambda df: Series[bool]),
        # il génère une ligne dans failure_cases PAR colonne du DataFrame pour chaque index en échec.
        # On déduplique donc sur (check, index) pour ne rapporter qu'une seule anomalie métier par ligne en échec.
        masque_df_check = fc["schema_context"] == "DataFrameSchema"
        fc_col = fc[~masque_df_check]
        fc_df = fc[masque_df_check].drop_duplicates(subset=["check", "index"], keep="first")

        for _, row in pd.concat([fc_col, fc_df], ignore_index=True).iterrows():
            regle = str(row["check"])
            idx = row["index"]

            if row["schema_context"] == "DataFrameSchema":
                col_cible = colonnes_par_regle_df.get(regle, str(row["column"]))
                valeur = df.loc[idx, col_cible] if (idx in df.index and col_cible in df.columns) else row["failure_case"]
            else:
                col_cible = str(row["column"])
                valeur = df.loc[idx, col_cible] if (idx in df.index and col_cible in df.columns) else row["failure_case"]

            # Harmonisation des règles natives Pandera (nullable, unique) avec le préfixe de sévérité
            if regle in ("not_nullable", "field_uniqueness"):
                regle = f"[BLOQUANT] {nom_fichier.split('.')[0]}_{col_cible}_{regle}"

            anomalies.append(
                {
                    "fichier": nom_fichier,
                    "regle": regle,
                    "colonne": col_cible,
                    "index_ligne": idx,
                    "valeur": valeur,
                }
            )

    return anomalies


def valider(erp: pd.DataFrame, web: pd.DataFrame, liaison: pd.DataFrame) -> pd.DataFrame:
    """
    Valide les trois DataFrames bruts (erp, web, liaison) sans les modifier et collecte
    l'intégralité des anomalies (bloquantes et alertes) en une seule passe.

    Paramètres
    ----------
    erp : pd.DataFrame
        Export brut de erp.xlsx
    web : pd.DataFrame
        Export brut de web.xlsx
    liaison : pd.DataFrame
        Export brut de liaison.xlsx

    Retourne
    --------
    pd.DataFrame
        DataFrame contenant les colonnes : ['fichier', 'regle', 'colonne', 'index_ligne', 'valeur']
    """
    colonnes_attendues = ["fichier", "regle", "colonne", "index_ligne", "valeur"]
    toutes_anomalies: list[dict] = []

    # 1. Contrôles intra-fichier
    toutes_anomalies.extend(_executer_validation(erp, _creer_schema_erp(), "erp.xlsx"))
    toutes_anomalies.extend(_executer_validation(web, _creer_schema_web(), "web.xlsx"))
    toutes_anomalies.extend(_executer_validation(liaison, _creer_schema_liaison(), "liaison.xlsx"))

    # 2. Contrôles inter-fichiers (cohérence des clés de jointure et statuts de publication)
    toutes_anomalies.extend(_valider_inter_fichiers(erp, web, liaison))

    if not toutes_anomalies:
        return pd.DataFrame(columns=colonnes_attendues)

    df_anomalies = pd.DataFrame(toutes_anomalies, columns=colonnes_attendues)

    # Tri déterministe pour faciliter l'audit par les équipes métier
    df_anomalies = (
        df_anomalies.drop_duplicates(subset=["fichier", "regle", "colonne", "index_ligne"])
        .sort_values(by=["fichier", "regle", "index_ligne"], ascending=[True, True, True])
        .reset_index(drop=True)
    )

    return df_anomalies

