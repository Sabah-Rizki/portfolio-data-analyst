"""
BottleNeck - Contrôles automatiques de qualité des données (ERP / Web / Liaison)
Compatible Python 3.13, pandas 2.x, pandera (API pandas).

Usage :
    anomalies = valider(erp, web, liaison)   # DataFrames bruts issus de pd.read_excel

Chaque anomalie est une ligne : fichier, regle, colonne, index_ligne, valeur.
Le niveau de gravité est en tête du libellé de la règle :
    "BLOQUANT | <code> | <libellé>"  -> à corriger avant chargement dans le nouvel ERP
    "ALERTE   | <code> | <libellé>"  -> à faire valider par le métier
index_ligne = index pandas (base 0) ; ligne Excel = index_ligne + 2 (en-tête en ligne 1).
"""
from __future__ import annotations

import datetime as dt
import math
import numbers
import warnings

import numpy as np
import pandas as pd

try:  # pandera >= 0.24 : API pandas dédiée
    import pandera.pandas as pa
except ImportError:  # versions plus anciennes
    import pandera as pa
from pandera.errors import SchemaError, SchemaErrors

BLOQUANT = "BLOQUANT"
ALERTE = "ALERTE"
COLONNES_SORTIE = ["fichier", "regle", "colonne", "index_ligne", "valeur"]

# Référentiels standard WordPress / WooCommerce (valeurs natives des CMS, pas des données métier)
STATUTS_WORDPRESS = {"publish", "future", "draft", "pending", "private", "trash", "auto-draft", "inherit"}
TAX_STATUS_WOOCOMMERCE = {"taxable", "shipping", "none"}
STATUTS_OUVERTURE = {"open", "closed"}
STATUTS_STOCK = {"instock", "outofstock"}

# Colonnes techniques WordPress : leur absence signale un changement de format d'export
# (alerte), alors que l'absence d'une colonne métier rend les contrôles impossibles (bloquant).
COLONNES_WEB_TECHNIQUES = [
    "virtual", "downloadable", "tax_status", "tax_class", "post_author", "post_date",
    "post_date_gmt", "post_content", "post_excerpt", "comment_status", "ping_status",
    "post_password", "post_name", "post_modified", "post_modified_gmt",
    "post_content_filtered", "post_parent", "guid", "menu_order", "post_mime_type",
    "comment_count",
]


# ---------------------------------------------------------------------------
# Fonctions utilitaires (lecture seule : aucune donnée n'est modifiée)
# ---------------------------------------------------------------------------
def _est_vide(v) -> bool:
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def _renseigne(v) -> bool:
    """Vrai si la valeur est présente (une chaîne faite uniquement d'espaces compte comme vide)."""
    if _est_vide(v):
        return False
    return not (isinstance(v, str) and not v.strip())


def _est_reel(v) -> bool:
    """Nombre réel fini, hors booléen et hors texte (un '12,5' saisi en texte est refusé)."""
    if isinstance(v, (bool, np.bool_)) or not isinstance(v, numbers.Real):
        return False
    return math.isfinite(float(v))


def _est_entier(v) -> bool:
    """Entier, ou flottant à valeur entière (pandas lit en float une colonne d'entiers contenant des vides)."""
    return _est_reel(v) and float(v).is_integer()


def _vaut(v, n: int) -> bool:
    return _est_entier(v) and int(v) == n


def _est_date(v) -> bool:
    if isinstance(v, (pd.Timestamp, dt.datetime, dt.date, np.datetime64)):
        return not _est_vide(v)
    if isinstance(v, str):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return not _est_vide(pd.to_datetime(v, errors="coerce"))
    return False  # un nombre n'est pas accepté comme date


def _num(s: pd.Series) -> pd.Series:
    """Vue numérique d'une colonne : ce qui n'est pas un nombre devient NaN (déjà signalé par une règle de type)."""
    return pd.to_numeric(s.map(lambda v: v if _est_reel(v) else np.nan), errors="coerce").astype(float)


def _dates(s: pd.Series) -> pd.Series:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(s.map(lambda v: v if _est_date(v) else None), errors="coerce", format="mixed")


def _cle(v):
    """Forme commune d'une clé de jointure, utilisée UNIQUEMENT pour comparer les fichiers entre eux
    (15298, 15298.0 et '15298' désignent le même article)."""
    if _est_vide(v):
        return None
    if isinstance(v, (bool, np.bool_)):
        return str(v)
    if isinstance(v, numbers.Integral):
        return str(int(v))
    if isinstance(v, numbers.Real):
        f = float(v)
        return str(int(f)) if f.is_integer() else str(f)
    texte = str(v).strip()
    return texte or None


def _cle_numerique(v) -> bool:
    c = _cle(v)
    return isinstance(c, str) and c.isascii() and c.isdigit()


def _ensemble(s: pd.Series) -> set:
    return {k for k in s.map(_cle) if isinstance(k, str)}


def _col(df: pd.DataFrame, nom: str) -> pd.Series:
    """Colonne si elle existe, sinon une série vide (son absence est signalée par la règle STRUCT-01)."""
    if nom in df.columns:
        return df[nom]
    return pd.Series(np.nan, index=df.index, dtype=object)


def _colonne(*checks, required: bool = True):
    # dtype=None : les types sont contrôlés ligne à ligne par des règles explicites,
    # pour obtenir l'index et la valeur de chaque anomalie (et non un simple « mauvais dtype »).
    return pa.Column(dtype=None, nullable=True, required=required, checks=list(checks))


def _fabrique_regles(fichier: str, incidents: list):
    """Crée des pa.Check nommés « NIVEAU | CODE | libellé ». Si une règle plante (format inattendu),
    on note un incident technique et les autres contrôles continuent."""

    def regle(niveau, code, libelle, fonction, ignore_na=True):
        nom = f"{niveau} | {code} | {libelle}"

        def _executer(s: pd.Series) -> pd.Series:
            try:
                res = fonction(s)
                if not isinstance(res, pd.Series):
                    res = pd.Series(res, index=s.index)
                return res.reindex(s.index).astype("boolean").fillna(True).astype(bool)
            except Exception as exc:  # noqa: BLE001 - on ne doit jamais s'arrêter
                incidents.append({
                    "fichier": fichier,
                    "regle": f"{BLOQUANT} | TECH-01 | règle {code} non exécutée : {type(exc).__name__}: {exc}",
                    "colonne": s.name, "index_ligne": None, "valeur": None,
                })
                return pd.Series(True, index=s.index)

        return pa.Check(_executer, name=nom, error=nom, ignore_na=ignore_na)

    return regle


# ---------------------------------------------------------------------------
# 1. Règles du fichier ERP
# ---------------------------------------------------------------------------
def _schema_erp(erp: pd.DataFrame, R) -> pa.DataFrameSchema:
    prix = _num(_col(erp, "price"))
    achat = _num(_col(erp, "purchase_price"))
    stock = _num(_col(erp, "stock_quantity"))

    # Seuil haut d'écart interquartile, recalculé à chaque export (aucune valeur codée en dur)
    prix_positifs = prix[prix > 0]
    if len(prix_positifs) >= 4:
        q1, q3 = prix_positifs.quantile(0.25), prix_positifs.quantile(0.75)
        seuil_prix = float(q3 + 1.5 * (q3 - q1))
    else:
        seuil_prix = math.inf

    def statut_coherent(s):
        q = stock.reindex(s.index)
        attendu = pd.Series(np.where(q > 0, "instock", "outofstock"), index=s.index)
        # on ne juge la cohérence que si le stock est numérique et le statut dans le domaine (sinon déjà signalé)
        return q.isna() | ~s.isin(STATUTS_STOCK) | s.eq(attendu)

    def marge_positive(s):
        p, a = _num(s), achat.reindex(s.index)
        return ~(p.notna() & a.notna() & (p <= a))

    return pa.DataFrameSchema(name="erp", strict=False, columns={
        "product_id": _colonne(
            # Clé primaire de l'ERP : sans elle, impossible de rapprocher la ligne de la liaison et du site.
            R(BLOQUANT, "ERP-01", "product_id manquant", lambda s: s.map(_renseigne), ignore_na=False),
            # Le dictionnaire impose un entier : un texte ou un décimal indique une saisie corrompue.
            R(BLOQUANT, "ERP-02", "product_id non entier", lambda s: s.map(_est_entier)),
            # Une clé en double fausserait toutes les jointures (prix et stocks comptés deux fois).
            R(BLOQUANT, "ERP-03", "product_id en double",
              lambda s: ~(s.map(_cle).notna() & s.map(_cle).duplicated(keep=False))),
            # Un identifiant nul ou négatif est inhabituel pour une clé technique : à confirmer.
            R(ALERTE, "ERP-04", "product_id <= 0", lambda s: _num(s).isna() | (_num(s) > 0)),
        ),
        "onsale_web": _colonne(
            # L'indicateur décide de la mise en ligne : une valeur absente rend le statut commercial inconnu.
            R(BLOQUANT, "ERP-05", "onsale_web manquant", lambda s: s.map(_renseigne), ignore_na=False),
            # Indicateur binaire selon le dictionnaire : seuls 0 et 1 ont un sens.
            R(BLOQUANT, "ERP-06", "onsale_web hors {0, 1}", lambda s: s.map(lambda v: _vaut(v, 0) or _vaut(v, 1))),
        ),
        "price": _colonne(
            # Le prix de vente est une donnée de référence obligatoire dans l'ERP.
            R(BLOQUANT, "ERP-07", "price manquant", lambda s: s.map(_renseigne), ignore_na=False),
            # Un prix saisi en texte (ex. '12,5') casse la valorisation et les calculs de CA.
            R(BLOQUANT, "ERP-08", "price non numérique", lambda s: s.map(_est_reel)),
            # Un prix nul ou négatif n'a pas de sens commercial pour un caviste.
            R(BLOQUANT, "ERP-09", "price <= 0", lambda s: _num(s).isna() | (_num(s) > 0)),
            # Vente à perte ou marge nulle : possible (déstockage, promotion) mais à justifier.
            R(ALERTE, "ERP-10", "price <= purchase_price (marge nulle ou négative)", marge_positive),
            # Prix atypique : les produits premium sont légitimes, donc simple alerte à valider.
            R(ALERTE, "ERP-11", f"price atypique (> Q3 + 1,5 x IQR = {seuil_prix:.2f} EUR)",
              lambda s: ~(_num(s) > seuil_prix)),
        ),
        "stock_quantity": _colonne(
            # Le stock est indispensable pour le statut de disponibilité et la valorisation.
            R(BLOQUANT, "ERP-12", "stock_quantity manquant", lambda s: s.map(_renseigne), ignore_na=False),
            # On stocke des bouteilles entières : une quantité décimale est une erreur de saisie.
            R(BLOQUANT, "ERP-13", "stock_quantity non entier", lambda s: s.map(_est_entier)),
            # Un stock physique négatif est impossible et ne peut pas servir de stock d'ouverture du nouvel ERP.
            R(BLOQUANT, "ERP-14", "stock_quantity < 0", lambda s: _num(s).isna() | (_num(s) >= 0)),
        ),
        "stock_status": _colonne(
            # Le statut pilote l'affichage de la disponibilité sur le site.
            R(BLOQUANT, "ERP-15", "stock_status manquant", lambda s: s.map(_renseigne), ignore_na=False),
            # Le domaine de valeurs est fixé par la règle de gestion.
            R(BLOQUANT, "ERP-16", "stock_status hors {'instock', 'outofstock'}", lambda s: s.isin(STATUTS_STOCK)),
            # Règle de gestion explicite : 'instock' si stock_quantity > 0, sinon 'outofstock'.
            R(BLOQUANT, "ERP-17", "stock_status incohérent avec stock_quantity", statut_coherent),
        ),
        "purchase_price": _colonne(
            # Sans prix d'achat, pas de calcul de marge ; la vente reste possible, d'où une alerte.
            R(ALERTE, "ERP-18", "purchase_price manquant", lambda s: s.map(_renseigne), ignore_na=False),
            # Un prix d'achat en texte casse la valorisation du stock.
            R(BLOQUANT, "ERP-19", "purchase_price non numérique", lambda s: s.map(_est_reel)),
            # Un coût d'achat négatif est impossible.
            R(BLOQUANT, "ERP-20", "purchase_price < 0", lambda s: _num(s).isna() | (_num(s) >= 0)),
            # Un coût nul peut correspondre à un échantillon ou un cadeau fournisseur : à confirmer.
            R(ALERTE, "ERP-21", "purchase_price = 0", lambda s: ~(_num(s) == 0)),
        ),
    })


# ---------------------------------------------------------------------------
# 2. Règles du fichier Web (WordPress / WooCommerce)
# ---------------------------------------------------------------------------
def _schema_web(web: pd.DataFrame, R) -> pa.DataFrameSchema:
    pt = _col(web, "post_type")
    produit = pt.eq("product")
    image = pt.eq("attachment")
    vide = web.isna().all(axis=1)
    cles = _col(web, "sku").map(_cle)
    a_cle = cles.map(lambda k: isinstance(k, str))

    types_par_sku: dict[str, set] = {}
    for k, t in zip(cles, pt):
        if isinstance(k, str):
            types_par_sku.setdefault(k, set()).add(t)
    a_image = cles.map(lambda k: isinstance(k, str) and "attachment" in types_par_sku.get(k, ()))
    a_produit = cles.map(lambda k: isinstance(k, str) and "product" in types_par_sku.get(k, ()))

    paire = pd.Series(
        [(k, t) if isinstance(k, str) and isinstance(t, str) else None for k, t in zip(cles, pt)],
        index=web.index, dtype=object,
    )
    doublon = paire.notna() & paire.duplicated(keep=False)
    nb_avis = _num(_col(web, "rating_count"))

    def seulement_produit(fonction):
        """Applique une règle aux lignes 'product' uniquement (les lignes image n'ont pas ces attributs)."""
        return lambda s: fonction(s) | ~produit.reindex(s.index, fill_value=False)

    def note_coherente(s):
        note, nb = _num(s), nb_avis.reindex(s.index)
        incoherent = ((nb == 0) & note.notna() & (note != 0)) | \
                     ((nb > 0) & note.notna() & ((note < 1) | (note > 5)))
        return ~incoherent

    def chronologie(s):
        creation = _dates(_col(web, "post_date")).reindex(s.index)
        modification = _dates(s)
        return ~(creation.notna() & modification.notna() & (modification < creation))

    colonnes = {
        "sku": _colonne(
            # Le sku est la clé de jointure avec la liaison : une ligne sans sku est inexploitable.
            R(BLOQUANT, "WEB-01", "sku manquant (hors ligne entièrement vide)",
              lambda s: s.map(_renseigne) | vide.reindex(s.index), ignore_na=False),
            # Une ligne totalement vide est un artefact d'export, à purger mais sans risque métier.
            R(ALERTE, "WEB-02", "ligne entièrement vide", lambda s: ~vide.reindex(s.index), ignore_na=False),
            # Le sku est « normalement numérique » : un code texte (bon cadeau, variante...) doit être validé.
            R(ALERTE, "WEB-03", "sku non numérique", lambda s: s.map(_cle_numerique)),
            # Des espaces parasites font échouer les jointures exactes dans les outils aval.
            R(ALERTE, "WEB-04", "sku avec espaces en début ou fin",
              lambda s: s.map(lambda v: not isinstance(v, str) or v == v.strip())),
            # Un produit (ou une image) en double ferait compter deux fois les ventes et le CA.
            R(BLOQUANT, "WEB-05", "couple (sku, post_type) en double", lambda s: ~doublon.reindex(s.index)),
            # Chaque produit doit avoir son image : un produit sans visuel se vend mal en ligne.
            R(ALERTE, "WEB-06", "produit sans ligne image (attachment)",
              lambda s: ~(produit & a_cle & ~a_image).reindex(s.index)),
            # Une image sans produit correspond à un résidu d'un produit supprimé.
            R(ALERTE, "WEB-07", "image (attachment) sans ligne produit",
              lambda s: ~(image & a_cle & ~a_produit).reindex(s.index)),
        ),
        "post_type": _colonne(
            # Le type distingue produit et image : sans lui, on ne sait pas quelle ligne garder.
            R(BLOQUANT, "WEB-08", "post_type manquant (hors ligne entièrement vide)",
              lambda s: s.map(_renseigne) | vide.reindex(s.index), ignore_na=False),
            # Seuls deux types sont attendus selon le dictionnaire.
            R(BLOQUANT, "WEB-09", "post_type hors {'product', 'attachment'}",
              lambda s: s.isin({"product", "attachment"})),
        ),
        "total_sales": _colonne(
            # Les ventes cumulées servent au calcul du CA par produit.
            R(ALERTE, "WEB-10", "total_sales manquant sur une ligne produit",
              seulement_produit(lambda s: s.map(_renseigne)), ignore_na=False),
            # Une quantité en texte est inexploitable.
            R(BLOQUANT, "WEB-11", "total_sales non numérique", lambda s: s.map(_est_reel)),
            # Des ventes cumulées ne peuvent pas être négatives.
            R(BLOQUANT, "WEB-12", "total_sales < 0", lambda s: _num(s).isna() | (_num(s) >= 0)),
            # On vend des unités entières : une valeur décimale est suspecte.
            R(ALERTE, "WEB-13", "total_sales non entier",
              lambda s: s.map(lambda v: not _est_reel(v) or _est_entier(v))),
        ),
        "product_type": _colonne(
            # La famille sert aux analyses par catégorie (vins, spiritueux, huiles...).
            R(ALERTE, "WEB-14", "product_type manquant sur une ligne produit",
              seulement_produit(lambda s: s.map(_renseigne)), ignore_na=False),
        ),
        "post_title": _colonne(
            # Un produit sans libellé n'est pas présentable aux clients.
            R(ALERTE, "WEB-15", "post_title manquant sur une ligne produit",
              seulement_produit(lambda s: s.map(_renseigne)), ignore_na=False),
        ),
        "post_status": _colonne(
            # Statut hors des valeurs natives de WordPress : export altéré ou plugin à identifier.
            R(ALERTE, "WEB-16", "post_status hors statuts WordPress", lambda s: s.isin(STATUTS_WORDPRESS)),
        ),
        "average_rating": _colonne(
            # Une note doit être numérique pour être affichée et agrégée.
            R(BLOQUANT, "WEB-17", "average_rating non numérique", lambda s: s.map(_est_reel)),
            # L'échelle WooCommerce va de 0 à 5 étoiles.
            R(BLOQUANT, "WEB-18", "average_rating hors [0, 5]",
              lambda s: _num(s).isna() | _num(s).between(0, 5)),
            # Sans avis, la note doit valoir 0 ; avec avis, elle est d'au moins 1 étoile.
            R(ALERTE, "WEB-19", "average_rating incohérent avec rating_count", note_coherente),
        ),
        "rating_count": _colonne(
            # Un nombre d'avis est un entier positif ou nul.
            R(BLOQUANT, "WEB-20", "rating_count non entier ou négatif",
              lambda s: s.map(lambda v: _est_entier(v) and float(v) >= 0)),
        ),
    }
    for c in ("virtual", "downloadable"):
        # Indicateurs binaires WooCommerce : toute autre valeur révèle un export altéré.
        colonnes[c] = _colonne(R(ALERTE, "WEB-21", f"{c} hors {{0, 1}}",
                                 lambda s: s.map(lambda v: _vaut(v, 0) or _vaut(v, 1))))
    # Valeurs natives WooCommerce : une autre valeur fausserait le calcul de TVA.
    colonnes["tax_status"] = _colonne(R(ALERTE, "WEB-22", "tax_status hors {'taxable', 'shipping', 'none'}",
                                        lambda s: s.isin(TAX_STATUS_WOOCOMMERCE)))
    for c in ("comment_status", "ping_status"):
        # Valeurs natives WordPress.
        colonnes[c] = _colonne(R(ALERTE, "WEB-23", f"{c} hors {{'open', 'closed'}}",
                                 lambda s: s.isin(STATUTS_OUVERTURE)))
    for c in ("post_date", "post_date_gmt", "post_modified", "post_modified_gmt"):
        # Une date illisible empêche les analyses d'ancienneté du catalogue.
        colonnes[c] = _colonne(R(ALERTE, "WEB-24", f"{c} n'est pas une date valide",
                                 lambda s: s.map(_est_date)))
    # Un contenu ne peut pas être modifié avant d'avoir été créé.
    colonnes["post_modified"] = _colonne(
        R(ALERTE, "WEB-24", "post_modified n'est pas une date valide", lambda s: s.map(_est_date)),
        R(ALERTE, "WEB-25", "post_modified antérieur à post_date", chronologie),
    )
    # La ligne attachment est censée être une image (dictionnaire) : un autre type MIME est suspect.
    colonnes["post_mime_type"] = _colonne(R(
        ALERTE, "WEB-26", "attachment sans type MIME image/*",
        lambda s: ~(image.reindex(s.index) & ~s.map(lambda v: isinstance(v, str) and v.startswith("image/"))),
        ignore_na=False))
    # Un produit protégé par mot de passe est invisible pour le public.
    colonnes["post_password"] = _colonne(R(
        ALERTE, "WEB-27", "produit protégé par mot de passe",
        lambda s: ~(produit.reindex(s.index) & s.map(_renseigne))))
    # Colonnes techniques sans règle de contenu : seule leur présence est contrôlée (STRUCT-01).
    for c in COLONNES_WEB_TECHNIQUES:
        colonnes.setdefault(c, _colonne())

    return pa.DataFrameSchema(name="web", strict=False, columns=colonnes)


# ---------------------------------------------------------------------------
# 3. Règles du fichier Liaison
# ---------------------------------------------------------------------------
def _schema_liaison(liaison: pd.DataFrame, R) -> pa.DataFrameSchema:
    return pa.DataFrameSchema(name="liaison", strict=False, columns={
        "product_id": _colonne(
            # Une ligne de liaison sans produit ERP ne relie rien.
            R(BLOQUANT, "LIA-01", "product_id manquant", lambda s: s.map(_renseigne), ignore_na=False),
            # Même format que la clé ERP (entier).
            R(BLOQUANT, "LIA-02", "product_id non entier", lambda s: s.map(_est_entier)),
            # Un produit ERP lié deux fois crée des doublons à la jointure.
            R(BLOQUANT, "LIA-03", "product_id en double",
              lambda s: ~(s.map(_cle).notna() & s.map(_cle).duplicated(keep=False))),
        ),
        "id_web": _colonne(
            # id_web peut être vide (produit pas encore en ligne) : aucune règle sur les valeurs manquantes.
            # En revanche, un article web rattaché à deux produits ERP rend la jointure ambiguë.
            R(BLOQUANT, "LIA-04", "id_web en double",
              lambda s: ~(s.map(_cle).notna() & s.map(_cle).duplicated(keep=False))),
            # Table tenue à la main : un code non numérique est souvent une faute de frappe.
            R(ALERTE, "LIA-05", "id_web non numérique", lambda s: s.map(_cle_numerique)),
            # Les espaces parasites font échouer les jointures exactes.
            R(ALERTE, "LIA-06", "id_web avec espaces en début ou fin",
              lambda s: s.map(lambda v: not isinstance(v, str) or v == v.strip())),
        ),
    })


# ---------------------------------------------------------------------------
# 4. Règles entre fichiers (cohérence des clés de jointure)
# ---------------------------------------------------------------------------
def _schema_x_erp(erp: pd.DataFrame, liaison: pd.DataFrame, R) -> pa.DataFrameSchema:
    cles_liaison = _ensemble(_col(liaison, "product_id"))
    return pa.DataFrameSchema(name="erp_vs_liaison", strict=False, columns={
        "product_id": _colonne(
            # Chaque produit ERP doit figurer dans la liaison, sinon il ne peut jamais être rapproché du site.
            R(BLOQUANT, "X-01", "product_id ERP absent de la liaison (inter-fichiers)",
              lambda s: s.map(lambda v: _cle(v) is None or _cle(v) in cles_liaison)),
            required=False),
    })


def _schema_x_liaison(erp, web, liaison, R) -> pa.DataFrameSchema:
    cles_erp = _ensemble(_col(erp, "product_id"))
    produit_web = _col(web, "post_type").eq("product")
    cles_sku = _col(web, "sku").map(_cle)
    cles_web_produit = {k for k in cles_sku[produit_web] if isinstance(k, str)}

    onsale: dict = {}
    for k, v in zip(_col(erp, "product_id").map(_cle), _col(erp, "onsale_web")):
        if isinstance(k, str):
            onsale.setdefault(k, v)
    statut_web: dict = {}
    for k, v in zip(cles_sku[produit_web], _col(web, "post_status")[produit_web]):
        if isinstance(k, str):
            statut_web.setdefault(k, v)

    pid = _col(liaison, "product_id").map(_cle)
    idw = _col(liaison, "id_web").map(_cle)
    en_vente = pid.map(lambda k: isinstance(k, str) and _vaut(onsale.get(k), 1))
    hors_vente = pid.map(lambda k: isinstance(k, str) and _vaut(onsale.get(k), 0))
    connu_web = idw.map(lambda k: isinstance(k, str) and k in cles_web_produit)
    publie = idw.map(lambda k: isinstance(k, str) and statut_web.get(k) == "publish")

    return pa.DataFrameSchema(name="liaison_vs_erp_web", strict=False, columns={
        "product_id": _colonne(
            # Une liaison vers un produit inexistant dans l'ERP est orpheline : prix et stock introuvables.
            R(BLOQUANT, "X-02", "product_id de la liaison absent de l'ERP (inter-fichiers)",
              lambda s: s.map(lambda v: _cle(v) is None or _cle(v) in cles_erp)),
            required=False),
        "id_web": _colonne(
            # Un id_web renseigné doit désigner un vrai produit du site (ligne 'product').
            R(BLOQUANT, "X-03", "id_web absent des produits du site (inter-fichiers)",
              lambda s: s.map(lambda v: _cle(v) is None or _cle(v) in cles_web_produit)),
            # Un produit en vente doit avoir sa référence web, sinon ses ventes en ligne ne sont pas rattachées.
            R(ALERTE, "X-04", "id_web vide alors que onsale_web = 1 (inter-fichiers)",
              lambda s: s.map(_renseigne) | ~en_vente.reindex(s.index), ignore_na=False),
            # Un produit retiré de la vente dans l'ERP mais visible sur le site peut être commandé à tort.
            R(ALERTE, "X-05", "onsale_web = 0 mais produit publié sur le site (inter-fichiers)",
              lambda s: ~(hors_vente & publie).reindex(s.index)),
            # Un produit déclaré en vente mais non publié est un manque à gagner.
            R(ALERTE, "X-06", "onsale_web = 1 mais produit non publié sur le site (inter-fichiers)",
              lambda s: ~(en_vente & connu_web & ~publie).reindex(s.index)),
            required=False),
    })


def _schema_x_web(web: pd.DataFrame, liaison: pd.DataFrame, R) -> pa.DataFrameSchema:
    cles_id_web = _ensemble(_col(liaison, "id_web"))
    produit = _col(web, "post_type").eq("product")

    def rattache(s):
        sans_lien = s.map(lambda v: isinstance(_cle(v), str) and _cle(v) not in cles_id_web)
        return ~(produit.reindex(s.index, fill_value=False) & sans_lien)

    return pa.DataFrameSchema(name="web_vs_liaison", strict=False, columns={
        # Un produit vendu en ligne sans correspondance ERP : CA non rattachable, prix et stock inconnus.
        "sku": _colonne(R(BLOQUANT, "X-07", "produit web absent de la liaison (inter-fichiers)", rattache),
                        required=False),
    })


# ---------------------------------------------------------------------------
# Conversion des erreurs Pandera et fonction principale
# ---------------------------------------------------------------------------
def _convertir(fichier: str, failure_cases: pd.DataFrame, colonnes_alerte: set) -> list[dict]:
    lignes = []
    for r in failure_cases.to_dict("records"):
        check = "" if _est_vide(r.get("check")) else str(r.get("check"))
        if check.startswith("<Check ") and check.endswith(">"):
            check = check[len("<Check "):-1]
        colonne, valeur, idx = r.get("column"), r.get("failure_case"), r.get("index")
        if check == "column_in_dataframe":
            # Structure : une colonne attendue manque dans l'export.
            colonne = valeur
            niveau = ALERTE if isinstance(valeur, str) and valeur in colonnes_alerte else BLOQUANT
            regle, valeur = f"{niveau} | STRUCT-01 | colonne attendue absente de l'export", None
        elif check.startswith((BLOQUANT, ALERTE)):
            regle = check
        else:
            regle = f"{BLOQUANT} | STRUCT-02 | contrôle Pandera '{check}'"
        lignes.append({
            "fichier": fichier,
            "regle": regle,
            "colonne": None if _est_vide(colonne) else colonne,
            "index_ligne": int(idx) if _est_entier(idx) else (None if _est_vide(idx) else idx),
            "valeur": valeur,
        })
    return lignes


def valider(erp: pd.DataFrame, web: pd.DataFrame, liaison: pd.DataFrame) -> pd.DataFrame:
    """Exécute toutes les règles sans jamais s'arrêter à la première erreur.
    Renvoie un DataFrame : fichier, regle, colonne, index_ligne, valeur (bloquants en premier)."""
    anomalies: list[dict] = []
    incidents: list[dict] = []

    controles = [
        ("erp", erp, lambda R: _schema_erp(erp, R), set()),
        ("web", web, lambda R: _schema_web(web, R), set(COLONNES_WEB_TECHNIQUES)),
        ("liaison", liaison, lambda R: _schema_liaison(liaison, R), set()),
        ("erp", erp, lambda R: _schema_x_erp(erp, liaison, R), set()),
        ("liaison", liaison, lambda R: _schema_x_liaison(erp, web, liaison, R), set()),
        ("web", web, lambda R: _schema_x_web(web, liaison, R), set()),
    ]
    for fichier, df, construire, colonnes_alerte in controles:
        R = _fabrique_regles(fichier, incidents)
        try:
            if not isinstance(df, pd.DataFrame):
                raise TypeError(f"{fichier} n'est pas un DataFrame ({type(df).__name__})")
            construire(R).validate(df, lazy=True)  # lazy=True : collecte de toutes les erreurs
        except SchemaErrors as err:
            anomalies.extend(_convertir(fichier, err.failure_cases, colonnes_alerte))
        except SchemaError as err:  # sécurité (ne devrait pas arriver en mode lazy)
            anomalies.append({"fichier": fichier, "regle": f"{BLOQUANT} | STRUCT-02 | {err}",
                              "colonne": None, "index_ligne": None, "valeur": None})
        except Exception as exc:  # noqa: BLE001 - un schéma qui plante ne bloque pas les autres
            incidents.append({"fichier": fichier,
                              "regle": f"{BLOQUANT} | TECH-02 | schéma non exécuté : {type(exc).__name__}: {exc}",
                              "colonne": None, "index_ligne": None, "valeur": None})

    resultat = pd.DataFrame(anomalies + incidents, columns=COLONNES_SORTIE)
    try:
        resultat["index_ligne"] = resultat["index_ligne"].astype("Int64")
    except (TypeError, ValueError):
        pass  # index non entier : on conserve les libellés d'origine
    ordre = ~resultat["regle"].astype(str).str.startswith(BLOQUANT)
    resultat = (resultat.assign(_ordre=ordre)
                .sort_values(["_ordre", "fichier", "regle", "index_ligne"], kind="stable")
                .drop(columns="_ordre")
                .reset_index(drop=True))
    return resultat


if __name__ == "__main__":
    erp = pd.read_excel("erp.xlsx")
    web = pd.read_excel("web.xlsx")
    liaison = pd.read_excel("liaison.xlsx")

    anomalies = valider(erp, web, liaison)
    niveau = anomalies["regle"].str.partition(" | ")[0]
    print(f"{len(anomalies)} anomalies dont {(niveau == BLOQUANT).sum()} bloquantes "
          f"et {(niveau == ALERTE).sum()} alertes\n")
    print(anomalies.groupby(["fichier", "regle"]).size().to_string())
