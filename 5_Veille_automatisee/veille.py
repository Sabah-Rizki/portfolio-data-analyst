"""Veille automatisée — collecte hebdomadaire de flux RSS / Atom vers un journal Excel.

Fonctionnement
- Les sources sont listées dans `sources.csv` (modifiable dans Excel) : nom, thème, adresse du flux.
- Le script lit chaque flux, garde les articles publiés depuis moins de JOURS_MAX jours,
  et AJOUTE au fichier `journal_veille.xlsx` uniquement ceux qui n'y sont pas déjà (clé : le lien).
- Les colonnes « statut » et « pertinence » sont à remplir à la main lors de la revue du lundi.
- Une source en panne n'arrête pas les autres : l'erreur est notée dans `veille.log`.

Dépendances : Python 3.10+, pandas, openpyxl (déjà présents avec Anaconda). Aucune autre librairie.
Utilisation : python veille.py        (ou planifié chaque semaine, voir LISEZMOI_veille.md)
"""
from __future__ import annotations

import csv
import html
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd

DOSSIER = Path(__file__).resolve().parent
SOURCES = DOSSIER / "sources.csv"
JOURNAL = DOSSIER / "journal_veille.xlsx"
JOURS_MAX = 30          # ignore les articles plus anciens
DELAI_S = 20            # délai maximal par flux
COLONNES = ["date_collecte", "date_publication", "theme", "source", "titre", "lien", "statut", "pertinence", "note"]

logging.basicConfig(filename=DOSSIER / "veille.log", level=logging.INFO, encoding="utf-8",
                    format="%(asctime)s %(levelname)s %(message)s")


# Certains sites (dont la CNIL) refusent les programmes qui ne se présentent pas comme un navigateur
NAVIGATEUR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"


def _texte(el) -> str:
    brut = "".join(el.itertext()) if el is not None else ""              # garde le texte des balises <b>
    return html.unescape(re.sub(r"<[^>]+>", "", brut)).strip()


def _date(valeur: str) -> datetime | None:
    if not valeur:
        return None
    for lire in (parsedate_to_datetime, lambda v: datetime.fromisoformat(v.replace("Z", "+00:00"))):
        try:
            d = lire(valeur.strip())
            if d.year < 2000:            # Google Alertes met parfois 1970-01-01 quand la date est inconnue
                return None
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
    return None


def lire_flux(url: str) -> list[dict]:
    """Renvoie les articles d'un flux RSS 2.0 ou Atom : titre, lien, date."""
    requete = urllib.request.Request(url, headers={"User-Agent": NAVIGATEUR,
                                               "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8"})
    with urllib.request.urlopen(requete, timeout=DELAI_S) as rep:
        racine = ET.fromstring(rep.read())
    articles = []
    for item in racine.iter("item"):                                     # RSS 2.0
        articles.append({"titre": _texte(item.find("title")), "lien": _texte(item.find("link")),
                         "date": _date(_texte(item.find("pubDate")))})
    atom = "{http://www.w3.org/2005/Atom}"
    for entree in racine.iter(f"{atom}entry"):                           # Atom (GitHub, Google Alertes)
        lien = entree.find(f"{atom}link")
        href = lien.get("href", "") if lien is not None else ""
        if "google.com/url" in href:                                     # lien de redirection Google Alertes
            m = re.search(r"[?&]url=([^&]+)", href)
            href = urllib.parse.unquote(m.group(1)) if m else href
        articles.append({"titre": _texte(entree.find(f"{atom}title")), "lien": href,
                         "date": _date(_texte(entree.find(f"{atom}updated")) or _texte(entree.find(f"{atom}published")))})
    return articles


def charger_sources() -> list[dict]:
    with open(SOURCES, newline="", encoding="utf-8-sig") as f:
        return [s for s in csv.DictReader(f, delimiter=";") if s.get("url", "").strip()]


def main() -> None:
    maintenant = datetime.now(timezone.utc)
    limite = maintenant - timedelta(days=JOURS_MAX)
    journal = pd.read_excel(JOURNAL) if JOURNAL.exists() else pd.DataFrame(columns=COLONNES)
    deja_vus = set(journal["lien"].dropna().astype(str))

    nouveaux, bilan = [], []
    for src in charger_sources():
        try:
            articles = lire_flux(src["url"].strip())
        except Exception as exc:  # une source en panne n'arrête pas la collecte
            logging.warning("Source en échec : %s (%s)", src["nom"], exc)
            code = f" {exc.code}" if hasattr(exc, "code") else ""               # ex. HTTPError 403 = accès refusé
            bilan.append(f"  ÉCHEC  {src['nom']} : {type(exc).__name__}{code}")
            continue
        n = 0
        for a in articles:
            if not a["lien"] or a["lien"] in deja_vus or (a["date"] and a["date"] < limite):
                continue
            deja_vus.add(a["lien"])
            nouveaux.append({"date_collecte": maintenant.strftime("%Y-%m-%d"),
                             "date_publication": a["date"].strftime("%Y-%m-%d") if a["date"] else "",
                             "theme": src["theme"], "source": src["nom"], "titre": a["titre"], "lien": a["lien"],
                             "statut": "à lire", "pertinence": "", "note": ""})
            n += 1
        bilan.append(f"  OK     {src['nom']} : {n} nouveauté(s) sur {len(articles)} article(s)")

    if nouveaux:
        journal = pd.concat([journal, pd.DataFrame(nouveaux)], ignore_index=True)
        journal = journal.sort_values(["date_collecte", "date_publication"], ascending=False, kind="stable")
        journal.to_excel(JOURNAL, index=False)
    message = f"Veille du {maintenant:%d/%m/%Y} : {len(nouveaux)} nouveauté(s) ajoutée(s) à {JOURNAL.name}"
    logging.info(message)
    print(message, *bilan, sep="\n")


if __name__ == "__main__":
    main()
