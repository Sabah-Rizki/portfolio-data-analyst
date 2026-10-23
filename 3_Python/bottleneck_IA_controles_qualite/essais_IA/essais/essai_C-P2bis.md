Voici le module de contrôle. **Je n'ai pas pu l'exécuter ici**, ni sur vos fichiers ni dans un environnement Pandera. Avant de l'industrialiser, lancez-le une fois sur les trois exports réels et vérifiez les points listés à la fin.

```python
"""
Contrôles qualité des données BottleNeck : ERP / site web / table de liaison.

Chaque export peut être rejoué :
    anomalies = valider(erp, web, liaison)

Le DataFrame renvoyé a les colonnes : fichier, regle, colonne, index_ligne, valeur.
Le niveau de gravité est en tête du libellé de la règle :
    [BLOQUANT] : la donnée est fausse ou inexploitable, l'export doit être corrigé avant la reprise dans l'ERP ;
    [ALERTE]   : la donnée est suspecte, le métier doit la valider (elle peut être juste).
Compatible Python 3.13, pandas 2.x, pandera (anciennes et nouvelles API d'import).
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

try:  # pandera >= 0.24 : API pandas dans le sous-module dédié
    import pandera.pandas as pa
except ImportError:  # versions antérieures
    import pandera as pa
from pandera.errors import SchemaErrors

# --------------------------------------------------------------------------
# Paramètres
# --------------------------------------------------------------------------
BLOQUANT = "BLOQUANT"
ALERTE = "ALERTE"
COLONNES_SORTIE = ["fichier", "regle", "colonne", "index_ligne", "valeur"]

ERP_COLONNES = ["product_id", "onsale_web", "price", "stock_quantity",
                "stock_status", "purchase_price"]
LIAISON_COLONNES = ["product_id", "id_web"]
# Colonnes web sans lesquelles ni la jointure ni l'analyse des ventes ne sont possibles
WEB_COLONNES_CRITIQUES = ["sku", "post_type", "total_sales"]
WEB_COLONNES_METIER = ["product_type", "post_title", "post_status",
                       "average_rating", "rating_count"]
WEB_COLONNES_TECHNIQUES = [
    "virtual", "downloadable", "tax_status", "tax_class", "post_author",
    "post_date", "post_date_gmt", "post_content", "post_excerpt",
    "comment_status", "ping_status", "post_password", "post_name",
    "post_modified", "post_modified_gmt", "post_content_filtered",
    "post_parent", "guid", "menu_order", "post_mime_type", "comment_count",
]

STATUTS_STOCK = ["instock", "outofstock"]                      # règle de gestion fournie
POST_TYPES = ["product", "attachment"]                         # dictionnaire fourni
POST_STATUS_WP = ["publish", "future", "draft", "pending",     # statuts standard WordPress
                  "private", "trash", "auto-draft", "inherit"]
TAX_STATUS_WC = ["taxable", "shipping", "none"]                # valeurs standard WooCommerce
OUVERT_FERME = ["open", "closed"]                              # valeurs standard WordPress
NOTE_MIN, NOTE_MAX = 0, 5                                      # échelle d'avis WooCommerce
COEF_TUKEY = 1.5                                               # seuil d'alerte prix atypique


# --------------------------------------------------------------------------
# Outils (aucune modification des DataFrames reçus)
# --------------------------------------------------------------------------
def _col(df, nom: str) -> pd.Series:
    """Colonne si elle existe, sinon série vide alignée (l'absence est signalée par le schéma)."""
    if isinstance(df, pd.DataFrame) and nom in df.columns:
        return df[nom]
    index = df.index if isinstance(df, pd.DataFrame) else pd.RangeIndex(0)
    return pd.Series(np.nan, index=index, dtype="object")


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _vide(s: pd.Series) -> pd.Series:
    """Vrai si la cellule est vide (NaN ou texte blanc)."""
    blanc = s.astype("string").str.strip().eq("")
    return (s.isna() | blanc).fillna(True).astype(bool)


def _est_entier(s: pd.Series) -> pd.Series:
    n = _num(s)
    return (n.notna() & (n % 1 == 0)).astype(bool)


def _egal(s: pd.Series, valeur: str) -> pd.Series:
    return s.astype("string").str.strip().eq(valeur).fillna(False).astype(bool)


def _date(s: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(s):
        return s
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(s, errors="coerce", format="mixed")


def _cle(v):
    """Clé de jointure en texte : 15298, 15298.0 et '15298' donnent la même clé."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if isinstance(v, (bool, np.bool_)):
        return str(v)
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, (float, np.floating)):
        return str(int(v)) if float(v).is_integer() else repr(float(v))
    t = str(v).strip()
    return t or None


def _cles(s: pd.Series) -> pd.Series:
    return s.map(_cle)


def _unique(k: pd.Series) -> pd.Series:
    return (k.isna() | ~k.duplicated(keep=False)).astype(bool)


def _cle_numerique(k: pd.Series) -> pd.Series:
    return (k.isna() | k.map(lambda v: isinstance(v, str) and v.isdecimal())).astype(bool)


def _espaces_parasites(s: pd.Series) -> pd.Series:
    return s.map(lambda v: isinstance(v, str) and v != v.strip()).astype(bool)


def _anomalie(fichier, regle, colonne, index_ligne, valeur) -> dict:
    return {"fichier": fichier, "regle": regle, "colonne": colonne,
            "index_ligne": index_ligne, "valeur": valeur}


def _check(ctx, colonne, niveau, code, libelle, fn) -> pa.Check:
    """Règle Pandera nommée. Si son évaluation plante, elle est journalisée et le contrôle continue."""
    nom = f"[{niveau}] {code} - {libelle}"

    def _verifier(s: pd.Series) -> pd.Series:
        try:
            res = pd.Series(fn(s)).reindex(s.index)
            return res.astype("boolean").fillna(True).astype(bool)
        except Exception as exc:  # aucune règle ne doit interrompre la campagne
            ctx["journal"].append(_anomalie(
                ctx["fichier"], f"[{BLOQUANT}] TECH - règle non évaluable : {nom}",
                colonne, None, repr(exc)))
            return pd.Series(True, index=s.index)

    return pa.Check(_verifier, name=nom, ignore_na=False)


def _colonne(ctx, nom, regles=()) -> pa.Column:
    # dtype=None : pas de typage strict, car les exports sont bruts. Les types sont
    # contrôlés ligne à ligne par les règles, ce qui permet de désigner la ligne fautive.
    return pa.Column(checks=[_check(ctx, nom, *r) for r in regles],
                     nullable=True, required=True, coerce=False)


# --------------------------------------------------------------------------
# Référentiels de clés (contrôles entre fichiers)
# --------------------------------------------------------------------------
def _referentiels(erp, web, liaison) -> dict:
    erp_pid = _cles(_col(erp, "product_id"))
    lia_pid = _cles(_col(liaison, "product_id"))
    lia_idweb = _cles(_col(liaison, "id_web"))
    web_sku = _cles(_col(web, "sku"))
    est_produit = _egal(_col(web, "post_type"), "product")
    est_image = _egal(_col(web, "post_type"), "attachment")
    est_publie = _egal(_col(web, "post_status"), "publish")

    correspondance = {}
    for pid, idw in zip(lia_pid, lia_idweb):
        if pid is not None:
            correspondance[pid] = idw

    return {
        "erp_pid": erp_pid,
        "set_erp_pid": list(set(erp_pid.dropna())),
        "set_lia_pid": list(set(lia_pid.dropna())),
        "set_lia_idweb": list(set(lia_idweb.dropna())),
        "pid_vers_idweb": correspondance,
        "web_sku": web_sku,
        "est_produit": est_produit,
        "est_image": est_image,
        "set_sku_produit": list(set(web_sku[est_produit].dropna())),
        "set_sku_image": list(set(web_sku[est_image].dropna())),
        "set_sku_publie": list(set(web_sku[est_produit & est_publie].dropna())),
    }


# --------------------------------------------------------------------------
# Schéma ERP
# --------------------------------------------------------------------------
def _schema_erp(erp, ref, ctx) -> pa.DataFrameSchema:
    onsale = _num(_col(erp, "onsale_web"))
    prix = _num(_col(erp, "price"))
    stock = _num(_col(erp, "stock_quantity"))
    achat = _num(_col(erp, "purchase_price"))
    pid = ref["erp_pid"]
    idweb = pid.map(lambda k: ref["pid_vers_idweb"].get(k) if k is not None else None)
    connu_liaison = pid.isin(ref["set_lia_pid"])

    # Borne haute de Tukey, calculée sur les prix positifs de l'export courant
    p_ok = prix[prix > 0]
    if len(p_ok) >= 4:
        q1, q3 = p_ok.quantile(0.25), p_ok.quantile(0.75)
        borne_haute = q3 + COEF_TUKEY * (q3 - q1)
    else:
        borne_haute = np.inf

    B, A = BLOQUANT, ALERTE
    colonnes = {
        "product_id": _colonne(ctx, "product_id", [
            # Clé primaire de l'ERP : sans elle, impossible de rattacher prix, stock et ventes.
            (B, "ERP-B01", "product_id renseigné", lambda s: ~_vide(s)),
            # Un identifiant technique est un entier positif ; une décimale ou un texte trahit une saisie ou un export corrompu.
            (B, "ERP-B02", "product_id entier strictement positif",
             lambda s: _vide(s) | (_est_entier(s) & (_num(s) > 0))),
            # Un doublon de clé fausserait le stock, le CA et la jointure (lignes multipliées).
            (B, "ERP-B03", "product_id unique", lambda s: _unique(_cles(s))),
            # INTER-FICHIERS : tout produit ERP doit figurer dans la liaison, sinon son lien avec le site est perdu.
            (B, "X-01", "product_id ERP présent dans liaison.product_id",
             lambda s: pid.isna() | pid.isin(ref["set_lia_pid"])),
        ]),
        "onsale_web": _colonne(ctx, "onsale_web", [
            # Indicateur binaire de mise en vente : toute autre valeur rend le périmètre du site indéterminé.
            (B, "ERP-B04", "onsale_web renseigné et égal à 0 ou 1",
             lambda s: ~_vide(s) & _num(s).isin([0, 1])),
            # INTER-FICHIERS : un produit en vente doit avoir un id_web (un id_web vide signifie "pas encore en ligne").
            (B, "X-05", "produit en vente (onsale_web=1) sans id_web dans la liaison",
             lambda s: ~(onsale.eq(1) & connu_liaison & idweb.isna())),
            # INTER-FICHIERS : en vente dans l'ERP mais non publié sur le site : ventes manquées ou statut ERP obsolète.
            (A, "X-06", "produit en vente (onsale_web=1) dont l'article web n'est pas publié",
             lambda s: ~(onsale.eq(1) & idweb.isin(ref["set_sku_produit"])
                         & ~idweb.isin(ref["set_sku_publie"]))),
            # INTER-FICHIERS : publié sur le site mais déclaré hors vente dans l'ERP : risque de vendre un produit retiré.
            (A, "X-07", "produit hors vente (onsale_web=0) mais publié sur le site",
             lambda s: ~(onsale.eq(0) & idweb.isin(ref["set_sku_publie"]))),
            # Stock disponible non proposé à la vente : capital immobilisé, à confirmer (réserve, fin de série...).
            (A, "ERP-A06", "stock disponible (stock_quantity>0) mais onsale_web=0",
             lambda s: ~(onsale.eq(0) & (stock > 0))),
        ]),
        "price": _colonne(ctx, "price", [
            # Un prix doit être un nombre, sinon aucun calcul de CA ou de marge n'est possible.
            (B, "ERP-B05", "price numérique", lambda s: _vide(s) | _num(s).notna()),
            # Un produit en ligne sans prix positif serait vendu gratuitement ou bloquerait la commande.
            (B, "ERP-B06", "price renseigné et > 0 pour un produit en vente",
             lambda s: ~(onsale.eq(1) & ~(_num(s) > 0))),
            # Un prix de vente négatif n'a pas de sens commercial.
            (B, "ERP-B07", "price non négatif", lambda s: ~(_num(s) < 0)),
            # Hors vente, un prix vide ou nul n'empêche pas de vendre, mais il doit être complété avant la mise en ligne.
            (A, "ERP-A01", "price vide ou nul sur un produit hors vente",
             lambda s: ~(onsale.ne(1) & (_vide(s) | _num(s).eq(0)))),
            # Vendre sous le prix d'achat est possible (déstockage, promotion) mais doit être une décision consciente.
            (A, "ERP-A04", "price inférieur au purchase_price (vente à perte)",
             lambda s: ~(_num(s) < achat)),
            # Prix statistiquement atypique : une ALERTE seulement, car le catalogue premium rend les prix élevés légitimes.
            (A, "ERP-A05", f"price atypique (> Q3 + {COEF_TUKEY} x IQR), à confirmer par le métier",
             lambda s: ~(_num(s) > borne_haute)),
        ]),
        "stock_quantity": _colonne(ctx, "stock_quantity", [
            # Le stock est un nombre d'unités : il doit être renseigné et entier.
            (B, "ERP-B08", "stock_quantity renseigné et entier",
             lambda s: ~_vide(s) & _est_entier(s)),
            # Un stock physique négatif est impossible : erreur de mouvement ou de saisie.
            (B, "ERP-B09", "stock_quantity non négatif", lambda s: ~(_num(s) < 0)),
        ]),
        "stock_status": _colonne(ctx, "stock_status", [
            # Le site n'interprète que ces deux valeurs : toute autre valeur casse l'affichage de la disponibilité.
            (B, "ERP-B10", "stock_status égal à 'instock' ou 'outofstock'",
             lambda s: s.isin(STATUTS_STOCK)),
            # Règle de gestion : instock si stock > 0, outofstock sinon. Une incohérence fait vendre du vide ou masque du stock.
            (B, "ERP-B11", "stock_status cohérent avec stock_quantity",
             lambda s: ~(stock.notna() & s.isin(STATUTS_STOCK) & s.ne(
                 pd.Series(np.where(stock > 0, "instock", "outofstock"), index=s.index)))),
        ]),
        "purchase_price": _colonne(ctx, "purchase_price", [
            # Un prix d'achat renseigné doit être un nombre positif ou nul.
            (B, "ERP-B12", "purchase_price numérique et non négatif",
             lambda s: _vide(s) | (_num(s) >= 0)),
            # Sans prix d'achat, la marge et la valorisation du stock sont incalculables.
            (A, "ERP-A02", "purchase_price manquant (marge incalculable)", lambda s: ~_vide(s)),
            # Un prix d'achat nul est rare (échantillon, cadeau fournisseur) : à confirmer.
            (A, "ERP-A03", "purchase_price nul", lambda s: ~_num(s).eq(0)),
        ]),
    }
    # strict=True : une colonne non prévue est signalée (changement de format de l'export).
    return pa.DataFrameSchema(colonnes, strict=True, name="erp")


# --------------------------------------------------------------------------
# Schéma liaison
# --------------------------------------------------------------------------
def _schema_liaison(liaison, ref, ctx) -> pa.DataFrameSchema:
    B, A = BLOQUANT, ALERTE
    colonnes = {
        "product_id": _colonne(ctx, "product_id", [
            # Une ligne de liaison sans product_id ne relie rien : fichier tenu à la main, oubli probable.
            (B, "LIA-B01", "product_id renseigné", lambda s: ~_vide(s)),
            # Même format que la clé ERP, sinon la jointure échoue.
            (B, "LIA-B02", "product_id entier strictement positif",
             lambda s: _vide(s) | (_est_entier(s) & (_num(s) > 0))),
            # Un produit ERP ne doit avoir qu'une correspondance, sinon ses ventes sont comptées plusieurs fois.
            (B, "LIA-B03", "product_id unique", lambda s: _unique(_cles(s))),
            # INTER-FICHIERS : un product_id absent de l'ERP est orphelin (produit supprimé ou faute de frappe).
            (B, "X-02", "liaison.product_id présent dans erp.product_id",
             lambda s: _cles(s).isna() | _cles(s).isin(ref["set_erp_pid"])),
        ]),
        "id_web": _colonne(ctx, "id_web", [
            # Un article du site ne peut correspondre qu'à un produit ERP, sinon CA et stock sont dupliqués.
            (B, "LIA-B04", "id_web unique (hors vides)", lambda s: _unique(_cles(s))),
            # INTER-FICHIERS : un id_web renseigné doit exister comme produit sur le site, sinon les ventes sont perdues à la jointure.
            (B, "X-03", "id_web renseigné présent parmi les sku 'product' de web.xlsx",
             lambda s: _cles(s).isna() | _cles(s).isin(ref["set_sku_produit"])),
            # Le code article est normalement numérique : une valeur texte doit être validée (bon cadeau, variante, erreur...).
            (A, "LIA-A01", "id_web non numérique", lambda s: _cle_numerique(_cles(s))),
            # Des espaces invisibles cassent les jointures dans les autres outils (Excel, BI).
            (A, "LIA-A02", "id_web avec espaces parasites", lambda s: ~_espaces_parasites(s)),
        ]),
    }
    return pa.DataFrameSchema(colonnes, strict=True, name="liaison")


# --------------------------------------------------------------------------
# Schéma web
# --------------------------------------------------------------------------
def _schema_web(web, ref, ctx) -> pa.DataFrameSchema:
    B, A = BLOQUANT, ALERTE
    sku = ref["web_sku"]
    est_produit, est_image = ref["est_produit"], ref["est_image"]
    ligne_vide = (web.isna().all(axis=1) if isinstance(web, pd.DataFrame)
                  else pd.Series(dtype=bool))
    nb_avis = _num(_col(web, "rating_count"))
    date_creation = _date(_col(web, "post_date"))

    def _dans(valeurs):
        return lambda s: _vide(s) | s.isin(valeurs)

    def _date_valide(s):
        return _vide(s) | _date(s).notna()

    colonnes = {
        "sku": _colonne(ctx, "sku", [
            # Une ligne entièrement vide est un artefact d'export à purger.
            (A, "WEB-A01", "ligne entièrement vide", lambda s: ~ligne_vide),
            # Le sku est la clé de jointure vers la liaison : sans lui, les ventes du produit ne sont pas rattachables.
            (B, "WEB-B02", "sku renseigné sur une ligne product",
             lambda s: ~(est_produit & sku.isna())),
            # Un produit ne doit apparaître qu'une fois, sinon ses ventes sont comptées en double.
            (B, "WEB-B03", "sku unique parmi les lignes product",
             lambda s: ~(est_produit & sku.notna()
                         & sku.where(est_produit).duplicated(keep=False))),
            # INTER-FICHIERS : un produit du site sans correspondance dans la liaison n'a ni prix ni stock ERP.
            (B, "X-04", "sku 'product' présent dans liaison.id_web",
             lambda s: ~(est_produit & sku.notna() & ~sku.isin(ref["set_lia_idweb"]))),
            # Le sku est normalement numérique : une valeur texte doit être validée par le métier.
            (A, "WEB-A02", "sku non numérique", lambda s: _cle_numerique(sku)),
            # Espaces invisibles : jointures fragiles dans les autres outils.
            (A, "WEB-A03", "sku avec espaces parasites", lambda s: ~_espaces_parasites(s)),
            # Chaque produit a normalement une ligne image : produit sans visuel sur le site.
            (A, "WEB-A04", "ligne product sans ligne attachment de même sku",
             lambda s: ~(est_produit & sku.notna() & ~sku.isin(ref["set_sku_image"]))),
            # Image orpheline : produit supprimé ou sku mal saisi.
            (A, "WEB-A05", "ligne attachment sans ligne product de même sku",
             lambda s: ~(est_image & sku.notna() & ~sku.isin(ref["set_sku_produit"]))),
            # Normalement une seule image par produit : plusieurs lignes peuvent être légitimes (galerie) ou des doublons.
            (A, "WEB-A06", "sku présent sur plusieurs lignes attachment",
             lambda s: ~(est_image & sku.notna()
                         & sku.where(est_image).duplicated(keep=False))),
            # Une image sans sku ne peut être rattachée à aucun produit.
            (A, "WEB-A07", "sku vide sur une ligne attachment",
             lambda s: ~(est_image & sku.isna())),
        ]),
        "post_type": _colonne(ctx, "post_type", [
            # Seuls ces deux types sont prévus : toute autre valeur rend la distinction produit / image impossible.
            (B, "WEB-B01", "post_type égal à 'product' ou 'attachment' (ligne non vide)",
             lambda s: ligne_vide | s.isin(POST_TYPES)),
        ]),
        "total_sales": _colonne(ctx, "total_sales", [
            # Les ventes cumulées sont des quantités : numériques et jamais négatives.
            (B, "WEB-B04", "total_sales numérique et non négatif",
             lambda s: _vide(s) | (_num(s) >= 0)),
            # Sans total_sales sur un produit, le CA est sous-estimé.
            (A, "WEB-A08", "total_sales vide sur une ligne product",
             lambda s: ~(est_produit & _vide(s))),
            # On vend des unités entières : une décimale signale un problème d'export.
            (A, "WEB-A09", "total_sales non entier",
             lambda s: _vide(s) | _num(s).isna() | _est_entier(s)),
        ]),
        "product_type": _colonne(ctx, "product_type", [
            # La famille sert aux analyses par catégorie : un produit sans famille sort des rapports.
            (A, "WEB-A11", "product_type renseigné sur une ligne product",
             lambda s: ~(est_produit & _vide(s))),
        ]),
        "post_title": _colonne(ctx, "post_title", [
            # Un produit sans libellé est invendable en ligne et inidentifiable pour le métier.
            (A, "WEB-A12", "post_title renseigné sur une ligne product",
             lambda s: ~(est_produit & _vide(s))),
        ]),
        "post_status": _colonne(ctx, "post_status", [
            # Un statut inconnu de WordPress rend la visibilité du produit indéterminée.
            (A, "WEB-A13", "post_status parmi les statuts WordPress (ligne non vide)",
             lambda s: ligne_vide | s.isin(POST_STATUS_WP)),
        ]),
        "average_rating": _colonne(ctx, "average_rating", [
            # Les notes WooCommerce vont de 0 à 5 : une valeur hors bornes est impossible.
            (B, "WEB-B05", f"average_rating entre {NOTE_MIN} et {NOTE_MAX}",
             lambda s: _vide(s) | _num(s).between(NOTE_MIN, NOTE_MAX)),
            # Une note sans aucun avis est incohérente (avis supprimés ou calcul non mis à jour).
            (A, "WEB-A10", "average_rating > 0 alors que rating_count = 0",
             lambda s: ~((_num(s) > 0) & nb_avis.eq(0))),
        ]),
        "rating_count": _colonne(ctx, "rating_count", [
            # Un nombre d'avis est un entier positif ou nul.
            (B, "WEB-B06", "rating_count entier et non négatif",
             lambda s: _vide(s) | (_est_entier(s) & (_num(s) >= 0))),
        ]),
        # ---- Colonnes techniques WordPress : anomalies sans impact direct sur l'analyse, donc ALERTE ----
        "virtual": _colonne(ctx, "virtual", [
            # Indicateur binaire WooCommerce (produit sans livraison).
            (A, "WEB-A14", "virtual égal à 0 ou 1", lambda s: _vide(s) | _num(s).isin([0, 1])),
        ]),
        "downloadable": _colonne(ctx, "downloadable", [
            # Indicateur binaire WooCommerce (produit téléchargeable) ; un vin ne devrait pas l'être.
            (A, "WEB-A15", "downloadable égal à 0 ou 1", lambda s: _vide(s) | _num(s).isin([0, 1])),
        ]),
        "tax_status": _colonne(ctx, "tax_status", [
            # Un statut fiscal inconnu peut fausser le calcul de TVA.
            (A, "WEB-A16", "tax_status parmi taxable / shipping / none", _dans(TAX_STATUS_WC)),
        ]),
        "comment_status": _colonne(ctx, "comment_status", [
            # Valeurs WordPress attendues ; une autre valeur trahit un export altéré.
            (A, "WEB-A17", "comment_status égal à open ou closed", _dans(OUVERT_FERME)),
        ]),
        "ping_status": _colonne(ctx, "ping_status", [
            (A, "WEB-A18", "ping_status égal à open ou closed", _dans(OUVERT_FERME)),
        ]),
        "post_date": _colonne(ctx, "post_date", [
            # Les dates servent aux analyses d'ancienneté du catalogue.
            (A, "WEB-A19", "post_date est une date valide", _date_valide),
        ]),
        "post_date_gmt": _colonne(ctx, "post_date_gmt", [
            (A, "WEB-A20", "post_date_gmt est une date valide", _date_valide),
        ]),
        "post_modified": _colonne(ctx, "post_modified", [
            (A, "WEB-A21", "post_modified est une date valide", _date_valide),
            # Un article ne peut pas avoir été modifié avant d'avoir été créé.
            (A, "WEB-A22", "post_modified postérieur ou égal à post_date",
             lambda s: ~(_date(s) < date_creation)),
        ]),
        "post_modified_gmt": _colonne(ctx, "post_modified_gmt", [
            (A, "WEB-A23", "post_modified_gmt est une date valide", _date_valide),
        ]),
        "post_mime_type": _colonne(ctx, "post_mime_type", [
            # Une ligne attachment est censée être une image (type MIME image/...).
            (A, "WEB-A24", "post_mime_type de type image/* sur une ligne attachment",
             lambda s: ~(est_image & ~s.astype("string").str.startswith("image/")
                         .fillna(False).astype(bool))),
        ]),
    }
    # Autres colonnes techniques : seule leur présence est contrôlée.
    for nom in WEB_COLONNES_TECHNIQUES:
        colonnes.setdefault(nom, _colonne(ctx, nom))
    return pa.DataFrameSchema(colonnes, strict=True, name="web")


# --------------------------------------------------------------------------
# Exécution et collecte
# --------------------------------------------------------------------------
def _executer(fichier, fabrique, df, ref, critiques) -> list[dict]:
    ctx = {"fichier": fichier, "journal": []}
    if not isinstance(df, pd.DataFrame):
        return [_anomalie(fichier, f"[{BLOQUANT}] TECH - l'objet reçu n'est pas un DataFrame",
                          None, None, type(df).__name__)]
    try:
        schema = fabrique(df, ref, ctx)
        schema.validate(df, lazy=True)  # lazy=True : toutes les erreurs sont collectées
        return ctx["journal"]
    except SchemaErrors as exc:
        cas = exc.failure_cases
    except Exception as exc:  # incident d'exécution : tracé, la validation des autres fichiers continue
        return ctx["journal"] + [_anomalie(
            fichier, f"[{BLOQUANT}] TECH - échec de la validation du fichier", None, None, repr(exc))]

    lignes = list(ctx["journal"])
    for _, r in cas.iterrows():
        check = str(r.get("check"))
        colonne, valeur, index = r.get("column"), r.get("failure_case"), r.get("index")
        if check.startswith("column_in_dataframe"):
            # Une colonne attendue est absente de l'export.
            nom = valeur if isinstance(valeur, str) else colonne
            niveau = BLOQUANT if nom in critiques else ALERTE
            regle = f"[{niveau}] STRUCT-01 - colonne attendue absente de l'export"
            colonne, valeur, index = nom, None, None
        elif check.startswith("column_in_schema"):
            # Une colonne non prévue est présente : changement de format à faire valider.
            nom = valeur if isinstance(valeur, str) else colonne
            regle = f"[{ALERTE}] STRUCT-02 - colonne non prévue au dictionnaire de données"
            colonne, valeur, index = nom, None, None
        elif check.startswith("["):
            regle = check
        else:
            regle = f"[{BLOQUANT}] PANDERA - {check}"
        lignes.append(_anomalie(fichier, regle, colonne,
                                None if pd.isna(index) else index, valeur))
    return lignes


def valider(erp: pd.DataFrame, web: pd.DataFrame, liaison: pd.DataFrame) -> pd.DataFrame:
    """Contrôle les trois exports bruts et renvoie toutes les anomalies (sans jamais s'arrêter)."""
    anomalies: list[dict] = []
    try:
        ref = _referentiels(erp, web, liaison)
    except Exception as exc:
        anomalies.append(_anomalie("inter-fichiers",
                                   f"[{BLOQUANT}] TECH - référentiels de clés non calculables",
                                   None, None, repr(exc)))
        vide = pd.Series(dtype="object")
        ref = {"erp_pid": vide, "set_erp_pid": [], "set_lia_pid": [], "set_lia_idweb": [],
               "pid_vers_idweb": {}, "web_sku": vide, "est_produit": vide.astype(bool),
               "est_image": vide.astype(bool), "set_sku_produit": [], "set_sku_image": [],
               "set_sku_publie": []}

    anomalies += _executer("erp.xlsx", _schema_erp, erp, ref, set(ERP_COLONNES))
    anomalies += _executer("liaison.xlsx", _schema_liaison, liaison, ref, set(LIAISON_COLONNES))
    anomalies += _executer("web.xlsx", _schema_web, web, ref, set(WEB_COLONNES_CRITIQUES))

    resultat = pd.DataFrame(anomalies, columns=COLONNES_SORTIE)
    resultat["index_ligne"] = pd.to_numeric(resultat["index_ligne"], errors="coerce").astype("Int64")
    resultat["valeur"] = resultat["valeur"].astype("object")
    return (resultat.sort_values(["fichier", "regle", "index_ligne"], na_position="first")
                    .reset_index(drop=True))


# --------------------------------------------------------------------------
# Exemple d'utilisation
# --------------------------------------------------------------------------
if __name__ == "__main__":
    erp = pd.read_excel("erp.xlsx")
    web = pd.read_excel("web.xlsx")
    liaison = pd.read_excel("liaison.xlsx")

    anomalies = valider(erp, web, liaison)
    niveau = anomalies["regle"].str.extract(r"^\[(\w+)\]")[0].rename("niveau")
    print(anomalies.groupby([niveau, "fichier", "regle"]).size().to_string())
    anomalies.to_excel("anomalies_qualite.xlsx", index=False)

    # Code retour non nul s'il y a au moins une anomalie bloquante (utilisable en chaîne automatisée)
    raise SystemExit(1 if (niveau == BLOQUANT).any() else 0)
```

**Comment sont classées les erreurs**
- **BLOQUANT** : la donnée casse une règle de gestion, une clé ou une jointure. Elle fausserait le CA, le stock ou la reprise dans l'ERP. On corrige avant tout chargement.
- **ALERTE** : la donnée est suspecte mais peut être juste (prix premium, vente à perte, image manquante, sku texte, colonne technique…). Le métier tranche.
- Le niveau figure en tête de la colonne `regle`, au format `[BLOQUANT] CODE - libellé`. Le résultat garde ainsi exactement les 5 colonnes demandées, et le niveau se retrouve avec `str.extract`.

**Hypothèses**
1. **Numéro de ligne :** `index_ligne` est l'index pandas, qui commence à 0. Pour retrouver la ligne Excel, ajoutez 2 (l'en-tête occupe la ligne 1, lecture par défaut de `read_excel`). Les erreurs de structure (colonne absente ou en trop) n'ont pas de ligne.
2. **Pas de typage strict Pandera :** sur des fichiers bruts, un contrôle de type Pandera signale la colonne entière sans désigner de ligne. Les types (entier, numérique, date) sont donc vérifiés ligne par ligne par des règles nommées.
3. **Comparaison des clés :** les clés sont comparées sous forme de texte normalisé (15298, 15298.0 et "15298" sont identiques). Les espaces en début ou fin sont ignorés pour la jointure mais signalés en alerte. Les zéros en tête ("0123" et 123) ne sont pas rapprochés.
4. **Jointure web ↔ liaison :** elle ne porte que sur les lignes `post_type = 'product'`. Les lignes `attachment` servent seulement au contrôle « produit / image ».
5. **Définitions :** « en vente » signifie `onsale_web = 1` ; « publié sur le site » signifie `post_status = 'publish'`.
6. **Stock :** un stock négatif est bloquant (pas de vente en reliquat ni de précommande). À confirmer avec BottleNeck.
7. **product_id :** c'est un entier strictement positif.
8. **Unicité dans la liaison :** un id_web ne peut correspondre qu'à un seul product_id. Les doublons sont bloquants.
9. **Listes de valeurs :** pour `post_status`, `tax_status`, `comment_status` et `ping_status`, j'ai repris les valeurs standard de WordPress / WooCommerce. Elles sont à vérifier sur votre installation, d'où leur classement en alerte.
10. **Prix atypique :** le seuil est celui de Tukey (Q3 + 1,5 × IQR), calculé sur les prix positifs de chaque export. Il ne déclenche qu'une alerte, jamais un blocage, et ne supprime rien, puisque les prix élevés sont attendus. Le coefficient se règle dans `COEF_TUKEY`.
11. **Pas de liste fermée pour `product_type` :** le dictionnaire se termine par « … ». Seule l'absence de famille est signalée.
12. **Volumes non contrôlés :** les effectifs (825 / 1 513 lignes) changent à chaque export. Je ne les ai pas codés en dur ; la complétude est vérifiée par les contrôles de clés croisés (X-01 à X-04).
13. **Colonnes :** sont bloquantes les absences de toutes les colonnes ERP et liaison, et de `sku`, `post_type` et `total_sales` côté web. Une autre colonne web absente, ou une colonne non prévue, donne une alerte.
14. **Plusieurs images pour un même sku :** c'est une alerte et non une erreur (une galerie d'images est possible).
15. **Aucune donnée inventée :** toutes les valeurs de référence viennent du dictionnaire fourni ou des standards WordPress / WooCommerce. Les seuils sont calculés sur l'export lui-même.

**À vérifier au premier lancement (non testé ici)**
- Vérifiez la version de Pandera installée. Le module essaie d'abord `pandera.pandas`, puis l'ancien `import pandera`.
- Vérifiez que les règles de structure STRUCT-01 et STRUCT-02 sont bien détectées. Leur libellé interne dans Pandera (`column_in_dataframe` / `column_in_schema`) peut varier selon la version.
- Pour contrôler quelques anomalies, ouvrez la ligne Excel correspondante (index + 2).