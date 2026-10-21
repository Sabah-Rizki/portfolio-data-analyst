La fonction `valider(erp, web, liaison)` ci-dessous centralise les contrôles intra-fichiers et inter-fichiers via **Pandera** en mode `lazy=True` afin de capturer l'intégralité des anomalies sans interrompre l'exécution. Les règles distinguent les erreurs critiques (`[BLOQUANT]`) des anomalies métier à soumettre aux équipes (`[ALERTE]`) directement dans l'intitulé de la règle, tout en respectant strictement la structure de sortie attendue (`fichier`, `regle`, `colonne`, `index_ligne`, `valeur`).

```python
import pandas as pd
import numpy as np
import pandera as pa
from pandera.errors import SchemaErrors


def _normaliser_id(serie: pd.Series) -> pd.Series:
    """
    Normalise les identifiants (sku, id_web, product_id) lus depuis Excel sans modifier
    les DataFrames originaux. Convertit par exemple 15298.0 (float Excel) ou ' 15298 ' en '15298',
    et unifie toutes les valeurs manquantes en np.nan.
    """
    s = serie.dropna().astype(str).str.strip()
    s = s.str.replace(r"\.0$", "", regex=True)
    s = s.replace({"": np.nan, "nan": np.nan, "None": np.nan, "<NA>": np.nan})
    return s.reindex(serie.index)


def _extraire_anomalies_pandera(
    nom_fichier: str, df_source: pd.DataFrame, err: SchemaErrors
) -> list[dict]:
    """
    Transforme l'objet SchemaErrors généré par Pandera (lazy=True) en liste de dictionnaires
    au format exact attendu : fichier, regle, colonne, index_ligne, valeur.
    """
    anomalies = []
    fc = err.failure_cases

    for _, row in fc.iterrows():
        idx = row["index"]
        col = row["column"]
        check_name = str(row["check"])
        failure_case = row["failure_case"]

        # Lorsqu'un check porte sur le DataFrame entier ou que la colonne n'est pas renseignée
        if pd.isna(col) or col is None:
            col = "__dataframe__"

        # Si l'erreur concerne un index précis et une colonne précise, on récupère la vraie valeur brute
        # (car sur les checks DataFrame-level, failure_case renvoie souvent False au lieu de la valeur)
        if pd.notna(idx) and idx in df_source.index:
            if col in df_source.columns:
                val = df_source.loc[idx, col]
            else:
                val = failure_case
            idx_out = int(idx) if isinstance(idx, (int, np.integer)) else idx
        else:
            # Erreur globale de schéma (ex: colonne manquante dans l'export)
            idx_out = -1
            val = failure_case

        anomalies.append(
            {
                "fichier": nom_fichier,
                "regle": check_name,
                "colonne": str(col),
                "index_ligne": idx_out,
                "valeur": val,
            }
        )
    return anomalies


def valider(
    erp: pd.DataFrame, web: pd.DataFrame, liaison: pd.DataFrame
) -> pd.DataFrame:
    """
    Exécute l'ensemble des contrôles de qualité des données (intra-fichiers et inter-fichiers)
    sur les exports bruts ERP, Web et Liaison pour BottleNeck.
    """
    anomalies_collectees: list[dict] = []

    # =========================================================================
    # 1. SCHÉMA PANDERA : FICHIER ERP (erp.xlsx)
    # =========================================================================
    schema_erp = pa.DataFrameSchema(
        columns={
            "product_id": pa.Column(
                nullable=False,
                unique=True,
                coerce=False,
                checks=[
                    # Justification métier : L'identifiant ERP est la clé primaire du référentiel produit.
                    # Un format non entier ou négatif empêche la migration vers le nouvel ERP.
                    pa.Check(
                        lambda s: s.dropna().apply(
                            lambda x: isinstance(x, (int, np.integer))
                            or (isinstance(x, float) and x.is_integer())
                        )
                        & (s.dropna() > 0),
                        name="[BLOQUANT] ERP_PRODUCT_ID_ENTIER_POSITIF : product_id doit être un entier strictement positif",
                    )
                ],
            ),
            "onsale_web": pa.Column(
                nullable=False,
                coerce=False,
                checks=[
                    # Justification métier : Ce flag pilote la synchronisation e-commerce.
                    # Toute valeur autre que 0 ou 1 provoque un comportement imprévisible du connecteur Web.
                    pa.Check.isin(
                        [0, 1],
                        name="[BLOQUANT] ERP_ONSALE_WEB_DOMAINE : onsale_web doit valoir strictement 0 ou 1",
                    )
                ],
            ),
            "price": pa.Column(
                nullable=False,
                coerce=False,
                checks=[
                    # Justification métier : Vendre à un prix nul ou négatif entraîne une perte financière directe
                    # et constitue un motif d'annulation de vente (prix dérisoire / erreur d'étiquetage).
                    pa.Check.gt(
                        0,
                        name="[BLOQUANT] ERP_PRICE_STRICTEMENT_POSITIF : Le prix de vente HT doit être > 0 €",
                    ),
                    # Justification métier : BottleNeck vend des grands crus et vieux spiritueux (prix élevé normal),
                    # mais une saisie erronée (ex: centimes non séparés) peut créer un prix aberrant (> 5 000 €).
                    pa.Check.le(
                        5000,
                        name="[ALERTE] ERP_PRICE_ELEVE_PREMIUM : Prix HT > 5 000 € à faire confirmer par le métier (Grand Cru / Spiritueux rare ?)",
                    ),
                ],
            ),
            "purchase_price": pa.Column(
                nullable=False,
                coerce=False,
                checks=[
                    # Justification métier : Le coût d'achat HT est indispensable au calcul de la marge brute et à la valorisation du stock.
                    pa.Check.gt(
                        0,
                        name="[BLOQUANT] ERP_PURCHASE_PRICE_POSITIF : Le prix d'achat HT doit être > 0 €",
                    )
                ],
            ),
            "stock_quantity": pa.Column(
                nullable=False,
                coerce=False,
                checks=[
                    # Justification métier : Les bouteilles et huiles sont des biens physiques insécables ;
                    # le stock doit obligatoirement être un nombre entier.
                    pa.Check(
                        lambda s: s.dropna().apply(
                            lambda x: isinstance(x, (int, np.integer))
                            or (isinstance(x, float) and x.is_integer())
                        ),
                        name="[BLOQUANT] ERP_STOCK_QTY_ENTIER : La quantité en stock doit être un nombre entier",
                    ),
                    # Justification métier : Un stock négatif traduit un écart d'inventaire ou une vente à découvert non régularisée.
                    pa.Check.ge(
                        0,
                        name="[BLOQUANT] ERP_STOCK_QTY_NON_NEGATIF : La quantité en stock ne peut pas être négative (< 0)",
                    ),
                ],
            ),
            "stock_status": pa.Column(
                nullable=False,
                coerce=False,
                checks=[
                    # Justification métier : Le statut de stock ne peut prendre que les deux valeurs reconnues par le système.
                    pa.Check.isin(
                        ["instock", "outofstock"],
                        name="[BLOQUANT] ERP_STOCK_STATUS_DOMAINE : stock_status doit être 'instock' ou 'outofstock'",
                    ),
                    # Justification métier : Règle de gestion stricte du dictionnaire ('instock' si stock_quantity > 0, 'outofstock' sinon).
                    # Une désynchronisation bloque des ventes disponibles ou permet de vendre un produit en rupture.
                    pa.Check(
                        lambda s: (
                            (
                                (erp.loc[s.index, "stock_quantity"] > 0)
                                & (s == "instock")
                            )
                            | (
                                (erp.loc[s.index, "stock_quantity"] <= 0)
                                & (s == "outofstock")
                            )
                        ),
                        name="[BLOQUANT] ERP_COHERENCE_STOCK_QTY_STATUS : Incohérence entre stock_quantity et stock_status",
                    ),
                ],
            ),
        },
        checks=[
            # Justification métier : La revente à perte (prix de vente HT < prix d'achat HT) est illégale en France
            # (hors liquidation réglementée) et détruit la marge commerciale.
            pa.Check(
                lambda df: (df["price"] >= df["purchase_price"])
                | df["price"].isna()
                | df["purchase_price"].isna(),
                name="[BLOQUANT] ERP_MARGE_NEGATIVE : Prix de vente HT (price) inférieur au prix d'achat HT (purchase_price)",
            ),
            # Justification métier : Un taux de marge supérieur à 90% (price > 10 * purchase_price) révèle souvent
            # une erreur d'unité dans le prix d'achat (prix à la bouteille vs prix au carton de 6 ou 12).
            pa.Check(
                lambda df: (df["price"] <= df["purchase_price"] * 10)
                | df["price"].isna()
                | df["purchase_price"].isna(),
                name="[ALERTE] ERP_MARGE_ATYPIQUE : Prix de vente HT supérieur à 10x le prix d'achat HT (erreur d'unité carton/bouteille ?)",
            ),
        ],
        strict=False,
    )

    try:
        schema_erp.validate(erp, lazy=True)
    except SchemaErrors as err:
        anomalies_collectees.extend(_extraire_anomalies_pandera("erp.xlsx", erp, err))

    # =========================================================================
    # 2. SCHÉMA PANDERA : FICHIER LIAISON (liaison.xlsx)
    # =========================================================================
    def _check_unicite_id_web(s: pd.Series) -> pd.Series:
        norm = _normaliser_id(s)
        return ~norm.duplicated(keep=False) | norm.isna()

    def _check_format_id_web(s: pd.Series) -> pd.Series:
        norm = _normaliser_id(s)
        return norm.isna() | norm.str.match(r"^\d+$")

    schema_liaison = pa.DataFrameSchema(
        columns={
            "product_id": pa.Column(
                nullable=False,
                unique=True,
                coerce=False,
                checks=[
                    # Justification métier : Chaque produit ERP ne doit figurer qu'une seule fois dans la table de liaison.
                    pa.Check(
                        lambda s: s.dropna().apply(
                            lambda x: isinstance(x, (int, np.integer))
                            or (isinstance(x, float) and x.is_integer())
                        )
                        & (s.dropna() > 0),
                        name="[BLOQUANT] LIAISON_PRODUCT_ID_VALIDE : product_id doit être un entier strictement positif et unique",
                    )
                ],
            ),
            "id_web": pa.Column(
                nullable=True,  # Peut être vide pour un produit pas encore mis en ligne
                coerce=False,
                checks=[
                    # Justification métier : Si deux produits ERP pointent vers le même id_web (SKU),
                    # l'écrasement mutuel des stocks et des prix sur le site est garanti (relation 1-1 violée).
                    pa.Check(
                        _check_unicite_id_web,
                        name="[BLOQUANT] LIAISON_ID_WEB_DOUBLON : Un même id_web est rattaché à plusieurs product_id",
                    ),
                    # Justification métier : Le dictionnaire précise que le SKU est normalement numérique
                    # (ex: les valeurs atypiques texte comme 'bon-cadeau-25-euros' ou '13127-1' doivent être signalées).
                    pa.Check(
                        _check_format_id_web,
                        name="[ALERTE] LIAISON_ID_WEB_NON_NUMERIQUE : id_web contient des caractères non numériques",
                    ),
                ],
            ),
        },
        strict=False,
    )

    try:
        schema_liaison.validate(liaison, lazy=True)
    except SchemaErrors as err:
        anomalies_collectees.extend(
            _extraire_anomalies_pandera("liaison.xlsx", liaison, err)
        )

    # =========================================================================
    # 3. SCHÉMA PANDERA : FICHIER WEB (web.xlsx)
    # =========================================================================
    # Pré-calculs vectorisés sur web.xlsx pour les contrôles complexes de structure WooCommerce
    web_Total_Null_Row = web.isna().all(axis=1)
    web_Sku_Norm = (
        _normaliser_id(web["sku"])
        if "sku" in web.columns
        else pd.Series(np.nan, index=web.index)
    )
    web_Post_Type = (
        web["post_type"]
        if "post_type" in web.columns
        else pd.Series(np.nan, index=web.index)
    )

    # Unicité du couple (sku, post_type) pour éviter deux fiches 'product' ou deux 'attachment' pour le même SKU
    dup_sku_post_type = (
        web.assign(_sku_norm=web_Sku_Norm)
        .duplicated(subset=["_sku_norm", "post_type"], keep=False)
        & web_Sku_Norm.notna()
    )

    # Vérification que chaque SKU présent possède exactement 1 ligne 'product' et 1 ligne 'attachment'
    if "sku" in web.columns and "post_type" in web.columns:
        valid_sku_df = web.assign(_sku_norm=web_Sku_Norm).dropna(subset=["_sku_norm"])
        type_counts = (
            valid_sku_df.groupby("_sku_norm")["post_type"]
            .value_counts()
            .unstack(fill_value=0)
        )
        for col_t in ["product", "attachment"]:
            if col_t not in type_counts.columns:
                type_counts[col_t] = 0
        skus_complets = set(
            type_counts[
                (type_counts["product"] == 1) & (type_counts["attachment"] == 1)
            ].index
        )
        has_pair_product_attachment = web_Sku_Norm.isna() | web_Sku_Norm.isin(
            skus_complets
        )
    else:
        has_pair_product_attachment = pd.Series(True, index=web.index)

    schema_web = pa.DataFrameSchema(
        columns={
            "sku": pa.Column(
                nullable=True,  # Géré finement via les checks ci-dessous pour distinguer lignes vides vs produits sans SKU
                coerce=False,
                checks=[
                    # Justification métier : Dans l'export WooCommerce, des lignes totalement vides peuvent se glisser.
                    # Elles polluent les traitements et doivent être purgées ou signalées.
                    pa.Check(
                        lambda s: ~web_Total_Null_Row.loc[s.index],
                        name="[ALERTE] WEB_LIGNE_ENTIEREMENT_VIDE : Ligne fantôme (toutes les colonnes sont nulles) dans l'export WooCommerce",
                    ),
                    # Justification métier : Un produit renseigné (ligne non vide avec un titre/type) sans SKU
                    # est impossible à relier à l'ERP pour mettre à jour ses stocks ou comptabiliser son CA.
                    pa.Check(
                        lambda s: web_Total_Null_Row.loc[s.index]
                        | web_Sku_Norm.loc[s.index].notna(),
                        name="[BLOQUANT] WEB_SKU_MANQUANT_SUR_PRODUIT : Fiche produit active dans WooCommerce mais dépourvue de code SKU",
                    ),
                    # Justification métier : Le code article (SKU) est normalement numérique selon le dictionnaire.
                    pa.Check(
                        lambda s: web_Sku_Norm.loc[s.index].isna()
                        | web_Sku_Norm.loc[s.index].str.match(r"^\d+$"),
                        name="[ALERTE] WEB_SKU_NON_NUMERIQUE : Le SKU contient des caractères non numériques (ex: bon cadeau)",
                    ),
                    # Justification métier : Un même SKU ne peut pas avoir deux lignes 'product' (doublon de fiche produit sur le site).
                    pa.Check(
                        lambda s: ~dup_sku_post_type.loc[s.index],
                        name="[BLOQUANT] WEB_DOUBLON_SKU_POST_TYPE : Doublon détecté sur le couple (sku, post_type)",
                    ),
                    # Justification métier : D'après le dictionnaire, chaque produit apparaît normalement sur 2 lignes :
                    # 'product' (la fiche) et 'attachment' (l'image). S'il manque l'image, le produit s'affiche sans visuel sur le site.
                    pa.Check(
                        lambda s: has_pair_product_attachment.loc[s.index],
                        name="[ALERTE] WEB_PAIRE_PRODUCT_ATTACHMENT_INCOMPLETE : Le SKU ne possède pas exactement 1 ligne 'product' et 1 ligne 'attachment' (image manquante ou fiche orpheline)",
                    ),
                ],
            ),
            "post_type": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : Seuls les types 'product' et 'attachment' sont attendus dans cet export catalogue.
                    pa.Check(
                        lambda s: web_Total_Null_Row.loc[s.index]
                        | s.isin(["product", "attachment"]),
                        name="[BLOQUANT] WEB_POST_TYPE_INVALIDE : post_type doit être 'product' ou 'attachment'",
                    )
                ],
            ),
            "total_sales": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : Le cumul des ventes sert au calcul du chiffre d'affaires Web.
                    # Il ne peut être ni manquant (sur une ligne valide), ni négatif, ni décimal.
                    pa.Check(
                        lambda s: web_Total_Null_Row.loc[s.index]
                        | (
                            s.notna()
                            & (s >= 0)
                            & s.dropna()
                            .apply(
                                lambda x: isinstance(x, (int, np.integer))
                                or (isinstance(x, float) and x.is_integer())
                            )
                            .reindex(s.index, fill_value=False)
                        ),
                        name="[BLOQUANT] WEB_TOTAL_SALES_INVALIDE : total_sales doit être un entier positif ou nul (>= 0)",
                    )
                ],
            ),
            "product_type": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : La famille produit est indispensable pour l'analyse des ventes par catégorie
                    # et la navigation sur le site e-commerce.
                    pa.Check(
                        lambda s: web_Total_Null_Row.loc[s.index]
                        | (s.notna() & (s.astype(str).str.strip() != "")),
                        name="[ALERTE] WEB_PRODUCT_TYPE_MANQUANT : Famille de produit (product_type) non renseignée",
                    ),
                    # Justification métier : Vérification que la famille appartient aux catégories connues du caviste.
                    pa.Check(
                        lambda s: s.isna()
                        | s.isin(
                            [
                                "Vin",
                                "Champagne",
                                "Whisky",
                                "Cognac",
                                "Gin",
                                "Huile d'olive",
                                "Autre",
                            ]
                        ),
                        name="[ALERTE] WEB_PRODUCT_TYPE_ATYPIQUE : Famille de produit non standard à vérifier par le métier",
                    ),
                ],
            ),
            "post_title": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : Un produit sans libellé ne peut pas être identifié par le client sur le site.
                    pa.Check(
                        lambda s: web_Total_Null_Row.loc[s.index]
                        | (s.notna() & (s.astype(str).str.strip() != "")),
                        name="[BLOQUANT] WEB_POST_TITLE_MANQUANT : Le titre du produit (post_title) est vide ou manquant",
                    )
                ],
            ),
            "post_status": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : Contrôle des statuts de publication standards WordPress/WooCommerce.
                    pa.Check(
                        lambda s: web_Total_Null_Row.loc[s.index]
                        | s.isin(["publish", "inherit", "draft", "private", "pending"]),
                        name="[ALERTE] WEB_POST_STATUS_INATTENDU : Statut de publication WordPress inhabituel",
                    )
                ],
            ),
            "average_rating": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : Les notes clients WooCommerce sont bornées sur une échelle de 0 à 5 étoiles.
                    pa.Check(
                        lambda s: web_Total_Null_Row.loc[s.index]
                        | ((s >= 0) & (s <= 5)),
                        name="[BLOQUANT] WEB_AVERAGE_RATING_HORS_BORNES : La note moyenne doit être comprise entre 0 et 5",
                    )
                ],
            ),
            "rating_count": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : Le nombre d'avis clients ne peut pas être négatif.
                    pa.Check(
                        lambda s: web_Total_Null_Row.loc[s.index] | (s >= 0),
                        name="[BLOQUANT] WEB_RATING_COUNT_NEGATIF : Le nombre d'avis (rating_count) doit être >= 0",
                    )
                ],
            ),
            "post_date": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : Une date de création antérieurement postérieure à la date de dernière modification
                    # signale une corruption d'horodatage dans la base WordPress.
                    pa.Check(
                        lambda s: web_Total_Null_Row.loc[s.index]
                        | (
                            pd.to_datetime(s, errors="coerce")
                            <= pd.to_datetime(
                                web.loc[s.index, "post_modified"], errors="coerce"
                            )
                        )
                        | s.isna()
                        | web.loc[s.index, "post_modified"].isna(),
                        name="[ALERTE] WEB_CHRONOLOGIE_DATES_INCOHERENTE : post_date est postérieure à post_modified",
                    )
                ],
            ),
        },
        strict=False,
    )

    try:
        schema_web.validate(web, lazy=True)
    except SchemaErrors as err:
        anomalies_collectees.extend(_extraire_anomalies_pandera("web.xlsx", web, err))

    # =========================================================================
    # 4. SCHÉMAS PANDERA INTER-FICHIERS (Cohérence des clés et règles croisées)
    # =========================================================================
    erp_pids = set(_normaliser_id(erp["product_id"]).dropna())
    liaison_pids = set(_normaliser_id(liaison["product_id"]).dropna())
    liaison_id_webs = set(_normaliser_id(liaison["id_web"]).dropna())
    web_skus = set(web_Sku_Norm.dropna())

    # Mapping product_id -> id_web depuis liaison pour vérifier la cohérence avec erp.onsale_web
    liaison_norm_df = pd.DataFrame(
        {
            "pid": _normaliser_id(liaison["product_id"]),
            "id_web": _normaliser_id(liaison["id_web"]),
        }
    ).dropna(subset=["pid"])
    pid_to_idweb = (
        liaison_norm_df.drop_duplicates(subset=["pid"])
        .set_index("pid")["id_web"]
        .to_dict()
    )

    erp_pid_norm_series = _normaliser_id(erp["product_id"])
    erp_mapped_idweb = erp_pid_norm_series.map(pid_to_idweb)

    # 4.A - Contrôles inter-fichiers portés par ERP
    schema_inter_erp = pa.DataFrameSchema(
        columns={
            "product_id": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : Tout produit du référentiel ERP doit être répertorié dans la table de liaison.
                    pa.Check(
                        lambda s: _normaliser_id(s).isin(liaison_pids),
                        name="[BLOQUANT] INTER_ERP_ABSENT_DE_LIAISON : Produit présent dans erp.xlsx mais absent de liaison.xlsx",
                    )
                ],
            ),
            "onsale_web": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : Un produit marqué en vente en ligne (onsale_web = 1) dans l'ERP
                    # doit impérativement avoir un id_web renseigné dans liaison.xlsx.
                    pa.Check(
                        lambda s: (s != 1) | erp_mapped_idweb.loc[s.index].notna(),
                        name="[BLOQUANT] INTER_ONSALE_SANS_ID_WEB : Produit marqué onsale_web=1 dans l'ERP mais sans id_web dans liaison.xlsx",
                    ),
                    # Justification métier : Un produit marqué en vente en ligne (onsale_web = 1) dans l'ERP
                    # doit effectivement exister dans l'export WooCommerce (web.xlsx) pour pouvoir être acheté.
                    pa.Check(
                        lambda s: (s != 1)
                        | (
                            erp_mapped_idweb.loc[s.index].notna()
                            & erp_mapped_idweb.loc[s.index].isin(web_skus)
                        ),
                        name="[BLOQUANT] INTER_ONSALE_ABSENT_DU_SITE_WEB : Produit marqué onsale_web=1 dans l'ERP mais introuvable dans web.xlsx",
                    ),
                    # Justification métier : Si un produit a onsale_web = 0 mais possède un SKU actif sur le site web,
                    # il risque d'être vendu en ligne alors que l'ERP a désactivé sa commercialisation web.
                    pa.Check(
                        lambda s: (s != 0)
                        | ~erp_mapped_idweb.loc[s.index].isin(web_skus),
                        name="[ALERTE] INTER_OFFSALE_PRESENT_SUR_WEB : Produit marqué onsale_web=0 dans l'ERP mais toujours présent dans web.xlsx",
                    ),
                ],
            ),
        },
        strict=False,
    )

    try:
        schema_inter_erp.validate(erp, lazy=True)
    except SchemaErrors as err:
        anomalies_collectees.extend(_extraire_anomalies_pandera("erp.xlsx", erp, err))

    # 4.B - Contrôles inter-fichiers portés par LIAISON
    schema_inter_liaison = pa.DataFrameSchema(
        columns={
            "product_id": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : Intégrité référentielle : liaison.product_id est une clé étrangère vers erp.product_id.
                    # Un product_id orphelin dans liaison pointe vers un produit ERP inexistant.
                    pa.Check(
                        lambda s: _normaliser_id(s).isin(erp_pids),
                        name="[BLOQUANT] INTER_LIAISON_PRODUCT_ID_ORPHELIN : product_id dans liaison.xlsx introuvable dans erp.xlsx",
                    )
                ],
            ),
            "id_web": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : Si un id_web est renseigné manuellement dans liaison.xlsx mais n'existe pas
                    # dans web.xlsx, il s'agit soit d'une erreur de saisie manuelle, soit d'un produit préparé mais non publié.
                    pa.Check(
                        lambda s: _normaliser_id(s).isna()
                        | _normaliser_id(s).isin(web_skus),
                        name="[ALERTE] INTER_LIAISON_ID_WEB_ABSENT_DE_WEB : id_web renseigné dans liaison.xlsx mais absent de web.xlsx (produit dépublié ou erreur de saisie ?)",
                    )
                ],
            ),
        },
        strict=False,
    )

    try:
        schema_inter_liaison.validate(liaison, lazy=True)
    except SchemaErrors as err:
        anomalies_collectees.extend(
            _extraire_anomalies_pandera("liaison.xlsx", liaison, err)
        )

    # 4.C - Contrôles inter-fichiers portés par WEB
    schema_inter_web = pa.DataFrameSchema(
        columns={
            "sku": pa.Column(
                nullable=True,
                coerce=False,
                checks=[
                    # Justification métier : Tout produit vendu sur le site (web.sku) doit être rattaché à l'ERP via liaison.id_web,
                    # faute de quoi ses ventes ne remontent pas en comptabilité et ses stocks sont déconnectés.
                    pa.Check(
                        lambda s: web_Sku_Norm.loc[s.index].isna()
                        | web_Sku_Norm.loc[s.index].isin(liaison_id_webs),
                        name="[BLOQUANT] INTER_WEB_SKU_NON_RELIE_LIAISON : SKU présent dans web.xlsx mais absent de liaison.xlsx (orphelin Web)",
                    )
                ],
            )
        },
        strict=False,
    )

    try:
        schema_inter_web.validate(web, lazy=True)
    except SchemaErrors as err:
        anomalies_collectees.extend(_extraire_anomalies_pandera("web.xlsx", web, err))

    # =========================================================================
    # 5. MISE EN FORME DU DATAFRAME FINAL DES ANOMALIES
    # =========================================================================
    colonnes_attendues = ["fichier", "regle", "colonne", "index_ligne", "valeur"]
    if not anomalies_collectees:
        return pd.DataFrame(columns=colonnes_attendues)

    df_anomalies = pd.DataFrame(anomalies_collectees)[colonnes_attendues]
    df_anomalies = df_anomalies.sort_values(
        by=["fichier", "index_ligne", "colonne", "regle"]
    ).reset_index(drop=True)

    return df_anomalies

```

---

### Hypothèses de travail retenues

1. **Typage de la distinction `[BLOQUANT]` vs `[ALERTE]**` : Le contrat d'interface imposant strictement 5 colonnes en sortie (`fichier`, `regle`, `colonne`, `index_ligne`, `valeur`), le niveau de criticité est préfixé directement dans le nom de la règle (`regle`).
* **`[BLOQUANT]`** : Intégrité référentielle rompue, clés primaires/étrangères dupliquées ou nulles, stocks négatifs, incohérences `stock_quantity` / `stock_status`, ventes à perte (`price < purchase_price`), ou produits marqués `onsale_web = 1` mais absents du site.
* **`[ALERTE]`** : Valeurs atypiques nécessitant un arbitrage métier (prix > 5 000 € pouvant correspondre à un grand cru comme le *Domaine de la Romanée-Conti* ou un vieux cognac, taux de marge > 10x le prix d'achat, identifiants alphanumériques comme `bon-cadeau-25-euros` ou `13127-1`, `id_web` mappé dans `liaison.xlsx` pour un produit `onsale_web = 0` pas encore mis en ligne sur `web.xlsx`, ou lignes fantômes 100 % vides issues de l'export Excel WooCommerce).


2. **Normalisation non destructive pour les jointures** : Excel ayant tendance à typer certains codes numériques en flottants (`15298.0`) ou en chaînes de caractères selon les cellules d'une même colonne (`id_web` et `sku`), les comparaisons inter-fichiers normalisent la représentation textuelle à la volée en interne sans jamais altérer les DataFrames bruts passés en entrée ni la `valeur` remontée dans le rapport d'anomalies.
3. **Gestion des lignes fantômes dans `web.xlsx**` : L'export WooCommerce contient fréquemment des lignes entièrement vides (`NaN` sur toutes les colonnes) et des lignes de produits légitimes dont seul le `sku` est manquant. Pour éviter de déclencher une dizaine d'erreurs redondantes par ligne entièrement vide (sur `post_type`, `total_sales`, `post_title`, etc.), celles-ci sont isolées par une règle dédiée (`[ALERTE] WEB_LIGNE_ENTIEREMENT_VIDE`), tandis que les vraies fiches produits sans `sku` déclenchent l'erreur critique `[BLOQUANT] WEB_SKU_MANQUANT_SUR_PRODUIT`.
4. **Seuil d'alerte sur les produits premium** : Le seuil de vérification des prix élevés est fixé à **5 000 € HT** et celui d'écart de marge à **10 fois le prix d'achat HT** afin de ne pas générer de faux positifs sur les grands millésimes (généralement compris entre 150 € et 1 500 € HT) tout en interceptant les erreurs de frappe (ex. oubli de la virgule des centimes).