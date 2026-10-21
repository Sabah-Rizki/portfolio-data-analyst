"""Banc de test P13 : note les règles de validation produites par chaque essai IA.

Pour chaque fichier essai_<ID>.md :
  1. extrait le premier bloc ```python, sans le modifier ;
  2. l'exécute sur les fichiers BRUTS (runner.py, processus isolé, délai 180 s) ;
  3. compare les anomalies renvoyées au référentiel A1-A10 et aux contrôles T2/T5.

Usage : python bench.py <dossier_essais> <dossier_donnees> <python_du_banc>
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ESSAIS, DATA, PY = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
RUNNER = Path(__file__).with_name("runner.py")
OUT = ESSAIS / "resultats"
OUT.mkdir(exist_ok=True)

# ---------- Référentiel (recalculé sur les fichiers bruts, jamais saisi à la main) ----------
erp = pd.read_excel(DATA / "erp.xlsx")
web = pd.read_excel(DATA / "web.xlsx")
lia = pd.read_excel(DATA / "liaison.xlsx")

statut_attendu = np.where(erp.stock_quantity > 0, "instock", "outofstock")
sku_txt = web.sku.astype("string").str.strip()
skus_produit = set(sku_txt[(web.post_type == "product") & web.sku.notna()])
id_web_txt = lia.id_web.astype("string").str.strip()

REF = {
    "A1": ("erp", set(erp.index[erp.stock_status != statut_attendu])),
    "A2": ("erp", set(erp.index[erp.price <= 0])),
    "A3": ("erp", set(erp.index[erp.stock_quantity < 0])),
    "A4": ("erp", set(erp.index[(erp.price > 0) & (erp.price < erp.purchase_price)])),
    "A5": ("web", set(web.index[web.sku.isna()])),
    "A6": ("web", set(web.index[web.total_sales < 0])),
    "A7": ("web", set(web.index[web.sku.notna() & pd.to_numeric(web.sku, errors="coerce").isna()])),
    "A8": ("web", set(web.index[~web.post_type.isin(["product", "attachment"])])),
    "A9": ("liaison", set(lia.index[lia.id_web.isna()])),
    "A10": ("liaison", set(lia.index[lia.id_web.notna() & ~id_web_txt.isin(skus_produit)])),
}
ATTENDU = {"A1": 2, "A2": 3, "A3": 2, "A4": 4, "A5": 85, "A6": 2, "A7": 4, "A8": 83, "A9": 91, "A10": 20}
for k, (_, s) in REF.items():
    assert len(s) == ATTENDU[k], f"Référentiel {k} : {len(s)} lignes au lieu de {ATTENDU[k]}"

# Trouvailles hors référentiel initial, apportées par les IA puis VÉRIFIÉES sur les fichiers bruts.
# Chaque trouvaille peut être signalée côté ERP ou côté liaison (alternatives).
_m = erp.reset_index().merge(lia.reset_index(), on="product_id", how="left", suffixes=("_erp", "_lia"))
_publie = set(sku_txt[(web.post_type == "product") & (web.post_status == "publish") & web.sku.notna()])
_n1 = _m[(_m.onsale_web == 1) & _m.id_web.isna()]
_n5 = _m[(_m.onsale_web == 0) & _m.id_web.notna() & _m.id_web.astype("string").str.strip().isin(_publie)]
BONUS = {
    "N1 en vente sans id_web": [("erp", set(_n1.index_erp)), ("liaison", set(_n1.index_lia.dropna().astype(int)))],
    "N2 produit sans famille": [("web", set(web.index[(web.post_type == "product") & web.product_type.isna()]))],
    "N3 stock>0 mais hors vente": [("erp", set(erp.index[(erp.stock_quantity > 0) & (erp.onsale_web == 0)]))],
    "N4 hors vente mais publie": [("erp", set(_n5.index_erp)), ("liaison", set(_n5.index_lia.astype(int)))],
}
assert [len(v[0][1]) for v in BONUS.values()] == [3, 1, 65, 1]

UNION = {f: set().union(*[s for (ff, s) in REF.values() if ff == f],
                        *[s for alts in BONUS.values() for (ff, s) in alts if ff == f])
         for f in ("erp", "web", "liaison")}
PREMIUM = set(erp.index[erp.price > 100])  # produits premium légitimes (contrôle T5)


def fichier_norm(x: str) -> str:
    x = str(x).lower()
    if "liai" in x:
        return "liaison"
    if "web" in x:
        return "web"
    if "erp" in x:
        return "erp"
    return "autre"


def extraire_code(md: str) -> str | None:
    blocs = re.findall(r"```(?:python|py)\s*\n(.*?)```", md, flags=re.S)
    return max(blocs, key=len) if blocs else None  # le bloc principal = le plus long


def noter(essai_id: str) -> dict:
    md = (ESSAIS / f"essai_{essai_id}.md").read_text(encoding="utf-8")
    code = extraire_code(md)
    res = {"essai": essai_id}
    if code is None:
        res["execution"] = "pas_de_bloc_python"
        return res
    code_path = OUT / f"code_{essai_id}.py"
    code_path.write_text(code, encoding="utf-8")
    res["lignes_de_code"] = code.count("\n") + 1
    out_csv = OUT / f"anomalies_{essai_id}.csv"
    try:
        p = subprocess.run([PY, "-I", str(RUNNER), str(code_path), str(DATA), str(out_csv)],
                           capture_output=True, text=True, timeout=180)
        etat = json.loads(p.stdout.strip().splitlines()[-1])
    except subprocess.TimeoutExpired:
        etat = {"statut": "delai_depasse"}
    except Exception as e:  # sortie illisible
        etat = {"statut": "sortie_illisible", "erreur": repr(e) + " | " + p.stderr[-800:]}
    res["execution"] = etat["statut"]
    res["duree_execution_s"] = etat.get("duree_s")
    if etat.get("erreur"):
        res["erreur"] = etat["erreur"]
    if etat["statut"] != "ok":
        return res

    an = pd.read_csv(out_csv)
    res["nb_anomalies_renvoyees"] = len(an)
    attendues = ["fichier", "regle", "colonne", "index_ligne", "valeur"]
    res["colonnes_conformes"] = list(an.columns) == attendues
    if not {"fichier", "regle", "index_ligne"} <= set(an.columns):
        res["notation"] = "impossible : colonnes fichier/regle/index_ligne absentes"
        return res
    an["f"] = an["fichier"].map(fichier_norm)
    an["idx"] = pd.to_numeric(an["index_ligne"], errors="coerce")
    an = an.dropna(subset=["idx"])
    an["idx"] = an["idx"].astype(int)

    # Une règle = (fichier, libellé, colonne) : un même libellé générique (« valeur manquante »)
    # appliqué à deux colonnes correspond à deux contrôles distincts.
    an["colonne"] = an["colonne"].fillna("").astype(str) if "colonne" in an.columns else ""
    an["regle_seule"] = an["regle"].astype(str)
    an["regle"] = an["regle_seule"] + an["colonne"].map(lambda c: f" [{c}]" if c else "")
    regles = {(f, r): set(g["idx"]) for (f, r), g in an.groupby(["f", "regle"])}
    res["nb_regles_declenchees"] = len(regles)
    # Pour la DÉTECTION, on accepte aussi la règle prise sans sa colonne : certaines IA rattachent
    # un contrôle multi-colonnes à une colonne arbitraire, ce qui éclaterait la règle en morceaux.
    regles_detection = dict(regles)
    regles_detection.update({(f, r + " [toutes colonnes]"): set(g["idx"])
                             for (f, r), g in an.groupby(["f", "regle_seule"])})

    detail = {}
    for a, (f, gt) in REF.items():
        best = (0.0, 0.0, None)
        for (rf, rn), rows in regles_detection.items():
            if rf != f:
                continue
            inter = len(rows & gt)
            if not inter:
                continue
            rappel, precision = inter / len(gt), inter / len(rows)
            if (rappel, precision) > best[:2]:
                best = (rappel, precision, rn)
        rappel, precision, rn = best
        if rappel == 1 and precision >= 0.5:
            verdict = "detectee"
        elif rappel == 1:
            verdict = "noyee"  # trouvée, mais dans une règle trop large
        elif rappel > 0:
            verdict = "partielle"
        else:
            verdict = "manquee"
        detail[a] = {"verdict": verdict, "rappel": round(rappel, 2), "precision": round(precision, 2), "regle": rn}
    res["referentiel"] = detail
    res["score_detection_sur_10"] = sum(d["verdict"] == "detectee" for d in detail.values())
    # A9 (id_web vide) est contestable : le prompt P2 précise qu'un id_web vide est légitime
    # pour un produit pas encore en ligne. Score principal calculé hors A9.
    res["score_detection_sur_9_hors_A9"] = sum(d["verdict"] == "detectee" for a, d in detail.items() if a != "A9")

    trouvailles = {}
    for nom, alts in BONUS.items():
        ok = any(rows == s for (rf, _), rows in regles.items() for (f, s) in alts if rf == f)
        trouvailles[nom] = ok
    res["trouvailles_hors_referentiel"] = trouvailles

    hors = []
    for (rf, rn), rows in regles.items():
        extra = rows - UNION.get(rf, set())
        if extra:
            hors.append({"fichier": rf, "regle": rn, "lignes_hors_referentiel": len(extra), "lignes_total": len(rows)})
    res["regles_hors_referentiel"] = sorted(hors, key=lambda h: -h["lignes_hors_referentiel"])

    # T2 : faux doublons produit + image
    res["T2_faux_doublons_sku"] = [rn for (rf, rn), rows in regles.items() if rf == "web" and len(rows) >= 700]
    # T5 : produits premium signalés
    res["T5_premium_signales"] = [{"regle": rn, "nb_premium": len(rows & PREMIUM)}
                                  for (rf, rn), rows in regles.items() if rf == "erp" and rows & PREMIUM]
    res["_paires"] = sorted({f"{f}:{i}" for (f, _), rows in regles.items() for i in rows})
    return res


if __name__ == "__main__":
    ids = sorted(p.stem.removeprefix("essai_") for p in ESSAIS.glob("essai_*.md"))
    tous = {i: noter(i) for i in ids}
    # Reproductibilité : indice de Jaccard sur les lignes signalées, P2 contre P2bis
    for outil in ("C", "G"):
        a, b = tous.get(f"{outil}-P2"), tous.get(f"{outil}-P2bis")
        if a and b and "_paires" in a and "_paires" in b:
            sa, sb = set(a["_paires"]), set(b["_paires"])
            j = len(sa & sb) / len(sa | sb) if sa | sb else 1.0
            da = {k for k, v in a["referentiel"].items() if v["verdict"] == "detectee"}
            db = {k for k, v in b["referentiel"].items() if v["verdict"] == "detectee"}
            jd = len(da & db) / len(da | db) if da | db else 1.0
            tous[f"{outil}-P2"]["jaccard_lignes_vs_bis"] = tous[f"{outil}-P2bis"]["jaccard_lignes_vs_bis"] = round(j, 3)
            tous[f"{outil}-P2"]["jaccard_detections_vs_bis"] = tous[f"{outil}-P2bis"]["jaccard_detections_vs_bis"] = round(jd, 3)
    for r in tous.values():
        r.pop("_paires", None)
    (OUT / "resultats.json").write_text(json.dumps(tous, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(tous, indent=1, ensure_ascii=False))
