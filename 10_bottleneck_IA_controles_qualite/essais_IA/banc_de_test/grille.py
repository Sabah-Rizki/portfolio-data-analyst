"""Grille d'évaluation P13 : note chaque essai sur 100 à partir des mesures du banc (resultats.json).

Règles de notation (fixées avant calcul, identiques pour tous les essais) :
- Qualité (30)            = 30 x anomalies détectées / 9 (A9 exclue, voir référentiel).
- Robustesse / biais (15) = 15 si aucune fausse erreur bloquante (contrôles T1 à T5), 0 si le code ne tourne pas.
- Exécution (15)          = 15 si le code tourne sans modification, 0 sinon.
- Reproductibilité (15)   = 15 x moyenne(Jaccard des détections, Jaccard des lignes) entre P2 et P2bis,
                            propriété de l'outil, appliquée à ses trois essais.
- Sécurité (10)           = 5 pour tous : aucune donnée envoyée (garanti par le protocole),
                            mais aucun essai ne signale les colonnes personnelles post_author / guid.
- Maintenabilité (10)     = 10/3 x grille de lecture sur 3 points (MAINT ci-dessous, justifiée).
- Temps et sobriété (5)   = 5 si exécution médiane < 1 s, 2 si >= 1 s, 0 si le code ne tourne pas.
"""
import json
import sys
from pathlib import Path

RES = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

# Durées médianes d'exécution sur 5 lancements (secondes), mesurées le 20/10/2026.
MEDIANE_S = {"C-P1": 0.268, "C-P2": 0.371, "C-P2bis": 0.417, "G-P2": 5.78, "G-P2bis": 0.22}

# Grille de lecture : (justification métier règle par règle, hypothèses listées, gravité exploitable en sortie)
MAINT = {
    "C-P1": (0, 1, 0, "pas de justification par règle ; points à vérifier listés ; pas de niveau de gravité"),
    "C-P2": (1, 1, 1, "chaque règle justifiée ; 15 hypothèses ; BLOQUANT / ALERTE présent sur toutes les lignes"),
    "C-P2bis": (1, 1, 1, "chaque règle justifiée ; 15 hypothèses ; BLOQUANT / ALERTE présent sur toutes les lignes"),
    "G-P1": (0, 0, 0, "commentaires rares ; aucune hypothèse ; pas de niveau de gravité"),
    "G-P2": (1, 1, 0, "règles justifiées ; 5 hypothèses ; niveau perdu en sortie pour 218 lignes sur 301"),
    "G-P2bis": (1, 1, 1, "règles justifiées ; 4 hypothèses ; niveau visible sur 80 lignes sur 85"),
}


def jaccard(outil: str) -> float | None:
    v = RES.get(f"{outil}-P2", {})
    if "jaccard_detections_vs_bis" not in v:
        return None
    return (v["jaccard_detections_vs_bis"] + v["jaccard_lignes_vs_bis"]) / 2


lignes = {}
for e, v in RES.items():
    ok = v.get("execution") == "ok"
    det = v.get("score_detection_sur_9_hors_A9") or 0
    j = jaccard(e[0])
    m = MAINT[e]
    notes = {
        "Qualité": 30 * det / 9 if ok else 0,
        "Robustesse": (15 if not v.get("T2_faux_doublons_sku") else 0) if ok else 0,
        "Exécution": 15 if ok else 0,
        "Reproductibilité": 15 * j if j is not None else 0,
        "Sécurité": 5,
        "Maintenabilité": 10 / 3 * sum(m[:3]),
        "Temps": (5 if MEDIANE_S[e] < 1 else 2) if ok else 0,
    }
    notes = {k: round(x, 1) for k, x in notes.items()}
    notes["Total"] = round(sum(notes.values()), 1)
    notes["justif_maintenabilite"] = m[3]
    lignes[e] = notes

Path(sys.argv[2]).write_text(json.dumps(lignes, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"{'Essai':8} " + " ".join(f"{k[:6]:>7}" for k in list(lignes['C-P1'])[:-1]))
for e, n in lignes.items():
    print(f"{e:8} " + " ".join(f"{n[k]:>7}" for k in list(n)[:-1]))
for o in "CG":
    print(o, "Jaccard moyen :", round(jaccard(o), 3))
