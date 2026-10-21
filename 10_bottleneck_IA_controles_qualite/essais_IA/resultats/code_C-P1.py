"""
Validation Pandera des fichiers erp.xlsx, web.xlsx et liaison.xlsx
(boutique en ligne de vins et spiritueux).

Compatibilité : Python 3.13, pandas 2.x, pandera (>= 0.24 conseillé, fonctionne aussi avant).
Usage :
    erp = pd.read_excel("erp.xlsx")
    web = pd.read_excel("web.xlsx")
    liaison = pd.read_excel("liaison.xlsx")
    anomalies = valider(erp, web, liaison)
"""

import datetime as dt

import numpy as np
import pandas as pd

try:
    import pandera.pandas as pa      # pandera >= 0.24
except ImportError:
    import pandera as pa             # pandera < 0.24
from pandera.errors import SchemaErrors


# ---------------------------------------------------------------------------
# Référentiels : valeurs standard WooCommerce / WordPress.
# À CONFIRMER sur vos fichiers, par exemple : web["post_status"].value_counts(dropna=False)
# ---------------------------------------------------------------------------
STOCK_STATUS = ["instock", "outofstock"]
TAX_STATUS = ["taxable", "shipping", "none"]
POST_STATUS = ["publish", "future", "draft", "pending", "private",
               "trash", "auto-draft", "inherit"]
OUVERT_FERME = ["open", "closed"]
POST_TYPE = ["product", "product_variation", "attachment"]

COLONNES = ["fichier", "regle", "colonne", "index_ligne", "valeur"]

# Libellés lisibles pour les contrôles natifs de Pandera
LIBELLES = {
    "not_nullable": "valeur manquante",
    "field_uniqueness": "doublon",
    "column_in_dataframe": "colonne absente",
}


# ---------------------------------------------------------------------------
# Outils de conversion (jamais appliqués aux données d'origine, uniquement
# utilisés à l'intérieur des contrôles)
# ---------------------------------------------------------------------------
def _num(s: pd.Series) -> pd.Series:
    """Conversion numérique tolérante : ce qui n'est pas convertible devient NaN."""
    return pd.to_numeric(s, errors="coerce")


def _date(s: pd.Series) -> pd.Series:
    """Conversion en dates : ce qui n'est pas une date devient NaT."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return s

    def conv(x):
        if isinstance(x, (dt.date, np.datetime64, pd.Timestamp)):
            try:
                return pd.Timestamp(x)
            except (ValueError, TypeError):
                return pd.NaT
        if isinstance(x, str) and x.strip():
            try:
                return pd.Timestamp(x.strip())
            except (ValueError, TypeError):
                return pd.NaT
        return pd.NaT          # nombre, booléen, vide... -> pas une date

    return pd.to_datetime(s.map(conv), errors="coerce")


def _norm_id(s: pd.Series) -> pd.Series:
    """Normalise un identifiant 'texte ou nombre' : 15258.0 -> '15258', ' 15258 ' -> '15258'."""
    def f(x):
        if isinstance(x, str):
            x = x.strip()
            return x if x else pd.NA
        if pd.isna(x):
            return pd.NA
        if isinstance(x, (int, np.integer)):
            return str(int(x))
        if isinstance(x, (float, np.floating)):
            return str(int(x)) if float(x).is_integer() else str(x)
        return str(x).strip()
    return s.map(f).astype("object")


def _autre(df: pd.DataFrame, col: str, index) -> pd.Series:
    """Récupère une autre colonne du même DataFrame, alignée sur l'index contrôlé."""
    if col in df.columns:
        return df[col].reindex(index)
    return pd.Series(np.nan, index=index, dtype="float64")


# ---------------------------------------------------------------------------
# Fabrique de règles Pandera (contrôles vectorisés renvoyant une Series booléenne :
# True = valeur conforme)
# ---------------------------------------------------------------------------
def _regle(libelle, fn):
    return pa.Check(lambda s: fn(s).astype(bool), name=libelle, error=libelle)


def r_numerique():
    return _regle("type : valeur non numérique",
                  lambda s: s.isna() | _num(s).notna())


def r_entier():
    def f(s):
        n = _num(s)
        return n.isna() | (n % 1 == 0)
    return _regle("type : nombre non entier", f)


def r_min(borne, strict=False):
    def f(s):
        n = _num(s)
        return n.isna() | ((n > borne) if strict else (n >= borne))
    libelle = f"valeur ≤ {borne}" if strict else f"valeur < {borne}"
    return _regle(libelle, f)


def r_entre(a, b):
    def f(s):
        n = _num(s)
        return n.isna() | n.between(a, b)
    return _regle(f"valeur hors de l'intervalle [{a} ; {b}]", f)


def r_binaire():
    def f(s):
        n = _num(s)
        return n.isna() | n.isin([0, 1])
    return _regle("valeur différente de 0 / 1", f)


def r_texte():
    return _regle("type : valeur non textuelle",
                  lambda s: s.map(lambda x: isinstance(x, str) or pd.isna(x)))


def r_non_vide():
    return _regle("texte vide ou composé d'espaces",
                  lambda s: s.map(lambda x: not isinstance(x, str) or x.strip() != ""))


def r_dans(valeurs):
    return _regle(f"valeur hors référentiel {valeurs}",
                  lambda s: s.isna() | s.isin(valeurs))


def r_regex(motif, libelle):
    def f(s):
        txt = s.map(lambda x: x.strip() if isinstance(x, str) else x)
        return s.isna() | ~s.map(lambda x: isinstance(x, str)) | txt.astype("string").str.match(motif).fillna(False)
    return _regle(libelle, f)


def r_date():
    return _regle("date invalide", lambda s: s.isna() | _date(s).notna())


def r_pas_futur():
    def f(s):
        d = _date(s)
        return d.isna() | (d <= pd.Timestamp.now())
    return _regle("date dans le futur", f)


def r_unique_num():
    def f(s):
        n = _num(s)
        return n.isna() | ~n.duplicated(keep=False)
    return _regle("doublon", f)


def r_unique_id():
    def f(s):
        ids = _norm_id(s)
        return ids.isna() | ~ids.duplicated(keep=False)
    return _regle("doublon (identifiant normalisé)", f)


def r_dans_num(ensemble, libelle):
    def f(s):
        n = _num(s)
        return n.isna() | n.isin(ensemble)
    return _regle(libelle, f)


def r_dans_id(ensemble, libelle):
    def f(s):
        ids = _norm_id(s)
        return ids.isna() | ids.isin(ensemble)
    return _regle(libelle, f)


def _col(*checks, nullable=True, unique=False, required=True):
    """Colonne sans contrainte de dtype (données brutes) : les types sont
    contrôlés ligne à ligne par les règles, pour obtenir l'index de chaque anomalie."""
    return pa.Column(None, checks=[c for c in checks if c is not None],
                     nullable=nullable, unique=unique, required=required)


# ---------------------------------------------------------------------------
# Exécution d'un schéma et mise au format des anomalies
# ---------------------------------------------------------------------------
def _collecter(fichier: str, schema: pa.DataFrameSchema, df: pd.DataFrame):
    try:
        schema.validate(df, lazy=True)          # lazy=True : collecte TOUT
        return None
    except SchemaErrors as exc:
        fc = exc.failure_cases
    except Exception as exc:                    # filet de sécurité : on ne s'arrête jamais
        return pd.DataFrame([{"fichier": fichier,
                              "regle": f"erreur d'exécution : {exc!r}",
                              "colonne": None, "index_ligne": None, "valeur": None}])

    out = pd.DataFrame({
        "fichier": fichier,
        "regle": fc["check"].astype(str).map(lambda c: LIBELLES.get(c, c)),
        "colonne": fc["column"].astype("object"),
        "index_ligne": fc["index"],
        "valeur": fc["failure_case"],
    })
    absente = out["regle"].eq("colonne absente") & out["colonne"].isna()
    out.loc[absente, "colonne"] = out.loc[absente, "valeur"]
    return out


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------
def valider(erp: pd.DataFrame, web: pd.DataFrame, liaison: pd.DataFrame) -> pd.DataFrame:
    """Renvoie un DataFrame des anomalies : fichier, regle, colonne, index_ligne, valeur.
    index_ligne = index pandas d'origine (ligne Excel = index_ligne + 2 avec l'en-tête)."""

    # --- Référentiels croisés (calculés uniquement à partir des fichiers fournis) ---
    ids_erp = set(_num(erp["product_id"]).dropna()) if "product_id" in erp.columns else None
    ids_liaison = set(_num(liaison["product_id"]).dropna()) if "product_id" in liaison.columns else None
    idweb_liaison = set(_norm_id(liaison["id_web"]).dropna()) if "id_web" in liaison.columns else None

    if "post_type" in web.columns:
        web_prod = web[web["post_type"].eq("product")]
    else:
        web_prod = web.iloc[0:0]
    sku_web = set(_norm_id(web_prod["sku"]).dropna()) if "sku" in web_prod.columns else None

    if {"product_id", "id_web"} <= set(liaison.columns):
        lien = pd.DataFrame({"pid": _num(liaison["product_id"]),
                             "web": _norm_id(liaison["id_web"])}).dropna()
        pid_avec_web = set(lien["pid"])
    else:
        pid_avec_web = None

    # --- Règles inter-colonnes ERP ---
    def _marge(s):
        achat, vente = _num(s), _num(_autre(erp, "price", s.index))
        return achat.isna() | vente.isna() | (achat < vente)

    def _coherence_stock(s):
        q = _num(_autre(erp, "stock_quantity", s.index))
        return (q.isna() | ~s.isin(STOCK_STATUS)
                | ((q > 0) & s.eq("instock"))
                | ((q <= 0) & s.eq("outofstock")))

    def _onsale_sans_web(s):
        n = _num(s)
        pid = _num(_autre(erp, "product_id", s.index))
        return n.isna() | n.ne(1) | pid.isna() | pid.isin(pid_avec_web)

    def _prix_atypique(s):
        n = _num(s)
        q1, q3 = n.quantile(0.25), n.quantile(0.75)
        return n.isna() | (n <= q3 + 1.5 * (q3 - q1))

    schema_erp = pa.DataFrameSchema({
        "product_id": _col(
            r_numerique(), r_entier(), r_min(0, strict=True), r_unique_num(),
            r_dans_num(ids_liaison, "product_id absent de liaison.xlsx") if ids_liaison is not None else None,
            nullable=False),
        "onsale_web": _col(
            r_numerique(), r_entier(), r_binaire(),
            _regle("en vente web (onsale_web = 1) sans id_web dans liaison.xlsx", _onsale_sans_web)
            if pid_avec_web is not None else None,
            nullable=False),
        "price": _col(
            r_numerique(), r_min(0, strict=True),
            _regle("[alerte] prix atypique (> Q3 + 1,5 × IQR)", _prix_atypique),
            nullable=False),
        "stock_quantity": _col(r_numerique(), r_entier(), r_min(0), nullable=False),
        "stock_status": _col(
            r_texte(), r_dans(STOCK_STATUS),
            _regle("stock_status incohérent avec stock_quantity", _coherence_stock),
            nullable=False),
        "purchase_price": _col(
            r_numerique(), r_min(0, strict=True),
            _regle("prix d'achat ≥ prix de vente", _marge),
            nullable=False),
    })

    # --- Règles inter-colonnes WEB ---
    def _note_sans_avis(s):
        nb, note = _num(_autre(web, "rating_count", s.index)), _num(s)
        return nb.isna() | note.isna() | (nb > 0) | note.eq(0)

    def _posterieur(col_ref):
        def f(s):
            d1, d0 = _date(s), _date(_autre(web, col_ref, s.index))
            return d1.isna() | d0.isna() | (d1 >= d0)
        return _regle(f"date de modification antérieure à {col_ref}", f)

    schema_web = pa.DataFrameSchema({
        "sku": _col(r_non_vide(), nullable=False),
        "virtual": _col(r_numerique(), r_binaire()),
        "downloadable": _col(r_numerique(), r_binaire()),
        "rating_count": _col(r_numerique(), r_entier(), r_min(0)),
        "average_rating": _col(r_numerique(), r_entre(0, 5),
                               _regle("note moyenne non nulle sans aucun avis", _note_sans_avis)),
        "total_sales": _col(r_numerique(), r_entier(), r_min(0)),
        "tax_status": _col(r_texte(), r_dans(TAX_STATUS)),
        "tax_class": _col(r_numerique()),
        "post_author": _col(r_numerique(), r_entier(), r_min(0, strict=True)),
        "post_date": _col(r_date(), r_pas_futur()),
        "post_date_gmt": _col(r_date(), r_pas_futur()),
        "post_content": _col(r_numerique()),
        "product_type": _col(r_texte(), r_non_vide()),
        "post_title": _col(r_texte(), r_non_vide()),
        "post_excerpt": _col(r_texte()),
        "post_status": _col(r_texte(), r_dans(POST_STATUS)),
        "comment_status": _col(r_texte(), r_dans(OUVERT_FERME)),
        "ping_status": _col(r_texte(), r_dans(OUVERT_FERME)),
        "post_password": _col(r_numerique()),
        "post_name": _col(r_texte(), r_non_vide()),
        "post_modified": _col(r_date(), r_pas_futur(), _posterieur("post_date")),
        "post_modified_gmt": _col(r_date(), r_pas_futur(), _posterieur("post_date_gmt")),
        "post_content_filtered": _col(r_numerique()),
        "post_parent": _col(r_numerique(), r_entier(), r_min(0)),
        "guid": _col(r_texte(), r_regex(r"^https?://\S+$", "URL guid invalide")),
        "menu_order": _col(r_numerique(), r_entier()),
        "post_type": _col(r_texte(), r_dans(POST_TYPE), nullable=False),
        "post_mime_type": _col(r_texte(), r_regex(r"^[\w.+-]+/[\w.+-]+$", "type MIME invalide")),
        "comment_count": _col(r_numerique(), r_entier(), r_min(0)),
    })

    # Règles propres aux lignes produit (post_type == "product") ; index d'origine conservé.
    # required=False : une colonne absente est déjà signalée par schema_web.
    schema_web_produits = pa.DataFrameSchema({
        "sku": _col(
            r_unique_id(),
            r_dans_id(idweb_liaison, "sku produit absent de liaison.xlsx (id_web)")
            if idweb_liaison is not None else None,
            nullable=False, required=False),
        "post_title": _col(nullable=False, required=False),
        "post_name": _col(nullable=False, unique=True, required=False),
    })

    # --- LIAISON ---
    schema_liaison = pa.DataFrameSchema({
        "product_id": _col(
            r_numerique(), r_entier(), r_min(0, strict=True), r_unique_num(),
            r_dans_num(ids_erp, "product_id absent de erp.xlsx") if ids_erp is not None else None,
            nullable=False),
        "id_web": _col(
            r_non_vide(), r_unique_id(),
            r_dans_id(sku_web, "id_web absent des sku produits de web.xlsx") if sku_web is not None else None,
            nullable=False),
    })

    # --- Collecte de toutes les anomalies ---
    morceaux = [
        _collecter("erp.xlsx", schema_erp, erp),
        _collecter("web.xlsx", schema_web, web),
        _collecter("web.xlsx", schema_web_produits, web_prod),
        _collecter("liaison.xlsx", schema_liaison, liaison),
    ]
    morceaux = [m for m in morceaux if m is not None and not m.empty]
    if not morceaux:
        return pd.DataFrame(columns=COLONNES)

    res = pd.concat(morceaux, ignore_index=True)[COLONNES]
    res["index_ligne"] = pd.to_numeric(res["index_ligne"], errors="coerce").astype("Int64")
    return (res.sort_values(["fichier", "regle", "colonne", "index_ligne"],
                            na_position="first", kind="stable")
               .reset_index(drop=True))


if __name__ == "__main__":
    erp = pd.read_excel("erp.xlsx")
    web = pd.read_excel("web.xlsx")
    liaison = pd.read_excel("liaison.xlsx")

    anomalies = valider(erp, web, liaison)
    print(f"{len(anomalies)} anomalies détectées")
    print(anomalies.groupby(["fichier", "colonne", "regle"], dropna=False)
                   .size().rename("nb").reset_index().to_string(index=False))
