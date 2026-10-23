"""Exécute la fonction valider() d'un essai IA sur les fichiers BRUTS, sans aucune modification du code.

Usage : python -I runner.py <fichier_code.py> <dossier_donnees> <sortie.csv>
Écrit un JSON d'état sur stdout (statut, durée, erreur éventuelle).
"""
import json
import sys
import time
import traceback
import warnings

warnings.filterwarnings("ignore")

code_path, data_dir, out_csv = sys.argv[1], sys.argv[2], sys.argv[3]
etat = {"statut": None, "duree_s": None, "erreur": None, "nb_lignes": None, "colonnes": None}

import pandas as pd  # noqa: E402

erp = pd.read_excel(f"{data_dir}/erp.xlsx")
web = pd.read_excel(f"{data_dir}/web.xlsx")
liaison = pd.read_excel(f"{data_dir}/liaison.xlsx")

ns = {"__name__": "essai_ia"}
try:
    src = open(code_path, encoding="utf-8").read()
    exec(compile(src, code_path, "exec"), ns)
except Exception:
    etat["statut"] = "echec_import"
    etat["erreur"] = traceback.format_exc()[-1500:]
    print(json.dumps(etat))
    sys.exit(0)

if "valider" not in ns:
    etat["statut"] = "pas_de_fonction_valider"
    print(json.dumps(etat))
    sys.exit(0)

t0 = time.perf_counter()
try:
    res = ns["valider"](erp.copy(), web.copy(), liaison.copy())
    etat["duree_s"] = round(time.perf_counter() - t0, 3)
except Exception:
    etat["duree_s"] = round(time.perf_counter() - t0, 3)
    etat["statut"] = "echec_execution"
    etat["erreur"] = traceback.format_exc()[-1500:]
    print(json.dumps(etat))
    sys.exit(0)

if not isinstance(res, pd.DataFrame):
    etat["statut"] = "retour_pas_dataframe"
    etat["erreur"] = repr(type(res))
    print(json.dumps(etat))
    sys.exit(0)

etat["statut"] = "ok"
etat["nb_lignes"] = int(len(res))
etat["colonnes"] = list(map(str, res.columns))
res.to_csv(out_csv, index=False)
print(json.dumps(etat))
